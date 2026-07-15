"""Validated source paths for the Antigravity 2.x builder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourcePath:
    path: Path
    resolved: Path
    label: str

    def read_bytes(self) -> bytes:
        return self.resolved.read_bytes()

    def read_text(self) -> str:
        return self.resolved.read_text()


class SourceBoundary:
    def __init__(self, repository: Path, root: Path) -> None:
        self.repository = repository.resolve(strict=True)
        self.root = root
        self.resolved_root = self._resolve_root()

    def files(self, pattern: str = "**/*") -> tuple[SourcePath, ...]:
        if self.resolved_root is None:
            return ()
        files = []
        for path in sorted(self.root.glob(pattern)):
            source = self._resolve(path)
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if source.resolved.is_file():
                files.append(source)
        return tuple(files)

    def directories(self) -> tuple[Path, ...]:
        if self.resolved_root is None:
            return ()
        directories = []
        for path in sorted(self.root.iterdir()):
            source = self._resolve(path)
            if source.resolved.is_dir():
                directories.append(source.path)
        return tuple(directories)

    def file(self, path: Path) -> SourcePath:
        source = self._resolve(path)
        if not source.resolved.is_file():
            raise self._error("invalid Antigravity source file", path)
        return source

    def label(self, path: Path) -> str:
        try:
            return path.relative_to(self.repository).as_posix()
        except ValueError:
            return path.name

    def _resolve_root(self) -> Path | None:
        if not self.root.exists() and not self.root.is_symlink():
            return None
        if self.root.is_symlink():
            raise self._error(
                "Antigravity source directory link is not allowed", self.root
            )
        try:
            resolved = self.root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise self._error(
                "invalid Antigravity source directory", self.root
            ) from None
        if not resolved.is_relative_to(self.repository):
            raise self._error("Antigravity source escapes repository", self.root)
        return resolved if resolved.is_dir() else None

    def _resolve(self, path: Path) -> SourcePath:
        if self.resolved_root is None:
            raise self._error("missing Antigravity source directory", self.root)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise self._error("invalid Antigravity source link", path) from None
        if not resolved.is_relative_to(self.repository):
            raise self._error("Antigravity source escapes repository", path)
        if not resolved.is_relative_to(self.resolved_root):
            raise self._error("Antigravity source escapes declared root", path)
        if path.is_symlink() and resolved.is_dir():
            raise self._error("Antigravity source directory link is not allowed", path)
        return SourcePath(path, resolved, self.label(path))

    def _error(self, reason: str, path: Path) -> ValueError:
        return ValueError(f"{reason}: {self.label(path)}")
