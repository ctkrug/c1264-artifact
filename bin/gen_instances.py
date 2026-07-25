#!/usr/bin/env python3
"""Regenerate the 47 frontier CNF instances and check them against published hashes.

This is the reproducibility gate of the artifact.  For each node it rebuilds the
DIMACS file from scratch through :mod:`c1264.encode` and compares the SHA-256 to
the value published in ``data/frontier.json``.  A single mismatch is a failure:
the proof certificates were produced against specific bytes, so a differing byte
means the stored certificate does not certify the regenerated instance.

    bin/gen_instances.py --out build/cnf                    # sequential encoding
    bin/gen_instances.py --out build/cnf --encoding kmtotalizer --no-hash-check
    bin/gen_instances.py --out build/cnf --nodes s-r0-1 t-0  # a subset, for a smoke test

Exit status: 0 if every requested node was generated and (unless disabled) every
hash matched; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from c1264.encode import ENCODINGS, build_cnf, write_cnf
from c1264.frontier import blocker_path, load_frontier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="output directory for .cnf files")
    parser.add_argument(
        "--encoding",
        default="sequential",
        choices=sorted(ENCODINGS),
        help="cardinality translation (default: sequential, the one the hashes pin)",
    )
    parser.add_argument("--nodes", nargs="*", help="node names to build (default: all 47)")
    parser.add_argument(
        "--no-hash-check",
        action="store_true",
        help="skip the published-hash comparison; required for --encoding kmtotalizer, "
             "whose instances are legitimately different bytes",
    )
    parser.add_argument(
        "--receipts",
        type=Path,
        help="write per-node provenance receipts to this JSON file",
    )
    args = parser.parse_args()

    frontier = load_frontier()
    names = sorted(args.nodes) if args.nodes else sorted(frontier)
    unknown = [name for name in names if name not in frontier]
    if unknown:
        print(f"unknown node names: {unknown}", file=sys.stderr)
        return 1

    check_hashes = not args.no_hash_check
    if check_hashes and args.encoding != "sequential":
        print(
            "refusing to hash-check a non-sequential encoding: published hashes pin the "
            "sequential translation.  Pass --no-hash-check if that is what you meant.",
            file=sys.stderr,
        )
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    receipts: dict[str, dict] = {}
    failures: list[str] = []
    started = time.monotonic()

    for name in names:
        record = frontier[name]
        cnf, receipt = build_cnf(blocker_path(record), record["leaf"], args.encoding)
        digest = write_cnf(cnf, args.out / f"{name}.cnf")
        receipt["node"] = name
        receipt["cnf_sha256"] = digest
        receipts[name] = receipt

        if check_hashes:
            expected = record["cnf_sha256"]
            status = "MATCH" if digest == expected else "MISMATCH"
            if digest != expected:
                failures.append(name)
            print(
                f"{name:8s} b{record['blocker_orbits']:<3d} vars={cnf.nv:<6d} "
                f"clauses={len(cnf.clauses):<6d} {digest[:16]} {status}"
            )
        else:
            print(
                f"{name:8s} b{record['blocker_orbits']:<3d} vars={cnf.nv:<6d} "
                f"clauses={len(cnf.clauses):<6d} {digest[:16]}"
            )

    elapsed = time.monotonic() - started
    if args.receipts:
        args.receipts.parent.mkdir(parents=True, exist_ok=True)
        args.receipts.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n")

    if check_hashes:
        matched = len(names) - len(failures)
        print(f"\n{matched}/{len(names)} hashes matched in {elapsed:.1f}s")
        if failures:
            print(f"FAILED nodes: {sorted(failures)}", file=sys.stderr)
            return 1
    else:
        print(f"\n{len(names)} instances written in {elapsed:.1f}s (hash check skipped)")

    # A single non-cardinality core across all nodes is NOT expected -- each node
    # pins different blocks -- but within a node the core must be encoding
    # independent.  bin/check_encoding_provenance.py verifies that pairing.
    return 0


if __name__ == "__main__":
    sys.exit(main())
