"""K631 lighting: read-modify-write of config block C6 and colour block C8.

Layout verified against the official app's captured traffic (via
ahmad-bradii/Redragon_K631RGB-PRO_Setup) and a live read of this keyboard.
Every write is preceded by a backup and limited to a handful of changed bytes.
"""

import json
import os
import re
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from .hidraw import DeviceError, Keyboard

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "drakelight")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")

Buf = bytes | bytearray


def _migrate_config_dir() -> None:
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
OFF_PAIR = 0x26  # effect m: [OFF_PAIR + 2(m-1)] colour mode, [+1] speed<<4 | brightness
OFF_COLOUR = 0x1D  # effect m: 7 RGB slots at OFF_COLOUR + 21(m-1); slot 0 = single colour
COLOUR_RECORD = 21
EFFECTS = range(1, 21)  # 21 is per-key "self-define", not supported here
COLOUR_EFFECTS = {1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18, 19, 20}
COLOURFUL = 0x07
MAX_CHANGED = 3
WRITE_GAP = 0.06


NAMES = {
    1: "Fixed on",
    2: "Respire",
    3: "Rainbow",
    4: "Flash away",
    5: "Raindrops",
    6: "Rainbow wheel",
    7: "Ripples shining",
    8: "Stars twinkle",
    9: "Shadow disappear",
    10: "Retro snake",
    11: "Neon stream",
    12: "Reaction",
    13: "Sine wave",
    14: "Retinue scanning",
    15: "Rotating windmill",
    16: "Colorful waterfall",
    17: "Blossoming",
    18: "Rotating storm",
    19: "Collision",
    20: "Perfect",
}


def effect_name(m: int) -> str:
    return NAMES.get(m, f"Effect {m}")


def validate(cfg: Buf) -> None:
    if len(cfg) != BLOCK or cfg[1] != 0x83 or cfg[2] != 0xC6:
        raise DeviceError(f"unexpected block header {bytes(cfg[:3]).hex(' ')}; refusing to write")
    if cfg[0x0E:0x10] != b"\x5a\xa5" or cfg[0x4E:0x50] != b"\x5a\xa5":
        raise DeviceError("config block markers missing; refusing to write")
    if not 1 <= cfg[OFF_EFFECT] <= 21:
        raise DeviceError(f"unexpected effect byte {cfg[OFF_EFFECT]:#x}; refusing to write")


def validate_colours(col: Buf) -> None:
    if len(col) != BLOCK or col[1] != 0x88:
        raise DeviceError("colour block looks wrong; refusing to write")
    if all(b == 0 for b in col[8:]):
        raise DeviceError("colour block is empty; refusing to write")


class State:
    def __init__(self, config: Buf, colours: Buf) -> None:
        self.config = bytearray(config)
        self.colours = bytearray(colours)

    @property
    def effect(self) -> int:
        return self.config[OFF_EFFECT]

    def _pair(self, m: int) -> int:
        return OFF_PAIR + 2 * (m - 1)

    def speed(self, m: int | None = None) -> int | None:
        m = m or self.effect
        return self.config[self._pair(m) + 1] >> 4 if m in EFFECTS else None

    def brightness(self, m: int | None = None) -> int | None:
        m = m or self.effect
        return self.config[self._pair(m) + 1] & 0x0F if m in EFFECTS else None

    def colourful(self, m: int | None = None) -> bool:
        m = m or self.effect
        return m in EFFECTS and self.config[self._pair(m)] == COLOURFUL

    def colour(self, m: int | None = None) -> tuple[int, ...] | None:
        m = m or self.effect
        if m not in COLOUR_EFFECTS or self.colourful(m):
            return None
        o = OFF_COLOUR + (m - 1) * COLOUR_RECORD
        return tuple(self.colours[o : o + 3])

    def as_dict(self) -> dict[str, Any]:
        m = self.effect
        return {
            "effect": m,
            "name": effect_name(m),
            "speed": self.speed(),
            "brightness": self.brightness(),
            "colourful": self.colourful(),
            "colour": self.colour(),
            "has_colour": m in COLOUR_EFFECTS,
        }


