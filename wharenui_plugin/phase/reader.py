"""Private-phase, plugin-owned read-only filesystem reader."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MAX_READ_BYTES = 64 * 1024
_ALLOWED_SUFFIXES = {".md", ".py"}
_EXCLUDED_NAMES = {"auth.json", "config.yaml"}
_EXCLUDED_DIRS = {"journal", "logs", "cache"}


def _package_root(name: str) -> Path | None:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError):
        return None
    if spec is None or not spec.origin or spec.origin in {"built-in", "frozen"}:
        return None
    return Path(spec.origin).resolve().parent


def derived_roots() -> tuple[Path, ...]:
    roots = [Path.home() / ".hermes" / "memories", Path.home() / ".hermes" / "SOUL.md"]
    for name in ("agent", "hermes_cli", "wharenui_plugin"):
        root = _package_root(name)
        if root is not None:
            roots.append(root)
    return tuple(root.resolve() for root in roots if root.exists())


def _inside(path: Path, root: Path) -> bool:
    try:
        if root.is_file():
            return path == root
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _excluded(path: Path) -> bool:
    if path.name in _EXCLUDED_NAMES or path.suffix == ".key":
        return True
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def read_private_file(raw_path: str, *, max_bytes: int = MAX_READ_BYTES) -> str:
    """Read one allowlisted Markdown/Python file on the current process filesystem."""
    if sys.platform != "linux":
        raise RuntimeError("private filesystem reader is POSIX/Linux-only until its path guard is ported")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("path is required")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    path = Path(raw_path).expanduser().resolve()
    if _excluded(path):
        raise PermissionError("path is excluded from private reads")
    if path.suffix not in _ALLOWED_SUFFIXES:
        raise PermissionError("only Markdown and Python files may be read")
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if not any(_inside(path, root) for root in derived_roots()):
        raise PermissionError("path is outside the private-read allowlist")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"file exceeds private-read cap of {max_bytes} bytes")
    return path.read_text(encoding="utf-8")


def handle_private_read(args=None, agent=None, **kwargs) -> str:
    phase = getattr(agent, "_phase", "public") if agent is not None else "public"
    if phase == "public":
        raise PermissionError("private filesystem reads are private-only")
    if args is None:
        args = kwargs
    if not isinstance(args, dict) or not isinstance(args.get("path"), str):
        raise ValueError("private_read requires a string 'path'")
    path = Path(args["path"]).expanduser().resolve()
    return json.dumps({"status": "success", "path": str(path), "content": read_private_file(args["path"])})
