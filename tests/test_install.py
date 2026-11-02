import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from install import write_cursor_config


def test_cursor_config_uses_this_machine_paths(tmp_path: Path) -> None:
    root = tmp_path / "tcmdiagnosticmcp"
    python = tmp_path / "python"
    dest = write_cursor_config(root, python, dest=tmp_path / "mcp.json")
    saved = json.loads(dest.read_text(encoding="utf-8"))
    server = saved["mcpServers"]["tcm-eczema"]
    assert server["command"] == str(python)
    assert server["args"] == ["-m", "tcm_eczema_mcp"]
    assert server["cwd"] == str(root)
