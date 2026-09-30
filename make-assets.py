#!/usr/bin/env python3
"""Из stickers/*.png делает иконки приложения и встроенные картинки в index.html.

  python3 make-assets.py

Пишет icons/icon-192.png, icon-512.png, icon-maskable.png и обновляет
блок «stickers» внутри <style> в index.html — картинки уезжают туда
как data:URI, чтобы одностраничная версия для артефакта тоже работала.

Зависимостей нет: PNG (RGBA, 8 бит, без чересстрочности) читается и
пишется вручную.
"""
import base64, pathlib, struct, sys, zlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "stickers"
ICONS = HERE / "icons"

ICON_BG = (234, 241, 255)      # светло-голубой под цвет стикеров


# ---------------------------------------------------------------- PNG чтение
def png_read(path):
    d = path.read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path}: не PNG")
    w = h = None
    idat = bytearray()
    i = 8
    while i < len(d):
        ln = struct.unpack(">I", d[i:i + 4])[0]
        tag = d[i + 4:i + 8]
        body = d[i + 8:i + 8 + ln]
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if (depth, ctype, inter) != (8, 6, 0):
                sys.exit(f"{path}: нужен RGBA 8 бит без чересстрочности")
        elif tag == b"IDAT":
            idat += body
        i += 12 + ln
    raw = zlib.decompress(bytes(idat))

    stride = w * 4
    out = bytearray(stride * h)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        if f == 1:
            for x in range(4, stride):
                line[x] = (line[x] + line[x - 4]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x - 4] if x >= 4 else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - 4] if x >= 4 else 0
                b = prev[x]
                c = prev[x - 4] if x >= 4 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        elif f != 0:
            sys.exit(f"{path}: неизвестный фильтр {f}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, out


def png_write(path, w, h, px):
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- обработка
def trim(w, h, px, thr=8):
    """Обрезает прозрачные поля вокруг стикера."""
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = y * w * 4
        for x in range(w):
            if px[row + x * 4 + 3] > thr:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 < 0:
        return w, h, px
    nw, nh = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        s = ((y + y0) * w + x0) * 4
        out[y * nw * 4:(y + 1) * nw * 4] = px[s:s + nw * 4]
    return nw, nh, out


def scale(w, h, px, nw, nh):
    """Усреднение по блоку — для уменьшения даёт чистый результат."""
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        sy0, sy1 = y * h // nh, max(y * h // nh + 1, (y + 1) * h // nh)
        for x in range(nw):
            sx0, sx1 = x * w // nw, max(x * w // nw + 1, (x + 1) * w // nw)
            r = g = b = a = n = 0
            for sy in range(sy0, sy1):
                base = sy * w * 4
                for sx in range(sx0, sx1):
                    i = base + sx * 4
                    al = px[i + 3]
                    r += px[i] * al; g += px[i + 1] * al; b += px[i + 2] * al
                    a += al; n += 1
            o = (y * nw + x) * 4
            if a:
                out[o] = r // a; out[o + 1] = g // a; out[o + 2] = b // a
            out[o + 3] = a // n
    return out


def fit(w, h, box):
    return (box, max(1, round(h * box / w))) if w >= h else (max(1, round(w * box / h)), box)


def on_background(w, h, px, size, share, bg):
    """Кладёт стикер на непрозрачный квадрат size×size."""
    tw, th = fit(w, h, round(size * share))
    s = scale(w, h, px, tw, th)
    out = bytearray()
    for _ in range(size * size):
        out += bytes((bg[0], bg[1], bg[2], 255))
    ox, oy = (size - tw) // 2, (size - th) // 2
    for y in range(th):
        for x in range(tw):
            i = (y * tw + x) * 4
            al = s[i + 3]
            if not al:
                continue
            o = ((y + oy) * size + (x + ox)) * 4
            for c in range(3):
                out[o + c] = (s[i + c] * al + out[o + c] * (255 - al)) // 255
    return out


# ---------------------------------------------------------------- сборка
INLINE = {"book": 96, "student": 160, "growth": 128, "sad": 160, "star": 96}

def main():
    ICONS.mkdir(exist_ok=True)
    cache = {}
    for name in sorted(set(list(INLINE) + ["book"])):
        w, h, px = png_read(SRC / f"{name}.png")
        cache[name] = trim(w, h, px)
        print(f"{name}: {w}×{h} → обрезано {cache[name][0]}×{cache[name][1]}")

    # иконки приложения
    bw, bh, bpx = cache["book"]
    for size, share, fname in ((192, .76, "icon-192.png"),
                               (512, .76, "icon-512.png"),
                               (512, .56, "icon-maskable.png")):
        png_write(ICONS / fname, size, size, on_background(bw, bh, bpx, size, share, ICON_BG))
        print("иконка", fname, (ICONS / fname).stat().st_size, "байт")

    # встраиваемые картинки
    css = ["/* === stickers: сгенерировано make-assets.py, не править руками === */",
           ".stk{background-repeat:no-repeat;background-position:center;background-size:contain;"
           "display:inline-block;flex:none}"]
    tmp = HERE / "_stk.png"
    for name, box in INLINE.items():
        w, h, px = cache[name]
        tw, th = fit(w, h, box)
        png_write(tmp, tw, th, scale(w, h, px, tw, th))
        b64 = base64.b64encode(tmp.read_bytes()).decode()
        css.append(f".stk-{name}{{background-image:url(data:image/png;base64,{b64})}}")
        print(f"стикер {name}: {tw}×{th}, {len(b64) // 1024} КБ base64")
    tmp.unlink()
    css.append("/* === /stickers === */")

    idx = HERE / "index.html"
    s = idx.read_text(encoding="utf-8")
    block = "\n".join(css)
    start = "/* === stickers: сгенерировано make-assets.py, не править руками === */"
    end = "/* === /stickers === */"
    if start in s:
        a = s.index(start); b = s.index(end) + len(end)
        s = s[:a] + block + s[b:]
    else:
        s = s.replace("*{box-sizing:border-box}", block + "\n\n*{box-sizing:border-box}", 1)
    idx.write_text(s, encoding="utf-8")
    print("index.html обновлён")


if __name__ == "__main__":
    main()
