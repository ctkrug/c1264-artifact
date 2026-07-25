"""Independent byte-level CNF audit for the 20 fixed-link extension instances E(L).

Pure standard library -- imports NO PySAT code and NO campaign generator code.
Companion to independent_cnf_audit.py (which covers the 47 Layer-A ledger CNFs);
together they discharge the residual encoding-library assumption for every CNF
in the primary certificate chain.

Each extension instance asks: can the fixed optimal link L at a degree-20 point be
extended to a 40-block covering of the remaining structure?  Its CNF is built from
the link witness alone:

  1. primary variables 1..462 = the co-blocks (6-subsets of {2..12}, i.e. blocks
     avoiding the distinguished point 1), in itertools.combinations order;
  2. residual coverage -- for each 4-subset T of {1..12} NOT covered by a link
     block, the width-21 clause "some chosen co-block contains T" (4-subsets
     through point 1 are all link-covered, so every clause is over co-blocks);
  3. 55 pair segments -- for each pair {q,r} of {2..12},
     EQUALS(126 co-blocks containing the pair, target - deg_L(q,r)) with
     target = 10 on the fixed perfect matching {1,2},{3,4},...,{11,12} and 9
     otherwise, under the same documented pruned sequential-counter construction
     (independent_seq_encoder.py, clean-room from Sinz 2005), auxiliaries stacked
     after variable 462 in pair order.

The audit re-derives each CNF from its link witness with the clean-room encoder,
re-serializes in DIMACS, and requires sha256 equality with the shipped file and
with the pinned audit record (which also pins the link witness and DRAT proof).

claim: every clause of all 20 extension CNFs is reproduced byte-for-byte from the
published construction by an independent implementation with no PySAT dependency,
so the encoding-library assumption is discharged for Layer B as well.

claim_limit: this audits the CNFs, not the proofs -- UNSAT of each instance comes
from the certificate replay (cake_lpr).  That the 20 links exhaust all optimal
links up to symmetry is the blocker-orbit closure, audited separately
(blocker-20.json / independent-witness-blocker.json).
"""
import hashlib
import itertools
import json
from pathlib import Path

from independent_seq_encoder import equals_seq

R = Path("/Users/Krug/c1264-ledger-preserved")
MATCHING = {(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12)}
CO_BLOCKS = list(itertools.combinations(range(2, 13), 6))  # 462 co-blocks


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_link(path: Path) -> list[tuple[int, ...]]:
    """Read a 20-block C(11,5,3)-with-exact-degrees link witness; lift the point
    set {1..11} to {2..12} and adjoin the distinguished point 1 to every block."""
    blocks = [tuple(int(t) for t in line.split()) for line in path.read_text().splitlines() if line.strip()]
    assert len(blocks) == 20 == len(set(blocks)) and all(len(b) == 5 for b in blocks)
    triples = set().union(*(set(itertools.combinations(b, 3)) for b in blocks))
    assert triples == set(itertools.combinations(range(1, 12), 3))
    assert sorted(sum(p in b for b in blocks) for p in range(1, 12)) == [9] * 10 + [10]
    return [(1, *(p + 1 for p in b)) for b in blocks]


def build(link_path: Path) -> tuple[int, list[list[int]], int]:
    lifted = load_link(link_path)
    clauses: list[list[int]] = []
    coverage = 0
    for target in itertools.combinations(range(1, 13), 4):
        if any(set(target) <= set(b) for b in lifted):
            continue
        clause = [i for i, b in enumerate(CO_BLOCKS, 1) if set(target) <= set(b)]
        assert clause, target
        clauses.append(clause)
        coverage += 1
    top = len(CO_BLOCKS)
    for pair in itertools.combinations(range(2, 13), 2):
        mult = sum(set(pair) <= set(b) for b in lifted)
        bound = (10 if pair in MATCHING else 9) - mult
        lits = [i for i, b in enumerate(CO_BLOCKS, 1) if set(pair) <= set(b)]
        cls, top = equals_seq(lits, bound, top)
        clauses.extend(cls)
    return coverage, clauses, top


def serialize_dimacs(nv: int, clauses: list[list[int]]) -> bytes:
    lines = [f"p cnf {nv} {len(clauses)}"]
    lines.extend(" ".join(map(str, c + [0])) for c in clauses)
    return ("\n".join(lines) + "\n").encode("ascii")


def instances() -> dict[str, dict[str, Path]]:
    out: dict[str, dict[str, Path]] = {}
    base9 = json.loads((R / "work/base9/base9-audit.json").read_text())
    for name in base9:
        out[name] = {
            "cnf": R / "work/base9/cnf" / f"{name}.cnf",
            "link": R / "work/base9/cnf" / f"{name}.link.txt",
            "record": base9[name],
        }
    residual = json.loads((R / "work/residual-audit.json").read_text())
    for name in residual:
        loc = "work/residual" if name.endswith("-canon") else "work/loop/residual"
        wit = "work/newlinks" if name.endswith("-canon") else "work/loop/newlinks"
        out[name] = {
            "cnf": R / loc / f"{name}.cnf",
            "link": R / wit / f"{name}.txt",
            "record": residual[name],
        }
    for extra in sorted(R.glob("work/loop-audit-*.json")):
        rec = json.loads(extra.read_text())
        for name in rec:
            out[name] = {
                "cnf": R / "work/loop/residual" / f"{name}.cnf",
                "link": R / "work/loop/newlinks" / f"{name}.txt",
                "record": rec[name],
            }
    assert len(out) == 20, sorted(out)
    return out


def main() -> None:
    rows: dict[str, dict[str, object]] = {}
    bad: list[str] = []
    for name, spec in sorted(instances().items()):
        record = spec["record"]
        link_sha = sha(spec["link"])
        shipped_sha = sha(spec["cnf"])
        coverage, clauses, nv = build(spec["link"])
        rebuilt_sha = hashlib.sha256(serialize_dimacs(nv, clauses)).hexdigest()
        row = {
            "link_sha256": link_sha,
            "link_matches_record": link_sha == record["link_sha256"],
            "shipped_sha256": shipped_sha,
            "matches_record_sha": shipped_sha == record["cnf_sha256"],
            "byte_identical": rebuilt_sha == shipped_sha,
            "variables": nv,
            "clauses": len(clauses),
            "coverage_clauses": coverage,
            "vars_match": nv == record["variables"],
            "clauses_match": len(clauses) == record["clauses"],
            "proof_gz_sha256": record["proof_gz_sha256"],
            "ok": None,
        }
        row["ok"] = all(row[k] for k in (
            "link_matches_record", "matches_record_sha", "byte_identical",
            "vars_match", "clauses_match",
        ))
        if not row["ok"]:
            bad.append(name)
        rows[name] = row
        print(f"{name:28} {'OK' if row['ok'] else 'FAIL ' + str({k: v for k, v in row.items() if v is False})}",
              flush=True)

    summary = {
        "instances": len(rows),
        "ok": len(rows) - len(bad),
        "bad": bad,
        "claim": __doc__.split("claim: ")[1].split("claim_limit:")[0].strip(),
        "claim_limit": __doc__.split("claim_limit: ")[1].strip(),
        "encoder": "final/independent_seq_encoder.py (clean-room, Sinz 2005, no PySAT)",
        "encoder_sha256": sha(R / "final/independent_seq_encoder.py"),
        "auditor_sha256": sha(Path(__file__)),
    }
    out = {"summary": summary, "instances": rows}
    (R / "final/independent-extension-audit.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
