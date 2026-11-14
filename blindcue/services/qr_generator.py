"""Pure-Python QR Code (ISO/IEC 18004) Generator for BlindCUE.

Zero external dependencies. Runs 100% natively on Linux, macOS, and Windows.
Supports byte encoding mode with Error Correction Level M for instant LAN pairing URLs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

# ── Galois Field GF(2^8) Arithmetic ──────────────────────────────────
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _EXP[_i + 255] = _x
    _LOG[_x] = _i
    _x = (_x << 1) ^ (0x11D if (_x & 0x80) else 0)


def _gmul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _poly_mul(p1: list[int], p2: list[int]) -> list[int]:
    res = [0] * (len(p1) + len(p2) - 1)
    for i, c1 in enumerate(p1):
        if c1:
            for j, c2 in enumerate(p2):
                if c2:
                    res[i + j] ^= _gmul(c1, c2)
    return res


def _rs_generator_poly(num_ec: int) -> list[int]:
    g = [1]
    for i in range(num_ec):
        g = _poly_mul(g, [1, _EXP[i]])
    return g


def _rs_encode(data: list[int], num_ec: int) -> list[int]:
    gen = _rs_generator_poly(num_ec)
    res = list(data) + [0] * num_ec
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j, g in enumerate(gen):
                res[i + j] ^= _gmul(g, coef)
    return res[len(data):]


# ── QR Code Specification Tables (ECC Level M, Versions 1..6) ────────
# (version, total_data_bytes, ec_bytes_per_block, num_blocks)
_VERSIONS_M = [
    (1, 16, 10, 1),   # V1: 21x21, 16 data, 10 EC
    (2, 28, 16, 1),   # V2: 25x25, 28 data, 16 EC
    (3, 44, 26, 1),   # V3: 29x29, 44 data, 26 EC
    (4, 64, 18, 2),   # V4: 33x33, 64 data, 36 EC (2 blocks of 32 data, 18 EC)
    (5, 86, 24, 2),   # V5: 37x37, 86 data, 48 EC (2 blocks of 43 data, 24 EC)
    (6, 108, 16, 4),  # V6: 41x41, 108 data, 64 EC (4 blocks of 27 data, 16 EC)
]

_ALIGN_PATTERNS = {
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
}

# Pre-computed 15-bit format information words for Mask 0..7 with ECC Level M (BCH 15,5)
_FORMAT_BITS_M = [
    0x5412, 0x5125, 0x5E7C, 0x5B4B,
    0x45F9, 0x40CE, 0x4F97, 0x4AA0,
]


def _choose_version(data_len: int) -> tuple[int, int, int, int]:
    for ver, data_cap, ec_per_blk, blks in _VERSIONS_M:
        # Byte mode overhead: 4-bit mode indicator + 8-bit character count = 12 bits = ~2 bytes
        if data_len + 3 <= data_cap:
            return ver, data_cap, ec_per_blk, blks
    return _VERSIONS_M[-1]


def encode_qr_matrix(text: str) -> list[list[int]]:
    """Encode text into a 2D matrix of binary modules (1 for black, 0 for white)."""
    raw_data = text.encode("utf-8")
    ver, total_data, ec_per_block, num_blocks = _choose_version(len(raw_data))
    size = 17 + 4 * ver

    # 1. Build Data Bitstream (Byte Mode: 0100 + 8-bit length + raw bytes + terminator)
    bits = [0, 1, 0, 0]
    char_count = len(raw_data)
    for b in range(7, -1, -1):
        bits.append((char_count >> b) & 1)
    for byte in raw_data:
        for b in range(7, -1, -1):
            bits.append((byte >> b) & 1)

    # Terminator up to 4 bits
    req_bits = total_data * 8
    pad_needed = min(4, req_bits - len(bits))
    bits.extend([0] * pad_needed)

    # Pad to byte boundary
    while len(bits) % 8 != 0:
        bits.append(0)

    # Pad with alternating 0xEC, 0x11
    pad_bytes = [0xEC, 0x11]
    pad_idx = 0
    while len(bits) < req_bits:
        pad = pad_bytes[pad_idx % 2]
        pad_idx += 1
        for b in range(7, -1, -1):
            bits.append((pad >> b) & 1)

    # Convert bitstream to data bytes
    data_bytes: list[int] = []
    for i in range(0, len(bits), 8):
        byte_val = 0
        for b in range(8):
            byte_val = (byte_val << 1) | bits[i + b]
        data_bytes.append(byte_val)

    # 2. Divide data bytes into blocks and calculate Reed-Solomon ECC
    block_data_len = total_data // num_blocks
    blocks_data: list[list[int]] = []
    blocks_ec: list[list[int]] = []

    for b in range(num_blocks):
        b_data = data_bytes[b * block_data_len : (b + 1) * block_data_len]
        blocks_data.append(b_data)
        blocks_ec.append(_rs_encode(b_data, ec_per_block))

    # Interleave data bytes, then interleave ECC bytes
    final_codewords: list[int] = []
    for i in range(block_data_len):
        for b in range(num_blocks):
            final_codewords.append(blocks_data[b][i])
    for i in range(ec_per_block):
        for b in range(num_blocks):
            final_codewords.append(blocks_ec[b][i])

    # Convert final codewords to bitstream
    cw_bits: list[int] = []
    for cw in final_codewords:
        for b in range(7, -1, -1):
            cw_bits.append((cw >> b) & 1)

    # 3. Create matrix: -1 = unassigned, 0 = white, 1 = black
    matrix = [[-1] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_finder(r: int, c: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size:
                    reserved[nr][nc] = True
                    if 0 <= dr <= 6 and 0 <= dc <= 6:
                        if dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4):
                            matrix[nr][nc] = 1
                        else:
                            matrix[nr][nc] = 0
                    else:
                        matrix[nr][nc] = 0

    # Finder patterns
    set_finder(0, 0)
    set_finder(0, size - 7)
    set_finder(size - 7, 0)

    # Timing patterns
    for i in range(8, size - 8):
        if matrix[6][i] == -1:
            matrix[6][i] = 1 if i % 2 == 0 else 0
            reserved[6][i] = True
        if matrix[i][6] == -1:
            matrix[i][6] = 1 if i % 2 == 0 else 0
            reserved[i][6] = True

    # Alignment pattern for V >= 2
    if ver in _ALIGN_PATTERNS:
        positions = _ALIGN_PATTERNS[ver]
        for ar in positions:
            for ac in positions:
                if reserved[ar][ac]:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        reserved[ar + dr][ac + dc] = True
                        if abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0):
                            matrix[ar + dr][ac + dc] = 1
                        else:
                            matrix[ar + dr][ac + dc] = 0

    # Reserve Format Info areas
    for i in range(9):
        reserved[8][i] = True
        reserved[i][8] = True
    for i in range(8):
        reserved[8][size - 1 - i] = True
        reserved[size - 1 - i][8] = True
    # Dark module
    matrix[size - 8][8] = 1
    reserved[size - 8][8] = True

    # 4. Place Data Bits (Zigzag upwards/downwards)
    bit_idx = 0
    dir_up = True
    col = size - 1
    while col > 0:
        if col == 6:  # Skip vertical timing column
            col -= 1
        cols = [col, col - 1]
        rows = list(range(size - 1, -1, -1)) if dir_up else list(range(size))
        for r in rows:
            for c in cols:
                if not reserved[r][c]:
                    b_val = cw_bits[bit_idx] if bit_idx < len(cw_bits) else 0
                    bit_idx += 1
                    # Apply Mask 0: (row + col) % 2 == 0
                    mask = ((r + c) % 2 == 0)
                    matrix[r][c] = b_val ^ (1 if mask else 0)
        dir_up = not dir_up
        col -= 2

    # 5. Write Format Information (Mask 0, Level M: 0x5412)
    format_word = _FORMAT_BITS_M[0]
    fmt_bits = [(format_word >> (14 - i)) & 1 for i in range(15)]

    # Around top-left finder
    matrix[8][0] = fmt_bits[0]
    matrix[8][1] = fmt_bits[1]
    matrix[8][2] = fmt_bits[2]
    matrix[8][3] = fmt_bits[3]
    matrix[8][4] = fmt_bits[4]
    matrix[8][5] = fmt_bits[5]
    matrix[8][7] = fmt_bits[6]
    matrix[8][8] = fmt_bits[7]
    matrix[7][8] = fmt_bits[8]
    matrix[5][8] = fmt_bits[9]
    matrix[4][8] = fmt_bits[10]
    matrix[3][8] = fmt_bits[11]
    matrix[2][8] = fmt_bits[12]
    matrix[1][8] = fmt_bits[13]
    matrix[0][8] = fmt_bits[14]

    # Around top-right and bottom-left finders
    for i in range(8):
        matrix[8][size - 1 - i] = fmt_bits[i]
    for i in range(7):
        matrix[size - 7 + i][8] = fmt_bits[8 + i]

    # Normalize matrix to 0/1
    for r in range(size):
        for c in range(size):
            if matrix[r][c] == -1:
                matrix[r][c] = 0

    return matrix


def generate_qr_pixmap(text: str, size: int = 200, quiet_zone: int = 2) -> QPixmap:
    """Generate high-contrast QPixmap QR code without requiring any external tools."""
    matrix = encode_qr_matrix(text)
    dim = len(matrix)
    total_dim = dim + 2 * quiet_zone

    scale = max(4, size // total_dim)
    img_size = total_dim * scale

    image = QImage(img_size, img_size, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))

    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#000000"))

    for r in range(dim):
        for c in range(dim):
            if matrix[r][c] == 1:
                x = (c + quiet_zone) * scale
                y = (r + quiet_zone) * scale
                painter.drawRect(x, y, scale, scale)

    painter.end()
    return QPixmap.fromImage(image).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

