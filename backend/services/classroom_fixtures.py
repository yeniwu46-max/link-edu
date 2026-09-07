"""Authored, non-personal test image. Not classroom evidence or training data."""
import base64
import struct
import zlib

def probe_image():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    pixels = (b'\x00' + bytes([45, 100, 230]) * 64 + bytes([250, 150, 200]) * 64) * 96
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', 128, 96, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode()
