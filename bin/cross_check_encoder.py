#!/usr/bin/env python3
"""Rebuild all 81 instances with a clean-room encoder that does not use PySAT.

``src/c1264/encode.py`` is the residual trust assumption of the lower bound: no
machine checks the translation from the combinatorial claim into clauses, and one
step of that translation -- the exact-degree cardinality constraint -- is
delegated to a library (PySAT's ``CardEnc.equals`` with ``EncType.seqcounter``).
This script removes the library from the loop.

``verify/independent_seq_encoder.py`` is an independent implementation of the
same published construction (Sinz, CP 2005, LNCS 3709 pp. 827-831), written
from the paper rather than from PySAT's source, importing nothing outside the
standard library.  Here it is used to rebuild every deposited instance and the
result is compared, byte for byte, against the SHA-256 published in the
manifests -- the same hashes the proof certificates were issued against.

Three checks, matching the three instance families:

  * **PySAT agreement** -- one call to :func:`c1264.encode.base_cnf` and one
    clean-room rebuild of the shared Layer-A core, compared clause by clause.
    The core is node independent, so this single comparison covers all 61
    Layer-A instances at the clause level.
  * **Layer A** (47 frontier + 14 auxiliary) -- clean-room coverage clauses and
    clean-room cardinality segments, followed by each instance's own tail
    (blocker clauses plus case-tree units, which are plain clause data over the
    462 primary variables and involve no library).  ``lb-c1042-8-deg3`` is
    unrelated to the link encoding and is instead rebuilt from first principles:
    one variable per 4-subset of {1..10}, 45 pair clauses, AT-MOST-8, and the
    WLOG units.
  * **Layer B** (20 extension instances) -- rebuilt entirely from the deposited
    link witnesses in ``data/links/``, with no artifact code at all.  Layer B's
    CNFs contain no unit clauses, so nothing about the case analysis or its
    canonicalisation enters here.

    bin/cross_check_encoder.py --out build/cross-check.json
    bin/cross_check_encoder.py --layer b            # the 20 extensions only

What a pass means: the cardinality clauses in the deposited instances are the
published encoding and not merely whatever a particular PySAT build emits.  It
does not make the encoder *verified* -- both implementations are unverified
Python, and a shared misreading of the combinatorial claim would survive.  See
``docs/PROOF-MAP.md`` and ``verify/README.md``.

Exit status: 0 if every requested instance was reproduced, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "verify"))

from independent_seq_encoder import atmost_seq, equals_seq  # noqa: E402  clean-room

Clause = List[int]

N_PRIMARY = 462  # C(11,5): one variable per candidate link block
MATCHING = {(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12)}


# --- serialisation ---------------------------------------------------------
#
# PySAT's CNF.to_file writes "p cnf <nv> <nc>" and then one space-separated
# clause per line, zero-terminated, ASCII, trailing newline.  This reproduces
# that byte for byte; docs/REPRODUCIBILITY.md section 5 records the check.


def serialize_dimacs(nv: int, clauses: List[Clause]) -> bytes:
    lines = [f"p cnf {nv} {len(clauses)}"]
    lines.extend(" ".join(map(str, clause + [0])) for clause in clauses)
    return ("\n".join(lines) + "\n").encode("ascii")


def sha256_of(nv: int, clauses: List[Clause]) -> str:
    return hashlib.sha256(serialize_dimacs(nv, clauses)).hexdigest()


# --- clean-room Layer A core ----------------------------------------------


def clean_room_core() -> Tuple[List[Clause], List[Clause], int]:
    """The 165 coverage clauses and the 11 exact-degree segments, from scratch.

    Blocks are the 5-subsets of {1..11} in ``itertools.combinations`` order,
    numbered from 1; variable *i* is true iff block *i* is in the link.  Point 1
    carries degree 10 and points 2..11 degree 9, which forces |L| = 20 without a
    global cardinality constraint.
    """
    blocks = list(itertools.combinations(range(1, 12), 5))
    position = {block: index for index, block in enumerate(blocks, 1)}
    coverage = [
        [position[block] for block in blocks if set(triple) <= set(block)]
        for triple in itertools.combinations(range(1, 12), 3)
    ]
    top = N_PRIMARY
    segments: List[Clause] = []
    for point in range(1, 12):
        literals = [i for i, block in enumerate(blocks, 1) if point in block]
        clauses, top = equals_seq(literals, 10 if point == 1 else 9, top)
        segments.extend(clauses)
    return coverage, segments, top


def clean_room_lb_c1042() -> Tuple[int, List[Clause]]:
    """``lb-c1042-8-deg3`` from first principles: UNSAT means C(10,4,2) >= 9.

    A separate, much smaller problem used as a warm-up: 210 variables (the
    4-subsets of {1..10}), one clause per pair, AT-MOST-8 over everything, three
    positive units fixing a WLOG parallel class through point 1 and negative
    units forbidding every other block through point 1.
    """
    blocks = list(itertools.combinations(range(1, 11), 4))
    position = {block: index for index, block in enumerate(blocks, 1)}
    clauses = [
        [position[block] for block in blocks if set(pair) <= set(block)]
        for pair in itertools.combinations(range(1, 11), 2)
    ]
    cardinality, top = atmost_seq(list(range(1, len(blocks) + 1)), 8, len(blocks))
    clauses.extend(cardinality)
    wlog = [(1, 2, 3, 4), (1, 5, 6, 7), (1, 8, 9, 10)]
    clauses.extend([position[block]] for block in wlog)
    clauses.extend([-position[block]] for block in blocks if 1 in block and block not in wlog)
    return top, clauses


# --- clean-room Layer B ---------------------------------------------------

CO_BLOCKS = list(itertools.combinations(range(2, 13), 6))  # C(11,6) = 462


def load_link(path: Path) -> List[Tuple[int, ...]]:
    """Read a 20-block link witness over {1..11}; lift to {2..12} and adjoin 0.

    The witness is checked here rather than trusted: 20 distinct 5-subsets
    covering every triple of {1..11}, with degree sequence 10, 9^10.  Lifting
    relabels the link's point *p* as *p+1* and adjoins the distinguished point 1,
    so the blocks live in the 12-point space of the cover.
    """
    blocks = [
        tuple(int(token) for token in line.split())
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if len(blocks) != 20 or len(set(blocks)) != 20 or any(len(b) != 5 for b in blocks):
        raise ValueError(f"{path}: expected 20 distinct 5-subsets")
    triples = set().union(*(set(itertools.combinations(b, 3)) for b in blocks))
    if triples != set(itertools.combinations(range(1, 12), 3)):
        raise ValueError(f"{path}: link does not cover every triple of a 11-set")
    degrees = sorted(sum(point in b for b in blocks) for point in range(1, 12))
    if degrees != [9] * 10 + [10]:
        raise ValueError(f"{path}: degree sequence {degrees}, expected 10 and ten 9s")
    return [(1, *(point + 1 for point in block)) for block in blocks]


def clean_room_extension(link_path: Path) -> Tuple[int, List[Clause], int]:
    """E(L): can this link extend to a 41-block cover?  UNSAT says no.

    Variables 1..462 are the 6-subsets of {2..12} -- the blocks avoiding the
    distinguished point 1, since the blocks through it are exactly the lifted
    link.  Coverage clauses are emitted only for quadruples the link leaves
    uncovered, and each pair of {2..12} gets an exact residual budget: 10 on the
    fixed perfect matching, 9 elsewhere, minus what the link already spends.
    There are no unit clauses.
    """
    lifted = load_link(link_path)
    clauses: List[Clause] = []
    coverage_count = 0
    for target in itertools.combinations(range(1, 13), 4):
        if any(set(target) <= set(block) for block in lifted):
            continue
        clause = [i for i, block in enumerate(CO_BLOCKS, 1) if set(target) <= set(block)]
        if not clause:
            raise ValueError(f"{link_path}: quadruple {target} is uncoverable")
        clauses.append(clause)
        coverage_count += 1
    top = len(CO_BLOCKS)
    for pair in itertools.combinations(range(2, 13), 2):
        multiplicity = sum(set(pair) <= set(block) for block in lifted)
        bound = (10 if pair in MATCHING else 9) - multiplicity
        literals = [i for i, block in enumerate(CO_BLOCKS, 1) if set(pair) <= set(block)]
        segment, top = equals_seq(literals, bound, top)
        clauses.extend(segment)
    return coverage_count, clauses, top


# --- the three checks -----------------------------------------------------


def check_pysat_agreement(coverage: List[Clause], segments: List[Clause], top: int) -> dict:
    """Compare the clean-room Layer-A core against PySAT's, clause by clause."""
    from c1264.encode import base_cnf

    cnf, _ = base_cnf("sequential")
    library = cnf.clauses
    row = {
        "pysat_variables": cnf.nv,
        "clean_room_variables": top,
        "variables_match": cnf.nv == top,
        "coverage_clauses": len(coverage),
        "cardinality_clauses": len(segments),
        "clause_count_match": len(library) == len(coverage) + len(segments),
        "coverage_match": library[: len(coverage)] == coverage,
        "cardinality_match": library[len(coverage):] == segments,
    }
    row["ok"] = all(
        row[key] for key in
        ("variables_match", "clause_count_match", "coverage_match", "cardinality_match")
    )
    return row


