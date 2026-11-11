import os
import sys
import tempfile

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="drakelight-test-")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from drakelight import hidraw  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_keyboard(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("tests must use a fake keyboard, never a real device")

    monkeypatch.setattr(hidraw.Keyboard, "__init__", refuse)
