"""Approximate per-key look of each onboard effect, for the GUI preview only.

These are estimates of what the keyboard does, not a reproduction of its firmware.
key_colour() returns an (r, g, b) tuple in 0..1 for one key at time t.
"""
import colorsys
import math

SPEED = {1: 0.6, 2: 1.0, 3: 1.5, 4: 2.2}
TAU = 2 * math.pi


def rnd(a, b=0):
    n = (a * 374761393 + b * 668265263 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def hsv(h, s=1.0, v=1.0):
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


def scale(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def lerp(a, b, f):
    return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))


class Look:
    """base: (r,g,b) 0..255 single colour; palette: list of 0..255 colours used when colourful."""

    def __init__(self, base, colourful, palette):
        self.base = tuple(c / 255 for c in base)
        self.colourful = colourful and bool(palette)
        self.pal = [tuple(c / 255 for c in p) for p in palette] or [self.base]

    def at(self, u, smooth=False):
        if not self.colourful:
            return self.base
        n = len(self.pal)
        if not smooth:
            return self.pal[int(math.floor(u)) % n]
        i = int(math.floor(u))
        return lerp(self.pal[i % n], self.pal[(i + 1) % n], u - i)


def angle(x, y):
    return math.atan2((y - 0.5), (x - 0.5) * 3.2) / TAU


def dist(x, y, cx=0.5, cy=0.5):
    return math.hypot((x - cx) * 3.2, (y - cy)) / 1.9


def key_colour(effect, look, x, y, idx, row, col, t, ncols=15):
    """x, y in 0..1 across the board; idx unique key id; t already speed-scaled."""
    if effect == 1:
        return look.at(t * 0.3, True)
    if effect == 2:
        k = 0.5 - 0.5 * math.cos(t * 2.0)
        return scale(look.at(t / math.pi), k)
    if effect == 3:
        return hsv(x * 0.9 - t * 0.15)
    if effect == 4:
        ph = (t * 0.5) % 1.4
        d = ph - x
        k = max(0.0, 1 - d * 2.2) if 0 <= d < 0.45 else 0.0
        return scale(look.at(t * 0.5 / 1.4), k)
    if effect == 5:
        local = (t / 3.0 + rnd(idx)) % 1
        k = math.exp(-local * 9) if local < 0.5 else 0.0
        return scale(look.at(rnd(idx, int(t / 3.0 + rnd(idx))) * 7), k)
    if effect == 6:
        return hsv(angle(x, y) + t * 0.2)
    if effect == 7:
        e = int(t / 2.5)
        cx, cy = 0.15 + 0.7 * rnd(e, 1), 0.2 + 0.6 * rnd(e, 2)
        wave = (t % 2.5) * 0.4
        k = max(0.0, 1 - abs(dist(x, y, cx, cy) - wave) * 7) * max(0.0, 1 - (t % 2.5) / 2.5)
        return scale(look.at(e), k)
    if effect == 8:
        local = (t * 0.6 + rnd(idx) * 10) % 3
        k = math.sin(math.pi * local) if local < 1 else 0.0
        return scale(look.at(rnd(idx, int(t * 0.2)) * 7), k)
    if effect == 9:
        band = abs((x + y * 0.4) - (t * 0.5 % 1.6))
        k = 0.08 + 0.92 * min(1.0, band / 0.2)
        return scale(look.at(t * 0.1), k)
    if effect == 10:
        pos = row * ncols + (col if row % 2 == 0 else ncols - 1 - col)
        total = 5 * ncols
        behind = ((t * 12) - pos) % total
        k = max(0.0, 1 - behind / 10) if behind < 10 else 0.0
        return scale(look.at(t / 6), k)
    if effect == 11:
        return look.at(x * 3 - t * 0.8, True)
    if effect == 12:
        local = (t + rnd(idx, 1) * 30) % 12
        k = 0.07 + (math.exp(-local * 4) if local < 1.5 else 0.0)
        return scale(look.at(rnd(idx, int(t / 12 + rnd(idx, 1))) * 7), min(1.0, k))
    if effect == 13:
        k = 0.5 + 0.5 * math.sin(TAU * (x * 1.5 - t * 0.4) + y * 1.2)
        return scale(look.at(t * 0.05), k)
    if effect == 14:
        s = abs((t * 0.5) % 2 - 1)
        return scale(look.at(t * 0.25), max(0.0, 1 - abs(x - s) * 7))
    if effect == 15:
        a = angle(x, y)
        k = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(a * TAU * 3 - t * 2))
        return scale(hsv(a + t * 0.1), k)
    if effect == 16:
        return hsv(y * 0.8 - t * 0.35 + rnd(col) * 0.3)
    if effect == 17:
        r = dist(x, y)
        return scale(hsv(r * 1.2 - t * 0.3), 0.6 + 0.4 * math.sin(r * 8 - t * 3))
    if effect == 18:
        u = angle(x, y) * 2 + dist(x, y) * 2 - t * 0.6
        return scale(look.at(u * 3.5, True), 0.35 + 0.65 * (0.5 + 0.5 * math.sin(u * TAU)))
    if effect == 19:
        ph = (t * 0.7) % 1
        xl, xr = ph * 0.5, 1 - ph * 0.5
        k = max(0.0, 1 - abs(x - xl) * 6) + max(0.0, 1 - abs(x - xr) * 6)
        k += max(0.0, (ph - 0.9) * 10) * 0.6 if ph > 0.9 else 0.0
        return scale(look.at(int(t * 0.7)), min(1.0, k))
    if effect == 20:
        return scale(look.at(int(t * 0.75)), 1.0 if (t * 1.5) % 2 < 1 else 0.12)
    return look.base
