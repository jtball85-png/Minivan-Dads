from brain.governance import (
    BRAIN_DECIDES,
    CEO_REQUIRED,
    apply_governance,
    enforce_tier,
    parse_decision_blocks,
)

CLEAN_BLOCK = """#### Decision: Approve a new sticker design
- Recommendation: Ship the sticker as-is.
- Checklist: money=no, brand=no, legal=no, irreversible=no
- Tag: [BRAIN DECIDES]
"""

CHECKLIST_YES_BLOCK = """#### Decision: Increase ad budget
- Recommendation: Raise the weekly ad budget by $20.
- Checklist: money=yes, brand=no, legal=no, irreversible=no
- Tag: [BRAIN DECIDES]
"""

KEYWORD_ONLY_BLOCK = """#### Decision: File the trademark
- Recommendation: Proceed with the Class 25 trademark filing.
- Checklist: money=no, brand=no, legal=no, irreversible=no
- Tag: [BRAIN DECIDES]
"""

MALFORMED_BLOCK = """#### Decision: Something vague
- Recommendation: do a thing
"""

BOTH_MECHANISMS_BLOCK = """#### Decision: Rebrand and raise ad spend
- Recommendation: Change the brand name and raise ad budget by $50.
- Checklist: money=yes, brand=yes, legal=no, irreversible=no
- Tag: [BRAIN DECIDES]
"""


def test_clean_block_passes_through_unmodified():
    parsed = parse_decision_blocks(CLEAN_BLOCK)[0]
    enforced = enforce_tier(parsed)

    assert enforced.final_tag == BRAIN_DECIDES
    assert enforced.upgraded is False

    corrected, _ = apply_governance(CLEAN_BLOCK)
    assert corrected == CLEAN_BLOCK


def test_checklist_yes_forces_upgrade():
    parsed = parse_decision_blocks(CHECKLIST_YES_BLOCK)[0]
    enforced = enforce_tier(parsed)

    assert enforced.final_tag == CEO_REQUIRED
    assert enforced.upgraded is True
    assert any("checklist" in r for r in enforced.reasons)


def test_keyword_match_forces_upgrade_even_with_checklist_all_no():
    parsed = parse_decision_blocks(KEYWORD_ONLY_BLOCK)[0]
    enforced = enforce_tier(parsed)

    assert enforced.final_tag == CEO_REQUIRED
    assert enforced.upgraded is True
    assert any("keyword" in r for r in enforced.reasons)


def test_malformed_block_defaults_to_ceo_required_fail_safe():
    parsed = parse_decision_blocks(MALFORMED_BLOCK)[0]
    assert parsed.well_formed is False

    enforced = enforce_tier(parsed)

    assert enforced.final_tag == CEO_REQUIRED
    assert enforced.upgraded is True


def test_apply_governance_writes_corrected_tag_into_markdown():
    corrected, results = apply_governance(CHECKLIST_YES_BLOCK)

    assert "[CEO REQUIRED]" in corrected
    assert "[BRAIN DECIDES]" not in corrected
    assert "auto-upgraded" in corrected
    assert results[0].final_tag == CEO_REQUIRED


def test_upgrade_reasons_are_additive_when_both_mechanisms_fire():
    parsed = parse_decision_blocks(BOTH_MECHANISMS_BLOCK)[0]
    enforced = enforce_tier(parsed)

    assert enforced.upgraded is True
    assert len(enforced.reasons) == 2
    assert any("checklist" in r for r in enforced.reasons)
    assert any("keyword" in r for r in enforced.reasons)


def _block(title: str, recommendation: str) -> str:
    return (
        f"#### Decision: {title}\n"
        f"- Recommendation: {recommendation}\n"
        f"- Checklist: money=no, brand=no, legal=no, irreversible=no\n"
        f"- Tag: [BRAIN DECIDES]\n"
    )


def test_tier_change_keywords_force_upgrade():
    block = _block(
        "Promote market_intel",
        "Promote the department to Tier 2 given six weeks of clean reports.",
    )
    enforced = enforce_tier(parse_decision_blocks(block)[0])
    assert enforced.final_tag == CEO_REQUIRED
    assert any("tier_change" in r for r in enforced.reasons)


def test_publish_and_account_creation_keywords_force_upgrade():
    for rec in (
        "Publish the launch post directly to Instagram.",
        "Create a TikTok Shop account for the brand.",
    ):
        enforced = enforce_tier(parse_decision_blocks(_block("External action", rec))[0])
        assert enforced.final_tag == CEO_REQUIRED, rec


def test_bare_logo_and_pricing_keywords_force_upgrade():
    for rec in (
        "Update the logo colorway for the fall drop.",
        "Set the tee price at $24 for the launch window.",
    ):
        enforced = enforce_tier(parse_decision_blocks(_block("Brand tweak", rec))[0])
        assert enforced.final_tag == CEO_REQUIRED, rec


def test_ordinary_operational_prose_does_not_false_positive():
    # Real phrasing from the W29 acceptance-test agenda — must stay BRAIN DECIDES.
    block = _block(
        "Expand market_intel standing watch list",
        "Approve adding Amazon Merch and TikTok Shop to the watch list; "
        "expanding scope addresses staling data directly with no cost or risk.",
    )
    enforced = enforce_tier(parse_decision_blocks(block)[0])
    assert enforced.final_tag == BRAIN_DECIDES
    assert enforced.upgraded is False


def test_apply_governance_handles_multiple_blocks_independently():
    markdown = CLEAN_BLOCK + "\n" + CHECKLIST_YES_BLOCK
    corrected, results = apply_governance(markdown)

    assert len(results) == 2
    assert results[0].final_tag == BRAIN_DECIDES
    assert results[1].final_tag == CEO_REQUIRED
    # The clean block's text must be untouched even though a later block changed.
    assert "Approve a new sticker design" in corrected
    assert corrected.count("[CEO REQUIRED]") == 1
