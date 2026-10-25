"""Sensor drivers behind one interface.

Every driver reports `available`. A sensor that is not connected, or whose
library is missing, reads None and shows as "missing" on the kiosk and as
missing evidence in analyses. No driver ever substitutes a made-up value.

How the hardware talks to this code:
  * The Pi has no analog inputs. Light, rotary angle and air quality are
    analog, so they are read through an ADC: the Grove Base HAT (built-in ADC)
    or an ADS1115 over I2C.
  * Without an ADC, a plain photoresistor still works with the RC timing
    trick: LDR + capacitor on a GPIO pin, measure how long it takes to charge.
  * The DS18B20 waterproof probe is digital (1-Wire on GPIO4):
    enable `dtoverlay=w1-gpio` and read /sys/bus/w1/devices/28-*/temperature.
"""

from __future__ import annotations

import glob
import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("litmus.sensors")


class Sensor(Protocol):
    name: str
    unit: str
    available: bool
    detail: str

    def read(self) -> float | None: ...


@dataclass
class Missing:
    """Placeholder for a sensor that is not connected. Always reads None."""
    name: str
    unit: str
    detail: str = "not connected"
    available: bool = False

    def read(self) -> float | None:
        return None


# ------------------------------------------------------------------ ADCs

class ADC(Protocol):
    def read_ratio(self, channel: int) -> float | None: ...


class GroveADC:
    """Seeed Grove Base HAT for Raspberry Pi (STM32 ADC on I2C 0x08, older boards 0x04).

    Talks to the HAT directly over I2C with smbus2, so the grove.py package
    (which often fails to install on a Pi 5) is not required.
    """

    def __init__(self) -> None:
        from smbus2 import SMBus  # type: ignore[import-not-found]
        self._bus = SMBus(1)
        self._addr = None
        for addr in (0x08, 0x04):
            try:
                self._bus.read_byte(addr)
                self._addr = addr
                break
            except OSError:
                continue
        if self._addr is None:
            raise RuntimeError("Grove Base HAT not found on I2C (expected 0x08 or 0x04)")

    def read_ratio(self, channel: int) -> float | None:
        reg = 0x30 + channel  # per-mille of the 3.3 V reference, 0..999
        self._bus.write_byte(self._addr, reg)
        raw = self._bus.read_word_data(self._addr, reg)
        return raw / 999.0


class ADS1115ADC:
    def __init__(self) -> None:
        import board  # type: ignore[import-not-found]
        import busio  # type: ignore[import-not-found]
        import adafruit_ads1x15.ads1115 as ADS  # type: ignore[import-not-found]
        from adafruit_ads1x15.analog_in import AnalogIn  # type: ignore[import-not-found]
        i2c = busio.I2C(board.SCL, board.SDA)
        self._ads = ADS.ADS1115(i2c)
        self._pins = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
        self._AnalogIn = AnalogIn

    def read_ratio(self, channel: int) -> float | None:
        ch = self._AnalogIn(self._ads, self._pins[channel])
        return max(0.0, min(1.0, ch.voltage / 3.3))


def make_adc(kind: str) -> ADC | None:
    try:
        if kind == "grove":
            return GroveADC()
        if kind == "ads1115":
            return ADS1115ADC()
    except Exception as exc:  # noqa: BLE001 - hardware or library absent
        log.warning("ADC %s unavailable: %s", kind, exc)
    return None


class AnalogSensor:
    def __init__(self, name: str, unit: str, adc: ADC, channel: int, scale: float = 1.0, detail: str = ""):
        self.name, self.unit, self._adc, self._ch, self._scale = name, unit, adc, channel, scale
        self.detail = detail or f"ADC channel {channel}"
        self.available = True

    def read(self) -> float | None:
        try:
            r = self._adc.read_ratio(self._ch)
        except Exception as exc:  # noqa: BLE001 - a flaky read is a missing read
            log.debug("%s read failed: %s", self.name, exc)
            return None
        return None if r is None else round(r * self._scale, 4)


# ------------------------------------------------------------------ digital

def _rp1_chip():
    """Open the GPIO chip that drives the 40-pin header (gpiochip0 on new kernels, gpiochip4 on older Pi 5 ones)."""
    import lgpio  # type: ignore[import-not-found]
    for n in (0, 4, 1, 2, 3):
        try:
            h = lgpio.gpiochip_open(n)
        except Exception:  # noqa: BLE001 - chip not present
            continue
        try:
            _, _, label = lgpio.gpio_get_chip_info(h)
            if "rp1" in label or "pinctrl-bcm" in label:
                return lgpio, h
        except Exception:  # noqa: BLE001
            pass
        lgpio.gpiochip_close(h)
    raise RuntimeError("no GPIO header chip found")


