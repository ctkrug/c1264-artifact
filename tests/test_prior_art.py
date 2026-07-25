"""Tests over `data/coverdata-2026-07-24.json` -- the record of prior knowledge.

This file is a snapshot of the standard table of best-known covering numbers,
taken 2026-07-24, and it is the artifact's source of truth for *what was already
known*. It plays no part in the proof; it fixes the baseline the proof moves, so
that the contribution can be stated without appealing to memory of the literature.

The datum that matters is the entry for `C(12,6,4)`:

    size   = 41   the best known upper bound -- prior art, a JCD article, 1996
    low_bd = 40   the best known lower bound before this work

So the upper bound is not new (and `data/design-*-41.txt` are the deposited
designs realising it); the contribution is closing the gap from below, 40 -> 41.
A test rather than a sentence in the README, because the claim "we improved the
lower bound from 40" is checkable and should be checked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COVERDATA = REPO / "data" / "coverdata-2026-07-24.json"

TABLE = json.loads(COVERDATA.read_text())


def test_the_table_is_the_snapshot_it_claims_to_be():
    assert len(TABLE) == 9482
    # A covering number needs v > k > t >= 2; the key format is what indexes it.
    assert all(key.startswith("C(") and key.endswith(")") for key in TABLE)


def test_the_upper_bound_of_41_is_prior_art():
    record = TABLE["C(12,6,4)"]
    assert record["size"] == 41
    # ...and the table attributes it, so the deposit is not claiming it.
    assert record["imps"], "the table records no attribution for the 41-block design"
    assert any(str(imp[0]) == "41" for imp in record["imps"])


def test_the_lower_bound_this_work_closes_was_40():
    record = TABLE["C(12,6,4)"]
    assert record["low_bd"] == 40, (
        "the artifact's stated contribution is 40 -> 41; if the table now says "
        "something else, the contribution statement in README.md is stale"
    )
    assert record["low_bd"] < record["size"], "the table records no gap to close"


@pytest.mark.parametrize("key,expected", [("C(10,4,2)", 9)])
def test_the_warmup_instance_agrees_with_the_table(key, expected):
    # `lb-c1042-8-deg3` refutes eight blocks, i.e. establishes C(10,4,2) >= 9,
    # and the table's value is 9 -- so the warm-up reproduces a known number and
    # is a genuine end-to-end pipeline test, not a claim.
    assert TABLE[key]["size"] == expected
    assert TABLE[key]["low_bd"] == expected
