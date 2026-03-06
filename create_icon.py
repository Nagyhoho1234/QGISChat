"""Generate a simple placeholder icon PNG for the plugin."""
import struct
import zlib
import os


def create_png(width, height, color_rgb, output_path):
    r, g, b = color_rgb
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            raw_data += bytes([r, g, b, 255])

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += make_chunk(b'IDAT', zlib.compress(raw_data))
    png += make_chunk(b'IEND', b'')

    with open(output_path, 'wb') as f:
        f.write(png)


icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
create_png(32, 32, (21, 101, 192), icon_path)
print(f"Icon created: {icon_path}")
