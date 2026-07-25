# Proof map: claim → script → artifact

Every computational claim the paper makes, the script in this repository that
checks it, and the deposited object it is checked against. A referee should be
able to work down this table without reading the source in any other order.

Section numbers refer to the paper; adjust if the sections are renumbered.

## 0. What was known before

| Claim | Script | Artifact | Cost |
|---|---|---|---|
| The best known bounds on entry were `40 ≤ C(12,6,4) ≤ 41`, so the contribution is the lower bound | `tests/test_prior_art.py` — reads `size: 41`, `low_bd: 40` straight out of the table | `data/coverdata-2026-07-24.json` (snapshot of the best-known-values table, 9,482 entries) | instant |
| The 41-block upper bound is attributed prior art, not claimed here | `…::test_the_upper_bound_of_41_is_prior_art` — the table's own attribution (a JCD article, 1996) | same | instant |
| The warm-up instance's target, `C(10,4,2) = 9`, is a known value | `…::test_the_warmup_instance_agrees_with_the_table` | same | instant |

## 1. Upper bound, C(12,6,4) ≤ 41

| Claim | Script | Artifact | Cost |
|---|---|---|---|
| The 41 stated blocks cover all 495 quadruples | `bin/verify_cover.py` | `data/design-stored-41.txt` | instant |
| Same, by an unrelated implementation | `bin/verify_cover.c` (nested-loop scan, no shared code) | same | instant |
| The second published design also covers | both checkers | `data/design-lajolla-41.txt` | instant |
| The two designs are the same design relabelled | `tests/test_cover.py::test_the_two_designs_are_read_identically` | both | instant |
| The checker rejects plausible corruptions | `tests/test_cover.py` (dropped block, duplicated block, out-of-range point, repeated point, swapped point) | — | instant |
| 41 blocks is *not* a Steiner-like exact cover | `tests/test_cover.py::test_coverage_multiplicities_are_not_all_one` — multiplicity histogram `{1: 405, 2: 75, 4: 15}` | — | instant |

The last row exists because "optimal" is easy to misread as "each quadruple
covered once". 41 blocks contribute `41·C(6,4) = 615` covered slots to 495
quadruples, so 120 slots are necessarily surplus; any counting argument that
assumed exact coverage would be wrong.

## 2. Structural setup

| Claim | Script | Cost |
|---|---|---|
| The symmetry group is `C₂ ≀ S₅`, order `3840 = 2⁵·5!`, and is closed | `tests/test_structure.py`, `group.assert_group_order()` | seconds |
| 462 primary variables = the 5-subsets of `{1..11}`, in `itertools.combinations` order, variable `i` ↔ `BLOCKS[i-1]` | `tests/test_structure.py::test_positions_are_a_bijection_onto_1_through_462` | seconds |
| Triple coverage is 165 positive clauses of width `C(8,2) = 28` | `tests/test_structure.py::test_coverage_has_one_clause_per_triple_and_all_are_positive` | seconds |
| Exact degrees (10, then nine 9s) imply exactly 20 blocks — no global cardinality constraint is used | `blocks.implied_block_count()`, `tests/test_structure.py::test_degree_sequence_implies_exactly_twenty_blocks` | seconds |
| The 6 root orbits have sizes `(80, 120, 10, 32, 160, 60)` and partition all 462 blocks | `orbits.assert_root_orbits_partition()` | seconds |
| Root orbits 0–2 are exactly the 210 blocks through point 1 | `tests/test_structure.py::test_first_three_root_orbits_are_exactly_the_blocks_through_point_one` | seconds |
| Secondary and tertiary orbits partition their eligible domains | `tests/test_structure.py` (parametrised over all 6 roots) | seconds |

## 3. The encoder

`src/c1264/encode.py` is the only place a mathematical claim becomes a file. If it
is wrong, every certificate certifies the wrong thing, so it gets its own checks:

