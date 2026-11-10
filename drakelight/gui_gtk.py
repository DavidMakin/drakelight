"""GTK 4 / libadwaita GUI: an effect gallery with live animated tiles and a control bar."""
import json
import math
import os
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__, access, lighting, preview_fx  # noqa: E402
from .hidraw import AccessError, DeviceError, Keyboard, find_device  # noqa: E402

APP_ID = "io.github.davidmakin.Drakelight"
SETTINGS = os.path.join(lighting.CONFIG_DIR, "settings.json")

# 65% layout, row by row, key widths in units (16u wide).
LAYOUT = [
    [1] * 13 + [2, 1],
    [1.5] + [1] * 12 + [1.5, 1],
    [1.75] + [1] * 11 + [2.25, 1],
    [2.25] + [1] * 10 + [1.75, 1, 1],
    [1.25, 1.25, 1.25, 6.25, 1, 1, 1, 1, 1, 1],
]

SWATCHES = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0),
            (0, 255, 255), (0, 80, 255), (170, 0, 255), (255, 0, 200), (255, 255, 255)]
BRIGHT_LABELS = ["Off", "25%", "50%", "75%", "100%"]
SPEED_LABELS = {1: "Slow", 2: "Medium", 3: "Fast", 4: "Fastest"}
NO_SPEED = {1}

CSS = b"""
flowboxchild { border-radius: 14px; padding: 6px; }
flowboxchild:selected {
    background: alpha(@accent_bg_color, 0.22);
    outline: 2px solid @accent_bg_color;
    outline-offset: -2px;
}
.tile-name { font-weight: 600; font-size: 0.9em; }
.controls { padding: 16px; border-radius: 16px; }
.field-label { font-weight: 700; font-size: 0.85em; opacity: 0.75; }
.hint { opacity: 0.7; }
"""


def load_settings():
    try:
        with open(SETTINGS) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(d):
    try:
        os.makedirs(lighting.CONFIG_DIR, exist_ok=True)
        with open(SETTINGS, "w") as f:
            json.dump(d, f)
    except OSError:
        pass


def hex_of(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def draw_board(cr, w, h, effect, look, brightness, speed, t0):
    pad = 6
    units = 16
    unit = min((w - 2 * pad) / units, (h - 2 * pad) / 5)
    bw, bh = unit * units, unit * 5
    ox, oy = (w - bw) / 2, (h - bh) / 2
    cr.set_source_rgb(0.09, 0.1, 0.13)
    cr.rectangle(0, 0, w, h)
    cr.fill()
    gap = max(1.0, unit * 0.12)
    level = brightness / 4
    t = (time.monotonic() - t0) * preview_fx.SPEED.get(speed, 1.0)
    off = (0.15, 0.16, 0.2)
    idx = 0
    for r, row in enumerate(LAYOUT):
        x = 0.0
        for c, wd in enumerate(row):
            if brightness == 0:
                rgb = off
            else:
                lit = preview_fx.key_colour(effect, look, (x + wd / 2) / units, (r + 0.5) / 5,
                                            idx, r, c, t, len(row))
                rgb = tuple(off[i] * (1 - level * 0.6) + min(1.0, max(0.0, lit[i])) * level * 0.95
                            for i in range(3))
            cr.set_source_rgb(*rgb)
            cr.rectangle(ox + x * unit, oy + r * unit, wd * unit - gap, unit - gap)
            cr.fill()
            x += wd
            idx += 1


class Tile(Gtk.Box):
    def __init__(self, m, t0):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.m = m
        self.t0 = t0
        self.effect = m
        self.look = preview_fx.Look((255, 255, 255), False, [])
        self.brightness = 4
        self.speed = 2
        self.area = Gtk.DrawingArea(content_width=176, content_height=74)
        self.area.set_draw_func(self.draw)
        self.area.set_overflow(Gtk.Overflow.HIDDEN)
        self.area.add_css_class("card")
        name = Gtk.Label(label=lighting.effect_name(m), ellipsize=3)
        name.add_css_class("tile-name")
        self.append(self.area)
        self.append(name)

    def set_look(self, base, colourful, palette, brightness, speed):
        self.look = preview_fx.Look(base, colourful, palette)
        self.brightness, self.speed = brightness, speed
        self.area.queue_draw()

    @property
    def animated(self):
        return self.brightness > 0 and not (self.effect == 1 and not self.look.colourful)

    def draw(self, _a, cr, w, h):
        draw_board(cr, w, h, self.effect, self.look, self.brightness, self.speed, self.t0)


class Swatch(Gtk.DrawingArea):
    def __init__(self, rgb, on_pick, is_active):
        super().__init__(content_width=28, content_height=28, valign=Gtk.Align.CENTER)
        self.rgb = rgb
        self.is_active = is_active
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.set_draw_func(self.draw)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: on_pick(self.rgb))
        self.add_controller(click)
        self.set_tooltip_text(hex_of(rgb))

    def draw(self, _a, cr, w, h):
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 3
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgb(*(c / 255 for c in self.rgb))
        cr.fill()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.5)
        cr.set_line_width(1)
        cr.stroke()
        if self.is_active(self.rgb):
            cr.arc(cx, cy, r + 2.5, 0, 2 * math.pi)
            cr.set_source_rgba(0.95, 0.4, 0.05, 1)
            cr.set_line_width(2)
            cr.stroke()


