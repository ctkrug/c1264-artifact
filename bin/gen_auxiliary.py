#!/usr/bin/env python3
"""Regenerate the 14 auxiliary CNF instances and check the published hashes.

The 47 frontier nodes refute the live branches of the case tree; these fourteen
instances refute everything else, so the proof is only exhaustive with both sets
present.  See :mod:`c1264.auxiliary` for what each one covers.

    bin/gen_auxiliary.py --out build/cnf-aux
    bin/gen_auxiliary.py --out build/cnf-aux --jobs r2plus-b20 r345-tail

Exit status: 0 if every requested instance rebuilt to its published SHA-256,
1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

REPO = Path(__file__).resolve().parents[1]

from c1264.auxiliary import instances
from c1264.encode import write_cnf


def load_manifest() -> dict:
    return json.loads((REPO / "data" / "auxiliary.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="output directory for .cnf files")
    parser.add_argument("--jobs", nargs="*", help="instance names to build (default: all 14)")
    parser.add_argument(
        "--no-hash-check", action="store_true", help="write the instances without comparing hashes"
    )
    parser.add_argument("--receipts", type=Path, help="write per-instance receipts to this JSON file")
    args = parser.parse_args()

    manifest = load_manifest()
    builders = instances(REPO / "data" / "blockers")
    names = sorted(args.jobs) if args.jobs else sorted(builders)
    unknown = [name for name in names if name not in builders]
    if unknown:
        print(f"unknown instance names: {unknown}", file=sys.stderr)
        return 1

    receipts: dict[str, dict] = {}
    failures: list[str] = []
    started = time.monotonic()

    for name in names:
        cnf, receipt = builders[name]()
        digest = write_cnf(cnf, args.out / f"{name}.cnf")
        receipt["cnf_sha256"] = digest
        receipts[name] = receipt

        if args.no_hash_check:
            print(f"{name:18s} vars={cnf.nv:<6d} clauses={len(cnf.clauses):<6d} {digest[:16]}")
            continue

        expected = manifest[name]["cnf_sha256"]
        status = "MATCH" if digest == expected else "MISMATCH"
        if digest != expected:
            failures.append(name)
        print(
            f"{name:18s} vars={cnf.nv:<6d} clauses={len(cnf.clauses):<6d} "
            f"{digest[:16]} {status}"
        )

    elapsed = time.monotonic() - started
    if args.receipts:
        args.receipts.parent.mkdir(parents=True, exist_ok=True)
        args.receipts.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n")

    if args.no_hash_check:
        print(f"\n{len(names)} instances written in {elapsed:.1f}s (hash check skipped)")
        return 0

    print(f"\n{len(names) - len(failures)}/{len(names)} hashes matched in {elapsed:.1f}s")
    if failures:
        print(f"FAILED instances: {sorted(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
