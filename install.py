"""Install the eczema MCP and write this computer's Cursor config.

Run from the project folder:

    py -3 install.py

On macOS or Linux:

    python3 install.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / ".cursor" / "mcp.json"
MIN_VERSION = (3, 11)


def write_cursor_config(root: Path, python: Path, dest: Path | None = None) -> Path:
    """Write .cursor/mcp.json using this machine's Python and project folder."""
    path = dest or (root / ".cursor" / "mcp.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "mcpServers": {
            "tcm-eczema": {
                "command": str(python),
                "args": ["-m", "tcm_eczema_mcp"],
                "cwd": str(root),
            }
        }
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    if sys.version_info < MIN_VERSION:
        major, minor = MIN_VERSION
        found = ".".join(str(part) for part in sys.version_info[:3])
        raise SystemExit(f"Python {major}.{minor} or newer is required. This interpreter is {found}.")
    print("Installing the eczema case-study server...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(ROOT)])
    config = write_cursor_config(ROOT, Path(sys.executable))
    print()
    print("Installed.")
    print(f"Cursor config written to {config}")
    print()
    print("Next:")
    print("1. Reload the Cursor window (Command Palette, then Developer: Reload Window).")
    print("2. Open a new Agent chat in this project.")
    print("3. Ask it to start an eczema case with the tcm-eczema tools.")
    print()
    print("Your cases stay in this folder under data/. Names and emails stay in data/private/.")


if __name__ == "__main__":
    main()
