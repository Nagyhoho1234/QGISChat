"""Generate a chat bubble icon PNG for the plugin."""
import struct
import zlib
import os
import math


def create_chat_icon(size, output_path):
    """Draw a chat bubble with three dots on transparent background."""
    pixels = [[(0, 0, 0, 0)] * size for _ in range(size)]
    blue = (21, 101, 192, 255)
    white = (255, 255, 255, 255)

    # Bubble body: rounded rectangle
    bx1, by1 = 2, 3
    bx2, by2 = size - 3, size - 10
    radius = 5

    for y in range(size):
        for x in range(size):
            # Check if inside rounded rectangle
            in_body = False
            if bx1 + radius <= x <= bx2 - radius and by1 <= y <= by2:
                in_body = True
            elif bx1 <= x <= bx2 and by1 + radius <= y <= by2 - radius:
                in_body = True
            else:
                # Check corners
                corners = [
                    (bx1 + radius, by1 + radius),
                    (bx2 - radius, by1 + radius),
                    (bx1 + radius, by2 - radius),
                    (bx2 - radius, by2 - radius),
                ]
                for cx, cy in corners:
                    if math.hypot(x - cx, y - cy) <= radius:
                        in_body = True
                        break

            if in_body:
                pixels[y][x] = blue

    # Tail: small triangle at bottom-left
    tail_tip_x, tail_tip_y = 7, size - 4
    tail_base_left, tail_base_right = 5, 13
    tail_base_y = by2
    for y in range(tail_base_y, tail_tip_y + 1):
        progress = (y - tail_base_y) / max(1, tail_tip_y - tail_base_y)
        left = tail_base_left + (tail_tip_x - tail_base_left) * progress
        right = tail_base_right + (tail_tip_x - tail_base_right) * progress
        for x in range(int(left), int(right) + 1):
            if 0 <= x < size and 0 <= y < size:
                pixels[y][x] = blue

    # Three dots (ellipsis) inside the bubble
    dot_y = (by1 + by2) // 2
    dot_r = 2
    dot_positions = [size // 2 - 7, size // 2, size // 2 + 7]
    for dx in dot_positions:
        for y in range(dot_y - dot_r, dot_y + dot_r + 1):
            for x in range(dx - dot_r, dx + dot_r + 1):
                if math.hypot(x - dx, y - dot_y) <= dot_r and 0 <= x < size and 0 <= y < size:
                    pixels[y][x] = white

    # Encode as PNG
    raw_data = b''
    for row in pixels:
        raw_data += b'\x00'  # filter: none
        for r, g, b, a in row:
            raw_data += bytes([r, g, b, a])

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
    png += make_chunk(b'IDAT', zlib.compress(raw_data))
    png += make_chunk(b'IEND', b'')

    with open(output_path, 'wb') as f:
        f.write(png)


script_dir = os.path.dirname(os.path.abspath(__file__))
create_chat_icon(32, os.path.join(script_dir, 'icon.png'))
print("Icon created.")
