"""Tests over the structural layer: group, variable layout, orbit partitions.

These run in seconds and need no solver.  They are the cheap tripwire: if the
group definition or the variable layout drifts, these fail long before anyone
spends CPU hours on instances that no longer match the published hashes.

    python -m pytest tests/ -q
"""

from __future__ import annotations

import itertools

import pytest

from c1264 import blocks, group, orbits


# --- the group ------------------------------------------------------------

def test_group_order_is_3840_and_well_formed():
    assert group.assert_group_order() == 3840


def test_group_order_equals_wreath_product_arithmetic():
    assert group.GROUP_ORDER == 2 ** 5 * 120


def test_matching_covers_the_ten_non_fixed_points():
    covered = sorted(itertools.chain.from_iterable(group.PAIRS))
    assert covered == list(range(2, 12))


def test_group_maps_are_closed_under_composition():
    maps = list(group.group_maps())
    keys = {tuple(sorted(m.items())) for m in maps}
    for left in maps[:20]:  # a sample; full closure is 3840^2 compositions
        for right in maps[:20]:
            composed = {p: left[right[p]] for p in range(1, 12)}
            assert tuple(sorted(composed.items())) in keys


def test_link_roots_are_in_distinct_orbits():
    seen: list[frozenset] = []
    maps = list(group.group_maps())
    for root in group.LINK_ROOTS:
        orbit = group.orbit_of(root, maps)
        assert all(orbit.isdisjoint(other) for other in seen)
        seen.append(orbit)


# --- variable layout ------------------------------------------------------

def test_primary_variables_is_462():
    assert blocks.PRIMARY_VARIABLES == 462
    assert len(blocks.BLOCKS) == 462


def test_positions_are_a_bijection_onto_1_through_462():
    assert sorted(blocks.POSITION.values()) == list(range(1, 463))


def test_coverage_has_one_clause_per_triple_and_all_are_positive():
    clauses = blocks.coverage_clauses()
    assert len(clauses) == 165  # C(11,3)
    assert all(all(literal > 0 for literal in clause) for clause in clauses)
    # Each triple sits in C(8,2) = 28 of the 5-subsets.
    assert {len(clause) for clause in clauses} == {28}


def test_degree_sequence_implies_exactly_twenty_blocks():
    assert blocks.point_degree(1) == 10
    assert {blocks.point_degree(p) for p in range(2, 12)} == {9}
    assert blocks.implied_block_count() == 20


def test_point_literals_count_matches_the_combinatorics():
    # Blocks through a given point: C(10,4) = 210.
    for point in range(1, 12):
        assert len(blocks.point_literals(point)) == 210


# --- orbit partitions ----------------------------------------------------

def test_root_orbits_partition_all_462_blocks():
    # The load-bearing property of the primary case split.
    assert orbits.assert_root_orbits_partition() == [80, 120, 10, 32, 160, 60]


def test_root_orbit_sizes_sum_to_the_block_count():
    assert sum(group.LINK_ROOT_ORBIT_SIZES) == blocks.PRIMARY_VARIABLES


def test_first_three_root_orbits_are_exactly_the_blocks_through_point_one():
    # This is why "r >= 2 is refuted" plus "point 1 has degree 10" closes the
    # primary level: orbits 0..2 exhaust the blocks that can meet point 1.
    partition = orbits.root_orbits()
    through_one = {block for block in blocks.BLOCKS if 1 in block}
    assert set().union(*partition[:3]) == through_one


def test_root_orbits_cover_every_block():
    assert set().union(*orbits.root_orbits()) == set(blocks.BLOCKS)


@pytest.mark.parametrize("root_index", range(len(group.LINK_ROOTS)))
def test_secondary_orbits_partition_the_remaining_blocks(root_index):
    partition = orbits.secondary_orbits(root_index)
    union = set().union(*partition)
    assert union == set(blocks.BLOCKS) - {group.LINK_ROOTS[root_index]}
    assert sum(len(orbit) for orbit in partition) == len(union)


def test_tertiary_orbits_stay_inside_the_eligible_domain():
    partition = orbits.tertiary_orbits(0, 0)
    secondary = orbits.secondary_orbits(0)
    excluded = {group.LINK_ROOTS[0], min(secondary[0])}
    union = set().union(*partition)
    assert union.isdisjoint(excluded)
    assert union <= set(blocks.BLOCKS)
    assert sum(len(orbit) for orbit in partition) == len(union)


def test_tertiary_partition_has_at_least_the_thirty_three_frontier_orbits():
    # The case tree uses tertiary orbits 0..32 of (r=0, s=0) as nodes t-0..t-32.
    assert len(orbits.tertiary_orbits(0, 0)) >= 33


def test_negate_emits_sorted_negative_units():
    units = orbits.negate({blocks.BLOCKS[5], blocks.BLOCKS[1]})
    assert units == [[-2], [-6]]
