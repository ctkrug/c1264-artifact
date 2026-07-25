"""Independent byte-level CNF audit for the 47 frontier-node sequential CNFs.

Pure standard library -- imports NO PySAT code and NO campaign generator code.
The strategy: reconstruct the shipped CNF byte-for-byte from an explicitly
documented construction, so that no encoding library is trusted.

For each ledger node this script independently reconstructs, from first principles:

  1. the 165 coverage clauses  -- for each 3-subset T of {1..11}, the clause
     "some chosen 5-block contains T", blocks enumerated in itertools.combinations
     order and numbered 1..462;
  2. the 11 cardinality segments -- for each point p, EQUALS(deg(p) blocks, 10 if
     p==1 else 9) under the documented pruned sequential-counter construction
     (independent_seq_encoder.py, clean-room from Sinz 2005), auxiliaries stacked
     after variable 462 in segment order;

and then verifies against the shipped file that:

  3. the shipped clause list is exactly [coverage] + [segments] + [tail], where the
     tail consists of the pinned blocker file's clauses (parsed here independently)
     followed only by unit clauses over primary variables 1..462 (the branch and
     orbit-exclusion units);
  4. re-serializing the whole reconstruction in DIMACS format reproduces the shipped
     file BYTE-FOR-BYTE (sha256), and that hash equals both the provenance manifest's
     sequential_sha256 and the ledger's pinned cnf_sha256.

claim: every non-unit clause of every ledger CNF is reproduced byte-for-byte by an
independent implementation with no PySAT dependency; in particular the cardinality
blocks are exactly the published pruned sequential-counter encoding, so the residual
"encoding library" assumption is discharged for the primary certificate chain.

claim_limit: the branch/orbit-exclusion unit tails are verified to be unit clauses
over primary variables and hash-bound here, but WHICH units a node carries is the
branching structure, audited separately (independent-branch-space-corrected.json);
the kmtotalizer cross-check CNFs are outside this audit. UNSAT itself comes from the
certificate replay (cake_lpr), not from this file.
"""
import hashlib
import itertools
import json
from pathlib import Path

from independent_seq_encoder import equals_seq

R = Path("/Users/Krug/c1264-ledger-preserved")
CNF_DIR = R / "final" / "cnf"
BLOCKERS = {
    "catalog-9-blocking.cnf": R / "work/blockers/catalog-9-blocking.cnf",
    "catalog-13-blocking.cnf": R / "work/blockers/catalog-13-blocking.cnf",
    "blocker-20.cnf": R / "work/loop/blocker-20.cnf",
    "blocker-13.cnf": R / "work/loop/blocker-13.cnf",
}
N_PRIMARY = 462  # C(11,5)


def parse_dimacs(path: Path) -> tuple[int, list[list[int]]]:
    header = None
    clauses = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p cnf"):
            header = tuple(int(t) for t in line.split()[2:4])
            continue
        lits = [int(t) for t in line.split()]
        assert lits[-1] == 0, (path, line[:60])
        clauses.append(lits[:-1])
    assert header is not None and header[1] == len(clauses), (path, header, len(clauses))
    return header[0], clauses


def serialize_dimacs(nv: int, clauses: list[list[int]]) -> bytes:
    lines = [f"p cnf {nv} {len(clauses)}"]
    lines.extend(" ".join(map(str, c + [0])) for c in clauses)
    return ("\n".join(lines) + "\n").encode("ascii")


def build_core() -> tuple[list[list[int]], list[list[int]], int]:
    """Independently rebuild coverage clauses and the 11 cardinality segments."""
    blocks = list(itertools.combinations(range(1, 12), 5))
    positions = {block: index for index, block in enumerate(blocks, 1)}
    coverage = [
        [positions[b] for b in blocks if set(t) <= set(b)]
        for t in itertools.combinations(range(1, 12), 3)
    ]
    top = N_PRIMARY
    segments: list[list[int]] = []
    for point in range(1, 12):
        lits = [i for i, b in enumerate(blocks, 1) if point in b]
        cls, top = equals_seq(lits, 10 if point == 1 else 9, top)
        segments.extend(cls)
    return coverage, segments, top


def main() -> None:
    manifest = json.loads((R / "final" / "encoding-provenance.json").read_text())["nodes"]
    ledger = json.loads((R / "work" / "LEDGER-CHECKPOINT.json").read_text())["nodes"]
    coverage, segments, nv = build_core()
    blocker_clauses = {
        name: parse_dimacs(path)[1] for name, path in BLOCKERS.items() if path.exists()
    }

    rows: dict[str, dict[str, object]] = {}
    bad: list[str] = []
    for name in sorted(manifest):
        row: dict[str, object] = {}
        shipped_path = CNF_DIR / f"{name}-sequential.cnf"
        shipped_sha = hashlib.sha256(shipped_path.read_bytes()).hexdigest()
        shipped_nv, shipped = parse_dimacs(shipped_path)

        n_core = len(coverage) + len(segments)
        row["coverage_match"] = shipped[: len(coverage)] == coverage
        row["cardinality_match"] = shipped[len(coverage): n_core] == segments

        tail = shipped[n_core:]
        blk = blocker_clauses[manifest[name]["blocker_file"]]
        row["blocker_match"] = tail[: len(blk)] == blk
        units = tail[len(blk):]
        row["units_are_primary_units"] = all(
            len(c) == 1 and 1 <= abs(c[0]) <= N_PRIMARY for c in units
        )
        row["unit_count"] = len(units)
        row["units_sha256"] = hashlib.sha256(
            ("\n".join(" ".join(map(str, c)) for c in units) + "\n").encode()
        ).hexdigest()

        rebuilt = serialize_dimacs(max(nv, shipped_nv), coverage + segments + tail)
        rebuilt_sha = hashlib.sha256(rebuilt).hexdigest()
        row["byte_identical"] = rebuilt_sha == shipped_sha
        row["shipped_sha256"] = shipped_sha
        row["matches_provenance_sha"] = shipped_sha == manifest[name]["sequential_sha256"]
        row["matches_ledger_sha"] = shipped_sha == ledger[name]["cnf_sha256"]
        row["ok"] = all(
            row[k] for k in (
                "coverage_match", "cardinality_match", "blocker_match",
                "units_are_primary_units", "byte_identical",
                "matches_provenance_sha", "matches_ledger_sha",
            )
        )
        if not row["ok"]:
            bad.append(name)
        rows[name] = row
        print(f"{name:8} {'OK' if row['ok'] else 'FAIL '+str({k:v for k,v in row.items() if v is False})}",
              flush=True)

    summary = {
        "nodes": len(rows),
        "ok": len(rows) - len(bad),
        "bad": bad,
        "claim": __doc__.split("claim: ")[1].split("claim_limit:")[0].strip(),
        "claim_limit": __doc__.split("claim_limit: ")[1].strip(),
        "encoder": "final/independent_seq_encoder.py (clean-room, Sinz 2005, no PySAT)",
        "encoder_sha256": hashlib.sha256(
            (R / "final" / "independent_seq_encoder.py").read_bytes()
        ).hexdigest(),
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    out = {"summary": summary, "nodes": rows}
    (R / "final" / "independent-cnf-audit.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
