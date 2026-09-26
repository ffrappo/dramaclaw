"""Pluggable soundbed & audio generation provider.

Provides local Apple Silicon text-to-audio / ambient soundbed generation via
thinksound-native (Metal 4), with pluggable architecture for future soundbed models.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

DEFAULT_THINKSOUND_BIN = Path.home() / "works/repos/thinksound-native/build/ts-native"
DEFAULT_THINKSOUND_DIR = Path("/tmp/ts-weights")

KNOWN_SOUNDBED_MODELS = {
    "thinksound",
    "thinksound-native",
    "soundbed-local",
    "ambient-local",
    "ThinkSound-1S",
}


def is_soundbed_model(model_name: str) -> bool:
    name = (model_name or "").strip().lower()
    return name in {m.lower() for m in KNOWN_SOUNDBED_MODELS} or "thinksound" in name or "soundbed" in name


class SoundbedProvider(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        output_path: Path,
        duration_seconds: int = 8,
        seed: int | None = None,
        output_format: str = "mp3",
    ) -> Path:
        ...


class ThinkSoundNativeProvider:
    """Generates ambient sound beds locally using ThinkSound Native on Apple Silicon Metal 4."""

    def __init__(
        self,
        bin_path: Path | None = None,
        weights_dir: Path | None = None,
    ):
        self.bin_path = bin_path or Path(
            os.environ.get("THINKSOUND_BIN", str(DEFAULT_THINKSOUND_BIN))
        )
        self.weights_dir = weights_dir or Path(
            os.environ.get("THINKSOUND_DIR", str(DEFAULT_THINKSOUND_DIR))
        )

    def is_available(self) -> bool:
        return self.bin_path.is_file() and os.access(self.bin_path, os.X_OK) and self.weights_dir.is_dir()

    async def generate(
        self,
        *,
        prompt: str,
        output_path: Path,
        duration_seconds: int = 8,
        seed: int | None = None,
        output_format: str = "mp3",
    ) -> Path:
        if not self.is_available():
            raise RuntimeError(
                f"ThinkSound Native not available at {self.bin_path} with weights at {self.weights_dir}"
            )

        duration = max(1, min(int(duration_seconds or 8), 30))
        rnd_seed = seed if seed is not None else 4242

        # Ensure destination directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary wav path
        temp_wav = output_path.with_suffix(".temp.wav")
        cot_prompt = f"Ambience and environmental sound: {prompt}. Natural atmosphere, no voice, high acoustic fidelity."

        cmd = [
            str(self.bin_path),
            "--caption", prompt,
            "--cot", cot_prompt,
            "--dir", str(self.weights_dir),
            "--dur", str(duration),
            "--seed", str(rnd_seed),
            "--out", str(temp_wav),
        ]

        logger.info("Executing ThinkSound Native: %s", " ".join(cmd))
        loop = asyncio.get_running_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, check=False)
        )

        if proc.returncode != 0 or not temp_wav.is_file():
            raise RuntimeError(
                f"ThinkSound generation failed (code {proc.returncode}): {proc.stderr or proc.stdout}"
            )

        # Convert to requested format if needed
        fmt = output_format.lower().strip()
        if fmt in {"wav", "wave"}:
            if output_path != temp_wav:
                shutil.move(temp_wav, output_path)
            return output_path

        # Default: encode to MP3 via ffmpeg
        ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        if not os.path.exists(ffmpeg):
            # Fallback if ffmpeg is missing
            shutil.move(temp_wav, output_path)
            return output_path

        ffmpeg_cmd = [
            ffmpeg,
            "-y",
            "-i", str(temp_wav),
            "-codec:a", "libmp3lame",
            "-qscale:a", "2",
            str(output_path),
        ]
        conv = await loop.run_in_executor(
            None,
            lambda: subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)
        )
        if temp_wav.exists():
            temp_wav.unlink(missing_ok=True)

        if conv.returncode != 0 or not output_path.is_file():
            raise RuntimeError(f"ffmpeg MP3 conversion failed: {conv.stderr}")

        return output_path


def get_soundbed_provider(model_name: str = "thinksound-native") -> SoundbedProvider:
    """Return a configured soundbed provider instance based on model name or environment."""
    return ThinkSoundNativeProvider()
