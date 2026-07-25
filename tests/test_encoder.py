"""Tests over the encoder and the published-hash contract.

Split into three groups:

* blocker parsing -- the strict validation that keeps a malformed blocker from
  silently weakening an instance;
* instance anatomy -- clause counts and segment boundaries in the receipt;
* the hash contract -- three representative nodes regenerate to their published
  SHA-256.  The full 47-node sweep lives in ``bin/gen_instances.py`` because it
  takes minutes; these three cover one node per blocker file (9, 13 and 20
  orbits) so the fast test suite still exercises every blocker.
"""

from __future__ import annotations

import hashlib

import pytest

from c1264 import blocks, encode, frontier, orbits

FRONTIER = frontier.load_frontier()

#: One node per distinct blocker file, so the fast suite covers all three.
HASH_SAMPLE = ["s-r0-1", "s-r1-3", "s-r0-2"]


# --- blocker parsing ------------------------------------------------------

@pytest.mark.parametrize("name", sorted({r["blocker"] for r in FRONTIER.values()}))
def test_every_blocker_parses_and_is_negative_width_twenty(name):
    clauses = orbits.parse_blockers(frontier.REPO_ROOT / name)
    assert clauses
    for clause in clauses:
        assert len(clause) == 20
        assert all(-462 <= literal < 0 for literal in clause)


def test_blocker_clause_count_matches_declared_orbits():
    # Each blocked orbit contributes a whole orbit of 20-literal clauses, so the
    # file with more orbits must have strictly more clauses.
    sizes = {}
    for record in FRONTIER.values():
        clauses = orbits.parse_blockers(frontier.blocker_path(record))
        sizes[record["blocker_orbits"]] = len(clauses)
    assert sorted(sizes) == sorted(sizes, key=lambda k: sizes[k])


def test_malformed_blocker_is_rejected(tmp_path):
    bad = tmp_path / "bad.cnf"
    bad.write_text("p cnf 462 1\n-1 -2 0\n")  # width 2, not 20
    with pytest.raises(ValueError, match="exactly 20 distinct blocks"):
        orbits.parse_blockers(bad)


def test_blocker_with_wrong_header_count_is_rejected(tmp_path):
    bad = tmp_path / "bad.cnf"
    bad.write_text("p cnf 462 7\n" + " ".join(str(-i) for i in range(1, 21)) + " 0\n")
    with pytest.raises(ValueError, match="declares 7 clauses"):
        orbits.parse_blockers(bad)


def test_positive_literal_in_blocker_is_rejected(tmp_path):
    bad = tmp_path / "bad.cnf"
    literals = [str(-i) for i in range(1, 20)] + ["20"]
    bad.write_text("p cnf 462 1\n" + " ".join(literals) + " 0\n")
    with pytest.raises(ValueError, match="negative-only"):
        orbits.parse_blockers(bad)


# --- instance anatomy -----------------------------------------------------

def test_receipt_accounts_for_every_clause():
    record = FRONTIER["s-r0-1"]
    cnf, receipt = encode.build_cnf(frontier.blocker_path(record), record["leaf"], "sequential")
    accounted = (
        receipt["coverage_clause_count"]
        + receipt["cardinality_clause_count"]
        + receipt["tail_clause_count"]
    )
    assert accounted == len(cnf.clauses)
    assert receipt["tail_clause_first_zero_based"] == (
        receipt["coverage_clause_count"] + receipt["cardinality_clause_count"]
    )


def test_receipt_has_eleven_degree_segments_with_the_right_bounds():
    record = FRONTIER["t-0"]
    _, receipt = encode.build_cnf(frontier.blocker_path(record), record["leaf"], "sequential")
    segments = receipt["segments"]
    assert [s["point"] for s in segments] == list(range(1, 12))
    assert [s["bound"] for s in segments] == [10] + [9] * 10
    assert all(s["primary_literal_count"] == 210 for s in segments)