def check_frontier(coverage: List[Clause], segments: List[Clause], top: int) -> Dict[str, dict]:
    """The 47 case-tree frontier nodes."""
    from c1264.encode import non_cardinality_core
    from c1264.frontier import blocker_path, load_frontier

    frontier = load_frontier()
    rows: Dict[str, dict] = {}
    for name in sorted(frontier):
        record = frontier[name]
        leaf = record["leaf"]
        # Only the tail comes from artifact code, and only as clause data: the
        # blocker file plus case-tree units over variables 1..462.
        _, tail, _ = non_cardinality_core(
            blocker_path(record),
            leaf["root_index"],
            leaf["secondary_index"],
            leaf["tertiary_index"],
        )
        digest = sha256_of(top, coverage + segments + tail)
        rows[name] = {
            "tail_clauses": len(tail),
            "tail_over_primaries": all(
                all(1 <= abs(literal) <= N_PRIMARY for literal in clause) for clause in tail
            ),
            "expected_sha256": record["cnf_sha256"],
            "rebuilt_sha256": digest,
            "ok": digest == record["cnf_sha256"],
        }
    return rows


def check_auxiliary(coverage: List[Clause], segments: List[Clause], top: int) -> Dict[str, dict]:
    """The 14 exhaustiveness instances.

    Thirteen share the Layer-A core, so their tails are read off the instance
    the artifact builds -- which also gives a per-instance clause-level check
    that the library prefix is the clean-room prefix.  The fourteenth,
    ``lb-c1042-8-deg3``, is rebuilt from first principles.
    """
    from c1264.auxiliary import instances

    manifest = json.loads((REPO / "data" / "auxiliary.json").read_text())
    builders = instances(REPO / "data" / "blockers")
    n_core = len(coverage) + len(segments)
    core = coverage + segments
    rows: Dict[str, dict] = {}

    for name in sorted(manifest):
        expected = manifest[name]["cnf_sha256"]
        if name == "lb-c1042-8-deg3":
            nv, clauses = clean_room_lb_c1042()
            digest = sha256_of(nv, clauses)
            rows[name] = {
                "construction": "first principles (C(10,4,2) >= 9 warm-up)",
                "variables": nv,
                "clauses": len(clauses),
                "expected_sha256": expected,
                "rebuilt_sha256": digest,
                "ok": digest == expected,
            }
            continue

        cnf, _ = builders[name]()
        row = {
            "construction": "clean-room core + instance tail",
            "core_match": cnf.clauses[:n_core] == core,
            "tail_clauses": len(cnf.clauses) - n_core,
            "tail_over_primaries": all(
                all(1 <= abs(literal) <= N_PRIMARY for literal in clause)
                for clause in cnf.clauses[n_core:]
            ),
            "expected_sha256": expected,
        }
        digest = sha256_of(top, core + cnf.clauses[n_core:])
        row["rebuilt_sha256"] = digest
        row["ok"] = digest == expected and row["core_match"] and row["tail_over_primaries"]
        rows[name] = row
    return rows


