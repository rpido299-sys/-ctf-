"""Generate spectrogram images from the playlist archive."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Sequence
from zipfile import ZipFile

import matplotlib

# Headless backend for environments without a display.
matplotlib.use("Agg")

from PIL import Image

import librosa
import numpy as np


def compute_spectrogram(audio_path: Path) -> tuple[np.ndarray, int]:
    """Load *audio_path* and return its magnitude spectrogram in decibels."""

    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    stft = librosa.stft(y, n_fft=1024, hop_length=256, window="hann")
    magnitude = np.abs(stft)
    db = librosa.amplitude_to_db(magnitude, ref=np.max)
    return db, sr


def save_spectrogram_image(spectrogram: np.ndarray, target: Path) -> None:
    """Render *spectrogram* to *target* as a PNG image."""

    target.parent.mkdir(parents=True, exist_ok=True)

    # Downsample the spectrogram slightly to keep output images compact.
    reduced = spectrogram[::2, ::2]

    cmap = matplotlib.colormaps["magma"]
    normalized = reduced - reduced.min()
    peak = normalized.max()
    if peak > 0:
        normalized /= peak
    rgba = (cmap(normalized)[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(np.flipud(rgba))
    image.save(target)


def process_archive(archive_path: Path, output_dir: Path) -> Sequence[Path]:
    """Generate spectrograms for every MP3 in *archive_path*."""

    written: list[Path] = []
    with ZipFile(archive_path) as zf:
        members = sorted(name for name in zf.namelist() if name.lower().endswith(".mp3"))
        if not members:
            raise SystemExit("No MP3 files found inside the archive")

        for member in members:
            data = zf.read(member)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)

            try:
                print(f"processing {member}...")
                spectrogram, _ = compute_spectrogram(tmp_path)
                stem = Path(member).stem
                target = output_dir / f"{stem}_spectrogram.png"
                save_spectrogram_image(spectrogram, target)
                written.append(target)
            finally:
                tmp_path.unlink(missing_ok=True)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to playlist.zip")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("spectrograms"), help="Directory for the generated images"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = process_archive(args.archive, args.output)
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
