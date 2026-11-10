"""hidraw feature-report access with a strict command allow-list.

Report 5 is shared with the Sinowealth ISP bootloader (0x75 jump-to-bootloader,
0x45 erase), so only the (cmd, page) pairs below are ever sent.
"""
import fcntl
import glob
import os
import time

VID, PID = 0x258A, 0x0049
CMD_LEN = 6
DATA_LEN = 1032

READ_REQUESTS = {(0x83, 0xC6), (0x88, 0xC8)}
WRITE_REQUESTS = {(0x03, 0xC6), (0x08, 0xC8)}


class DeviceError(Exception):
    pass


class AccessError(DeviceError):
    """The hidraw node exists but this user may not open it."""


def _ioc(nr, size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr


def find_device():
    want = f"HID_ID=0003:{VID:08X}:{PID:08X}"
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(path, "device/uevent")) as f:
                uevent = f.read()
        except OSError:
            continue
        if want in uevent and "/input1" in uevent:
            return "/dev/" + os.path.basename(path)
    raise DeviceError("Keyboard 258a:0049 not found. Plug it in via USB-C and switch to wired mode.")


class Keyboard:
    def __init__(self, path=None):
        self.path = path or find_device()
        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except PermissionError:
            raise AccessError(
                f"No permission to open {self.path}. "
                "Run `drakelight setup-access` once, then replug the keyboard.") from None

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def read_page(self, cmd, page):
        if (cmd, page) not in READ_REQUESTS:
            raise DeviceError(f"read {cmd:02x}/{page:02x} is not allow-listed")
        fcntl.ioctl(self.fd, _ioc(0x06, CMD_LEN), bytearray([0x05, cmd, page, 0, 0, 0]))
        time.sleep(0.02)
        buf = bytearray(DATA_LEN)
        buf[0] = 0x06
        fcntl.ioctl(self.fd, _ioc(0x07, DATA_LEN), buf)
        return bytes(buf)

    def write_page(self, cmd, page, length, data):
        if (cmd, page) not in WRITE_REQUESTS:
            raise DeviceError(f"write {cmd:02x}/{page:02x} is not allow-listed")
        if len(data) != DATA_LEN - 8:
            raise DeviceError("data must be exactly 1024 bytes")
        buf = bytearray([0x06, cmd, page, 0, length, 0, 0, 0]) + bytes(data)
        fcntl.ioctl(self.fd, _ioc(0x06, DATA_LEN), buf)
