PREFIX ?= /usr/local
DESTDIR ?=
LIBDIR ?= $(PREFIX)/lib
APP_ID := io.github.davidmakin.Drakelight
VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' drakelight/__init__.py)

ifeq ($(PREFIX),/usr)
UDEVDIR ?= /usr/lib/udev/rules.d
else
UDEVDIR ?= /etc/udev/rules.d
endif

RELEASE_DATE := $(shell date -u -d @$${SOURCE_DATE_EPOCH:-$$(date +%s)} +%F)
METAINFO := build/$(APP_ID).metainfo.xml

.PHONY: install uninstall dist test clean metainfo

metainfo:
	@mkdir -p build
	sed -e 's|@VERSION@|$(VERSION)|' -e 's|@DATE@|$(RELEASE_DATE)|' data/$(APP_ID).metainfo.xml > $(METAINFO)

install: metainfo
	install -d $(DESTDIR)$(LIBDIR)/drakelight
	cp -r drakelight $(DESTDIR)$(LIBDIR)/drakelight/
	find $(DESTDIR)$(LIBDIR)/drakelight -name __pycache__ -prune -exec rm -rf {} +
	install -d $(DESTDIR)$(PREFIX)/bin
	sed 's|@LIBDIR@|$(LIBDIR)|' packaging/drakelight.in > $(DESTDIR)$(PREFIX)/bin/drakelight
	chmod 755 $(DESTDIR)$(PREFIX)/bin/drakelight
	install -Dm644 data/$(APP_ID).desktop $(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop
	install -Dm644 data/$(APP_ID).svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	install -Dm644 $(METAINFO) $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	install -Dm644 drakelight/data/70-drakelight.rules $(DESTDIR)$(UDEVDIR)/70-drakelight.rules
	@echo "Installed. Update caches with: gtk-update-icon-cache -f $(PREFIX)/share/icons/hicolor; update-desktop-database; udevadm control --reload"

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR)/drakelight
	rm -f $(DESTDIR)$(PREFIX)/bin/drakelight
	rm -f $(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	rm -f $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	rm -f $(DESTDIR)$(UDEVDIR)/70-drakelight.rules

dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=drakelight-$(VERSION)/ -o dist/drakelight-$(VERSION).tar.gz HEAD

test:
	python3 -m pytest -q

clean:
	rm -rf build dist
