# -*- coding: utf-8 -*-
"""Generate the ten Chatelaine standard empty-slot textures deterministically.

Shape source: Curios 9.5.1 standard ``assets/curios/textures/slot`` masks.
Color source: NetEase Minecraft 3.9 vanilla UI armor-slot textures.

The LGPL-3.0-or-later masks are stored separately from this MIT program.
The checked-in masks make generation independent from a local Gradle cache or
Minecraft installation.  PNG chunks, row filters and compression settings are
fixed, so the produced files are byte-stable for a given zlib implementation.
"""

from __future__ import print_function

import argparse
import binascii
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WIDTH = 16
HEIGHT = 16
NATIVE_SLOT_COLOR = (25, 32, 34, 255)
TRANSPARENT = (0, 0, 0, 0)

# ``#`` is an opaque native-black pixel; ``.`` is fully transparent.
MASKS = json.loads((PROJECT_ROOT / "THIRD_PARTY_LICENSES/curios-9.5.1/source/slot_masks.json").read_text(encoding="utf-8"))


def _chunk(kind, payload):
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _validate_mask(name, mask):
    if len(mask) != HEIGHT:
        raise ValueError("%s must contain %s rows" % (name, HEIGHT))
    for row in mask:
        if len(row) != WIDTH or set(row) - set(".#"):
            raise ValueError("%s contains an invalid row: %r" % (name, row))


def build_png(mask):
    rows = []
    for row in mask:
        pixels = bytearray()
        for value in row:
            pixels.extend(NATIVE_SLOT_COLOR if value == "#" else TRANSPARENT)
        rows.append(b"\x00" + bytes(pixels))
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _chunk(b"IEND", b"")
    )


def expected_files():
    result = {}
    for name in sorted(MASKS):
        _validate_mask(name, MASKS[name])
        result["empty_%s_slot.png" % name] = build_png(MASKS[name])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output-dir",
        help="Explicit destination; --check defaults to the runtime textures, generation to build/slot_textures.",
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / (
        "addon/resource_pack_chatelaine/textures/ui/chatelaine"
        if args.check else "build/slot_textures"
    )
    expected = expected_files()
    failures = []
    for filename, payload in expected.items():
        path = output_dir / filename
        digest = hashlib.sha256(payload).hexdigest()
        if args.check:
            if not path.is_file() or path.read_bytes() != payload:
                failures.append(filename)
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print("%s  %s" % (digest, path))
    if failures:
        print("slot texture mismatch: %s" % ", ".join(failures))
        return 1
    if args.check:
        print("Chatelaine standard slot textures match deterministic sources (%d files)" % len(expected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
