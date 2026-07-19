#!/usr/bin/env python3
"""Native atomic rename bindings for supported bundle-builder platforms."""

from __future__ import annotations

import ctypes
import os
import sys


_DARWIN_RENAME_EXCL = 0x00000004
_DARWIN_RENAME_SWAP = 0x00000002
_LINUX_RENAME_NOREPLACE = 1
_LINUX_RENAME_EXCHANGE = 2


class NativeRename:
    def __init__(self) -> None:
        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            name = "renameatx_np"
            self._exclusive = _DARWIN_RENAME_EXCL
            self._exchange = _DARWIN_RENAME_SWAP
        elif sys.platform.startswith("linux"):
            name = "renameat2"
            self._exclusive = _LINUX_RENAME_NOREPLACE
            self._exchange = _LINUX_RENAME_EXCHANGE
        else:
            raise RuntimeError(f"bundle publication is unsupported on {sys.platform}")
        try:
            function = getattr(library, name)
        except AttributeError as error:
            raise RuntimeError(f"native {name} is unavailable") from error
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_int
        self.function = function

    def no_replace(self, parent_fd: int, source: str, target: str) -> None:
        self._call(parent_fd, source, target, self._exclusive)

    def exchange(self, parent_fd: int, source: str, target: str) -> None:
        self._call(parent_fd, source, target, self._exchange)

    def _call(self, parent_fd: int, source: str, target: str, flag: int) -> None:
        ctypes.set_errno(0)
        result = self.function(
            parent_fd,
            os.fsencode(source),
            parent_fd,
            os.fsencode(target),
            flag,
        )
        if result == -1:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number), f"{source} -> {target}")
