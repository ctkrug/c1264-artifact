#!/usr/bin/env python3
"""Cross-encoding provenance gate.

For each requested node, build the instance under both cardinality translations
and assert three things:

  1. the sequential instance reproduces the published SHA-256 byte for byte;
  2. the two instances share the same ``non_cardinality_core_sha256`` -- i.e.
     they state the *same* combinatorial problem;
  3. the two instances are nevertheless different files -- i.e. the second
     encoding is a genuinely different translation, not an accidental copy.

Together these justify the paper's claim that refuting a node under both
encodings makes a cardinality-translation bug an implausible carrier of the
theorem: a bug would have to exist in two independently written encoders and
produce the same wrong answer on the same problem.

    bin/check_encoding_provenance.py --out build/provenance.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from c1264.encode import build_cnf, write_cnf
from c1264.frontier import blocker_path, load_frontier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="write the provenance record here")
    parser.add_argument("--nodes", nargs="*", help="node names to check (default: all 47)")
    parser.add_argument(
        "--scratch",
        type=Path,
        default=Path("build/provenance-scratch"),
        help="directory for the temporary DIMACS files",
    )
    args = parser.parse_args()

    frontier = load_frontier()
    names = sorted(args.nodes) if args.nodes else sorted(frontier)
    args.scratch.mkdir(parents=True, exist_ok=True)

    record: dict[str, dict] = {}
    failures: list[str] = []

    for name in names:
        node = frontier[name]
        blocker = blocker_path(node)
        row: dict[str, object] = {"blocker_orbits": node["blocker_orbits"]}

        digests = {}
        cores = {}
        for encoding in ("sequential", "kmtotalizer"):
            cnf, receipt = build_cnf(blocker, node["leaf"], encoding)
            digests[encoding] = write_cnf(cnf, args.scratch / f"{name}.{encoding}.cnf")
            cores[encoding] = receipt["non_cardinality_core_sha256"]
            row[f"{encoding}_vars"] = cnf.nv
            row[f"{encoding}_clauses"] = len(cnf.clauses)
            row[f"{encoding}_sha256"] = digests[encoding]

        row["non_cardinality_core_sha256"] = cores["sequential"]
        checks = {
            "sequential_matches_published": digests["sequential"] == node["cnf_sha256"],
            "cores_agree": cores["sequential"] == cores["kmtotalizer"],
            "encodings_differ": digests["sequential"] != digests["kmtotalizer"],
        }
        row["checks"] = checks
        record[name] = row

        failed = [key for key, ok in checks.items() if not ok]
        if failed:
            failures.append(name)
        print(f"{name:8s} {'OK' if not failed else 'FAIL ' + ','.join(failed)}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    print(f"\n{len(names) - len(failures)}/{len(names)} nodes passed all three checks")
    if failures:
        print(f"FAILED nodes: {sorted(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
