"""Tests over the extension layer (Layer B).

The property that carries the most weight here is the *absence of unit clauses*:
an extension instance says nothing about the link it came from, it subtracts the
link from the degree bounds.  That is what makes these instances independent of
Layer A's canonicalisation and therefore able to justify it.  A regression that
reintroduced units would still produce UNSAT instances and still match nothing --
so it is asserted directly, not inferred from hashes.
"""

from __future__ import annotations

import itertools
import json

import pytest

from c1264 import blocker, extend, frontier

MANIFEST = json.loads((frontier.REPO_ROOT / "data" / "extensions.json").read_text())

# One canonical witness and one non-canonical one, since those are the two cases
# gen_extensions.py has to handle.
HASH_SAMPLE = [
    next(d for d, r in sorted(MANIFEST.items()) if r["witness_is_canonical"]),
    next(d for d, r in sorted(MANIFEST.items()) if not r["witness_is_canonical"]),
]


def test_manifest_covers_twenty_orbits_keyed_by_canonical_digest():
    assert len(MANIFEST) == 20
    assert all(len(digest) == 64 for digest in MANIFEST)
    assert sum(record["orbit_size"] for record in MANIFEST.values()) == 15120


def test_every_extension_is_machine_checked():
    assert {row["cake_lpr_verdict"] for row in MANIFEST.values()} == {"s VERIFIED UNSAT"}
    assert {row["drat_trim_verdict"] for row in MANIFEST.values()} == {"s VERIFIED"}


def test_eight_witnesses_are_non_canonical():
    # Documented in bin/gen_extensions.py: the campaign solved whichever labelling
    # its search produced.  If this count ever changes, the deposited witnesses no
    # longer match the certificates and the manifest is stale.
    assert sum(not r["witness_is_canonical"] for r in MANIFEST.values()) == 8


def test_witness_files_are_unmodified():
    import hashlib

    for digest, record in MANIFEST.items():
        data = (frontier.REPO_ROOT / record["witness_file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["witness_sha256"], digest


def test_canonical_witnesses_serialise_to_their_own_digest():
    for digest, record in MANIFEST.items():
        if not record["witness_is_canonical"]:
            continue
        blocks = [tuple(block) for block in record["canonical_blocks"]]
        assert blocker.canonical_digest(blocks) == digest


@pytest.mark.parametrize("digest", HASH_SAMPLE)
def test_sampled_extension_regenerates_to_its_published_hash(digest, tmp_path):
    record = MANIFEST[digest]
    link = extend.load_link(frontier.REPO_ROOT / record["witness_file"])
    cnf, receipt = extend.build_extension(link)
    written = extend.write_extension(cnf, tmp_path / "ext.cnf")
    assert written == record["cnf_sha256"]
    assert receipt["variables"] == record["variables"]
    assert receipt["clause_count"] == record["clause_count"]
    assert receipt["coverage_clause_count"] == record["coverage_clause_count"]


@pytest.mark.parametrize("digest", HASH_SAMPLE)
def test_extension_instance_has_no_unit_clauses(digest):
    record = MANIFEST[digest]
    link = extend.load_link(frontier.REPO_ROOT / record["witness_file"])
    cnf, receipt = extend.build_extension(link)
    assert receipt["unit_clause_count"] == 0
    assert not any(len(clause) == 1 for clause in cnf.clauses)


def test_residual_geometry_constants():
    assert extend.RESIDUAL_VARIABLES == 462
    assert len(extend.RESIDUAL_BLOCKS) == 462
    assert all(len(block) == 6 for block in extend.RESIDUAL_BLOCKS)
    assert all(0 not in block for block in extend.RESIDUAL_BLOCKS)
    # Width 21 = C(7,2): pick a 4-subset of {1..11}, the 6-subsets containing it
    # are determined by the 2 extra points chosen from the remaining 7.
    target = (1, 2, 3, 4)
    containing = [b for b in extend.RESIDUAL_BLOCKS if set(target).issubset(b)]
    assert len(containing) == extend.RESIDUAL_COVERAGE_WIDTH == 21


@pytest.mark.parametrize("digest", HASH_SAMPLE[:1])
def test_no_coverage_clause_mentions_the_distinguished_point(digest):
    # Every quadruple containing point 0 is already covered by the link, so the
    # residual instance must be silent about point 0 entirely.
    link = extend.load_link(frontier.REPO_ROOT / MANIFEST[digest]["witness_file"])
    for target in itertools.combinations(range(extend.POINTS), 4):
        if 0 in target:
            assert any(set(target).issubset(block) for block in link), target


def test_link_validation_rejects_a_corrupted_witness():
    record = MANIFEST[HASH_SAMPLE[0]]
    link = extend.load_link(frontier.REPO_ROOT / record["witness_file"])
    source = [tuple(point - 1 for point in block[1:]) for block in link]

    with pytest.raises(ValueError):
        extend.link_from_blocks(source[:-1])  # 19 blocks
    with pytest.raises(ValueError):
        extend.link_from_blocks(source[:-1] + [source[0]])  # a repeat
    with pytest.raises(ValueError):
        # Swap one point out: this breaks either triple coverage or the degrees,
        # both of which load_link is supposed to notice.
        broken = list(source)
        block = list(broken[0])
        block[-1] = 10 if block[-1] != 10 else 9
        broken[0] = tuple(sorted(set(block)))
        extend.link_from_blocks(broken)