def backup_pair(st: State) -> None:
    """Write the current blocks as one timestamped pair (UTC, so ordering survives clock and DST changes)."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    for name, data in (("config", st.config), ("colours", st.colours)):
        with open(os.path.join(BACKUP_DIR, f"{stamp}-{name}.bin"), "xb") as f:
            f.write(data)


def _legacy_oldest() -> tuple[str, str] | None:
    try:
        files = sorted(os.listdir(BACKUP_DIR))
    except OSError:
        return None
    cfg = [f for f in files if f.endswith("-config.bin")]
    col = [f for f in files if f.endswith("-colours.bin")]
    if not cfg or not col:
        return None
    return os.path.join(BACKUP_DIR, cfg[0]), os.path.join(BACKUP_DIR, col[0])


def _original_paths() -> tuple[str, ...]:
    return tuple(os.path.join(BACKUP_DIR, f"original-{n}.bin") for n in ("config", "colours")) + (
        os.path.join(BACKUP_DIR, "original.json"),
    )


def ensure_original(st: State, identity: str = "") -> None:
    """Keep one never-overwritten copy of the state from before the first save."""
    cfg_p, col_p, meta_p = _original_paths()
    if os.path.exists(cfg_p) and os.path.exists(col_p):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    legacy = _legacy_oldest()
    if legacy:
        with open(legacy[0], "rb") as f:
            cfg = f.read()
        with open(legacy[1], "rb") as f:
            col = f.read()
    else:
        cfg, col = bytes(st.config), bytes(st.colours)
    for path, data in ((cfg_p, cfg), (col_p, col)):
        with open(path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    with open(meta_p, "w") as f:
        json.dump({"device": identity}, f)


def oldest_backup() -> tuple[str, str] | None:
    cfg_p, col_p, _ = _original_paths()
    if os.path.exists(cfg_p) and os.path.exists(col_p):
        return cfg_p, col_p
    return _legacy_oldest()


def parse_hex(text: str) -> tuple[int, ...]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", text.strip())
    if not m:
        raise ValueError("colour must be RRGGBB")
    h = m.group(1)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def read_state(kb: Keyboard) -> State:
    cfg = kb.read_page(0x83, 0xC6)
    validate(cfg)
    col = kb.read_page(0x88, 0xC8)
    validate_colours(col)
    return State(cfg, col)


def _changed(before: Buf, after: Buf) -> list[int]:
    return [i for i in range(2, BLOCK) if before[i] != after[i]]


def _write_blocks(
    kb: Keyboard,
    cfg_before: Buf,
    cfg_after: Buf,
    col_before: Buf = b"",
    col_after: Buf | None = None,
    allowed: tuple[set[int], set[int]] | None = None,
) -> tuple[list[int], list[int]]:
    """Write changed blocks. At most MAX_CHANGED bytes per block may differ, unless `allowed` names the
    (config offsets, colour offsets) that are permitted to change."""
    cfg_d = _changed(cfg_before, cfg_after)
    col_d = _changed(col_before, col_after) if col_after is not None else []
    if allowed is None:
        too_many = len(cfg_d) > MAX_CHANGED or len(col_d) > MAX_CHANGED
    else:
        too_many = not set(cfg_d) <= allowed[0] or not set(col_d) <= allowed[1]
    if too_many:
        raise DeviceError("refusing to write: more bytes would change than expected")
    if col_d:
        kb.write_page(0x08, 0xC8, 0x40, cast(Buf, col_after)[8:])
        time.sleep(WRITE_GAP)
    if cfg_d or col_d:
        kb.write_page(0x03, 0xC6, 0x00, cfg_after[8:])
        time.sleep(WRITE_GAP)
    return cfg_d, col_d


def _read_back(kb: Keyboard, cfg_d: list[int], cfg_after: Buf, col_d: list[int], col_after: Buf) -> State:
    new = read_state(kb)
    if any(new.config[i] != cfg_after[i] for i in cfg_d) or any(new.colours[i] != col_after[i] for i in col_d):
        raise DeviceError("the keyboard did not keep the change; its settings may be unchanged")
    return new


def _check_colour(colour: Sequence[int] | None) -> None:
    if colour is not None and not (len(colour) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in colour)):
        raise DeviceError("colour must be three values from 0 to 255")


def apply(
    effect: int,
    colour: Sequence[int] | None = None,
    colourful: bool | None = None,
    speed: int | None = None,
    brightness: int | None = None,
    kb: Keyboard | None = None,
) -> State:
    """Unspecified settings keep the keyboard's current values."""
    if effect not in EFFECTS:
        raise DeviceError("effect must be 1-20")
    if brightness is not None and not 0 <= brightness <= 4:
        raise DeviceError("brightness must be 0-4")
    if speed is not None and not 1 <= speed <= 4:
        raise DeviceError("speed must be 1-4")
    _check_colour(colour)
    if (colour is not None or colourful) and effect not in COLOUR_EFFECTS:
        raise DeviceError("this effect has no colour setting")
    own = kb is None
    kb = kb or Keyboard()
    try:
        st = read_state(kb)
        ensure_original(st, getattr(kb, "identity", ""))
        backup_pair(st)
        if st.config[OFF_SELF_DEFINE]:
            # Leaving per-key mode is its own guarded write so the settings write stays within the byte limit.
            step = bytearray(st.config)
            step[OFF_SELF_DEFINE] = 0
            step[OFF_EFFECT] = effect
            cfg_d, _ = _write_blocks(kb, _as_write(st.config), step)
            st = _read_back(kb, cfg_d, step, [], b"")
        cfg = bytearray(st.config)
        col = bytearray(st.colours)
        cfg[OFF_EFFECT] = effect
        i = OFF_PAIR + 2 * (effect - 1) + 1
        s = speed if speed is not None else cfg[i] >> 4
        b = brightness if brightness is not None else cfg[i] & 0x0F
        cfg[i] = (s << 4) | b
        if colourful:
            cfg[i - 1] = COLOURFUL
        elif colour is not None:
            if cfg[i - 1] == COLOURFUL:
                cfg[i - 1] = 0x00
            o = OFF_COLOUR + (effect - 1) * COLOUR_RECORD
            col[o : o + 3] = bytes(colour)
        cfg_d, col_d = _write_blocks(kb, _as_write(st.config), cfg, st.colours, col)
        return _read_back(kb, cfg_d, cfg, col_d, col)
    finally:
        if own:
            kb.close()


