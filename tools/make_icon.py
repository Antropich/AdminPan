"""Draws assets/icon.ico (crescent moon on black). Run: python tools/make_icon.py"""
from PIL import Image, ImageDraw

S = 1024
BG, MOON = (0, 0, 0, 255), (250, 228, 200, 255)


def draw():
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), S * 0.22, fill=255)
    base.paste(Image.new("RGBA", (S, S), BG), mask=m)
    r, c = S * 0.30, S / 2
    moon = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(moon)
    d.ellipse((c - r, c - r, c + r, c + r), fill=255)
    br = r * 0.82
    bx, by = c + r * 0.50, c - r * 0.22
    d.ellipse((bx - br, by - br, bx + br, by + br), fill=0)
    base.paste(Image.new("RGBA", (S, S), MOON), mask=moon)
    return base


if __name__ == "__main__":
    draw().save("assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
