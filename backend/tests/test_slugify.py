from __future__ import annotations

import pytest

from app.orgs.service import slugify


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Acme Rockets", "acme-rockets"),
        ("Acme Rockets & Co.", "acme-rockets-co"),
        ("  leading and trailing  ", "leading-and-trailing"),
        ("MiXeD CaSe", "mixed-case"),
        ("multiple   spaces", "multiple-spaces"),
        ("already-slugged", "already-slugged"),
        ("Café Ünïcode", "cafe-unicode"),
        ("under_scores", "under-scores"),
        ("2026 Q1 Team", "2026-q1-team"),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


@pytest.mark.parametrize("name", ["", "   ", "!!!", "///", "🙂"])
def test_unsluggable_names_fall_back(name: str) -> None:
    """Never return an empty slug — the column is NOT NULL and URL-facing."""
    assert slugify(name) == "org"


def test_result_is_truncated_and_well_formed() -> None:
    slug = slugify("word " * 100)
    assert len(slug) <= 80
    assert not slug.startswith("-")
    assert not slug.endswith("-")
