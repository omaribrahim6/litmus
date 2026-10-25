"""Touchscreen kiosk served by the station (open http://localhost:8080 in kiosk-mode Chromium)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .session import Session

STATIC = Path(__file__).parent / "static"


class StartIn(BaseModel):
    label: str = ""
    role: str = "reference"
    assumed_cause: str | None = None
    intro: bool = True


class AddIn(BaseModel):
    value: float


class ReadingIn(BaseModel):
    sensor: str = "temp_c"
    value: float
    unit: str = "°C"


class NoteIn(BaseModel):
    text: str


def create_app(session: Session) -> FastAPI:
    app = FastAPI(title="litmus-station")
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "kiosk.html")

    @app.get("/state")
    def state() -> dict:
        return session.snapshot()

    @app.get("/frame.jpg")
    def frame():
        from fastapi.responses import Response
        shot = session.camera.jpeg(quality=70)
        if shot is None:
            return Response(status_code=204)
        return Response(content=shot[0], media_type="image/jpeg", headers={"cache-control": "no-store"})

    @app.get("/stream.mjpg")
    def stream():
        """Live preview as MJPEG (about 12 fps): smoother than polling stills."""
        import time

        from fastapi.responses import StreamingResponse

        def frames():
            last = 0.0
            while True:
                shot = session.camera.jpeg(quality=65)
                if shot is not None and shot[1] != last:
                    last = shot[1]
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + shot[0] + b"\r\n"
                time.sleep(1 / 12)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.post("/start")
    def start(body: StartIn) -> dict:
        return session.start(body.label, body.role, body.assumed_cause, intro=body.intro)

    @app.post("/intro/stop")
    def intro_stop() -> dict:
        return session.stop_intro()

    @app.post("/intro/skip")
    def intro_skip() -> dict:
        return session.stop_intro(skip=True)

    @app.post("/intro/confirm")
    def intro_confirm() -> dict:
        return session.confirm_intro()

    @app.post("/intro/dismiss")
    def intro_dismiss() -> dict:
        return session.dismiss_intro()

    @app.post("/confirm")
    def confirm() -> dict:
        return session.confirm_step()

    @app.post("/next")
    def next_step() -> dict:
        return session.next_step()

    @app.post("/add")
    def add(body: AddIn) -> dict:
        return session.add_quantity(body.value)

    @app.post("/reading")
    def reading(body: ReadingIn) -> dict:
        return session.enter_reading(body.sensor, body.value, body.unit)

    @app.post("/note")
    def note(body: NoteIn) -> dict:
        return session.note(body.text)

    @app.post("/end")
    def end() -> dict:
        return session.end()

    @app.post("/reset")
    def reset() -> dict:
        with session.lock:
            if session.state != "recording":
                session._reset()
        return session.snapshot()

    return app
