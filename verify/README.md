# Independent audits

This directory holds the second-implementation checks on the lower bound: work
whose purpose is to re-derive a claim the main pipeline already makes, from an
independent implementation, so that agreement means something.

It has two kinds of content, and the difference matters when reading it.

## 1. Live — runs from this repository

| file | role |
| --- | --- |
| `independent_seq_encoder.py` | Clean-room sequential-counter `EQUALS` encoder. Imports nothing outside the standard library, and in particular no PySAT. Written from Sinz, *Towards an optimal CNF encoding of Boolean cardinality constraints*, CP 2005, LNCS 3709, pp. 827–831. |

It is imported by [`bin/cross_check_encoder.py`](../bin/cross_check_encoder.py),
which is the runnable form of the three CNF audits below:

```bash
make cross-check
```

That rebuilds **all 81 instances** — 47 frontier, 14 auxiliary, 20 extension —
with the clean-room encoder and compares each against the SHA-256 published in
`data/frontier.json`, `data/auxiliary.json` and `data/extensions.json`, i.e. the
bytes the deposited certificates were issued against. It also compares PySAT's
80,360 cardinality clauses against the clean-room ones clause by clause. Takes
about three minutes; writes `build/cross-check.json`.

Why this exists: `src/c1264/encode.py` is the artifact's declared trust root, and
one step inside it — the exact-degree cardinality constraint — is delegated to
`pysat.card.CardEnc.equals`. The cross-check removes that library from the chain.
It does **not** make the encoder verified: both implementations are unverified
Python, and a shared misreading of the combinatorial claim would survive both.
See `docs/PROOF-MAP.md` §3 for what is and is not discharged.

## 2. Archived — audit records from the campaign

The remaining six scripts were run during the campaign against the preserved
working tree, and they hardcode its path
(`R = Path("/Users/Krug/c1264-ledger-preserved")`) and read directories that are
not part of this deposit (`completeness/`, `work/`, `final/`). **They will not run
here, by design**: they audit the campaign's own intermediate files, most of
which are gigabytes of proof objects. They are deposited as the record of what
was checked and what came back, and each is paired with the JSON verdict it
produced. For the three that audit CNF bytes, `bin/cross_check_encoder.py`
supersedes them with a version that runs from this repository alone.

| script | verdict file | result |
| --- | --- | --- |
| `independent_cnf_audit.py` | `independent-cnf-audit.json` | 47 frontier CNFs, `ok: 47`, `bad: []` — superseded by `bin/cross_check_encoder.py` |
| `independent_aux_audit.py` | `independent-aux-audit.json` | 14 auxiliary CNFs, `ok: 14`, `bad: []` — superseded |
| `independent_extension_audit.py` | `independent-extension-audit.json` | 20 extension CNFs, `ok: 20`, `bad: []` — superseded |
| `independent_structure.py` | `independent-structure.json` | group order 3840 re-derived; root orbit sizes `[10, 32, 60, 80, 120, 160]` summing to 462; 3 orbits lie entirely through point 1 and 0 straddle it; secondary and tertiary counts re-derived by orbit–stabiliser |
| `independent_witness_blocker.py` | `independent-witness-blocker.json` | the 41-block design's link is a 20-block cover with degree vector `10, 9^10`; `blocker-20.cnf` is 15,120 distinct all-negative width-20 clauses forming exactly 20 orbits |
| `uniqueness_orbit.py` | `uniqueness-orbit.json` | orbit size 166,320 = 11!/240, of which 15,120 have a degree-10 point 1; `normalised_equals_blocked: true`, so the blocker blocks exactly that set |

Five further verdict files have no script here — they were produced by ad-hoc
analysis during the campaign and are kept for the same reason:

| verdict file | result |
| --- | --- |
| `independent-branch-space.json` | branch space independently derived as 247, matching the campaign's claim; 47 frontier nodes are distinct branches (33 tertiary, 6 r0, 8 r1) |
| `independent-branch-space-corrected.json` | see below |
| `independent-region-completeness.json` | `VERDICT_ALL_REGIONS_COMPLETE: true`; for every region, the orbits negated by a tail instance are a subset of the orbits individually closed by a solved UNSAT job |
| `independent-tail-attribution.json` | per-region attribution of which tail closes which orbits |
| `independent-cnf-semantics.json` | for each tail instance, the combinatorial meaning of its units checked against the region it claims to close |

### The r1 over-count

`independent-branch-space-corrected.json` records a correction to the campaign's
own bookkeeping, and it is stated here rather than buried:

> `finding: "branch tree is COMPLETE; campaign over-counted the r1 region"`

The campaign reported 247 branches, of which 68 in the r = 1 region. The true
number of legal r = 1 secondary orbits is **60**. The cause: the secondary orbits
were enumerated on a pool that included root-orbit-0 blocks, which the r = 1
canonical constraint (no orbit-0 block present) forbids. The consequence is that
16 individual r1 jobs collapse onto 12 distinct legal orbits — four were
duplicates.

This direction of error is harmless: a **superset** of the required branches was
solved, so no branch was left open. The file records both
`VERDICT_frontier_completeness_REDERIVED: true` and
`VERDICT_no_branch_left_open: true`, and the corrected partition is
122 tertiary + 38 r0-secondary + 60 r1-secondary, with r ≥ 2 closed by the single
symmetry-free instance `r2plus-b20`. A referee comparing the paper's branch
arithmetic against this file will find the discrepancy; it is a counting error in
the write-up of the case analysis, not a gap in it.
