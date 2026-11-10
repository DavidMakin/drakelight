"""K631 lighting: read-modify-write of config block C6 and colour block C8.

Layout verified against the official app's captured traffic (via
ahmad-bradii/Redragon_K631RGB-PRO_Setup) and a live read of this keyboard.
Every write is preceded by a backup and limited to a handful of changed bytes.
"""
import os
import time
from datetime import datetime

from .hidraw import DeviceError, Keyboard

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                          "drakelight")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")


def _migrate_config_dir():
    """Pre-release builds stored backups under ~/.config/redragon-k631; keep them."""
    old = os.path.join(os.path.dirname(CONFIG_DIR), "redragon-k631")
    if os.path.isdir(old) and not os.path.exists(CONFIG_DIR):
        try:
            os.rename(old, CONFIG_DIR)
        except OSError:
            pass


_migrate_config_dir()

BLOCK = 1032
OFF_SELF_DEFINE = 0x14
OFF_EFFECT = 0x15
OFF_PAIR = 0x26          # effect m: [OFF_PAIR + 2(m-1)] colour mode, [+1] speed<<4 | brightness
OFF_COLOUR = 0x1D        # effect m: 7 RGB slots at OFF_COLOUR + 21(m-1); slot 0 = single colour
COLOUR_RECORD = 21
EFFECTS = range(1, 21)   # 21 is per-key "self-define", not supported here
COLOUR_EFFECTS = {1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18, 19, 20}
COLOURFUL = 0x07
MAX_CHANGED = 3
WRITE_GAP = 0.06


NAMES = {
    1: "Fixed on", 2: "Respire", 3: "Rainbow", 4: "Flash away", 5: "Raindrops",
    6: "Rainbow wheel", 7: "Ripples shining", 8: "Stars twinkle", 9: "Shadow disappear",
    10: "Retro snake", 11: "Neon stream", 12: "Reaction", 13: "Sine wave",
    14: "Retinue scanning", 15: "Rotating windmill", 16: "Colorful waterfall",
    17: "Blossoming", 18: "Rotating storm", 19: "Collision", 20: "Perfect",
}


def effect_name(m):
    return NAMES.get(m, f"Effect {m}")


def validate(cfg):
    if len(cfg) != BLOCK or cfg[1] != 0x83 or cfg[2] != 0xC6:
        raise DeviceError(f"unexpected block header {bytes(cfg[:3]).hex(' ')}; refusing to write")
    if cfg[0x0E:0x10] != b"\x5a\xa5" or cfg[0x4E:0x50] != b"\x5a\xa5":
        raise DeviceError("config block markers missing; refusing to write")
    if not 1 <= cfg[OFF_EFFECT] <= 21:
        raise DeviceError(f"unexpected effect byte {cfg[OFF_EFFECT]:#x}; refusing to write")


def validate_colours(col):
    if len(col) != BLOCK or col[0] != 0x06 or col[1] != 0x88:
        raise DeviceError("colour block looks wrong; refusing to write")
    if all(b == 0 for b in col[8:]):
        raise DeviceError("colour block is empty; refusing to write")


class State:
    def __init__(self, config, colours):
        self.config = bytearray(config)
        self.colours = bytearray(colours)

    @property
    def effect(self):
        return self.config[OFF_EFFECT]

    def _pair(self, m):
        return OFF_PAIR + 2 * (m - 1)

    def speed(self, m=None):
        m = m or self.effect
        return self.config[self._pair(m) + 1] >> 4 if m in EFFECTS else None

    def brightness(self, m=None):
        m = m or self.effect
        return self.config[self._pair(m) + 1] & 0x0F if m in EFFECTS else None

    def colourful(self, m=None):
        m = m or self.effect
        return m in EFFECTS and self.config[self._pair(m)] == COLOURFUL

    def colour(self, m=None):
        m = m or self.effect
        if m not in COLOUR_EFFECTS or self.colourful(m):
            return None
        o = OFF_COLOUR + (m - 1) * COLOUR_RECORD
        return tuple(self.colours[o:o + 3])

    def as_dict(self):
        m = self.effect
        return {"effect": m, "name": effect_name(m), "speed": self.speed(),
                "brightness": self.brightness(), "colourful": self.colourful(),
                "colour": self.colour(), "has_colour": m in COLOUR_EFFECTS}


