#!/usr/bin/env python3
"""Audit an orbit blocker: closure, orbit identity, and licence to block.

The blockers are the one place where a search result enters the deductive
argument, so this script exists to let a referee check them without trusting the
search.  For the blocker given (default: all three shipped ones) it

  1. decodes the blocking clauses back into links, and refuses any clause that is
     not twenty distinct negative literals;
  2. partitions the blocked links into group orbits and fails if any orbit is not
     wholly blocked -- a non-closed blocker would treat some labellings
     differently from others, which the symmetry reduction may not do;
  3. checks the orbit-stabiliser identity ``|orbit| * |stabiliser| = 3840`` per
     orbit;
  4. for each orbit, checks that ``data/extensions.json`` records a witness *in
     that orbit* whose extension instance is machine-checked UNSAT.  That is the
     licence to block it: a link with no extension to a 40-block cover cannot
     occur in one.
  5. checks that a smaller blocker's orbits are a subset of the largest one's,
     which is what makes the staged blockers (9, 13, 20 orbits) a chain rather
     than three unrelated assumptions.

    bin/audit_blocker.py
    bin/audit_blocker.py --blocker data/blockers/blocker-20.cnf --json build/audit.json

Exit status: 0 if every check passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

REPO = Path(__file__).resolve().parents[1]

from c1264.blocker import blocked_links, canonical_digest, orbit_partition
from c1264.extend import load_link
from c1264.group import GROUP_ORDER, group_maps, image

DEFAULT_BLOCKERS = (
    "data/blockers/catalog-9-blocking.cnf",
    "data/blockers/catalog-13-blocking.cnf",
    "data/blockers/blocker-20.cnf",
)
REFERENCE = "data/blockers/blocker-20.cnf"


def witness_orbit_digest(witness: Path, maps) -> str:
    """Canonical digest of the orbit containing a deposited witness link."""
    link = tuple(sorted(tuple(block[1:]) for block in load_link(witness)))
    canonical = min(tuple(sorted(image(m, block) for block in link)) for m in maps)
    return canonical_digest(canonical)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--blocker",
        type=Path,
        action="append",
        help="blocker CNF to audit; repeatable (default: the three shipped blockers)",
    )
    parser.add_argument("--json", type=Path, help="write the audit result to this file")
    args = parser.parse_args()

    paths = args.blocker or [REPO / name for name in DEFAULT_BLOCKERS]
    extensions = json.loads((REPO / "data" / "extensions.json").read_text(encoding="utf-8"))
    maps = list(group_maps())

    # Which orbit each deposited witness actually lies in -- recomputed here
    # rather than read from the manifest, since that claim is the point.
    witness_orbits = {
        digest: witness_orbit_digest(REPO / record["witness_file"], maps)
        for digest, record in extensions.items()
    }

    problems: list[str] = []
    report: dict[str, object] = {"group_order": GROUP_ORDER, "blockers": {}}
    started = time.monotonic()

    for digest, claimed in sorted(witness_orbits.items()):
        if claimed != digest:
            problems.append(
                f"witness {extensions[digest]['witness_file']} lies in orbit "
                f"{claimed[:12]}, not the claimed {digest[:12]}"
            )
        verdict = extensions[digest]["cake_lpr_verdict"]
        if verdict != "s VERIFIED UNSAT":
            problems.append(f"orbit {digest[:12]} extension verdict is {verdict!r}")

    reference_orbits: set[str] = set()
    for path in paths:
        links = blocked_links(path)
        orbits = orbit_partition(path)
        digests = {record["canonical_sha256"] for record in orbits}
        covered = sum(int(record["orbit_size"]) for record in orbits)

        if covered != len(links):
            problems.append(f"{path.name}: orbits cover {covered} of {len(links)} blocked links")
        for record in orbits:
            product = int(record["orbit_size"]) * int(record["stabilizer_order"])
            if product != GROUP_ORDER:
                problems.append(
                    f"{path.name}: orbit {record['canonical_sha256'][:12]} has "
                    f"|orbit|*|stab| = {product}, expected {GROUP_ORDER}"
                )
            if record["canonical_sha256"] not in extensions:
                problems.append(
                    f"{path.name}: orbit {record['canonical_sha256'][:12]} has no "
                    "extension certificate in data/extensions.json"
                )

        if path.name == Path(REFERENCE).name:
            reference_orbits = digests
        report["blockers"][path.name] = {
            "blocked_links": len(links),
            "orbit_count": len(orbits),
            "orbit_sizes": sorted(int(record["orbit_size"]) for record in orbits),
            "canonical_digests": sorted(digests),
        }
        print(
            f"{path.name:28s} links={len(links):<6d} orbits={len(orbits):<3d} "
            f"closed=yes stabilisers=ok"
        )

    if reference_orbits:
        for name, summary in report["blockers"].items():
            extra = set(summary["canonical_digests"]) - reference_orbits
            if extra:
                problems.append(
                    f"{name}: {len(extra)} orbit(s) absent from {REFERENCE}, so the "
                    "staged blockers are not a chain"
                )

    report["problems"] = problems
    report["witness_orbits_confirmed"] = sum(
        1 for digest, claimed in witness_orbits.items() if digest == claimed
    )

    # The elapsed time is reported but deliberately kept out of the JSON: with
    # sort_keys=True and no other machine-dependent field, the record is then
    # byte-identical across runs and machines, so a referee can diff their
    # audit.json against the deposited one instead of reading both.
    elapsed = round(time.monotonic() - started, 1)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(
        f"\n{report['witness_orbits_confirmed']}/{len(witness_orbits)} extension witnesses "
        f"confirmed in their claimed orbit"
    )
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"all checks passed in {elapsed}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