class RCTiming:
    """Resistive sensor read without an ADC: time how long a capacitor takes to charge through it.

    Wiring: 3.3 V -> 1 kOhm -> sensor resistance -> GPIO pin, with a capacitor (about 1 uF)
    from the GPIO pin to GND. For a Grove rotary angle sensor use its VCC and SIG pins only
    (leave its GND unconnected) so the knob is a plain variable resistor.

    mode "angle": maps charge time to degrees using min_us/max_us (or the range seen so far).
    mode "light": brightness proxy (higher = brighter) for a bare photoresistor.
    """

    def __init__(self, name: str, unit: str, pin: int, mode: str, max_deg: float = 300.0,
                 min_us: float | None = None, max_us: float | None = None, timeout_ms: float = 60.0):
        self._lg, self._h = _rp1_chip()
        self.name, self.unit, self._pin, self._mode = name, unit, pin, mode
        self._max_deg, self._timeout = max_deg, timeout_ms / 1000.0
        self._min_us, self._max_us = min_us, max_us
        self._seen_min, self._seen_max = float("inf"), 0.0
        self.detail, self.available = f"RC timing on GPIO{pin}", True
        self.last_us: float | None = None

    def _charge_us(self) -> float | None:
        lg, h, pin = self._lg, self._h, self._pin
        lg.gpio_claim_output(h, pin, 0)
        time.sleep(0.002)  # discharge the capacitor
        lg.gpio_free(h, pin)
        lg.gpio_claim_input(h, pin, lg.SET_PULL_NONE)
        start = time.perf_counter()
        while lg.gpio_read(h, pin) == 0:
            if time.perf_counter() - start > self._timeout:
                lg.gpio_free(h, pin)
                return None
        dt = (time.perf_counter() - start) * 1e6
        lg.gpio_free(h, pin)
        return dt

    def read(self) -> float | None:
        samples = [s for s in (self._charge_us() for _ in range(3)) if s is not None]
        if not samples:
            return None
        us = sorted(samples)[len(samples) // 2]
        self.last_us = us
        if self._mode == "light":
            return round(1e4 / max(us, 1.0), 4)
        self._seen_min, self._seen_max = min(self._seen_min, us), max(self._seen_max, us)
        lo = self._min_us if self._min_us is not None else self._seen_min
        hi = self._max_us if self._max_us is not None else self._seen_max
        if hi - lo < 50:  # not calibrated yet and the knob has not moved: no meaningful angle
            return None
        return round(max(0.0, min(1.0, (us - lo) / (hi - lo))) * self._max_deg, 1)


class DS18B20:
    def __init__(self) -> None:
        paths = glob.glob("/sys/bus/w1/devices/28-*/temperature")
        if not paths:
            raise RuntimeError("no DS18B20 found on the 1-Wire bus")
        self._path = paths[0]
        self.name, self.unit, self.detail, self.available = "temp_c", "°C", "DS18B20 probe", True

    def read(self) -> float | None:
        try:
            with open(self._path) as f:
                return round(int(f.read().strip()) / 1000.0, 3)
        except (OSError, ValueError):
            return None


class DHT22:
    def __init__(self, pin: int, field_name: str):
        import adafruit_dht  # type: ignore[import-not-found]
        import board  # type: ignore[import-not-found]
        self._dev = adafruit_dht.DHT22(getattr(board, f"D{pin}"))
        self._field = field_name
        self.name = "air_temp_c" if field_name == "temperature" else "humidity"
        self.unit = "°C" if field_name == "temperature" else "%RH"
        self.detail, self.available = f"DHT22 on GPIO{pin}", True

    def read(self) -> float | None:
        try:
            v = getattr(self._dev, self._field)
            return None if v is None else round(float(v), 2)
        except Exception:  # noqa: BLE001 - DHT reads fail intermittently by design
            return None


# ------------------------------------------------------------------ simulation

class Simulated:
    """Development stand-in, used only with --simulate. Readings are tagged so they never pass as real."""

    def __init__(self, name: str, unit: str, base: float, noise: float, sim: "SimulatedBench"):
        self.name, self.unit, self._base, self._noise, self._sim = name, unit, base, noise, sim
        self.detail, self.available = "simulated", True

    def read(self) -> float | None:
        if self.name == "light":
            return round(self._base - 0.26 * self._sim.flip_progress() + random.gauss(0, self._noise), 4)
        if self.name == "mix_angle":
            return round(self._sim.angle() + random.gauss(0, 1.0), 2)
        return round(self._base + random.gauss(0, self._noise), 3)


class SimulatedBench:
    """Shared state for simulated sensors and camera: base added, flip, holder rotation."""

    def __init__(self, endpoint_ml: float = 4.0):
        self.endpoint_ml = endpoint_ml
        self.base_ml = 0.0
        self.flip_started: float | None = None
        self.mix_until = 0.0
        self.mix_start = 0.0

    def add_base(self, ml: float) -> None:
        self.base_ml += ml
        self.mix_start = time.time() + 0.8
        self.mix_until = self.mix_start + 3 * 1.6
        if self.flip_started is None and self.base_ml >= self.endpoint_ml - 1e-9:
            self.flip_started = self.mix_until + 0.5

    def flip_progress(self) -> float:
        if self.flip_started is None:
            return 0.0
        return max(0.0, min(1.0, (time.time() - self.flip_started) / 1.2))

    def angle(self) -> float:
        now = time.time()
        if self.mix_start <= now < self.mix_until:
            phase = ((now - self.mix_start) / 1.6) % 1.0
            return 180.0 * (phase / 0.4) if phase < 0.4 else (180.0 if phase < 0.55 else max(0.0, 180.0 * (1 - (phase - 0.55) / 0.4)))
        return 0.0

    def reset(self) -> None:
        self.__init__(self.endpoint_ml)


# ------------------------------------------------------------------ assembly

def build_sensors(hw: dict, simulate: SimulatedBench | None = None) -> dict[str, Sensor]:
    if simulate is not None:
        return {
            "light": Simulated("light", "ratio", 0.82, 0.006, simulate),
            "mix_angle": Simulated("mix_angle", "deg", 0.0, 1.0, simulate),
            "air_quality": Simulated("air_quality", "raw", 118.0, 3.0, simulate),
            "temp_c": Missing("temp_c", "°C", "no probe (simulated bench)"),
            "humidity": Missing("humidity", "%RH"),
        }
    sensors: dict[str, Sensor] = {}
    adc = make_adc(hw.get("adc", "none")) if hw.get("adc", "none") != "none" else None
    for name, unit, scale in (("light", "ratio", 1.0), ("mix_angle", "deg", None), ("air_quality", "raw", 1000.0)):
        spec = hw.get(name)
        if adc and spec is not None:
            s = scale if scale is not None else float(spec.get("max_deg", 300))
            sensors[name] = AnalogSensor(name, unit, adc, int(spec["channel"]), s)
        else:
            sensors[name] = Missing(name, unit, "no ADC" if spec is not None else "not connected")
    # No ADC: resistive sensors can still be read by RC charge timing on a GPIO pin.
    rc = dict(hw.get("rc") or {})
    if hw.get("light_rc_pin") is not None:
        rc.setdefault("light", {"pin": hw["light_rc_pin"]})
    for name, unit, mode in (("light", "rel", "light"), ("mix_angle", "deg", "angle")):
        spec = rc.get(name)
        if sensors[name].available or not spec:
            continue
        try:
            sensors[name] = RCTiming(name, unit, int(spec["pin"]), mode, float(spec.get("max_deg", 300)),
                                     spec.get("min_us"), spec.get("max_us"))
        except Exception as exc:  # noqa: BLE001
            log.warning("RC sensor %s unavailable: %s", name, exc)
            sensors[name] = Missing(name, unit, f"RC timing failed: {exc}")
    try:
        sensors["temp_c"] = DS18B20() if hw.get("ds18b20", True) else Missing("temp_c", "°C")
    except Exception:  # noqa: BLE001 - probe absent: temperature is entered by hand or missing
        sensors["temp_c"] = Missing("temp_c", "°C", "no probe; enter from a thermometer")
    if hw.get("dht22_pin") is not None:
        try:
            sensors["humidity"] = DHT22(int(hw["dht22_pin"]), "humidity")
        except Exception as exc:  # noqa: BLE001
            log.warning("DHT22 unavailable: %s", exc)
            sensors["humidity"] = Missing("humidity", "%RH")
    else:
        sensors["humidity"] = Missing("humidity", "%RH")
    return sensors


def isfinite(v: float | None) -> bool:
    return v is not None and not math.isnan(v) and not math.isinf(v)
