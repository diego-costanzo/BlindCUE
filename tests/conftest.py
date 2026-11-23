"""Keep the test run away from the user's real settings, autosave and app data.

Without this, tests that build a DeviceManager or a MainWindow read and write
the real QSettings (the registry on Windows, ~/.config/BlindCue on Linux) and
can find the real autosave: test_device_manager_swap_screen_b_onto_a, for
example, stored "HDMI-A-2" as the user's projector.

Loaded by pytest before any test module, so it is in place before the
program's modules import QSettings or compute their paths.
"""
from __future__ import annotations

import os
import tempfile

from PySide6 import QtCore

_SANDBOX = tempfile.mkdtemp(prefix="blindcue-tests-")

# Path.home() (autosave in ~/.config/blindcue) follows these variables.
for _var in ("HOME", "USERPROFILE"):
    os.environ[_var] = _SANDBOX

# QSettings("BlindCue", "BlindCue") uses the native format (the registry on
# Windows), which cannot be redirected: write an INI file in the sandbox.
_RealQSettings = QtCore.QSettings
_RealQSettings.setPath(_RealQSettings.Format.IniFormat, _RealQSettings.Scope.UserScope,
                       os.path.join(_SANDBOX, "settings"))


class _SandboxSettings(_RealQSettings):
    def __init__(self, *args, **kwargs):
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
            super().__init__(_RealQSettings.Format.IniFormat, _RealQSettings.Scope.UserScope,
                             args[0], args[1], *args[2:], **kwargs)
        else:
            super().__init__(*args, **kwargs)


QtCore.QSettings = _SandboxSettings
# Entering the show goes straight in, as before the readiness page (stage 1
# C2a step 7); tests/test_readiness.py turns the page on for itself.
_SandboxSettings("BlindCue", "BlindCue").setValue("live/readiness_check", False)
# App data (text-cue cache, logs) goes to Qt's separate test locations.
QtCore.QStandardPaths.setTestModeEnabled(True)
