#!/usr/bin/env python3
"""Decrypt an XOR-obfuscated PNG image and render it as ASCII art."""
from __future__ import annotations

import argparse
import io
from typing import Sequence

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - defensive guard
    raise SystemExit(
        "Pillow is required for this script. Install it via 'pip install pillow'."
    ) from exc

try:
    from mpmath import mp
except ImportError as exc:  # pragma: no cover - defensive guard
    raise SystemExit("mpmath is required for pi key generation.") from exc

DEFAULT_KEY = "pi"
ASCII_GRADIENT = "@%#*+=-:. "


def pi_key(length: int) -> str:
    """Return the first ``length`` characters of pi, including the decimal point."""
    if length <= 0:
        raise ValueError("Length must be greater than zero")
    if length == 1:
        return "3"

    mp.dps = length + 5
    pi_str = mp.nstr(mp.pi, n=length, strip_zeros=False)
    if len(pi_str) < length:
        pi_str = pi_str.ljust(length, "0")
    return pi_str[:length]


def xor_decrypt(data: bytes, key: str) -> bytes:
    """Return ``data`` XOR'ed with the repeating ``key`` string."""
    if not key:
        raise ValueError("Key must be a non-empty string")
    key_bytes = key.encode("utf-8")
    key_len = len(key_bytes)
    return bytes(byte ^ key_bytes[i % key_len] for i, byte in enumerate(data))


def image_to_ascii(image: Image.Image, width: int, palette: Sequence[str]) -> str:
    """Convert ``image`` to ASCII art with ``width`` characters."""
    if width <= 0:
        raise ValueError("Width must be greater than zero")
    if not palette:
        raise ValueError("Palette must contain at least one character")

    grayscale = image.convert("L")
    aspect_ratio = grayscale.height / grayscale.width
    height = max(1, int(width * aspect_ratio * 0.5))
    resized = grayscale.resize((width, height))

    scale = (len(palette) - 1) / 255
    rows = []
    for y in range(resized.height):
        row_chars = [palette[int(resized.getpixel((x, y)) * scale)] for x in range(resized.width)]
        rows.append("".join(row_chars))
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Path to the XOR-obfuscated PNG image")
    parser.add_argument(
        "--key",
        default=DEFAULT_KEY,
        help=(
            "XOR key string (default: 'pi', which expands to digits of pi long enough "
            "for the encrypted data)"
        ),
    )
    parser.add_argument(
        "--width",
        type=int,
        default=80,
        help="Width of the ASCII art in characters (default: 80)",
    )
    parser.add_argument(
        "--palette",
        default=ASCII_GRADIENT,
        help="Characters to use for the ASCII gradient from dark to light",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="Optional output path to store the decrypted PNG image",
    )
    args = parser.parse_args()

    with open(args.path, "rb") as f:
        encrypted = f.read()

    key = args.key
    if key == "pi":
        key = pi_key(len(encrypted))
    decrypted = xor_decrypt(encrypted, key)

    if args.save:
        with open(args.save, "wb") as f:
            f.write(decrypted)

    image = Image.open(io.BytesIO(decrypted))
    ascii_art = image_to_ascii(image, args.width, args.palette)
    print(ascii_art)


if __name__ == "__main__":
    main()
