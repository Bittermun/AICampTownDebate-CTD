import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.prompting.rule_cards import load_rule_card, render_rule_view, resolve_rule_refs


def test_rule_card_load_and_render():
    rc = load_rule_card("configs/rule_cards/tournament_core_v1.yaml")
    assert rc.version == "tournament_core_v1"
    assert "R_BANKRUPTCY" in rc.rules
    refs = resolve_rule_refs(rc, ["R_BANKRUPTCY", "R_MISSING"])
    assert refs == ["R_BANKRUPTCY"]
    rendered = render_rule_view(rc, "deliberation_compact", max_rules=4, include_ids=True)
    assert "RULE_CARD_VERSION" in rendered
    assert "R_BANKRUPTCY" in rendered


if __name__ == "__main__":
    test_rule_card_load_and_render()
    print("test_prompt_rule_cards: PASS")
