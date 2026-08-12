"""High-confidence candidates for transient work narration in comments."""

import hashlib
from collections import Counter

import comment_extract as ce
from _markers import flag_comment


def _key(text, kind):
    value = f"{kind}\0{text}".encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()[:16]


def findings(text, file_ext):
    """Return extracted flagged rows as (key, line, text, kind)."""
    rows = []
    for line, value, kind in ce.extract(text, file_ext):
        if flag_comment(value, kind == ce.DOCSTRING):
            rows.append((_key(value, kind), line, value, kind))
    return rows


def finding_counts(text, file_ext, file_path=None):
    """Return stable, content-free identifiers for state attribution."""
    return dict(Counter(key for key, _, _, _ in findings(text, file_ext)))


def added(before, after, file_ext):
    """Return newly added flagged rows without treating existing rows as new."""
    before_counts = Counter(finding_counts(before, file_ext))
    remaining = Counter(finding_counts(after, file_ext)) - before_counts
    rows = []
    for row in findings(after, file_ext):
        key = row[0]
        if remaining[key] > 0:
            rows.append(row)
            remaining[key] -= 1
    return rows
