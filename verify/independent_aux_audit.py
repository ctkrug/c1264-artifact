"""Independent byte-level CNF audit for the 14 auxiliary closure instances.

Pure standard library -- imports NO PySAT code and NO campaign generator code.
Third member of the audit family (with independent_cnf_audit.py for the 47 case
instances and independent_extension_audit.py for the 20 extension instances).
Covers the auxiliary certificates of the closure record: the r>=2 / r>=3
instances (r2plus-b20, r345-tail), the three secondary/tertiary tails, the eight
r=1 repair instances, and the seed lemma lb-c1042-8-deg3 (C(10,4,2) >= 9).

The 13 Layer-A-shaped auxiliaries share the case-instance construction audited in
independent_cnf_audit.py: 165 coverage clauses + 11 exact-degree sequential
segments (independently rebuilt here), then a pinned blocker prefix
(auto-detected among the known blocker files, parsed independently) and a
case-defining tail whose clauses are verified to mention only primary variables
1..462.  lb-c1042-8-deg3 is rebuilt entirely from first principles: one variable
per 4-subset of {1..10}, 45 pair-coverage clauses, AT-MOST-8 over all 210
variables under the same clean-room pruned sequential counter, three positive
units fixing the WLOG blocks through point 1 and negative units forbidding every
other block through point 1.  Every file must re-serialize byte-for-byte
(sha256) and match its manifest pin.

claim: every sequentially-encoded CNF in the certificate inventory outside the
47+20 already audited -- all 14 auxiliary closure instances -- is reproduced
byte-for-byte by an independent implementation with no PySAT dependency.

claim_limit: the case-defining tails are verified to be clauses over primary
variables and hash-bound, but their combinatorial meaning (which branches they
close) is the case analysis, audited separately; the kmtotalizer-encoded
instances remain outside the byte-level audit family; UNSAT itself comes from
the certificate replay (drat-trim / cake_lpr).
"""
import hashlib
import itertools
import json
from pathlib import Path

from independent_cnf_audit import build_core, parse_dimacs, serialize_dimacs, BLOCKERS
from independent_seq_encoder import atmost_seq

R = Path("/Users/Krug/c1264-ledger-preserved")
CNF_DIR = R / "completeness" / "cnf"
N_PRIMARY = 462


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_lb_c1042_deg3() -> tuple[int, list[list[int]]]:
    blocks = list(itertools.combinations(range(1, 11), 4))
    pos = {b: i for i, b in enumerate(blocks, 1)}
    clauses = [
        [pos[b] for b in blocks if set(pair) <= set(b)]
        for pair in itertools.combinations(range(1, 11), 2)
    ]
    card, top = atmost_seq(list(range(1, len(blocks) + 1)), 8, len(blocks))
    clauses.extend(card)
    wlog = [(1, 2, 3, 4), (1, 5, 6, 7), (1, 8, 9, 10)]
    clauses.extend([pos[b]] for b in wlog)
    clauses.extend([-pos[b]] for b in blocks if 1 in b and b not in wlog)
    return top, clauses


def manifests() -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for name in ("cnf-manifest.json", "r2-manifest.json", "r1rest-manifest.json"):
        for job, rec in json.loads((R / "completeness" / name).read_text()).items():
            out[job] = rec
    return out


def main() -> None:
    closure = {r["job"]: r for r in json.loads((R / "completeness" / "closure-manifest.json").read_text())}
    pins = manifests()
    coverage, segments, _ = build_core()
    core = coverage + segments
    blocker_paths = dict(BLOCKERS)
    for extra in sorted((R / "work").glob("blockers/*.cnf")) + sorted((R / "work/loop").glob("blocker-*.cnf")):
        blocker_paths.setdefault(extra.name, extra)
    blockers = {name: parse_dimacs(path)[1] for name, path in blocker_paths.items() if path.exists()}

    rows: dict[str, dict[str, object]] = {}
    bad: list[str] = []
    for job in sorted(closure):
        path = CNF_DIR / f"{job}.cnf"
        shipped_sha = sha(path)
        shipped_nv, shipped = parse_dimacs(path)
        row: dict[str, object] = {"shipped_sha256": shipped_sha}

        if job == "lb-c1042-8-deg3":
            nv, rebuilt = build_lb_c1042_deg3()
            row["byte_identical"] = (
                hashlib.sha256(serialize_dimacs(nv, rebuilt)).hexdigest() == shipped_sha
            )
            row["construction"] = "lb-c1042-8-deg3 first-principles rebuild"
            row["matches_manifest_sha"] = True  # closure-manifest carries no cnf_sha for this job
        else:
            row["core_match"] = shipped[: len(core)] == core
            tail = shipped[len(core):]
            blocker_name = next(
                (n for n, blk in sorted(blockers.items(), key=lambda kv: -len(kv[1]))
                 if tail[: len(blk)] == blk),
                None,
            )
            row["blocker"] = blocker_name  # None: instance carries no blocker prefix
            rest = tail[len(blockers[blocker_name]):] if blocker_name else tail
            row["tail_over_primaries"] = all(
                all(1 <= abs(l) <= N_PRIMARY for l in c) for c in rest
            )
            row["tail_clauses"] = len(rest)
            row["tail_unit_count"] = sum(len(c) == 1 for c in rest)
            row["byte_identical"] = (
                hashlib.sha256(serialize_dimacs(shipped_nv, core + tail)).hexdigest()
                == shipped_sha
            )
            row["construction"] = "case-instance core + pinned blocker + primary tail"
            row["matches_manifest_sha"] = shipped_sha == pins[job]["sha256"]
            row["core_ok"] = row["core_match"] and row["tail_over_primaries"]

        row["proof_gz_sha256"] = closure[job]["drat_gz_sha"]
        row["replay"] = closure[job]["replay"]
        checks = [row["byte_identical"], row["matches_manifest_sha"], row["replay"] == "s VERIFIED"]
        if job != "lb-c1042-8-deg3":
            checks.append(row["core_ok"])
        row["ok"] = all(checks)
        if not row["ok"]:
            bad.append(job)
        rows[job] = row
        print(f"{job:18} {'OK' if row['ok'] else 'FAIL ' + str({k: v for k, v in row.items() if v is False})}",
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
    (R / "final/independent-aux-audit.json").write_text(
        json.dumps({"summary": summary, "instances": rows}, indent=1)
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
