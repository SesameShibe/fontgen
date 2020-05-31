# coding: utf-8
import freetype
from freetype import (FT_LOAD_DEFAULT, FT_LOAD_NO_BITMAP, FT_LOAD_NO_HINTING,
                      FT_LOAD_RENDER, FT_RENDER_MODE_NORMAL, Face, Vector)
from io import BytesIO
import codecs
import struct
from PIL import Image


BLANK_CHARS = [u'\r', u'\n']


def f26d6_to_int(val):
    ret = (abs(val) & 0x7FFFFFC0) >> 6
    if val < 0:
        return -ret
    else:
        return ret


def f16d16_to_int(val):
    ret = (abs(val) & 0x3FFFC0) >> 16
    if val < 0:
        return -ret
    else:
        return ret


class Font(object):
    def __init__(self, ttfPath, pxWidth, pxHeight, fltr, padding, baseline, isAscii=False):
        self._fileName = ttfPath
        self.FtFont = freetype.Face(ttfPath)
        if isAscii:
            self.FtFont.set_pixel_sizes(pxHeight, pxHeight)
        else:
            self.FtFont.set_pixel_sizes(pxWidth, pxHeight)
        self.FontSize = pxWidth
        self.CellWidth = pxWidth+padding
        self.CellHeight = pxHeight+padding
        self.GlyphSize = (self.CellWidth, self.CellHeight)
        self.BaseLine = pxHeight-baseline
        self.Filter = fltr
        self.Chars = {}

    def addChars(self, chars):
        for c in chars:
            if not c in self.Chars.keys():
                self.addChar(c)

    def addChar(self, c):
        flags = FT_LOAD_RENDER | FT_LOAD_NO_HINTING
        self.FtFont.load_char(c, flags)

        glyphslot = self.FtFont.glyph
        bitmap = glyphslot.bitmap
        buf = bytearray('')

        if self._fileName[-3:] != 'bdf':
            adv = f26d6_to_int(glyphslot.metrics.horiAdvance)
            horiBearingX = f26d6_to_int(glyphslot.metrics.horiBearingX)
            horiBearingY = f26d6_to_int(glyphslot.metrics.horiBearingY)

            dxo = ((self.CellWidth - bitmap.width) / 2)
            dy = self.BaseLine - horiBearingY

            buf = bytearray('\x00'*(self.CellWidth*self.CellHeight))
            if(dxo + bitmap.width) > self.CellWidth:
                dxo -= dxo+bitmap.width-self.CellWidth
            for y in range(bitmap.rows):
                if(dy >= self.CellHeight):
                    break
                dx = dxo
                for x in range(bitmap.width):
                    if(dx >= self.CellWidth):
                        break
                    pos = y * bitmap.width + x
                    if(pos >= len(bitmap.buffer)):
                        break
                    a = ((bitmap.buffer[pos]) & 0xFF)
                    buf[self.CellWidth*dy+dx] = a
                    dx += 1
                dy += 1

            buf = compressGlyphBmp(buf, self.Filter)
        else:
            buf = [int('{:08b}'.format(btis)[::-1], 2)
                   for btis in bitmap.buffer]
        self.Chars[c] = buf
        self.GlyphDataLength = len(buf)

    def saveHeader(self, path):
        with open(path, 'w')as hdr:
            chars_str = ''
            glyphs_strs = []
            for k in sorted(self.Chars.keys()):
                val = self.Chars[k]
                chars_str += '0x%04x, ' % ord(k)

                s = '{'
                for c in val:
                    s += '0x%02x, ' % (c)
                s += '}'
                glyphs_strs.append(s)

            hdr.write('const uint8_t font_%d[%d][%d] =  {\n' % (
                self.FontSize, len(self.Chars), len(self.Chars.values()[0])))
            hdr.write(',\n'.join(glyphs_strs))
            hdr.write('};\n\n')

            hdr.write('const uint16_t chars_%d[] =  {\n' % self.FontSize)
            hdr.write(chars_str)
            hdr.write('};\n\n')

            hdr.write('const size_t font_%d_char_count =  %d;\n\n' %
                      (self.FontSize, len(self.Chars)))

            hdr.write('const uint16_t font_%d_cell_width = %d;\n\n' %
                      (self.FontSize, self.CellWidth))

            hdr.write('const uint16_t font_%d_cell_height = %d;\n\n' %
                      (self.FontSize, self.CellHeight))

    def saveBin(self, path):
        with open(path, 'wb') as fnt:
            for k in sorted(self.Chars.keys()):
                fnt.write(self.Chars[k])

    def saveImage(self, path):
        glyphsToImg(path, [self.Chars[k]
                           for k in sorted(self.Chars.keys())], self.GlyphSize, self.Filter)


