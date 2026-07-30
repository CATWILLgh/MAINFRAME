"""Project least-privilege credential guidance into staged releases."""

from __future__ import annotations

from pathlib import Path


SKILL_ROOTS = {
    "antigravity-2": "plugin/skills",
    "claude-code": "plugin/skills",
    "codex": "skills",
    "opencode": "skills",
}
PROJECTED_COMPONENTS = {"claude-code", "codex", "opencode"}
FORBIDDEN_GUIDANCE = (
    "auto-sourced from",
    "loaded into the shell environment by",
    "The store is sourced by",
    "source ~/.zshenv",
    "set -a",
    "The MAINFRAME configuration flow manages this line",
)
CURL_SOURCE = (
    "**Where tokens come from.** If "
    "[`secrets-handling`](../secrets-handling/SKILL.md) is active on this "
    "machine, generic API tokens live in "
    "`~/.config/credentials/secrets.env` and are loaded into the shell "
    "environment by `~/.zshenv`. The patterns below assume this — "
    "`$API_TOKEN` resolves because the store was sourced at shell start. If "
    "the token is in the store but not in the current shell env (e.g. just "
    "added via `secret set`), substitute inline: "
    "`$(secret get API_TOKEN)`. If `secrets-handling` is not active, treat "
    "the env-var examples as \"replace with whatever your project's "
    "credential source is\" (vault CLI, project `.env`, etc.) — the curl "
    "patterns themselves are agnostic."
)
CURL_REPLACEMENT = (
    "**Where tokens come from.** If "
    "[`secrets-handling`](../secrets-handling/SKILL.md) is active on this "
    "machine, generic API tokens live in "
    "`~/.config/credentials/secrets.env`. Use `$API_TOKEN` only when it is "
    "already present in the command environment; otherwise substitute it "
    "inline with `$(secret get API_TOKEN)`. If `secrets-handling` is not "
    "active, treat the env-var examples as \"replace with whatever your "
    "project's credential source is\" (vault CLI, project `.env`, etc.) — "
    "the curl patterns themselves are agnostic."
)
def project_release_secret_guidance(release_root: Path) -> None:
    targets = []
    for component, relative in SKILL_ROOTS.items():
        root = release_root / "bundles" / component / relative
        secret = root / "secrets-handling/SKILL.md"
        curl = root / "curl-requests/SKILL.md"
        targets.extend((secret, curl))
        if component not in PROJECTED_COMPONENTS:
            continue
        _write_projected(
            secret,
            _project_secret_skill(secret.read_text(encoding="utf-8")),
        )
        _write_projected(curl, _replace_once(
            curl.read_text(encoding="utf-8"),
            CURL_SOURCE,
            CURL_REPLACEMENT,
            f"{component} curl guidance",
        ))
    _validate_targets(targets)


def _project_secret_skill(text: str) -> str:
    return text


def _replace_once(text: str, source: str, replacement: str, label: str) -> str:
    if text.count(source) != 1:
        raise ValueError(f"release secret projection anchor drift: {label}")
    return text.replace(source, replacement)


def _write_projected(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _validate_targets(targets: list[Path]) -> None:
    if len(targets) != 8 or len(set(targets)) != 8:
        raise ValueError("release secret projection target set is incomplete")
    for target in targets:
        text = target.read_text(encoding="utf-8")
        if "$(secret get " not in text:
            raise ValueError(f"named secret guidance is missing: {target}")
        if any(phrase in text for phrase in FORBIDDEN_GUIDANCE):
            raise ValueError(f"global secret loading guidance remains: {target}")
