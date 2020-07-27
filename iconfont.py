import os
import struct
from os.path import join
from zlib import crc32

from PIL import Image


class IconEntry(object):
    def __init__(self, name, data):
        self.name, self.data = name, data
        self.crc = crc32(self.name) % (1 << 32)
        self.offset = 0


def encode_image(path):
    img = Image.open(path)
    img = img.resize((16, 16))
    pixels = list(img.getdata())

    tiles = [pixels[i:i + 8] for i in xrange(0, len(pixels), 8)]
    data = []
    for tile in tiles:
        bits = 0
        mask = 1
        for pixel in tile:
            if type(pixel) == tuple:
                pixel = sum(pixel)
            if pixel > 110:
                bits |= mask
            mask <<= 1
        data.append(bits)

    return data


def decode_image(data):
    pixels = []
    for bits in data:
        mask = 1
        while mask < 0x100:
            if(bits & mask):
                pixels.append((0, 0, 0, 255))
            else:
                pixels.append((0, 0, 0, 0))
            mask <<= 1
    img = Image.new(mode='RGBA', size=(16, 16))
    try:
        img.putdata(pixels, scale=1.0, offset=0.0)
    except:
        pass
    return img


def cname(name):
    name = name.replace('-', '_')
    name = name.upper()
    return name


def pack_icons(iconsdir, path_bin, path_hdr, path_json):
    files = [os.path.join(iconsdir, fn) for fn in os.listdir(iconsdir)]
    entries = []
    for filepath in files:
        print 'encode:', filepath
        data = encode_image(filepath)
        icon_name = os.path.splitext(os.path.split(filepath)[1])[0]
        icon = IconEntry(icon_name, data)
        entries.append(icon)

    sorted_entries = sorted(entries, cmp=lambda a, b: cmp(a.crc, b.crc))
    with open(path_bin, 'wb') as out:
        # Magic, section size, entry count, width, height
        header = 'ICON'+struct.pack('IHBB', 0, len(entries), 16, 16)
        out.write(header)

        out.write('\x00'*4*len(entries))
        for e in sorted_entries:
            e.offset = out.tell()
            out.write(struct.pack('B'*len(e.data), *e.data))
        sec_size = out.tell()
        out.seek(4, 0)
        out.write(struct.pack('I', sec_size))

        out.seek(len(header), 0)
        for e in sorted_entries:
            out.write(struct.pack('I', e.crc))

    with open(path_hdr, 'w') as hdr:
        hdr.write('\n'.join(
            ['#define ICON_'+cname(e.name)+' ('+hex(e.crc)+')' for e in entries]))

    with open(path_json, 'w') as json:
        json.write('{\n    "const": {\n')
        json.write(',\n'.join(
            ['        "'+cname(e.name)+'": '+'"ICON_'+cname(e.name)+'"' for e in entries]))
        json.write('}\n}')


if __name__ == "__main__":
    pack_icons('res/icons', 'iconfont.bin', 'iconfont.h', 'icons.json')
