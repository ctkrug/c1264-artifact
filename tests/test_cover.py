"""Tests for the upper-bound side: C(12,6,4) <= 41.

Both published designs must verify, and the checker must actually reject
plausible corruptions -- a checker that accepts everything proves nothing, so
the negative cases matter more than the positive ones here.
"""

from __future__ import annotations

import pytest

from c1264 import cover, frontier

DESIGNS = ["data/design-stored-41.txt", "data/design-lajolla-41.txt"]


@pytest.mark.parametrize("path", DESIGNS)
def test_published_design_is_a_valid_cover(path):
    blocks = cover.read_design(frontier.REPO_ROOT / path)
    assert cover.check_design(blocks) == []


def test_the_two_designs_are_read_identically():
    left, right = (cover.read_design(frontier.REPO_ROOT / p) for p in DESIGNS)
    assert sorted(map(sorted, left)) == sorted(map(sorted, right))


@pytest.fixture
def design():
    return cover.read_design(frontier.REPO_ROOT / DESIGNS[0])


def test_dropping_a_block_is_detected(design):
    errors = cover.check_design(design[:-1])
    assert any("block count 40" in e for e in errors)
    assert any("uncovered quadruples" in e for e in errors)


def test_duplicating_a_block_is_detected(design):
    errors = cover.check_design(design[:-1] + [design[0]])
    assert any("duplicate blocks" in e for e in errors)
    assert any("uncovered quadruples" in e for e in errors)


def test_out_of_range_point_is_detected(design):
    corrupted = list(design)
    corrupted[0] = (1, 2, 3, 4, 5, 13)
    assert any("not a 6-subset" in e for e in cover.check_design(corrupted))


def test_repeated_point_within_a_block_is_detected(design):
    corrupted = list(design)
    corrupted[0] = (1, 1, 2, 3, 4, 5)
    assert any("not a 6-subset" in e for e in cover.check_design(corrupted))


def test_swapping_one_point_breaks_coverage(design):
    # Optimality does *not* mean every quadruple is covered exactly once (see
    # test_coverage_multiplicities below), so the corruption is pinned to a
    # measured number rather than argued from minimality: relabelling the last
    # point of the first block leaves exactly six quadruples uncovered.
    corrupted = list(design)
    block = list(corrupted[0])
    block[-1] = 12 if block[-1] != 12 else 11
    corrupted[0] = tuple(block)
    errors = cover.check_design(corrupted)
    assert any("6 uncovered quadruples" in e for e in errors), errors


def test_coverage_multiplicities_are_not_all_one(design):
    # 41 blocks * C(6,4) = 615 covered slots against 495 quadruples, so 120
    # slots are surplus and the design is far from a Steiner-like system.  Pinned
    # exactly because the histogram is a fingerprint of *this* design: any edit
    # that preserves coverage but changes the blocks will move it.
    histogram: dict[int, int] = {}
    for quadruple, multiplicity in cover.coverage_multiplicity(design).items():
        histogram[multiplicity] = histogram.get(multiplicity, 0) + 1
    assert histogram == {1: 405, 2: 75, 4: 15}
    assert sum(m * c for m, c in histogram.items()) == 41 * 15


def test_empty_design_is_rejected():
    assert cover.check_design([]) != []
