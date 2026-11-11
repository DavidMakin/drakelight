import os

import pytest

from drakelight import lighting as L
from drakelight.hidraw import DeviceError, Keyboard


def make_config(effect=9, pair=0x14):
    b = bytearray(1032)
    b[0:3] = b"\x06\x83\xc6"
    b[0x0E:0x10] = b"\x5a\xa5"
    b[0x4E:0x50] = b"\x5a\xa5"
    b[L.OFF_EFFECT] = effect
    for m in range(1, 21):
        b[L.OFF_PAIR + 2 * (m - 1) + 1] = pair
    return b


def make_colours():
    b = bytearray(1032)
    b[0:3] = b"\x06\x88\x00"
    for i in range(8, 1032):
        b[i] = (i * 7) & 0xFF
    return b


class FakeKeyboard:
    def __init__(self, cfg=None, col=None):
        self.cfg = cfg if cfg is not None else make_config()
        self.col = col if col is not None else make_colours()
        self.writes = []
        self.events = []
        self.drop_writes = False
        self.identity = "usb-test/input1"

    def read_page(self, cmd, page):
        if (cmd, page) == (0x83, 0xC6):
            return bytes(self.cfg)
        if (cmd, page) == (0x88, 0xC8):
            return bytes(self.col)
        raise DeviceError("not allow-listed")

    def write_page(self, cmd, page, length, data):
        self.writes.append((cmd, page))
        files = sorted(os.listdir(L.BACKUP_DIR)) if os.path.isdir(L.BACKUP_DIR) else []
        self.events.append(("write", cmd, page, files))
        if self.drop_writes:
            return
        if (cmd, page) == (0x03, 0xC6):
            self.cfg[8:] = data
        elif (cmd, page) == (0x08, 0xC8):
            self.col[8:] = data

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


@pytest.fixture(autouse=True)
def tmp_backups(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(L, "WRITE_GAP", 0)


def test_validate_accepts_real_layout():
    L.validate(make_config())


def test_validate_rejects_firmware_code():
    fw = bytearray(1032)
    fw[0:3] = b"\x06\x83\xb6"
    fw[14:16] = b"\xf0\xa3"
    with pytest.raises(DeviceError):
        L.validate(fw)


def test_validate_rejects_missing_second_marker():
    cfg = make_config()
    cfg[0x4E] = 0
    with pytest.raises(DeviceError):
        L.validate(cfg)


def test_brightness_change_writes_one_byte_and_reads_back():
    kb = FakeKeyboard()
    before = bytes(kb.cfg)
    st = L.apply(9, brightness=2, kb=kb)
    assert st.brightness() == 2
    changed = [i for i in range(2, 1032) if before[i] != kb.cfg[i]]
    assert changed == [L.OFF_PAIR + 2 * 8 + 1]
    assert kb.writes == [(0x03, 0xC6)]


def test_colour_change_writes_colour_block_then_config():
    kb = FakeKeyboard()
    st = L.apply(9, colour=(1, 2, 3), kb=kb)
    assert st.colour() == (1, 2, 3)
    assert kb.writes == [(0x08, 0xC8), (0x03, 0xC6)]


def test_colourful_sets_mode_byte():
    kb = FakeKeyboard()
    st = L.apply(9, colourful=True, kb=kb)
    assert st.colourful()
    assert st.colour() is None


def test_effect_switch_clears_self_define_flag():
    cfg = make_config(effect=21)
    cfg[L.OFF_SELF_DEFINE] = 1
    kb = FakeKeyboard(cfg=cfg)
    st = L.apply(3, kb=kb)
    assert st.effect == 3 and kb.cfg[L.OFF_SELF_DEFINE] == 0


def test_no_write_when_nothing_changes():
    kb = FakeKeyboard()
    L.apply(9, kb=kb)
    assert kb.writes == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"effect": 0},
        {"effect": 21},
        {"effect": 9, "brightness": 5},
        {"effect": 9, "speed": 0},
        {"effect": 3, "colour": (1, 2, 3)},
    ],
)
def test_invalid_arguments_rejected_before_any_write(kwargs):
    kb = FakeKeyboard()
    with pytest.raises(DeviceError):
        L.apply(kb=kb, **kwargs)
    assert kb.writes == []


def test_write_guard_refuses_wide_changes():
    kb = FakeKeyboard()
    before = bytes(kb.cfg)
    after = bytearray(before)
    for i in range(100, 110):
        after[i] ^= 0xFF
    with pytest.raises(DeviceError):
        L._write_blocks(kb, before, after)
    assert kb.writes == []


