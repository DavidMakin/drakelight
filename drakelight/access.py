"""One-shot udev rule install so the keyboard's hidraw node is usable without root."""
import os
import subprocess

RULE_SRC = os.path.join(os.path.dirname(__file__), "data", "70-drakelight.rules")
RULE_DEST = "/etc/udev/rules.d/70-drakelight.rules"
PACKAGED_RULES = ("/usr/lib/udev/rules.d/70-drakelight.rules", "/lib/udev/rules.d/70-drakelight.rules")


def install_rule():
    """Install the rule via pkexec. The rule is piped over stdin because AppImage mounts are not readable by root."""
    reload = "udevadm control --reload && udevadm trigger --subsystem-match=hidraw --action=change"
    if any(os.path.exists(p) for p in PACKAGED_RULES):
        rule, script = b"", reload
    else:
        with open(RULE_SRC, "rb") as f:
            rule = f.read()
        script = f"cat > {RULE_DEST} && chmod 644 {RULE_DEST} && {reload}"
    try:
        proc = subprocess.run(["pkexec", "sh", "-c", script], input=rule, capture_output=True, timeout=120)
    except FileNotFoundError:
        raise RuntimeError("pkexec not found; install the rule manually (see README)") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("timed out waiting for authentication") from None
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "authentication cancelled")
