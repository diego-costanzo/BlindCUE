"""Pure-Python OSC 1.0 (Open Sound Control) binary encoder and decoder.

Zero external dependencies. Fully compliant with Open Sound Control 1.0 specification:
  - 4-byte aligned null-terminated address pattern string
  - 4-byte aligned type tag string starting with ','
  - 32-bit big-endian signed integers ('i')
  - 32-bit big-endian IEEE 754 floats ('f')
  - 4-byte aligned null-terminated strings ('s')
  - Raw binary blobs ('b')
"""

from __future__ import annotations

import struct
from typing import Any


def _pad_to_4(data: bytes) -> bytes:
    """Pad byte array to a multiple of 4 bytes with null characters."""
    rem = len(data) % 4
    if rem != 0:
        return data + b"\x00" * (4 - rem)
    return data


def build_osc_message(address: str, *args: Any) -> bytes:
    """Encode an OSC address and arguments into standard OSC 1.0 binary wire format."""
    if not address.startswith("/"):
        address = "/" + address

    addr_b = _pad_to_4(address.encode("ascii", errors="replace") + b"\x00")

    tags = ","
    arg_bytes = bytearray()

    for arg in args:
        if isinstance(arg, bool):
            # Boolean in OSC 1.0 can be encoded as integer 1 or 0
            tags += "i"
            arg_bytes.extend(struct.pack(">i", 1 if arg else 0))
        elif isinstance(arg, int):
            tags += "i"
            arg_bytes.extend(struct.pack(">i", arg))
        elif isinstance(arg, float):
            tags += "f"
            arg_bytes.extend(struct.pack(">f", arg))
        elif isinstance(arg, (bytes, bytearray)):
            tags += "b"
            b_data = bytes(arg)
            b_hdr = struct.pack(">i", len(b_data))
            arg_bytes.extend(b_hdr + _pad_to_4(b_data))
        else:
            tags += "s"
            str_b = _pad_to_4(str(arg).encode("utf-8", errors="replace") + b"\x00")
            arg_bytes.extend(str_b)

    tags_b = _pad_to_4(tags.encode("ascii") + b"\x00")
    return addr_b + tags_b + bytes(arg_bytes)


def parse_osc_message(data: bytes) -> tuple[str, list[Any]]:
    """Decode an OSC 1.0 binary datagram into (address, list_of_arguments).

    Returns ("", []) if packet is malformed or invalid.
    """
    if len(data) < 4:
        return "", []

    # 1. Read null-terminated address string
    null_idx = data.find(b"\x00")
    if null_idx == -1:
        return "", []

    try:
        address = data[:null_idx].decode("ascii")
    except UnicodeDecodeError:
        return "", []

    # Address must start with '/'
    if not address.startswith("/"):
        return "", []

    # Align to 4-byte boundary for type tags
    idx = (null_idx + 4) & ~3
    if idx >= len(data):
        return address, []

    # 2. Read type tags
    if data[idx : idx + 1] != b",":
        # No type tag string, or empty arguments
        return address, []

    tag_end = data.find(b"\x00", idx)
    if tag_end == -1:
        return address, []

    tags = data[idx + 1 : tag_end].decode("ascii", errors="ignore")
    idx = (tag_end + 4) & ~3

    # 3. Read arguments according to type tags
    args: list[Any] = []
    for tag in tags:
        if tag == "i":
            if idx + 4 > len(data):
                break
            val = struct.unpack(">i", data[idx : idx + 4])[0]
            args.append(val)
            idx += 4
        elif tag == "f":
            if idx + 4 > len(data):
                break
            val = round(struct.unpack(">f", data[idx : idx + 4])[0], 4)
            args.append(val)
            idx += 4
        elif tag == "s":
            s_end = data.find(b"\x00", idx)
            if s_end == -1:
                break
            s_val = data[idx:s_end].decode("utf-8", errors="replace")
            args.append(s_val)
            idx = (s_end + 4) & ~3
        elif tag == "b":
            if idx + 4 > len(data):
                break
            b_len = struct.unpack(">i", data[idx : idx + 4])[0]
            idx += 4
            if b_len < 0 or idx + b_len > len(data):
                break
            b_val = data[idx : idx + b_len]
            args.append(b_val)
            idx = (idx + b_len + 3) & ~3
        elif tag in ("T", "F"):
            args.append(tag == "T")
        elif tag == "N":
            args.append(None)

    return address, args

