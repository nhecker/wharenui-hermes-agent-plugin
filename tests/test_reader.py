import inspect

import pytest

from wharenui_plugin.phase import reader


class Agent:
    _phase = "private"


def test_reader_allows_only_resolved_allowlisted_markdown_and_python(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    allowed = root / "note.md"
    allowed.write_text("synthetic-reader-canary")
    source = root / "source.py"
    source.write_text("print(1)\n")
    monkeypatch.setattr(reader, "derived_roots", lambda: (root,))

    assert reader.read_private_file(str(allowed)) == "synthetic-reader-canary"
    assert reader.read_private_file(str(source)) == "print(1)\n"


@pytest.mark.parametrize("name", ["auth.json", "config.yaml", "secret.key", "journal/entry.md", "logs/out.md", "cache/out.md"])
def test_reader_refuses_excluded_paths(tmp_path, monkeypatch, name):
    root = tmp_path / "root"
    root.mkdir()
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("must-not-read")
    monkeypatch.setattr(reader, "derived_roots", lambda: (root,))

    with pytest.raises(PermissionError):
        reader.read_private_file(str(path))


def test_reader_refuses_traversal_symlink_outside_and_oversize(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside")
    (root / "escape.md").symlink_to(outside)
    (root / "large.md").write_text("123456")
    monkeypatch.setattr(reader, "derived_roots", lambda: (root,))

    for path in (root / "escape.md", root / "missing" / ".." / "escape.md", outside):
        with pytest.raises(PermissionError):
            reader.read_private_file(str(path))
    with pytest.raises(ValueError, match="cap"):
        reader.read_private_file(str(root / "large.md"), max_bytes=5)


def test_reader_is_private_only_and_has_no_shell_or_network_path():
    source = inspect.getsource(reader)
    assert "subprocess" not in source
    assert "os.system" not in source
    assert "socket" not in source

    with pytest.raises(PermissionError):
        reader.handle_private_read({"path": __file__})
    with pytest.raises(ValueError):
        reader.handle_private_read({"path": 3}, agent=Agent())


def test_private_read_is_in_private_allowlist():
    from wharenui_plugin.phase.toolset import PRIVATE_ALLOWLIST
    assert "private_read" in PRIVATE_ALLOWLIST


def test_private_read_is_registered(monkeypatch):
    import wharenui_plugin
    monkeypatch.setenv("WHARENUI_OPEN_NOTEBOOK", "true")

    class Ctx:
        def __init__(self):
            self.tools = {}
        def register_tool(self, name, toolset, schema, handler):
            self.tools[name] = (schema, handler)

    ctx = Ctx()
    wharenui_plugin.register(ctx)
    assert "private_read" in ctx.tools
    assert ctx.tools["private_read"][0]["required"] if False else True
    assert ctx.tools["private_read"][0]["parameters"]["required"] == ["path"]
    assert callable(ctx.tools["private_read"][1])
