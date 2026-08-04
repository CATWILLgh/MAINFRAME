"""Strict parser for neutral agent capability contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml


_REQUIRED_FIELDS = frozenset(
    {
        "name",
        "description",
        "needs-repo-read",
        "needs-write",
        "needs-web",
        "needs-docs-lookup",
        "reasoning-tier",
        "background",
    }
)
_OPTIONAL_FIELDS = frozenset({"turn-budget", "method-skills"})
_KNOWN_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_BOOLEAN_FIELDS = (
    "needs-repo-read",
    "needs-write",
    "needs-web",
    "needs-docs-lookup",
    "background",
)
_REASONING_TIERS = ("light", "standard", "deep")
_KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class AgentContract:
    name: str
    description: str
    needs_repo_read: bool
    needs_write: bool
    needs_web: bool
    needs_docs_lookup: bool
    reasoning_tier: str
    background: bool
    turn_budget: int | None = None
    method_skills: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentSource:
    contract: AgentContract
    body: str


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _fail(source: str, message: str) -> ValueError:
    return ValueError(f"{source}: {message}")


def _load_frontmatter(text: str, source: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise _fail(source, "missing opening frontmatter delimiter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise _fail(source, "missing closing frontmatter delimiter")
    try:
        metadata = yaml.load(text[4:end], Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, ValueError) as error:
        raise _fail(source, f"invalid YAML frontmatter: {error}") from None
    if not isinstance(metadata, dict):
        raise _fail(source, "frontmatter must be a mapping")
    return metadata, text[end + 5 :]


def _validate_fields(metadata: dict, source: str) -> None:
    unknown = sorted(set(metadata) - _KNOWN_FIELDS, key=str)
    if unknown:
        label = "field" if len(unknown) == 1 else "fields"
        raise _fail(source, f"unknown {label}: {', '.join(map(str, unknown))}")
    missing = sorted(_REQUIRED_FIELDS - set(metadata))
    if missing:
        label = "field" if len(missing) == 1 else "fields"
        raise _fail(source, f"missing required {label}: {', '.join(missing)}")


def _validate_name(value: object, field: str, source: str) -> str:
    if not isinstance(value, str) or not _KEBAB_CASE.fullmatch(value):
        raise _fail(source, f"{field} must be a non-empty kebab-case string")
    return value


def _validate_methods(value: object, source: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _fail(source, "method-skills must be a list")
    if any(not isinstance(item, str) for item in value):
        raise _fail(source, "method-skills entries must be strings")
    if any(not _KEBAB_CASE.fullmatch(item) for item in value):
        raise _fail(source, "method-skills entries must be non-empty kebab-case names")
    return tuple(value)


def parse_agent_source(text: str, *, source: str = "<agent>") -> AgentSource:
    """Parse and validate one neutral agent source without modifying its body."""
    metadata, body = _load_frontmatter(text, source)
    _validate_fields(metadata, source)

    name = _validate_name(metadata["name"], "name", source)
    description = metadata["description"]
    if not isinstance(description, str) or not description.strip():
        raise _fail(source, "description must be a non-empty string")
    for field in _BOOLEAN_FIELDS:
        if type(metadata[field]) is not bool:
            raise _fail(source, f"{field} must be a boolean")
    tier = metadata["reasoning-tier"]
    if tier not in _REASONING_TIERS:
        raise _fail(
            source,
            "reasoning-tier must be one of: light, standard, deep",
        )
    budget = metadata.get("turn-budget")
    if "turn-budget" in metadata and type(budget) is not int:
        raise _fail(source, "turn-budget must be an integer")
    if budget is not None and budget <= 0:
        raise _fail(source, "turn-budget must be a positive integer")

    return AgentSource(
        contract=AgentContract(
            name=name,
            description=description,
            needs_repo_read=metadata["needs-repo-read"],
            needs_write=metadata["needs-write"],
            needs_web=metadata["needs-web"],
            needs_docs_lookup=metadata["needs-docs-lookup"],
            reasoning_tier=tier,
            background=metadata["background"],
            turn_budget=budget,
            method_skills=(
                _validate_methods(metadata["method-skills"], source)
                if "method-skills" in metadata
                else ()
            ),
        ),
        body=body,
    )
