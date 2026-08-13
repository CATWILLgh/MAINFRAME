"""Atomic, expiring claims for low-stakes hook reminders."""

import hashlib
import os
import tempfile
import time


_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _root():
    return os.environ.get(
        "MAINFRAME_NOTICE_STATE_DIR",
        os.path.join(tempfile.gettempdir(), "mainframe-hook-notices"),
    )


def _cleanup(root):
    cutoff = time.time() - _MAX_AGE_SECONDS
    try:
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)
    except OSError:
        pass


def claim_once(topic, session_id, agent_id=None):
    """Return true once for a topic in one session and writer scope."""
    if not session_id:
        return False
    root = _root()
    os.makedirs(root, mode=0o700, exist_ok=True)
    _cleanup(root)
    signature = f"{topic}\0{session_id}\0{agent_id or 'main'}"
    path = os.path.join(root, hashlib.sha256(signature.encode()).hexdigest())
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    os.close(descriptor)
    return True