def check_extensions() -> Dict[str, dict]:
    """The 20 link-extension refutations, rebuilt from their witnesses alone."""
    manifest = json.loads((REPO / "data" / "extensions.json").read_text())
    rows: Dict[str, dict] = {}
    for key in sorted(manifest):
        record = manifest[key]
        link_path = REPO / record["witness_file"]
        witness_sha = hashlib.sha256(link_path.read_bytes()).hexdigest()
        coverage_count, clauses, nv = clean_room_extension(link_path)
        digest = sha256_of(nv, clauses)
        rows[key] = {
            "witness_file": record["witness_file"],
            "witness_sha256_match": witness_sha == record["witness_sha256"],
            "witness_is_canonical": record["witness_is_canonical"],
            "variables": nv,
            "variables_match": nv == record["variables"],
            "clauses": len(clauses),
            "clauses_match": len(clauses) == record["clause_count"],
            "coverage_clauses": coverage_count,
            "coverage_match": coverage_count == record["coverage_clause_count"],
            "unit_clauses": sum(1 for clause in clauses if len(clause) == 1),
            "expected_sha256": record["cnf_sha256"],
            "rebuilt_sha256": digest,
        }
        rows[key]["ok"] = digest == record["cnf_sha256"] and all(
            rows[key][field] for field in
            ("witness_sha256_match", "variables_match", "clauses_match", "coverage_match")
        )
    return rows