def backup(name, data):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = os.path.join(BACKUP_DIR, f"{stamp}-{name}.bin")
    with open(path, "xb") as f:
        f.write(data)
    return path


def read_state(kb):
    cfg = kb.read_page(0x83, 0xC6)
    validate(cfg)
    col = kb.read_page(0x88, 0xC8)
    validate_colours(col)
    return State(cfg, col)


def _changed(before, after):
    return [i for i in range(2, BLOCK) if before[i] != after[i]]


def _write_blocks(kb, cfg_before, cfg_after, col_before=None, col_after=None, limit=MAX_CHANGED):
    cfg_d = _changed(cfg_before, cfg_after)
    col_d = _changed(col_before, col_after) if col_after is not None else []
    if len(cfg_d) > limit or len(col_d) > limit:
        raise DeviceError("refusing to write: more bytes would change than expected")
    if col_d:
        col_after[1], col_after[2], col_after[3], col_after[4] = 0x08, 0xC8, 0x00, 0x40
        kb.write_page(0x08, 0xC8, 0x40, col_after[8:])
        time.sleep(WRITE_GAP)
    if cfg_d or col_d:
        kb.write_page(0x03, 0xC6, 0x00, cfg_after[8:])
        time.sleep(WRITE_GAP)


def apply(effect, colour=None, colourful=None, speed=None, brightness=None, kb=None):
    """Unspecified settings keep the keyboard's current values."""
    if effect not in EFFECTS:
        raise DeviceError("effect must be 1-20")
    if brightness is not None and not 0 <= brightness <= 4:
        raise DeviceError("brightness must be 0-4")
    if speed is not None and not 1 <= speed <= 4:
        raise DeviceError("speed must be 1-4")
    if (colour is not None or colourful) and effect not in COLOUR_EFFECTS:
        raise DeviceError("this effect has no colour setting")
    own = kb is None
    kb = kb or Keyboard()
    try:
        st = read_state(kb)
        backup("config", st.config)
        backup("colours", st.colours)
        cfg = bytearray(st.config)
        col = bytearray(st.colours)
        cfg[1] = 0x03
        cfg[OFF_SELF_DEFINE] = 0
        cfg[OFF_EFFECT] = effect
        i = OFF_PAIR + 2 * (effect - 1) + 1
        s = speed if speed is not None else cfg[i] >> 4
        b = brightness if brightness is not None else cfg[i] & 0x0F
        cfg[i] = (s << 4) | b
        if colourful:
            cfg[i - 1] = COLOURFUL
        elif colour is not None:
            cfg[i - 1] = 0x00
            o = OFF_COLOUR + (effect - 1) * COLOUR_RECORD
            col[o:o + 3] = bytes(colour)
        _write_blocks(kb, st.config[:1] + b"\x03" + st.config[2:], cfg, st.colours, col)
        return read_state(kb)
    finally:
        if own:
            kb.close()


def oldest_backup():
    try:
        files = sorted(os.listdir(BACKUP_DIR))
    except OSError:
        return None
    cfg = [f for f in files if f.endswith("-config.bin")]
    col = [f for f in files if f.endswith("-colours.bin")]
    if not cfg or not col:
        return None
    return os.path.join(BACKUP_DIR, cfg[0]), os.path.join(BACKUP_DIR, col[0])


def restore_first():
    """Restore the effect/speed/brightness/colour state from before first use."""
    pair = oldest_backup()
    if not pair:
        raise DeviceError("no backups found")
    with open(pair[0], "rb") as f:
        cfg0 = bytearray(f.read())
    with open(pair[1], "rb") as f:
        col0 = bytearray(f.read())
    validate(cfg0)
    validate_colours(col0)
    with Keyboard() as kb:
        cur = read_state(kb)
        cfg0[1] = 0x03
        _write_blocks(kb, bytes(cur.config[:1]) + b"\x03" + bytes(cur.config[2:]), cfg0,
                      cur.colours, col0, limit=BLOCK)
        return read_state(kb)