| Claim | Script | Cost |
|---|---|---|
| `CardEnc.equals` really encodes "exactly k of these" | `bin/encoder_sanity.py` — brute-forces all `2ⁿ` assignments for small `(n,k)` under both translations and compares the accepted set to the weight-`k` assignments | ~30 s |
| PySAT's cardinality clauses are the *published* encoding, not one library's private output | `bin/cross_check_encoder.py` — rebuilds all 81 instances with a clean-room Sinz-2005 encoder that imports no PySAT, and requires byte equality with the published hashes | ~3 min |
| A node built under either translation states the *same* problem | `bin/check_encoding_provenance.py` — equal `non_cardinality_core_sha256`, unequal file hashes | ~3 min |
| The coverage/degree segments occupy disjoint auxiliary variable ranges | assertions inside `encode.build_cnf` and `extend.build_extension` | per build |

`make cross-check` re-derives every one of the 81 deposited instances, byte for
byte, from an implementation written directly from Sinz's 2005 paper with no
PySAT dependency, and finds the 80,360 cardinality clauses clause-for-clause
identical (`verify/README.md`, `build/cross-check.json`).

The translation from combinatorial claim to clauses is checked by §2 (the
combinatorial structure, against brute-force ground truth) and §5–6 (the case
analysis), and `src/c1264/encode.py`, the ~200-line module where claim becomes
clause, is written to be read end to end.

## 4. Lower bound, Layer A: the 47-node case tree

| Claim | Script | Artifact |
|---|---|---|
| Each of the 47 leaves regenerates byte-identically from `(blocker, leaf)` | `bin/gen_instances.py --out build/cnf` | `data/frontier.json` → `cnf_sha256` |
| Each of the 47 is UNSAT, with a `drat-trim`-replayed proof | manifest `certificate.drat_trim_verdict` = `s VERIFIED`; re-derive with `bin/certify.sh` | `certificate.drat_raw_sha256`, `drat_gz_sha256` |
| Each of the 47 is `cake_lpr`-checked | manifest `certificate.cake_lpr_verdict` = `s VERIFIED UNSAT` | `certificate.lrat_sha256` |
| Each of the 47 was *also* refuted under the second encoding | manifest `certificate.second_encoding` | `second_encoding.drat_raw_sha256` |
| The tree's 47 leaves are 6 `s-r0-*` + 8 `s-r1-*` + 33 `t-*` | `tests/test_manifests.py::test_frontier_node_names_match_the_case_tree` | — |

**Node `s-r0-2`.** Its `cake_lpr` certificate is against the `kmtotalizer`
instance, not the sequential one: the sequential proof was 2.2 GB raw, was
replayed by `drat-trim`, and was then discarded under the campaign's disk budget
without being hashed. The substitution is sound because both encodings share
`non_cardinality_core_sha256 = fdfaac8a…` — they are two translations of one
problem — and the `kmtotalizer` instance has the full
solve → `drat-trim` → `cake_lpr` chain. The node's `certificate.note` records
this, and `tests/test_manifests.py` pins it. Anyone re-running tier 3 gets a
sequential certificate for it too.

## 5. Lower bound: exhaustiveness of the case tree

The tree enumerates leaves; the 14 auxiliary instances close everything it does
not enumerate. All are in `data/auxiliary.json` and rebuild via
`bin/gen_auxiliary.py`.

| Instance(s) | Closes |
|---|---|
| `r345-tail` | root orbits 3–5: every block through point 1 is forbidden, so point 1 cannot reach degree 10 |
| `r2plus-b20` | root orbits 2–5 with the 20-orbit blocker conjoined; symmetry-free (only negative units) |
| `r0-sec-tail` | secondary indices at and above the live limit under root 0 |
| `r1-sec-tail` | the same under root 1 |
| `r0s0-ter-tail` | tertiary indices above 32 under `(r=0, s=0)`, i.e. beyond `t-32` |
| `r1-gap-s{6,7,9,10,11,12,13,14}` (8) | secondary indices under root 1 that the live frontier skips |
| `lb-c1042-8-deg3` | nothing in the tree: a warm-up establishing `C(10,4,2) ≥ 9` (no eight 4-subsets of a 10-set cover all 45 pairs), kept because it exercises the whole pipeline on a known value; its full argument is in the docstring of `auxiliary.lower_bound_c1042_deg3` |

That these together with the 47 leaves form a *partition* is checked, not
asserted:

