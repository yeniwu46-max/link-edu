import base64
import struct
import zlib
from services.classroom_fixtures import probe_image

def test_synthetic_png_has_valid_crc_and_pixels():
    image = base64.b64decode(probe_image().split(',')[1])
    assert image[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8
    while pos < len(image):
        n = struct.unpack('>I', image[pos:pos+4])[0]
        part = image[pos+4:pos+8+n]
        assert zlib.crc32(part) == struct.unpack('>I', image[pos+8+n:pos+12+n])[0]
        if part[:4] == b'IDAT':
            pixels = zlib.decompress(part[4:])
            assert len(pixels) == (128 * 3 + 1) * 96
            assert pixels[1:4] == bytes([45,100,230])
        pos += n + 12