def test_segment_auxiliary_ranges_are_contiguous_and_disjoint():
    record = FRONTIER["t-0"]
    _, receipt = encode.build_cnf(frontier.blocker_path(record), record["leaf"], "sequential")
    previous_last = blocks.PRIMARY_VARIABLES
    for segment in receipt["segments"]:
        assert segment["auxiliary_first"] == previous_last + 1
        assert segment["auxiliary_last"] >= segment["auxiliary_first"]
        previous_last = segment["auxiliary_last"]


def test_tail_contains_the_canonical_positive_units():
    record = FRONTIER["t-0"]
    _, tail, metadata = encode.non_cardinality_core(
        frontier.blocker_path(record), **{
            "root_index": record["leaf"]["root_index"],
            "secondary_index": record["leaf"]["secondary_index"],
            "tertiary_index": record["leaf"]["tertiary_index"],
        }
    )
    positives = [clause[0] for clause in tail if len(clause) == 1 and clause[0] > 0]
    expected = [
        blocks.POSITION[tuple(metadata["primary_canonical_block"])],
        blocks.POSITION[tuple(metadata["secondary_canonical_block"])],
        blocks.POSITION[tuple(metadata["tertiary_canonical_block"])],
    ]
    assert positives == expected


def test_unknown_encoding_name_is_rejected():
    record = FRONTIER["t-0"]
    with pytest.raises(ValueError, match="unknown encoding"):
        encode.build_cnf(frontier.blocker_path(record), record["leaf"], "totalizer")


# --- the hash contract ----------------------------------------------------

@pytest.mark.parametrize("name", HASH_SAMPLE)
def test_node_regenerates_to_its_published_hash(name, tmp_path):
    record = FRONTIER[name]
    cnf, _ = encode.build_cnf(frontier.blocker_path(record), record["leaf"], "sequential")
    digest = encode.write_cnf(cnf, tmp_path / f"{name}.cnf")
    assert digest == record["cnf_sha256"], (
        f"{name} regenerated to {digest} but the ledger publishes {record['cnf_sha256']}; "
        "check the PySAT version pin in requirements.txt"
    )


@pytest.mark.parametrize("name", HASH_SAMPLE)
def test_encodings_agree_on_the_problem_and_differ_on_the_bytes(name, tmp_path):
    record = FRONTIER[name]
    receipts = {}
    digests = {}
    for encoding in ("sequential", "kmtotalizer"):
        cnf, receipt = encode.build_cnf(frontier.blocker_path(record), record["leaf"], encoding)
        receipts[encoding] = receipt
        digests[encoding] = encode.write_cnf(cnf, tmp_path / f"{name}.{encoding}.cnf")
    assert (
        receipts["sequential"]["non_cardinality_core_sha256"]
        == receipts["kmtotalizer"]["non_cardinality_core_sha256"]
    )
    assert digests["sequential"] != digests["kmtotalizer"]


def test_digest_clauses_is_dimacs_body_shaped():
    assert encode.digest_clauses([[1, -2], [3]]) == hashlib.sha256(
        b"1 -2 0\n3 0\n"
    ).hexdigest()


# --- the frontier definition ---------------------------------------------

def test_frontier_has_forty_seven_nodes_in_the_documented_shape():
    assert len(FRONTIER) == 47
    assert sum(1 for n in FRONTIER if n.startswith("s-r0-")) == 6
    assert sum(1 for n in FRONTIER if n.startswith("s-r1-")) == 8
    assert sum(1 for n in FRONTIER if n.startswith("t-")) == 33


def test_two_block_nodes_have_no_tertiary_index_and_three_block_nodes_do():
    for name, record in FRONTIER.items():
        tertiary = record["leaf"]["tertiary_index"]
        if name.startswith("t-"):
            assert tertiary == int(name[2:])
            assert record["leaf"]["root_index"] == 0
            assert record["leaf"]["secondary_index"] == 0
        else:
            assert tertiary is None
            assert record["leaf"]["root_index"] == int(name[3])
            assert record["leaf"]["secondary_index"] == int(name.rsplit("-", 1)[1])


def test_published_hashes_are_distinct():
    digests = [record["cnf_sha256"] for record in FRONTIER.values()]
    assert len(set(digests)) == len(digests)
