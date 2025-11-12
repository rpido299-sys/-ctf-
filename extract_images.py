"""Extract hidden images from the playlist archive.

This utility scans every MP3 inside `playlist.zip`, looks for embedded image signatures, and writes the recovered pictures to disk.

The script relies on Pillow (`pip install pillow`)."""

from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
from zipfile import ZipFile

from PIL import Image, ImageFile

# Some images inside the playlist contain trailing bytes. Allow Pillow to read
# such streams while we validate potential candidates.
ImageFile.LOAD_TRUNCATED_IMAGES = True

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_HEADERS: Sequence[bytes] = (b"GIF87a", b"GIF89a")
BMP_MAGIC = b"BM"

ExtractorResult = Tuple[int, bytes, str]


def is_valid_image(blob: bytes, expected_format: str) -> bool:
    """Return True if *blob* decodes as *expected_format* using Pillow."""

    bio = io.BytesIO(blob)
    try:
        with Image.open(bio) as im:  # type: ignore[arg-type]
            im.verify()
        bio.seek(0)
        with Image.open(bio) as im:
            return im.format == expected_format
    except Exception:
        return False


def extract_pngs(data: bytes) -> Iterable[ExtractorResult]:
    start = 0
    while True:
        idx = data.find(PNG_MAGIC, start)
        if idx == -1:
            break
        pos = idx + len(PNG_MAGIC)
        end = None
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos : pos + 4])[0]
            chunk_type = data[pos + 4 : pos + 8]
            pos += 8 + length + 4
            if pos > len(data):
                break
            if chunk_type == b"IEND":
                end = pos
                break
        if end is not None:
            blob = data[idx:end]
            if is_valid_image(blob, "PNG"):
                yield idx, blob, "png"
                start = end
                continue
        start = idx + 1


def extract_jpegs(data: bytes) -> Iterable[ExtractorResult]:
    start = 0
    while True:
        idx = data.find(JPEG_MAGIC, start)
        if idx == -1:
            break
        cursor = idx + len(JPEG_MAGIC)
        found = False
        while True:
            end = data.find(b"\xff\xd9", cursor)
            if end == -1:
                break
            blob = data[idx : end + 2]
            if is_valid_image(blob, "JPEG"):
                yield idx, blob, "jpg"
                start = end + 2
                found = True
                break
            cursor = end + 2
        if not found:
            start = idx + 1


def extract_gifs(data: bytes) -> Iterable[ExtractorResult]:
    for header in GIF_HEADERS:
        start = 0
        while True:
            idx = data.find(header, start)
            if idx == -1:
                break
            cursor = idx + len(header)
            found = False
            while True:
                end = data.find(b"\x3b", cursor)
                if end == -1:
                    break
                blob = data[idx : end + 1]
                if is_valid_image(blob, "GIF"):
                    yield idx, blob, "gif"
                    start = end + 1
                    found = True
                    break
                cursor = end + 1
            if not found:
                start = idx + 1


def extract_bmps(data: bytes) -> Iterable[ExtractorResult]:
    start = 0
    minimum_size = 54  # 14-byte header + 40-byte DIB header
    while True:
        idx = data.find(BMP_MAGIC, start)
        if idx == -1:
            break
        if idx + 6 > len(data):
            break
        size = struct.unpack("<I", data[idx + 2 : idx + 6])[0]
        if size >= minimum_size and idx + size <= len(data):
            blob = data[idx : idx + size]
            if is_valid_image(blob, "BMP"):
                yield idx, blob, "bmp"
                start = idx + size
                continue
        start = idx + 2


def extract_images(data: bytes) -> List[ExtractorResult]:
    results: List[ExtractorResult] = []
    for extractor in (extract_pngs, extract_jpegs, extract_gifs, extract_bmps):
        results.extend(extractor(data))
    return sorted(results, key=lambda item: item[0])


def process_archive(archive_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as zf:
        members = sorted(
            (name for name in zf.namelist() if name.lower().endswith(".mp3"))
        )
        if not members:
            raise SystemExit("No MP3 files found inside the archive")

        for member in members:
            data = zf.read(member)
            images = extract_images(data)
            if not images:
                continue
            stem = Path(member).stem
            for index, (_, blob, ext) in enumerate(images, start=1):
                target = output_dir / f"{stem}_{index}.{ext}"
                target.write_bytes(blob)
                print(f"Saved {target.relative_to(output_dir)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract hidden images from the playlist archive"
    )
    parser.add_argument(
        "archive",
        type=Path,
        help="Path to playlist.zip",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("extracted_images"),
        help="Where to save the decoded images (default: ./extracted_images)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    process_archive(args.archive, args.output)


if __name__ == "__main__":
    main()