def getFileEncoding(path):
    with open(path, 'rb')as f:
        magic = f.read(4)
        # utf-8
        if(magic[:3] == '\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif (magic[:2] == '\xff\xfe'):
            return 'utf-16le'
        elif (magic[:2] == '\xfe\xff'):
            return 'utf-16be'
        elif (magic == '\x00\x00\xff\xfe'):
            return 'utf-32le'
        elif (magic == '\xfe\xff\x00\x00'):
            return 'utf-32be'
        else:
            return 'utf-8'


def scanFiles(paths):
    chars = []
    for path in paths:
        encoding = getFileEncoding(path)
        with codecs.open(path, 'r', encoding) as f:
            print path
            text = f.read()
            for c in text:
                if c not in chars and c not in BLANK_CHARS:
                    chars.append(c)
    return sorted(chars)


def generateFont(ttfPath, size, chars, fltr, padding, baseline, savePath, imgSavePath):
    font = Font(ttfPath, size[0], size[1], fltr, padding, baseline)
    font.addChars(chars)
    font.saveHeader(savePath)
    if(imgSavePath):
        font.saveImage(imgSavePath)


def generateAsciiFont16(bdfPath, fltr, padding, baseline, savePath, imgSavePath):
    font = Font(bdfPath, 8, 13, fltr, padding, baseline, True)
    chars = [unichr(i) for i in range(0, 0x4FF)]
    font.addChars(chars)
    font.saveHeader(savePath)
    if(imgSavePath):
        font.saveImage(imgSavePath)


def generateUnicodeFont16(ttfPath, fltr, padding, baseline, savePath, imgSavePath):
    font = Font(ttfPath, 16, 16, fltr, padding, baseline)
    chars = []
    chars.extend([unichr(i)
                  for i in range(0x3000, 0x9FFF)])
    chars.extend([unichr(i)
                  for i in range(0xF900, 0xFFFF)])
    font.addChars(chars)
    font.saveHeader(savePath)
    if(imgSavePath):
        font.saveImage(imgSavePath)


def generateBinaryFont16(ttfPath, bdfPath, fltr, padding, baseline, savePath):
    halfWidthFont = Font(bdfPath, 8, 13, fltr, padding, baseline, True)
    halfWidthFont.addChars([unichr(i) for i in range(0, 0x4FF)])

    fullWidthFont1 = Font(ttfPath, 16, 16, fltr, padding, baseline, False)
    fullWidthFont1.addChars([unichr(i) for i in range(0x3000, 0x9FFF)])

    fullWidthFont2 = Font(ttfPath, 16, 16, fltr, padding, baseline, False)
    fullWidthFont2.addChars([unichr(i) for i in range(0xF900, 0xFFFF)])

    with open(savePath, 'wb')as fnt:
        w = fnt.write
        w('FONT')

        # Section count
        w(struct.pack('HH', 3, 2))
        w('\x00'*14*3)

        keys1 = sorted(halfWidthFont.Chars.keys())
        keys2 = sorted(fullWidthFont1.Chars.keys())
        keys3 = sorted(fullWidthFont2.Chars.keys())

        font1DataOffset = fnt.tell()
        for c in keys1:
            w(bytearray(halfWidthFont.Chars[c]))

        font2DataOffset = fnt.tell()
        for c in keys2:
            w(bytearray(fullWidthFont1.Chars[c]))

        font3DataOffset = fnt.tell()
        for c in keys3:
            w(bytearray(fullWidthFont2.Chars[c]))

        fnt.seek(8, 0)

        writeSection(w, 0, 0x4FF, 8, 13,
                     halfWidthFont.GlyphDataLength, font1DataOffset)

        writeSection(w, 0x3000, 0x9FFF, 16, 16,
                     fullWidthFont1.GlyphDataLength, font2DataOffset)

        writeSection(w, 0xF900, 0xFFFF, 16, 16,
                     fullWidthFont2.GlyphDataLength, font3DataOffset)


def writeSection(writer, codeStart, codeEnd, charWidth, charHeight, entrySize, dataOffset):
    # Code range
    writer(struct.pack('<HH', codeStart, codeEnd))
    # Char width
    writer(struct.pack('<B', charWidth))
    # Char height
    writer(struct.pack('<B', charHeight))
    # Glyph data lenght
    writer(struct.pack('<H', entrySize))
    writer(struct.pack('<I', dataOffset))


def compressGlyphBmp(bs, fltr):
    bits = 0
    rotate = 0
    result = []

    for i in range(len(bs)):
        b = bs[i]
        if (b >= fltr):
            bits |= 1 << rotate
        else:
            pass

        rotate += 1
        if(rotate >= 8):
            result.append(bits)
            rotate = 0
            bits = 0

    return result


def toImg(pixels1bpp, size):
    img = Image.new('RGBA', (size[0], size[1]))
    x = 0
    y = 0
    for bits in pixels1bpp:
        mask = 1
        while(mask < (1 << 8)):
            bit = bits & mask
            if(bit == mask):
                img.putpixel((x, y), (255, 255, 255, 255))
            mask <<= 1

            x += 1
            if(x == size[0]):
                x = 0
                y += 1

    return img


def glyphsToImg(path, glyphs, glyphSize, fltr):
    rows = len(glyphs) / 16 + 1
    img = Image.new('RGBA', (16*glyphSize[0], rows*glyphSize[1]))

    x = 0
    y = 0
    for g in glyphs:
        i = toImg(g, glyphSize)
        img.paste(i, (x*glyphSize[0], y*glyphSize[1]))

        x += 1
        if(x == 16):
            x = 0
            y += 1

    img.save(path)


if __name__ == "__main__":
    import argparse

    def parse_options():
        parser = argparse.ArgumentParser(
            description="Nintendo CTR Font Converter Text Filter(xllt) Generator.")
        parser.add_argument('-t', '--ttf', help="Set TrueType font file path.")
        parser.add_argument(
            '-d', '--bdf', help="Set Bitmap font file path for ascii chars.")
        parser.add_argument(
            '-s', '--size', help="Set font width.", nargs=2, type=int)
        parser.add_argument(
            '-f', '--files', help="Files to scan.", nargs='*', type=str)
        parser.add_argument(
            '-l', '--filter', help="Set bitmap grey filter.", default=90, type=int)
        parser.add_argument(
            '-p', '--padding', help="Set glyph padding.", default=3, type=int)
        parser.add_argument(
            '-b', '--baseline', help="Set baseline.", default=3, type=int)
        parser.add_argument('-o', '--output', help="Set output file path.")
        parser.add_argument(
            '-x', '--charset', help="Set raw charset path. If not set, the charset will not save.", default=None)
        parser.add_argument(
            '-i', '--image', help="Set image path. If not set, the image will not save.", default=False)
        parser.add_argument(
            '-a', '--ascii', help="Generate ASCII font.", action='store_true')
        parser.add_argument(
            '-u', '--unicode', help="Generate Unicode font.", action='store_true')
        parser.add_argument(
            '-r', '--binary', help="Generate Unicode font.", action='store_true')
        return parser.parse_args()

    def main():
        options = parse_options()
        if not options:
            return False

        if options.ascii:
            generateAsciiFont16(options.bdf, options.filter, options.padding,
                                options.baseline, options.output, options.image)
            return

        if options.unicode:
            generateUnicodeFont16(options.ttf, options.filter, options.padding,
                                  options.baseline, options.output, options.image)
            return

        if options.binary:
            generateBinaryFont16(options.ttf, options.bdf, options.filter, options.padding,
                                 options.baseline, options.output)
            return

        chars = scanFiles(options.files)
        if(options.charset):
            codecs.open(options.charset, 'w', 'utf-8').write(u''.join(chars))

        generateFont(options.ttf, options.size, chars, options.filter,
                     options.padding, options.baseline, options.output, options.image)

    main()
