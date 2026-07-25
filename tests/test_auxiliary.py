"""Tests over the auxiliary layer: the instances that make the tree exhaustive.

Rebuilding all fourteen takes about fifteen seconds, so only a sample is
hash-checked here; ``bin/gen_auxiliary.py`` does the full set.  The structural
assertions below are the ones that would catch a silent change of *meaning*
rather than of bytes.
"""

from __future__ import annotations

import json

import pytest

from c1264 import auxiliary, blocks, frontier, orbits

BLOCKERS = frontier.REPO_ROOT / "data" / "blockers"
MANIFEST = json.loads((frontier.REPO_ROOT / "data" / "auxiliary.json").read_text())

# One of each shape: a region instance, a tail instance and a gap instance.
HASH_SAMPLE = ["r345-tail", "r0-sec-tail", "r1-gap-s9"]


def test_manifest_lists_exactly_the_fourteen_builders():
    assert sorted(auxiliary.instances(BLOCKERS)) == sorted(MANIFEST)
    assert len(MANIFEST) == 14


def test_every_auxiliary_instance_is_machine_checked():
    # The artifact's claim is not "these were solved" but "these were checked by
    # cake_lpr", so the manifest must say so for all fourteen.
    assert {row["cake_lpr_verdict"] for row in MANIFEST.values()} == {"s VERIFIED UNSAT"}
    assert {row["drat_trim_verdict"] for row in MANIFEST.values()} == {"s VERIFIED"}
    assert {row["solver_verdict"] for row in MANIFEST.values()} == {"s UNSATISFIABLE"}


@pytest.mark.parametrize("name", HASH_SAMPLE)
def test_sampled_instance_regenerates_to_its_published_hash(name, tmp_path):
    from c1264.encode import write_cnf

    cnf, receipt = auxiliary.instances(BLOCKERS)[name]()
    digest = write_cnf(cnf, tmp_path / f"{name}.cnf")
    assert digest == MANIFEST[name]["cnf_sha256"]
    assert receipt["clause_count"] == MANIFEST[name]["clause_count"]
    assert receipt["variables"] == MANIFEST[name]["variables"]


def test_region_instances_assert_no_canonical_block():
    # r2plus-b20 and r345-tail are the two symmetry-free instances: they must
    # contain only negative units, or they would depend on the canonicalisation
    # they are used to justify.
    for through in (2, 3):
        units = auxiliary.region_units(through)
        assert units
        assert all(len(unit) == 1 and unit[0] < 0 for unit in units)


def test_r345_tail_forbids_every_block_through_point_one():
    # This is why the instance is UNSAT for an elementary reason: point 1 needs
    # degree 10 and has no block left to use.
    forbidden = {blocks.BLOCKS[-unit[0] - 1] for unit in auxiliary.region_units(3)}
    assert forbidden == {block for block in blocks.BLOCKS if 1 in block}
    assert len(forbidden) == 210


def test_r2plus_region_is_the_complement_of_the_first_two_orbits():
    partition = orbits.root_orbits()
    forbidden = {blocks.BLOCKS[-unit[0] - 1] for unit in auxiliary.region_units(2)}
    assert forbidden == set(partition[0]) | set(partition[1])
    assert len(forbidden) == 80 + 120


def test_gap_indices_are_disjoint_from_the_live_frontier():
    # A gap instance and a frontier node must never claim the same branch, or one
    # of them is redundant and the case analysis is not a partition.
    live = {
        record["leaf"]["secondary_index"]
        for name, record in frontier.load_frontier().items()
        if record["leaf"]["root_index"] == 1 and record["leaf"]["tertiary_index"] is None
    }
    assert live.isdisjoint(auxiliary.R1_GAP_SECONDARY)
    highest = auxiliary.LIVE_SECONDARY_LIMIT[1]
    assert max(live) < highest
    assert all(index < highest for index in auxiliary.R1_GAP_SECONDARY)


def test_gap_and_tail_indices_together_close_the_r1_level():
    # Every secondary index below the tail limit is either live or a gap.
    live = {
        record["leaf"]["secondary_index"]
        for name, record in frontier.load_frontier().items()
        if record["leaf"]["root_index"] == 1
    }
    limit = auxiliary.LIVE_SECONDARY_LIMIT[1]
    assert live | set(auxiliary.R1_GAP_SECONDARY) == set(range(limit))


def test_lower_bound_warmup_has_the_expected_shape():
    cnf = auxiliary.lower_bound_c1042_deg3()
    assert cnf.nv == 1826
    assert len(cnf.clauses) == 3555
    # 45 pair-coverage clauses, then the cardinality block, then 3 asserted
    # blocks and the 81 other blocks through point 1 forbidden.
    assert len([clause for clause in cnf.clauses if len(clause) == 1]) == 3 + 81
    positives = [clause[0] for clause in cnf.clauses if len(clause) == 1 and clause[0] > 0]
    assert len(positives) == 3
