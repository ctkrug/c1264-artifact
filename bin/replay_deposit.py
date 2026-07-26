#!/usr/bin/env python3
"""Map and replay the deposited DRAT certificates against their exact CNFs.

The certificate deposit may be either its extracted directory or the published
``.tar`` file.  By default this command performs the cheap but complete mapping
audit: every one of the 81 proof objects must be present, its compressed hash
must match the proof manifest, and its paired CNF must have the exact hash
recorded by the computational artifact.

Use ``--replay`` to decompress selected proofs, check them with ``drat-trim``,
emit LRAT, and check that with ``cake_lpr``.  ``--replay all`` performs the full
81-proof replay and therefore needs substantial time and scratch space.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Pair:
    logical_name: str
    proof_path: str
    proof_sha256: str
    cnf_path: Path
    cnf_sha256: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pairs() -> list[Pair]:
    frontier = json.loads((REPO / "data/frontier.json").read_text())
    auxiliary = json.loads((REPO / "data/auxiliary.json").read_text())
    extensions = json.loads((REPO / "data/extensions.json").read_text())
    pairs: list[Pair] = []

    for name, record in sorted(frontier.items()):
        cert = record["certificate"]
        encoding = cert["checked_encoding"]
        proof = f"frontier/{encoding}/{name}.drat.gz"
        cnf = (
            REPO / "data/cnf-checked/s-r0-2.kmtotalizer.cnf"
            if name == "s-r0-2"
            else REPO / f"build/cnf/{name}.cnf"
        )
        pairs.append(
            Pair(
                f"frontier/{name}",
                proof,
                cert["drat_gz_sha256"],
                cnf,
                cert["checked_cnf_sha256"],
            )
        )

    for name, record in sorted(auxiliary.items()):
        pairs.append(
            Pair(
                f"auxiliary/{name}",
                f"auxiliary/{name}.drat.gz",
                record["drat_gz_sha256"],
                REPO / f"build/cnf-aux/{name}.cnf",
                record["cnf_sha256"],
            )
        )

    for digest, record in sorted(extensions.items()):
        short = digest[:16]
        pairs.append(
            Pair(
                f"extension/{short}",
                f"extension/{short}.drat.gz",
                record["drat_gz_sha256"],
                REPO / f"build/cnf-ext/ext-{digest[:12]}.cnf",
                record["cnf_sha256"],
            )
        )
    return pairs


class Deposit:
    def __init__(self, path: Path):
        self.path = path
        self.tar: tarfile.TarFile | None = None
        if path.is_dir():
            self.index = json.loads((path / "index.json").read_text())
        else:
            self.tar = tarfile.open(path, "r")
            member = self.tar.extractfile("index.json")
            if member is None:
                raise ValueError("certificate tar has no index.json")
            self.index = json.load(member)
        self.index_by_name = {entry["name"]: entry for entry in self.index}

    def copy_compressed(self, relative: str, destination: Path) -> None:
        if self.tar is None:
            shutil.copyfile(self.path / relative, destination)
            return
        member = self.tar.extractfile(relative)
        if member is None:
            raise ValueError(f"certificate tar has no {relative}")
        with destination.open("wb") as out:
            shutil.copyfileobj(member, out, 1024 * 1024)

    def close(self) -> None:
        if self.tar is not None:
            self.tar.close()


def verdict(output: str, expected: str) -> bool:
    return expected in output.replace("\r", "").splitlines()


def run_checked(command: list[str], expected: str) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    output = completed.stdout + completed.stderr
    if completed.returncode != 0 or not verdict(output, expected):
        sys.stderr.write(output[-4000:])
        raise RuntimeError(f"missing exact verdict {expected!r}: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deposit", type=Path, help="certificate directory or .tar")
    parser.add_argument(
        "--replay",
        nargs="*",
        metavar="NAME",
        help="logical names to replay, or 'all' (default: mapping audit only)",
    )
    parser.add_argument("--drat-trim", default="drat-trim")
    parser.add_argument("--cake-lpr", default="cake_lpr")
    parser.add_argument("--work", type=Path, help="scratch directory (default: temporary)")
    args = parser.parse_args()

    pairs = load_pairs()
    deposit = Deposit(args.deposit)
    failures: list[str] = []
    expected_proofs = {pair.proof_path for pair in pairs}
    indexed_proofs = {entry["name"] for entry in deposit.index}
    if expected_proofs != indexed_proofs:
        failures.append(
            f"proof inventory differs: missing={sorted(expected_proofs - indexed_proofs)}, "
            f"extra={sorted(indexed_proofs - expected_proofs)}"
        )

    for pair in pairs:
        entry = deposit.index_by_name.get(pair.proof_path)
        if entry is None or entry.get("sha256_gz") != pair.proof_sha256:
            failures.append(f"{pair.logical_name}: proof hash/index mismatch")
        if not pair.cnf_path.is_file():
            failures.append(f"{pair.logical_name}: missing CNF {pair.cnf_path.relative_to(REPO)}")
        elif sha256(pair.cnf_path) != pair.cnf_sha256:
            failures.append(f"{pair.logical_name}: CNF hash mismatch")

    if failures:
        print("\n".join(f"FAILED: {failure}" for failure in failures), file=sys.stderr)
        deposit.close()
        return 1
    print(f"MAPPED: {len(pairs)}/81 proof objects to exact checked CNFs")

    if args.replay is None:
        deposit.close()
        return 0

    selected = pairs if args.replay == ["all"] else [
        pair for pair in pairs if pair.logical_name in set(args.replay)
    ]
    if len(selected) != (len(pairs) if args.replay == ["all"] else len(set(args.replay))):
        known = {pair.logical_name for pair in pairs}
        print(f"unknown replay name(s): {sorted(set(args.replay) - known)}", file=sys.stderr)
        deposit.close()
        return 2

    tools = [shutil.which(args.drat_trim), shutil.which(args.cake_lpr)]
    if any(tool is None for tool in tools):
        print("drat-trim and cake_lpr must be on PATH (or passed explicitly)", file=sys.stderr)
        deposit.close()
        return 2

    parent = args.work
    with tempfile.TemporaryDirectory(dir=parent) as scratch:
        scratch_path = Path(scratch)
        for index, pair in enumerate(selected, 1):
            gz_path = scratch_path / "proof.drat.gz"
            drat_path = scratch_path / "proof.drat"
            lrat_path = scratch_path / "proof.lrat"
            deposit.copy_compressed(pair.proof_path, gz_path)
            if sha256(gz_path) != pair.proof_sha256:
                raise RuntimeError(f"{pair.logical_name}: compressed proof hash mismatch")
            with gzip.open(gz_path, "rb") as source, drat_path.open("wb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            run_checked(
                [tools[0], str(pair.cnf_path), str(drat_path), "-L", str(lrat_path)],
                "s VERIFIED",
            )
            run_checked([tools[1], str(pair.cnf_path), str(lrat_path)], "s VERIFIED UNSAT")
            gz_path.unlink()
            drat_path.unlink()
            lrat_path.unlink()
            print(f"VERIFIED: {pair.logical_name} ({index}/{len(selected)})")

    deposit.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
