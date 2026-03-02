"""Helpers for loading and rendering compact rule cards for prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import json

import yaml


@dataclass
class Rule:
    id: str
    text: str
    tags: List[str]
    priority: int


@dataclass
class RuleCard:
    version: str
    rules: Dict[str, Rule]
    prompt_views: Dict[str, List[str]]


def load_rule_card(path: str) -> RuleCard:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Rule card must be a mapping.")
    version = str(payload.get("version", "")).strip()
    if not version:
        raise ValueError("Rule card missing version.")
    raw_rules = payload.get("rules", [])
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("Rule card rules must be a non-empty list.")
    rules: Dict[str, Rule] = {}
    for row in raw_rules:
        if not isinstance(row, dict):
            raise ValueError("Each rule must be a mapping.")
        rid = str(row.get("id", "")).strip()
        txt = str(row.get("text", "")).strip()
        if not rid or not txt:
            raise ValueError(f"Invalid rule entry: {json.dumps(row)}")
        rules[rid] = Rule(
            id=rid,
            text=txt,
            tags=[str(x) for x in row.get("tags", [])] if isinstance(row.get("tags", []), list) else [],
            priority=int(row.get("priority", 99)),
        )
    raw_views = payload.get("prompt_views", {})
    if not isinstance(raw_views, dict):
        raise ValueError("prompt_views must be a mapping.")
    prompt_views: Dict[str, List[str]] = {}
    for k, v in raw_views.items():
        if not isinstance(v, list):
            raise ValueError(f"prompt view '{k}' must be a list.")
        prompt_views[str(k)] = [str(x) for x in v]
    return RuleCard(version=version, rules=rules, prompt_views=prompt_views)


def resolve_rule_refs(rule_card: RuleCard, ids: List[str]) -> List[str]:
    out: List[str] = []
    for rid in ids:
        if rid in rule_card.rules:
            out.append(rid)
    return out


def render_rule_view(
    rule_card: RuleCard,
    view_name: str,
    max_rules: int = 8,
    include_ids: bool = True,
) -> str:
    refs = rule_card.prompt_views.get(view_name, [])
    if not refs:
        return ""
    refs = resolve_rule_refs(rule_card, refs)[: max(1, int(max_rules))]
    lines = [f"RULE_CARD_VERSION: {rule_card.version}"]
    for rid in refs:
        rule = rule_card.rules[rid]
        if include_ids:
            lines.append(f"- {rid}: {rule.text}")
        else:
            lines.append(f"- {rule.text}")
    return "\n".join(lines)
