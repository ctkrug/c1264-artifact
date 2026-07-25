"""Tests over the deposited manifests as a hash chain.

Nothing here rebuilds a CNF or runs a solver: these check that the three
manifests are internally consistent and that the published certificate inventory
is complete.  A referee reading only the JSON should be able to see that every
instance the argument depends on has a machine-checked refutation, and these
tests are that reading, mechanised.
"""

from __future__ import annotations

import json

import pytest

from c1264 import frontier

DATA = frontier.REPO_ROOT / "data"
FRONTIER = json.loads((DATA / "frontier.json").read_text())
AUXILIARY = json.loads((DATA / "auxiliary.json").read_text())
EXTENSIONS = json.loads((DATA / "extensions.json").read_text())

TOTAL_INSTANCES = 47 + 14 + 20


def test_inventory_sizes():
    assert (len(FRONTIER), len(AUXILIARY), len(EXTENSIONS)) == (47, 14, 20)
    assert len(FRONTIER) + len(AUXILIARY) + len(EXTENSIONS) == TOTAL_INSTANCES == 81


def test_frontier_node_names_match_the_case_tree():
    names = sorted(FRONTIER)
    assert len([n for n in names if n.startswith("s-r0-")]) == 6
    assert len([n for n in names if n.startswith("s-r1-")]) == 8
    assert len([n for n in names if n.startswith("t-")]) == 33


def test_every_instance_in_the_argument_is_cake_lpr_verified():
    # The single claim the whole artifact rests on.
    verdicts = (
        [record["certificate"]["cake_lpr_verdict"] for record in FRONTIER.values()]
        + [record["cake_lpr_verdict"] for record in AUXILIARY.values()]
        + [record["cake_lpr_verdict"] for record in EXTENSIONS.values()]
    )
    assert len(verdicts) == TOTAL_INSTANCES
    assert set(verdicts) == {"s VERIFIED UNSAT"}


def test_every_frontier_node_was_solved_under_both_cardinality_encodings():
    # Stronger than the paper's minimum: each node was independently refuted under
    # the seqcounter and kmtotalizer translations, and both DRAT proofs were
    # replayed by drat-trim.  Only one of the two is also cake_lpr-checked.
    for node, record in FRONTIER.items():
        cert = record["certificate"]
        second = cert["second_encoding"]
        assert cert["drat_trim_verdict"] == "s VERIFIED", node
        assert second["drat_trim_verdict"] == "s VERIFIED", node
        assert second["solver_verdict"] == "s UNSATISFIABLE", node
        assert second["encoding"] == "kmtotalizer"
        assert second["cnf_sha256"] != record["cnf_sha256"], node


def test_exactly_one_node_is_certified_under_the_second_encoding():
    # s-r0-2's sequential proof (2.2 GB raw) was replayed but not retained, so its
    # cake_lpr certificate is against the kmtotalizer instance.  That is sound
    # because both encodings share a non-cardinality core, but it is a genuine
    # asymmetry in the deposit and must not be smoothed over.
    exceptions = {
        node
        for node, record in FRONTIER.items()
        if record["certificate"]["checked_encoding"] != "sequential"
    }
    assert exceptions == {"s-r0-2"}
    cert = FRONTIER["s-r0-2"]["certificate"]
    assert cert["checked_encoding"] == "kmtotalizer"
    assert cert["checked_cnf_sha256"] == cert["second_encoding"]["cnf_sha256"]
    assert "non_cardinality_core_sha256" in cert
    assert "note" in cert


def test_checked_cnf_hash_is_the_published_one_except_for_that_node():
    for node, record in FRONTIER.items():
        cert = record["certificate"]
        if node == "s-r0-2":
            continue
        assert cert["checked_cnf_sha256"] == record["cnf_sha256"], node


@pytest.mark.parametrize(
    "manifest,field",
    [(FRONTIER, "cnf_sha256"), (AUXILIARY, "cnf_sha256"), (EXTENSIONS, "cnf_sha256")],
)
def test_hashes_are_well_formed_and_distinct(manifest, field):
    digests = [record[field] for record in manifest.values()]
    assert all(len(d) == 64 and set(d) <= set("0123456789abcdef") for d in digests)
    assert len(set(digests)) == len(digests)


def test_no_instance_hash_collides_across_layers():
    everything = (
        [r["cnf_sha256"] for r in FRONTIER.values()]
        + [r["cnf_sha256"] for r in AUXILIARY.values()]
        + [r["cnf_sha256"] for r in EXTENSIONS.values()]
    )
    assert len(set(everything)) == len(everything) == TOTAL_INSTANCES


def test_auxiliary_hashes_agree_with_the_campaign_ledger():
    # ledger_cnf_sha256 is what the original closure manifest recorded.  It is
    # null for exactly one instance, whose entry the campaign left blank -- that
    # hole was refilled from the preserved CNF and is called out here rather than
    # hidden.
    blank = [name for name, r in AUXILIARY.items() if r["ledger_cnf_sha256"] is None]
    assert blank == ["lb-c1042-8-deg3"]
    for name, record in AUXILIARY.items():
        if record["ledger_cnf_sha256"] is not None:
            assert record["ledger_cnf_sha256"] == record["cnf_sha256"], name


def test_root_tail_is_absent_from_the_auxiliary_inventory():
    # It was built during the campaign but never certified; the region it covered
    # is discharged by r2plus-b20 and r345-tail instead.  A stray entry here would
    # imply a certificate that does not exist.
    assert "root-tail" not in AUXILIARY


def test_blocker_references_are_real_files_and_staged():
    used = {record["blocker"] for record in FRONTIER.values()}
    for relative in used:
        assert (frontier.REPO_ROOT / relative).is_file(), relative
    orbits_used = {record["blocker_orbits"] for record in FRONTIER.values()}
    assert orbits_used <= {9, 13, 20}


def test_the_generated_check_records_carry_no_machine_dependent_field():
    # build/audit.json and build/provenance.json are the two records a referee is
    # invited to diff against the deposited copies rather than read line by line,
    # so they must come out byte-identical on any machine.  Both are written with
    # sort_keys=True; the remaining risk is a field that varies by run -- an
    # elapsed time, a hostname, an absolute path.  Timings belong on stdout.
    volatile = ("seconds", "elapsed", "time", "date", "host", "cwd", "user")

    def keys(payload):
        if isinstance(payload, dict):
            for key, value in payload.items():
                yield key
                yield from keys(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from keys(item)

    for name in ("audit.json", "provenance.json"):
        path = frontier.REPO_ROOT / "build" / name
        if not path.is_file():
            pytest.skip(f"build/{name} absent; run `make regenerate` first")
        offenders = sorted(k for k in keys(json.loads(path.read_text()))
                           if any(bad in k.lower() for bad in volatile))
        assert offenders == [], f"build/{name} would differ between runs: {offenders}"
