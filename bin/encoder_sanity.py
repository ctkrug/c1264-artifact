#!/usr/bin/env python3
"""Brute-force the one library primitive the encoding trusts.

The encoder's only non-elementary step is PySAT's ``CardEnc.equals``.  This
harness checks it semantically rather than structurally: for small ``(n, k)`` it
builds the encoding, then for every one of the 2**n assignments to the n input
literals asks a SAT solver whether the encoding can be satisfied with the
auxiliary variables free.  The encoding is correct on that case iff the accepted
set is exactly the weight-k assignments.

This does not prove ``CardEnc.equals`` correct at n = 210 (the largest degree
constraint in the real instances).  It does mean the artifact's central claim
about the encoding is tested against ground truth rather than merely asserted,
and it would catch an off-by-one bound, an inverted comparison, or an
under-constrained auxiliary chain in either translation.

    bin/encoder_sanity.py
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.solvers import Cadical195

#: (n, k) pairs.  Small enough to enumerate 2**n assignments, varied enough to
#: exercise k below, at, and above n/2.
CASES = [(3, 1), (4, 2), (5, 2), (5, 3), (6, 3), (7, 3), (8, 4)]

ENCODINGS = [("seqcounter", EncType.seqcounter), ("kmtotalizer", EncType.kmtotalizer)]


def check_case(n: int, k: int, encoding: int) -> list[tuple[tuple[bool, ...], bool]]:
    """Return the assignments where the encoding disagrees with weight-k truth."""
    literals = list(range(1, n + 1))
    cnf = CardEnc.equals(lits=literals, bound=k, encoding=encoding, top_id=n)
    disagreements = []
    with Cadical195(bootstrap_with=cnf.clauses) as solver:
        for bits in itertools.product([False, True], repeat=n):
            assumptions = [v if b else -v for v, b in zip(literals, bits)]
            accepted = solver.solve(assumptions=assumptions)
            if accepted != (sum(bits) == k):
                disagreements.append((bits, accepted))
    return disagreements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true", help="only print the overall verdict")
    args = parser.parse_args()

    failures = 0
    for n, k in CASES:
        for name, encoding in ENCODINGS:
            bad = check_case(n, k, encoding)
            if bad:
                failures += 1
            if not args.quiet:
                verdict = "PASS" if not bad else f"FAIL {bad[:3]}"
                print(f"n={n} k={k} enc={name:12s} assignments={2 ** n:<5d} {verdict}")

    total = len(CASES) * len(ENCODINGS)
    if failures:
        print(f"OVERALL: FAIL ({failures}/{total} case/encoding combinations)")
        return 1
    print(
        f"OVERALL: PASS - both encodings accept exactly the weight-k assignments "
        f"in all {total} case/encoding combinations"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
