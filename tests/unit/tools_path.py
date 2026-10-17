import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_validate() -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "kb.py"), "validate"], check=False
    ).returncode
