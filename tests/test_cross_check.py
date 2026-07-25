"""Fast tests over the clean-room cross-check.

``bin/cross_check_encoder.py`` rebuilds all 81 instances without PySAT and takes
about three minutes, which is too slow for a test suite that is meant to run in
seconds.  What is tested here is the part a regression would break silently:

* the clean-room sequential-counter encoder is *semantically* right, brute-forced
  against ground truth on small ``(n, k)`` -- so agreement with PySAT means both
  are right, not that both are wrong in the same way;
* it agrees with ``CardEnc.equals`` clause for clause on small ``(n, k)``;
* the byte-level contract holds on two representative instances -- one extension
  node and the warm-up ``lb-c1042-8-deg3``, both cheap enough to rebuild here.

The full 81-instance sweep is `make cross-check`.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bin"))
sys.path.insert(0, str(REPO / "verify"))

from independent_seq_encoder import atmost_seq, equals_seq  # noqa: E402
import cross_check_encoder as cross  # noqa: E402


# --- the clean-room encoder is semantically correct ------------------------

def models(clauses, nv, primaries):
    """Projections onto ``primaries`` of the assignments satisfying ``clauses``."""
    accepted = set()
    for bits in itertools.product((False, True), repeat=nv):
        value = (False,) + bits  # 1-based
        if all(any(value[abs(l)] == (l > 0) for l in clause) for clause in clauses):
            accepted.add(tuple(bits[p - 1] for p in primaries))
    return accepted


@pytest.mark.parametrize("n,k", [(4, 2), (5, 2), (5, 3), (6, 3)])
def test_clean_room_atmost_accepts_exactly_the_light_assignments(n, k):
    lits = list(range(1, n + 1))
    clauses, top = atmost_seq(lits, k, n)
    expected = {a for a in itertools.product((False, True), repeat=n) if sum(a) <= k}
    assert models(clauses, top, lits) == expected


@pytest.mark.parametrize("n,k", [(4, 2), (5, 2), (5, 3), (6, 3)])
def test_clean_room_equals_accepts_exactly_the_weight_k_assignments(n, k):
    lits = list(range(1, n + 1))
    clauses, top = equals_seq(lits, k, n)
    expected = {a for a in itertools.product((False, True), repeat=n) if sum(a) == k}
    assert models(clauses, top, lits) == expected


# --- and agrees with PySAT clause for clause ------------------------------

@pytest.mark.parametrize("n,k", [(4, 2), (6, 3), (8, 3), (12, 5)])
def test_clean_room_equals_matches_pysat_clause_for_clause(n, k):
    from pysat.card import CardEnc, EncType

    lits = list(range(1, n + 1))
    ours, top = equals_seq(lits, k, n)
    theirs = CardEnc.equals(
        lits=lits, bound=k, top_id=n, encoding=EncType.seqcounter
    ).clauses
    assert ours == theirs, f"clean-room and PySAT disagree at (n, k) = ({n}, {k})"
    assert top == max(abs(l) for clause in ours for l in clause)


# --- the byte-level contract, on two cheap instances ----------------------

def test_one_extension_instance_rebuilds_to_its_published_hash():
    manifest = json.loads((REPO / "data" / "extensions.json").read_text())
    key = sorted(manifest)[0]
    record = manifest[key]
    link_path = REPO / record["witness_file"]

    assert hashlib.sha256(link_path.read_bytes()).hexdigest() == record["witness_sha256"]

    coverage_count, clauses, nv = cross.clean_room_extension(link_path)
    assert nv == record["variables"]
    assert len(clauses) == record["clause_count"]
    assert coverage_count == record["coverage_clause_count"]
    assert not [c for c in clauses if len(c) == 1], "extension instances carry no units"
    assert cross.sha256_of(nv, clauses) == record["cnf_sha256"]


def test_the_c1042_warmup_rebuilds_from_first_principles():
    manifest = json.loads((REPO / "data" / "auxiliary.json").read_text())
    record = manifest["lb-c1042-8-deg3"]

    nv, clauses = cross.clean_room_lb_c1042()
    assert cross.sha256_of(nv, clauses) == record["cnf_sha256"]
