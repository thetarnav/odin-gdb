# GDB auto-load shim: when ./main.bin loads, GDB sources this file
# (requires `add-auto-load-safe-path` for the project dir, see readme.md).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import odin  # noqa: F401  (registration happens on import)