* `tests/test_auxiliary.py::test_gap_and_tail_indices_together_close_the_r1_level`
  — every secondary index below the tail limit is either a live node or a gap
  instance.
* `…::test_gap_indices_are_disjoint_from_the_live_frontier` — no branch is claimed
  twice.
* `…::test_r345_tail_forbids_every_block_through_point_one` — the 210 forbidden
  blocks are exactly those meeting point 1.
* `…::test_r2plus_region_is_the_complement_of_the_first_two_orbits`.
* `…::test_region_instances_assert_no_canonical_block` — the two region instances
  contain only *negative* units, so they do not depend on the canonicalisation
  they help justify.

`root-tail` was built during the campaign but never certified; it is deliberately
absent, and `tests/test_manifests.py::test_root_tail_is_absent_from_the_auxiliary_inventory`
keeps it absent. The region it would have covered is closed by `r2plus-b20` plus
`r345-tail`.

## 6. Lower bound, Layer B: licence to block 20 link orbits

This is the step a sceptical referee should read first, because it is where a
*search* result enters a *deductive* argument.

| Claim | Script | Artifact |
|---|---|---|
| Each blocker is a set of clauses of exactly 20 distinct negative literals | `orbits.parse_blockers` (strict; rejects positive literals, wrong widths, header mismatch) | `data/blockers/*.cnf` |
| The blocked links form complete group orbits — nothing is asserted about some labellings and not others | `bin/audit_blocker.py`, `blocker.orbit_partition` (raises if an orbit leaves the blocked set) | 9 / 13 / 20 orbits |
| `\|orbit\| · \|stabiliser\| = 3840` for every orbit | same | — |
| The staged blockers are a chain: 3776 ⊂ 6096 ⊂ 15120 links | `tests/test_blocker.py::test_staged_blockers_are_nested` | — |
| Every blocked orbit has a refuted extension instance | `bin/audit_blocker.py` check 4 | `data/extensions.json` |
| Each extension instance regenerates byte-identically | `bin/gen_extensions.py` | `cnf_sha256` |
| Each extension instance has **no unit clauses** | `extend.build_extension` assertion; `tests/test_extend.py::test_extension_instance_has_no_unit_clauses` | — |
| Every residual coverage clause has width `C(7,2) = 21` and never mentions the distinguished point | `extend.build_extension`; `tests/test_extend.py` | — |
| The deposited witness really lies in the orbit it claims | `bin/audit_blocker.py` recomputes each witness's canonical digest rather than trusting the manifest | `data/links/link-*.txt` |

**The eight non-canonical witnesses.** Twelve of the 20 deposited witnesses are
the lexicographically least representative of their orbit; eight are not, because
the campaign solved whichever labelling its search produced. That is sound — the
extension problem is invariant under the group, so refuting any member refutes the
orbit — but it means the exact witness text has to be deposited to reproduce the
bytes the certificates were issued against. It is deposited
(`data/links/`), the count is pinned
(`tests/test_extend.py::test_eight_witnesses_are_non_canonical`), and orbit
membership is recomputed for all 20 rather than assumed.

## 7. Putting it together

Tier 2 (`make regenerate`) establishes: the 81 files the certificates certify are
exactly the 81 files this source produces; the case analysis over them is a
partition; and the blockers are licensed. Tier 3 (`make certify`) re-derives the
81 refutations. Together those give `C(12,6,4) ≥ 41`; §1 gives `≤ 41`.

## 8. Reading order for a referee with one hour

1. `src/c1264/encode.py` — where claim becomes clause, ~200 lines. Everything else is scaffolding.
2. `src/c1264/extend.py` module docstring — why Layer B is independent of Layer A.
3. `./reproduce.sh` — run it; a few minutes.
4. `make cross-check` — the same 81 instances rebuilt without PySAT; three minutes.
   `verify/README.md` says what that does and does not settle, and records the
   campaign's own r1 branch-count correction.
5. `bin/audit_blocker.py --json build/audit.json` — the one search-derived input, audited.
6. `bin/certify.sh build/cnf-ext/ext-<any>.cnf` — one extension node end to end;
   the small ones finish in minutes and exercise the whole
   solve → `drat-trim` → `cake_lpr` chain.