def _as_write(config: Buf) -> bytes:
    """The write header differs from the read header only in byte 1, which is never compared."""
    return bytes(config[:1]) + b"\x03" + bytes(config[2:])


def restore_first() -> State:
    """Restore the lighting settings (effect, speed, brightness, colours) saved before the first save.

    Only the lighting offsets are copied from the backup, so other settings and any difference in the
    rest of the block are left as the keyboard has them.
    """
    pair = oldest_backup()
    if not pair:
        raise DeviceError("no backups found")
    with open(pair[0], "rb") as f:
        cfg0 = bytearray(f.read())
    with open(pair[1], "rb") as f:
        col0 = bytearray(f.read())
    validate(cfg0)
    validate_colours(col0)
    try:
        with open(_original_paths()[2]) as f:
            saved_device = json.load(f).get("device", "")
    except OSError, ValueError:
        saved_device = ""
    with Keyboard() as kb:
        if saved_device and kb.identity and saved_device != kb.identity:
            raise DeviceError(
                "this backup was taken from a keyboard on a different USB port; "
                "plug the keyboard into that port, or delete original.json in the backup folder"
            )
        cur = read_state(kb)
        backup_pair(cur)
        cfg = bytearray(cur.config)
        col = bytearray(cur.colours)
        cfg_ok = {OFF_SELF_DEFINE, OFF_EFFECT, *range(OFF_PAIR, OFF_PAIR + 2 * len(EFFECTS))}
        col_ok = set(range(OFF_COLOUR, OFF_COLOUR + COLOUR_RECORD * len(EFFECTS)))
        for i in cfg_ok:
            cfg[i] = cfg0[i]
        for i in col_ok:
            col[i] = col0[i]
        cfg_d, col_d = _write_blocks(kb, _as_write(cur.config), cfg, cur.colours, col, allowed=(cfg_ok, col_ok))
        return _read_back(kb, cfg_d, cfg, col_d, col)
