# Litmus station (Raspberry Pi 5)

The station records every run: sensors at 2 Hz, tube color from the webcam at 6 Hz, keyframes every 2 s and at every event, and the full video. It detects the color flip locally and uploads everything to the worker through an offline-safe outbox.

## Wiring

| Part | Connects to | Read as |
|---|---|---|
| Logitech USB webcam | USB | `camera: 0` (exposure and white balance are locked with `v4l2-ctl`) |
| Light sensor through the tube | ADC channel (Grove A0 or ADS1115 A0) | `light`, 0-1 ratio |
| Rotary angle sensor on the holder axis | ADC channel (Grove A2) | `mix_angle`, degrees; inversions counted in code |
| Air quality sensor (box floor) | ADC channel (Grove A4) | `air_quality`, raw |
| LED behind the tube | GPIO through a transistor, always on during runs | light source for the colorimeter |
| Confirm button | GPIO17 to GND | same as tapping Confirm on the screen |
| DS18B20 probe (optional) | 1-Wire on GPIO4 with a 4.7 kΩ pull-up | `temp_c`, measured |
| DHT22 (optional) | any GPIO | `humidity` |

**No ADC?** A plain photoresistor still works: LDR from 3.3 V to a GPIO pin, 1 µF capacitor from that pin to GND, set `light_rc_pin`. Mixing then falls back to the camera, and air quality is reported as missing. Missing sensors are shown as missing and become missing evidence; nothing is ever estimated.

**No temperature probe?** Tap "Enter reading" on the kiosk and type the thermometer value. It is stored as *reported*, not measured.

**Jugs and bottles.** Label the water jugs DISTILLED and TAP (large letters, facing the camera) and the vinegar bottles A and B. When a step is confirmed, Gemini reads the label in the keyframe and commits which one was used.

## Pi setup

```bash
sudo raspi-config nonint do_i2c 0                 # ADC on I2C
echo "dtoverlay=w1-gpio" | sudo tee -a /boot/firmware/config.txt   # DS18B20
sudo apt install -y python3-venv ffmpeg v4l-utils chromium-browser
git clone https://github.com/omaribrahim6/litmus && cd litmus/station
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt gpiozero lgpio
pip install grove.py                              # Grove Base HAT, or: pip install adafruit-circuitpython-ads1x15
cp station.example.json station.json              # edit channels to match the wiring
```

Create `station/.env`:

```
WORKER_URL=https://<worker host>
WORKER_TOKEN=<same as the worker>
STATION_ID=bench-1
EXPERIMENT_ID=vinegar-titration
```

Run it and open the kiosk full screen:

```bash
python -m litmus_station
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8080
```

## Without hardware

```bash
python -m litmus_station --simulate              # simulated sensors and camera; runs are flagged synthetic
python -m litmus_station --camera run.mp4        # replay a recorded session as the camera
```

## Calibrating the color region

The protocol's `roi` (in `db/experiments/vinegar-titration.json`) is the rectangle inside the tube where color is measured, as fractions of the frame. Fix the camera with clay, open the kiosk, and adjust `roi` until the box sits inside the liquid below the meniscus. Re-seed the protocol with `python -m litmus_worker.seed`.
