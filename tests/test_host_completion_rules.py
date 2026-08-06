from __future__ import annotations

import pytest

from app.services.host_completion_rules import infer_rules


def test_rule_inference_enforces_support_threshold_and_confidence_formula():
    pairs = [
        ("10.10.1.1", "10.30.1.1"),
        ("10.10.2.2", "10.30.2.2"),
        ("10.10.3.3", "10.30.3.3"),
        ("10.10.4.4", "10.31.4.4"),
    ]

    inactive = infer_rules(pairs, min_support=4)
    active = infer_rules(pairs, min_support=3)

    assert not any(
        rule.transformation.description == "10.10.0.0/16 -> 10.30.0.0/16"
        for rule in inactive
    )
    rule = next(
        rule
        for rule in active
        if rule.transformation.description == "10.10.0.0/16 -> 10.30.0.0/16"
    )
    assert rule.support == 3
    assert rule.contradictions == 1
    assert rule.confidence == pytest.approx(3 / 5 + 0.1)


def test_rule_inference_counts_rejections_and_derives_all_transformation_kinds():
    pairs = [
        ("10.10.1.7", "10.30.1.7"),
        ("10.10.2.7", "10.30.2.7"),
        ("10.10.3.7", "10.30.3.7"),
    ]

    rules = infer_rules(
        pairs,
        rejected_candidates=[("10.10.9.7", "10.30.9.7")],
        min_support=3,
    )

    prefix_rule = next(
        rule
        for rule in rules
        if rule.transformation.description == "10.10.0.0/16 -> 10.30.0.0/16"
    )
    assert prefix_rule.rejected == 1
    assert prefix_rule.contradictions == 1
    assert any(rule.transformation.prefix_length == 24 for rule in rules) is False
    assert any(rule.transformation.kind == "octet" for rule in rules)


def test_prefix_24_rule_is_inferred_when_last_octet_is_preserved():
    rules = infer_rules(
        [
            ("10.10.8.1", "10.30.9.1"),
            ("10.10.8.2", "10.30.9.2"),
            ("10.10.8.3", "10.30.9.3"),
        ]
    )

    rule = next(rule for rule in rules if rule.transformation.prefix_length == 24)
    assert rule.transformation.apply("10.10.8.99") == "10.30.9.99"
