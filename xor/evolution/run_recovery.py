"""XOR recovery. Same entry as evolution/run.py --circuit xor.

    python xor/evolution/run_recovery.py --bits 4
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evolution.run import main

if __name__ == "__main__":
    main("xor")
