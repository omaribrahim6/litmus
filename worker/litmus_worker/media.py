"""Media files (keyframes, run videos) stored on the worker's disk and served under /media."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from .config import settings


def media_root() -> Path:
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    return settings.media_dir


def frame_path(run_id: uuid.UUID, frame_id: uuid.UUID) -> tuple[Path, str]:
    rel = f"runs/{run_id}/frames/{frame_id}.jpg"
    return media_root() / rel, f"/media/{rel}"


def video_path(run_id: uuid.UUID, suffix: str = ".mp4") -> tuple[Path, str]:
    rel = f"runs/{run_id}/video{suffix}"
    return media_root() / rel, f"/media/{rel}"


def save_stream(src: BinaryIO, dest: Path) -> str:
    """Write a stream to disk and return its sha256."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with open(dest, "wb") as out:
        while chunk := src.read(1 << 20):
            h.update(chunk)
            out.write(chunk)
    return h.hexdigest()


def save_bytes(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def local_path(url: str) -> Path | None:
    if url.startswith("/media/"):
        return media_root() / url[len("/media/"):]
    return None


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def copy_into(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