def test_backup_exists_at_the_moment_of_the_first_write():
    kb = FakeKeyboard()
    L.apply(9, brightness=1, kb=kb)
    files = kb.events[0][3]
    assert any(n.endswith("-config.bin") for n in files) and any(n.endswith("-colours.bin") for n in files)
    assert "original-config.bin" in files and "original-colours.bin" in files


def test_original_backup_is_never_overwritten(tmp_path):
    kb = FakeKeyboard()
    first = bytes(kb.cfg)
    L.apply(9, brightness=1, kb=kb)
    L.apply(9, brightness=3, kb=kb)
    assert (tmp_path / "backups" / "original-config.bin").read_bytes() == first


@pytest.mark.parametrize("colour", [(1, 2), (1, 2, 3, 4), (256, 0, 0), (-1, 0, 0), ("a", 0, 0)])
def test_bad_colour_rejected_before_any_backup(colour, tmp_path):
    kb = FakeKeyboard()
    with pytest.raises(DeviceError):
        L.apply(9, colour=colour, kb=kb)
    assert kb.writes == [] and not (tmp_path / "backups").exists()


@pytest.mark.parametrize("text", ["-1-1-1", "+f+f+f", " fff ff", "1_2_3_", "ff00", "gg0000"])
def test_parse_hex_rejects_junk(text):
    with pytest.raises(ValueError):
        L.parse_hex(text)


def test_parse_hex_accepts_hash_and_case():
    assert L.parse_hex("#FF0080") == (255, 0, 128)


def test_read_back_mismatch_is_an_error():
    kb = FakeKeyboard()
    kb.drop_writes = True
    with pytest.raises(DeviceError, match="did not keep"):
        L.apply(9, brightness=2, kb=kb)


def test_leaving_per_key_mode_needs_two_guarded_writes():
    cfg = make_config(effect=21)
    cfg[L.OFF_SELF_DEFINE] = 1
    cfg[L.OFF_PAIR + 2 * 8] = L.COLOURFUL
    kb = FakeKeyboard(cfg=cfg)
    st = L.apply(9, colour=(5, 6, 7), speed=3, brightness=2, kb=kb)
    assert st.effect == 9 and st.colour() == (5, 6, 7) and st.speed() == 3 and st.brightness() == 2
    assert kb.cfg[L.OFF_SELF_DEFINE] == 0


def test_colour_keeps_unknown_mode_byte():
    cfg = make_config()
    cfg[L.OFF_PAIR + 2 * 8] = 0x03
    kb = FakeKeyboard(cfg=cfg)
    L.apply(9, colour=(1, 2, 3), kb=kb)
    assert kb.cfg[L.OFF_PAIR + 2 * 8] == 0x03


def test_restore_first_uses_oldest_backup(monkeypatch):
    kb = FakeKeyboard()
    L.apply(9, brightness=1, kb=kb)
    L.apply(9, brightness=3, kb=kb)
    monkeypatch.setattr(L, "Keyboard", lambda: kb)
    st = L.restore_first()
    assert st.brightness() == 4


def test_restore_copies_only_lighting_offsets(monkeypatch):
    kb = FakeKeyboard()
    L.apply(9, brightness=1, kb=kb)
    kb.cfg[0x200] = 0x42
    monkeypatch.setattr(L, "Keyboard", lambda: kb)
    L.restore_first()
    assert kb.cfg[0x200] == 0x42


def test_restore_backs_up_current_state_first(monkeypatch, tmp_path):
    kb = FakeKeyboard()
    L.apply(9, brightness=1, kb=kb)
    before = len(os.listdir(tmp_path / "backups"))
    monkeypatch.setattr(L, "Keyboard", lambda: kb)
    L.restore_first()
    assert len(os.listdir(tmp_path / "backups")) == before + 2


def test_restore_refuses_a_different_keyboard(monkeypatch):
    kb = FakeKeyboard()
    L.apply(9, brightness=1, kb=kb)
    kb.identity = "usb-other/input1"
    monkeypatch.setattr(L, "Keyboard", lambda: kb)
    with pytest.raises(DeviceError, match="different USB port"):
        L.restore_first()


def test_write_guard_allows_only_named_offsets():
    kb = FakeKeyboard()
    before = bytes(kb.cfg)
    after = bytearray(before)
    after[100] ^= 1
    with pytest.raises(DeviceError):
        L._write_blocks(kb, before, after, allowed=({101}, set()))
    assert kb.writes == []


def test_real_keyboard_refuses_bootloader_style_commands():
    kb = Keyboard.__new__(Keyboard)
    with pytest.raises(DeviceError):
        kb.read_page(0x75, 0xC6)
    with pytest.raises(DeviceError):
        kb.write_page(0x45, 0xC6, 0, bytes(1024))
    with pytest.raises(DeviceError):
        kb.write_page(0x03, 0xB6, 0, bytes(1024))
