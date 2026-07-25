#!/usr/bin/env python3
"""Regenerate the 20 extension instances that license the orbit blocker.

Each of the twenty blocked link orbits is blocked because one link in it was
shown not to extend to a 40-block cover.  This script rebuilds those twenty
residual instances from the deposited witnesses in ``data/links/`` and checks
their SHA-256 against ``data/extensions.json``.

Twelve of the deposited witnesses are the canonical (lexicographically least)
representatives of their orbit; the other eight are not, because the campaign
solved whichever labelling its search produced.  That is sound -- the extension
problem is invariant under the group, so refuting any member refutes the orbit --
but it means the witness itself has to be deposited to reproduce the exact bytes
the certificates were issued against.  ``bin/audit_blocker.py`` is what checks
each witness really lies in the orbit it claims.

    bin/gen_extensions.py --out build/cnf-ext
    bin/gen_extensions.py --out build/cnf-ext --orbits 681764d1b0bf

Exit status: 0 if every requested instance rebuilt to its published SHA-256,
1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

REPO = Path(__file__).resolve().parents[1]

from c1264.extend import build_extension, load_link, write_extension


def load_manifest() -> dict:
    return json.loads((REPO / "data" / "extensions.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="output directory for .cnf files")
    parser.add_argument(
        "--orbits",
        nargs="*",
        help="canonical digests, full or 12-character prefix (default: all 20)",
    )
    parser.add_argument("--no-hash-check", action="store_true", help="skip the hash comparison")
    parser.add_argument("--receipts", type=Path, help="write per-instance receipts to this JSON file")
    args = parser.parse_args()

    manifest = load_manifest()
    if args.orbits:
        selected = []
        for wanted in args.orbits:
            hits = [digest for digest in manifest if digest.startswith(wanted)]
            if len(hits) != 1:
                print(f"{wanted!r} matches {len(hits)} orbits, expected 1", file=sys.stderr)
                return 1
            selected.extend(hits)
        names = sorted(selected)
    else:
        names = sorted(manifest)

    receipts: dict[str, dict] = {}
    failures: list[str] = []
    started = time.monotonic()

    for digest in names:
        record = manifest[digest]
        witness = REPO / record["witness_file"]
        stored = hashlib.sha256(witness.read_bytes()).hexdigest()
        if stored != record["witness_sha256"]:
            print(f"{digest[:12]} witness file {witness} has been modified", file=sys.stderr)
            failures.append(digest)
            continue

        cnf, receipt = build_extension(load_link(witness))
        cnf_digest = write_extension(cnf, args.out / f"ext-{digest[:12]}.cnf")
        receipt["canonical_sha256"] = digest
        receipt["cnf_sha256"] = cnf_digest
        receipts[digest] = receipt

        if args.no_hash_check:
            print(f"{digest[:12]} vars={cnf.nv:<6d} clauses={len(cnf.clauses):<7d} {cnf_digest[:16]}")
            continue

        expected = record["cnf_sha256"]
        status = "MATCH" if cnf_digest == expected else "MISMATCH"
        if cnf_digest != expected:
            failures.append(digest)
        print(
            f"{digest[:12]} orbit={record['orbit_size']:<5d} vars={cnf.nv:<6d} "
            f"clauses={len(cnf.clauses):<7d} {cnf_digest[:16]} {status}"
        )

    elapsed = time.monotonic() - started
    if args.receipts:
        args.receipts.parent.mkdir(parents=True, exist_ok=True)
        args.receipts.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n")

    if args.no_hash_check:
        print(f"\n{len(names)} instances written in {elapsed:.1f}s (hash check skipped)")
        return 0 if not failures else 1

    print(f"\n{len(names) - len(failures)}/{len(names)} hashes matched in {elapsed:.1f}s")
    if failures:
        print(f"FAILED orbits: {sorted(d[:12] for d in failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
