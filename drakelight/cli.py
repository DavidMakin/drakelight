import argparse
import json

from . import __version__, lighting
from .hidraw import DeviceError, Keyboard


def _hex(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError("colour must be RRGGBB")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="drakelight")
    ap.add_argument("--version", action="version", version=f"drakelight {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("gui")
    sub.add_parser("check", help="verify the GTK 4 / libadwaita runtime imports")
    sub.add_parser("setup-access", help="install the udev rule (asks for your password)")
    sub.add_parser("status")
    sub.add_parser("effects")
    sub.add_parser("dump", help="read-only hex dump of config and colour pages")
    sub.add_parser("restore", help="restore lighting from the oldest backup")
    s = sub.add_parser("set")
    s.add_argument("-e", "--effect", type=int, required=True)
    s.add_argument("-c", "--colour", type=_hex)
    s.add_argument("--colourful", action="store_true")
    s.add_argument("-s", "--speed", type=int)
    s.add_argument("-b", "--brightness", type=int)
    a = ap.parse_args(argv)
    try:
        if a.cmd in (None, "gui"):
            try:
                from .gui_gtk import run
            except (ImportError, ValueError) as e:
                print(f"error: GTK 4 / libadwaita Python bindings missing ({e}). "
                      "Install python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1.")
                return 1
            return run()
        if a.cmd == "check":
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
            import cairo  # noqa: F401
            from gi.repository import Adw, Gtk
            print(f"ok: GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, "
                  f"libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}")
            return 0
        if a.cmd == "setup-access":
            from . import access
            access.install_rule()
            print("udev rule installed. Replug the keyboard if it is still not accessible.")
            return 0
        if a.cmd == "effects":
            for m in lighting.EFFECTS:
                print(f"{m:2d}  {lighting.effect_name(m)}"
                      f"{'  (colour)' if m in lighting.COLOUR_EFFECTS else ''}")
        elif a.cmd == "status":
            with Keyboard() as kb:
                print(json.dumps(lighting.read_state(kb).as_dict(), indent=2))
        elif a.cmd == "dump":
            with Keyboard() as kb:
                for name, cmd, page in (("config", 0x83, 0xC6), ("colours", 0x88, 0xC8)):
                    d = kb.read_page(cmd, page)
                    print(f"--- {name} ({len(d)} bytes)")
                    for i in range(0, 256, 16):
                        print(f"{i:04x}  {d[i:i + 16].hex(' ')}")
        elif a.cmd == "set":
            st = lighting.apply(a.effect, a.colour, a.colourful, a.speed, a.brightness)
            print(json.dumps(st.as_dict(), indent=2))
        elif a.cmd == "restore":
            print(json.dumps(lighting.restore_first().as_dict(), indent=2))
    except (DeviceError, RuntimeError) as e:
        print(f"error: {e}")
        return 1
