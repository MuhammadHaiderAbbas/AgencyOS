import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from packages.tools.registry import execute_tool

@pytest.mark.asyncio
async def test_files_read_traversal_blocked(tmp_path):
    from packages.config.config import load_settings
    load_settings(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path/'t.sqlite3'}")
    try:
        res = await execute_tool("files.read", {"path": "../../etc/passwd"})
        # handler raises PermissionError which execute_tool propagates
        assert False, "should have raised"
    except PermissionError as e:
        assert "outside sandbox" in str(e)

@pytest.mark.asyncio
async def test_files_write_traversal_blocked(tmp_path):
    from packages.config.config import load_settings
    load_settings(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path/'t2.sqlite3'}")
    # absolute path is sandboxed to workspace/etc/passwd — ensures not writing to real /etc
    res = await execute_tool("files.write", {"path": "/etc/passwd", "content": "pwned"})
    assert res["result"]["path"] == "/etc/passwd"
    # verify file was written inside sandbox, not to real filesystem
    assert (tmp_path / "workspace" / "etc" / "passwd").exists()
    assert not Path("/etc/passwd").read_text().startswith("pwned") if Path("/etc/passwd").exists() else True
    # traversal that escapes should still be blocked
    try:
        await execute_tool("files.write", {"path": "../../etc/passwd", "content": "pwned2"})
        assert False, "should have raised PermissionError"
    except PermissionError:
        assert True