def run_async(fn, done):
    def worker():
        try:
            res, err = fn(), None
        except (DeviceError, RuntimeError) as e:
            res, err = None, e
        except OSError as e:
            res, err = None, DeviceError(f"I/O error: {e}")
        GLib.idle_add(done, res, err)
    threading.Thread(target=worker, daemon=True).start()


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Redragon K631", default_width=960, default_height=800)
        self.state = None
        self.baseline = None
        self.busy = False
        self.updating = False
        self.effect_sel = 1
        self.t0 = time.monotonic()

        self.wtitle = Adw.WindowTitle(title="Redragon K631", subtitle="Looking for keyboard…")
        header = Adw.HeaderBar(title_widget=self.wtitle)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Re-read from keyboard")
        refresh.connect("clicked", lambda *_: self.reload())
        header.pack_start(refresh)

        menu = Gio.Menu()
        appearance = Gio.Menu()
        for label, val in (("Follow system", "system"), ("Light", "light"), ("Dark", "dark")):
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("app.theme", GLib.Variant("s", val))
            appearance.append_item(item)
        menu.append_section("Appearance", appearance)
        recovery = Gio.Menu()
        recovery.append("Restore original lighting…", "win.restore")
        menu.append_section("Recovery", recovery)
        about = Gio.Menu()
        about.append("About Drakelight", "win.about")
        menu.append_section(None, about)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text="Appearance and recovery"))
        restore = Gio.SimpleAction.new("restore", None)
        restore.connect("activate", self.on_restore)
        self.add_action(restore)
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)

        self.banner = Adw.Banner(revealed=False)
        self.banner.connect("button-clicked", self.on_enable_access)
        self.toasts = Adw.ToastOverlay(child=self.build())
        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        self.set_content(view)
        self.update_rows()
        self.update_dirty()
        GLib.timeout_add(80, self.tick)
        self.reload()

    def build(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                       margin_top=16, margin_bottom=20, margin_start=20, margin_end=20)

        heading = Gtk.Label(label="Effects", xalign=0)
        heading.add_css_class("title-3")
        sub = Gtk.Label(label="Previews are estimates of what each effect looks like on the keyboard.", xalign=0)
        sub.add_css_class("hint")
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        head.append(heading)
        head.append(sub)
        page.append(head)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                min_children_per_line=2, max_children_per_line=5,
                                row_spacing=4, column_spacing=4, activate_on_single_click=True,
                                valign=Gtk.Align.START)
        self.tiles = []
        for m in lighting.EFFECTS:
            tile = Tile(m, self.t0)
            self.flow.append(tile)
            self.tiles.append(tile)
        self.flow.connect("selected-children-changed", self.on_tile)
        scroller = Gtk.ScrolledWindow(child=self.flow, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        page.append(scroller)

        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        bar.add_css_class("card")
        bar.add_css_class("controls")

        crow = Gtk.Box(spacing=10)
        cl = Gtk.Label(label="COLOUR", xalign=0, width_chars=11)
        cl.add_css_class("field-label")
        crow.append(cl)
        self.colour_tools = Gtk.Box(spacing=8)
        for rgb in SWATCHES:
            self.colour_tools.append(Swatch(rgb, self.on_swatch, self.swatch_active))
        self.cbtn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=Gtk.Align.CENTER,
                                          tooltip_text="Custom colour")
        self.cbtn.connect("notify::rgba", self.on_colour)
        self.entry = Gtk.Entry(width_chars=8, max_length=7, valign=Gtk.Align.CENTER)
        self.entry.connect("activate", self.on_entry)
        self.entry.connect("notify::has-focus", lambda e, _p: None if e.has_focus() else self.on_entry(e))
        self.colour_tools.append(self.cbtn)
        self.colour_tools.append(self.entry)
        crow.append(self.colour_tools)
        self.colourful = Gtk.ToggleButton(label="Onboard colours", valign=Gtk.Align.CENTER,
                                          tooltip_text="Cycle through the keyboard's own colours")
        self.colourful.connect("toggled", self.on_colourful)
        crow.append(self.colourful)
        self.colour_hint = Gtk.Label(label="", xalign=0, hexpand=True)
        self.colour_hint.add_css_class("hint")
        crow.append(self.colour_hint)
        bar.append(crow)

        srow = Gtk.Box(spacing=24, homogeneous=True)
        self.bright_box, self.bright, self.bright_val = self.scale_field("BRIGHTNESS", 0, 4, BRIGHT_LABELS)
        self.speed_box, self.speed, self.speed_val = self.scale_field("SPEED", 1, 4, ["Slow", "", "", "Fast"])
        srow.append(self.bright_box)
        srow.append(self.speed_box)
        bar.append(srow)

        arow = Gtk.Box(spacing=8)
        self.dirty_label = Gtk.Label(label="", xalign=0, hexpand=True)
        self.dirty_label.add_css_class("hint")
        self.reload_btn = Gtk.Button(label="Discard changes")
        self.reload_btn.connect("clicked", lambda *_: self.reload())
        self.save_btn = Gtk.Button(label="Save to keyboard")
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self.on_save)
        arow.append(self.dirty_label)
        arow.append(self.reload_btn)
        arow.append(self.save_btn)
        bar.append(arow)
        page.append(bar)

        self.status = Gtk.Label(label="", xalign=0, wrap=True)
        self.status.add_css_class("hint")
        page.append(self.status)
        return page

    def scale_field(self, title, lo, hi, labels):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        top = Gtk.Box()
        name = Gtk.Label(label=title, xalign=0, hexpand=True)
        name.add_css_class("field-label")
        val = Gtk.Label(label="", xalign=1)
        val.add_css_class("hint")
        top.append(name)
        top.append(val)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        scale.set_draw_value(False)
        for i, label in zip(range(lo, hi + 1), labels):
            scale.add_mark(i, Gtk.PositionType.BOTTOM, label or None)
        scale.connect("value-changed", self.on_change)
        box.append(top)
        box.append(scale)
        return box, scale, val

    def tick(self):
        if self.is_active():
            for tile in self.tiles:
                if tile.animated:
                    tile.area.queue_draw()
        return True

    def selected_effect(self):
        return self.effect_sel

    def select_effect(self, m):
        self.updating = True
        self.effect_sel = m
        self.flow.select_child(self.tiles[m - 1].get_parent())
        self.updating = False

    def current_colour(self):
        c = self.cbtn.get_rgba()
        return (round(c.red * 255), round(c.green * 255), round(c.blue * 255))

    def set_colour(self, rgb):
        c = Gdk.RGBA()
        c.red, c.green, c.blue, c.alpha = rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, 1
        self.cbtn.set_rgba(c)
        self.entry.set_text(hex_of(rgb))

    def swatch_active(self, rgb):
        return (self.selected_effect() in lighting.COLOUR_EFFECTS and not self.colourful.get_active()
                and tuple(rgb) == self.current_colour())

    def snapshot(self):
        m = self.selected_effect()
        has_colour = m in lighting.COLOUR_EFFECTS
        cf = has_colour and self.colourful.get_active()
        return (m, cf, self.current_colour() if has_colour and not cf else None,
                int(self.bright.get_value()), int(self.speed.get_value()))

    @staticmethod
    def state_snapshot(st):
        m = st.effect
        if m not in lighting.EFFECTS:
            return None
        has_colour = m in lighting.COLOUR_EFFECTS
        cf = has_colour and st.colourful(m)
        return (m, cf, tuple(st.colour(m)) if has_colour and not cf else None, st.brightness(m), st.speed(m))

    def palette(self, m):
        if not self.state:
            return []
        o = lighting.OFF_COLOUR + (m - 1) * lighting.COLOUR_RECORD
        return [tuple(self.state.colours[o + 3 * i:o + 3 * i + 3]) for i in range(7)]

    def stored_look(self, m):
        st = self.state
        has_colour = m in lighting.COLOUR_EFFECTS
        o = lighting.OFF_COLOUR + (m - 1) * lighting.COLOUR_RECORD
        base = tuple(st.colours[o:o + 3]) if has_colour else (255, 255, 255)
        return base, has_colour and st.colourful(m), self.palette(m), st.brightness(m), max(1, st.speed(m))

    def refresh_tiles(self):
        if not self.state:
            return
        for tile in self.tiles:
            if tile.m != self.selected_effect():
                tile.set_look(*self.stored_look(tile.m))
        self.refresh_selected_tile()

    def refresh_selected_tile(self):
        m = self.selected_effect()
        has_colour = m in lighting.COLOUR_EFFECTS
        self.tiles[m - 1].set_look(self.current_colour() if has_colour else (255, 255, 255),
                                   has_colour and self.colourful.get_active(), self.palette(m),
                                   int(self.bright.get_value()), int(self.speed.get_value()))

    def populate(self, m):
        self.updating = True
        st = self.state
        has_colour = m in lighting.COLOUR_EFFECTS
        self.colourful.set_active(has_colour and st.colourful(m))
        self.bright.set_value(st.brightness(m))
        self.speed.set_value(max(1, st.speed(m)))
        o = lighting.OFF_COLOUR + (m - 1) * lighting.COLOUR_RECORD
        self.set_colour(tuple(st.colours[o:o + 3]) if has_colour else (255, 255, 255))
        self.updating = False
        self.refresh_all()

    def refresh_all(self):
        self.update_rows()
        self.refresh_tiles()
        self.update_dirty()

    def update_rows(self):
        m = self.selected_effect()
        has_colour = m in lighting.COLOUR_EFFECTS
        cf = self.colourful.get_active()
        self.colour_tools.set_visible(has_colour)
        self.colourful.set_visible(has_colour)
        self.colour_tools.set_sensitive(not cf)
        if not has_colour:
            self.colour_hint.set_text("This effect uses its own colours")
        elif cf:
            self.colour_hint.set_text("Using the keyboard's onboard colours")
        else:
            self.colour_hint.set_text("")
        b = int(self.bright.get_value())
        self.bright_val.set_text(BRIGHT_LABELS[b])
        uses_speed = m not in NO_SPEED
        self.speed_box.set_sensitive(uses_speed)
        self.speed_val.set_text(SPEED_LABELS[int(self.speed.get_value())] if uses_speed else "Not used by this effect")
        child = self.colour_tools.get_first_child()
        while child:
            if isinstance(child, Swatch):
                child.queue_draw()
            child = child.get_next_sibling()

    def update_dirty(self):
        dirty = self.state is not None and not self.busy and self.snapshot() != self.baseline
        self.save_btn.set_sensitive(dirty)
        self.reload_btn.set_sensitive(dirty)
        if self.state is None:
            self.dirty_label.set_text("")
        else:
            self.dirty_label.set_text("Unsaved changes" if dirty else "Everything is saved on the keyboard")

    def on_tile(self, flow):
        if self.updating or not self.state:
            return
        sel = flow.get_selected_children()
        if sel:
            m = sel[0].get_index() + 1
            if m != self.effect_sel:
                self.effect_sel = m
                self.populate(m)

    def on_swatch(self, rgb):
        if not self.state or self.selected_effect() not in lighting.COLOUR_EFFECTS:
            return
        self.updating = True
        self.set_colour(rgb)
        self.colourful.set_active(False)
        self.updating = False
        self.refresh_all()

    def on_colourful(self, *_):
        if not self.updating:
            self.refresh_all()

    def on_colour(self, *_):
        if self.updating:
            return
        self.entry.set_text(hex_of(self.current_colour()))
        self.updating = True
        self.colourful.set_active(False)
        self.updating = False
        self.refresh_all()

    def on_entry(self, entry):
        t = entry.get_text().strip().lstrip("#")
        try:
            if len(t) != 6:
                raise ValueError
            rgb = tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            entry.set_text(hex_of(self.current_colour()))
            return
        if rgb == self.current_colour():
            return
        self.on_swatch(rgb)

    def on_change(self, *_):
        if not self.updating:
            self.refresh_all()

    def set_busy(self, busy, text=""):
        self.busy = busy
        self.status.set_text(text)
        self.update_dirty()

    def run(self, fn, done, working):
        if self.busy:
            return
        self.set_busy(True, working)

        def finish(res, err):
            self.set_busy(False)
            if err:
                self.status.set_text(str(err))
                self.banner.set_title(str(err))
                self.banner.set_button_label("Enable access" if isinstance(err, AccessError) else None)
                self.banner.set_revealed(True)
                self.wtitle.set_subtitle("Keyboard not available")
            else:
                self.banner.set_revealed(False)
                done(res)
        run_async(fn, finish)

    def load_state(self, st):
        self.state = st
        self.baseline = self.state_snapshot(st)
        try:
            dev = find_device()
            self.wtitle.set_subtitle(f"Wired · {dev}")
        except DeviceError:
            pass
        m = st.effect if st.effect in lighting.EFFECTS else 1
        self.select_effect(m)
        self.populate(m)
        if st.effect not in lighting.EFFECTS:
            self.status.set_text("Keyboard is in per-key mode; saving an effect leaves it.")

    def reload(self):
        def rd():
            with Keyboard() as kb:
                return lighting.read_state(kb)
        self.run(rd, self.load_state, "Reading keyboard…")

    def on_enable_access(self, *_):
        def fix():
            access.install_rule()
            time.sleep(1)

        def done(_res, err):
            if err:
                self.toasts.add_toast(Adw.Toast(title=f"Could not enable access: {err}"))
            else:
                self.reload()
        run_async(fix, done)

    def on_save(self, *_):
        m, cf, colour, b, sp = self.snapshot()
        args = dict(effect=m, speed=sp, brightness=b, colour=colour, colourful=cf)

        def done(st):
            self.load_state(st)
            self.toasts.add_toast(Adw.Toast(title="Saved to keyboard"))
        self.run(lambda: lighting.apply(**args), done, "Saving…")

    def on_about(self, *_):
        Adw.AboutDialog(
            application_name="Drakelight", application_icon=APP_ID, version=__version__,
            developer_name="David Makin", website="https://github.com/DavidMakin/drakelight",
            issue_url="https://github.com/DavidMakin/drakelight/issues", license_type=Gtk.License.MIT_X11,
            comments="Keyboard lighting control for the Redragon K631. Unofficial and not affiliated with Redragon.",
        ).present(self)

    def on_restore(self, *_):
        dlg = Adw.AlertDialog(
            heading="Restore original lighting?",
            body="This writes back the lighting settings backed up before this app first saved. "
                 "For a full factory reset, hold Fn + Esc for 3 seconds on the keyboard itself.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("restore", "Restore")
        dlg.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)

        def answered(d, resp):
            if resp == "restore":
                def done(st):
                    self.load_state(st)
                    self.toasts.add_toast(Adw.Toast(title="Original lighting restored"))
                self.run(lighting.restore_first, done, "Restoring…")
        dlg.connect("response", answered)
        dlg.present(self)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    SCHEMES = {"system": Adw.ColorScheme.DEFAULT, "light": Adw.ColorScheme.FORCE_LIGHT,
               "dark": Adw.ColorScheme.FORCE_DARK}

    def set_theme(self, action, value):
        name = value.get_string()
        if name not in self.SCHEMES:
            name = "system"
        action.set_state(GLib.Variant("s", name))
        Adw.StyleManager.get_default().set_color_scheme(self.SCHEMES[name])
        cfg = load_settings()
        cfg["theme"] = name
        save_settings(cfg)

    def do_activate(self):
        if not self.lookup_action("theme"):
            saved = load_settings().get("theme", "system")
            act = Gio.SimpleAction.new_stateful("theme", GLib.VariantType.new("s"), GLib.Variant("s", "system"))
            act.connect("change-state", self.set_theme)
            self.add_action(act)
            act.change_state(GLib.Variant("s", saved))
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        (self.props.active_window or Window(self)).present()


def run():
    return App().run(sys.argv[:1])