def report(title: str, rows: Dict[str, dict], width: int = 20) -> List[str]:
    failed = [name for name, row in rows.items() if not row["ok"]]
    print(f"\n{title}")
    for name, row in rows.items():
        verdict = "OK" if row["ok"] else "FAIL"
        detail = "" if row["ok"] else "  " + str(
            {k: v for k, v in row.items() if v is False or k.endswith("sha256")}
        )
        print(f"  {name[:width]:<{width}} {row['rebuilt_sha256'][:16]} {verdict}{detail}")
    print(f"  {len(rows) - len(failed)}/{len(rows)} reproduced")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--layer",
        default="all",
        choices=("all", "a", "b"),
        help="a: the 61 link instances; b: the 20 extension instances (default: all)",
    )
    parser.add_argument("--out", type=Path, help="write a JSON report here")
    args = parser.parse_args()

    started = time.monotonic()
    result: Dict[str, object] = {
        "encoder": "verify/independent_seq_encoder.py",
        "encoder_sha256": hashlib.sha256(
            (REPO / "verify" / "independent_seq_encoder.py").read_bytes()
        ).hexdigest(),
        "cross_checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    failures: List[str] = []

    if args.layer in ("all", "a"):
        coverage, segments, top = clean_room_core()
        agreement = check_pysat_agreement(coverage, segments, top)
        result["pysat_agreement"] = agreement
        print("clean-room core vs PySAT CardEnc.equals(seqcounter)")
        print(
            f"  {agreement['coverage_clauses']} coverage + "
            f"{agreement['cardinality_clauses']} cardinality clauses, "
            f"{agreement['clean_room_variables']} variables: "
            f"{'identical' if agreement['ok'] else 'DIFFERENT'}"
        )
        if not agreement["ok"]:
            failures.append("pysat-agreement")

        frontier = check_frontier(coverage, segments, top)
        result["frontier"] = frontier
        failures += [f"frontier:{name}" for name in report("47 frontier instances", frontier, 10)]

        auxiliary = check_auxiliary(coverage, segments, top)
        result["auxiliary"] = auxiliary
        failures += [f"auxiliary:{name}" for name in report("14 auxiliary instances", auxiliary)]

    if args.layer in ("all", "b"):
        extensions = check_extensions()
        result["extensions"] = extensions
        failures += [
            f"extension:{name}" for name in report("20 extension instances", extensions, 16)
        ]

    total = sum(
        len(result[family]) for family in ("frontier", "auxiliary", "extensions")
        if family in result
    )
    result["instances"] = total
    result["reproduced"] = total - len([f for f in failures if not f.startswith("pysat")])
    result["failures"] = failures

    # Reported, not serialised -- see the same note in bin/audit_blocker.py.
    elapsed = round(time.monotonic() - started, 1)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(
        f"\n{result['reproduced']}/{total} instances rebuilt byte-for-byte without PySAT "
        f"in {elapsed}s"
    )
    if failures:
        print(f"FAILED: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
