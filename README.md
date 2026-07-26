# C(12,6,4) = 41 — computational artifact

The covering number `C(12,6,4)` is the least number of 6-subsets of a 12-set such
that every 4-subset is contained in at least one of them. This repository is the
complete computational record of the proof that it equals 41:

    C(12,6,4) <= 41    an explicit 41-block design, checked by two independent programs
    C(12,6,4) >= 41    a symmetry-reduced case analysis, 81 SAT refutations, each
                       machine-checked by cake_lpr (a checker verified in HOL4)

Everything the argument depends on is either derived here from first principles or
deposited here as a hash-identified certificate. Nothing is taken on the word of a
solver: every refutation is a proof object that was replayed by `drat-trim` and
then re-checked by `cake_lpr`, whose own correctness is a theorem in HOL4.

## Quick start

```bash
shasum -c MANIFEST.sha256
pip install -r requirements.txt
./reproduce.sh
```

That takes about fifteen minutes, needs no SAT solver, and checks everything
except the refutations themselves. It prints each step's elapsed time as it goes
and ends by saying exactly which claims it did and did not establish. `make help`
lists the tiers separately, and `SKIP_CROSS_CHECK=1 ./reproduce.sh` drops the
three-minute clean-room re-encoding.

Two steps dominate: rebuilding all 47 frontier nodes under *both* cardinality
encodings for the provenance check (~6 min) and the clean-room cross-check
(~3 min). Everything else together is under four minutes. All wall-clock figures
here and in `make help` were measured on an Apple M-series laptop under CPython
3.14.6, single-threaded throughout; they are for calibration, not a contract.

## What the three tiers establish

| Tier | Command | Cost | Establishes |
|---|---|---|---|
| 1 | `make check` | ~2 min | `C(12,6,4) <= 41` completely; the group, the variable layout, the orbit partitions, and `CardEnc.equals` against ground truth |
| 2 | `make regenerate` | ~10 min | all 81 baseline CNF instances regenerate **byte for byte** from this source; the case analysis is exhaustive; the blockers are orbit-closed and licensed |
| 2b | `make cross-check` | ~3 min | the same 81 sequential baseline instances rebuilt by a clean-room encoder that imports no PySAT; byte-identical |
| 3 | `make certify` | CPU-days, ~200 GB scratch | the 81 refutations themselves, from scratch |

Tier 2 is the one that matters for a referee. A hash match there binds the source
to the published formulas. For 80 primary certificates the checked formula is
that sequential baseline. The largest case, `s-r0-2`, instead carries a
`cake_lpr` certificate for its kmtotalizer translation; that exact checked CNF is
deposited at `data/cnf-checked/s-r0-2.kmtotalizer.cnf`. The manifest also binds
both translations to the same non-cardinality core, and the sequential
translation was separately solved and accepted by `drat-trim`. Tier 2 checks
that the 47 case-tree nodes plus the 14 auxiliary instances genuinely cover
every branch.

After downloading the separate certificate archive, audit all 81 proof-to-CNF
pairings without replaying the large proofs:

```bash
python bin/replay_deposit.py /path/to/c1264-certificates-v1.0.0.tar
```

Add `--replay frontier/s-r0-1` for a representative full
DRAT-to-LRAT-to-`cake_lpr` replay, or `--replay all` for the complete campaign.

## The argument in one page

**Upper bound.** Two 41-block designs are deposited (`data/design-*-41.txt`;
they are relabellings of each other). `bin/verify_cover.py` verifies coverage by a
bitmask sweep, `bin/verify_cover.c` by a nested-loop membership scan with no
shared code. Both must print `VALID`.

**Lower bound.** Suppose a 40-block cover exists. Fix a point; its *link* is a
covering of all triples of the remaining 11 points by 5-subsets — a `C(11,5,3)`
instance with 462 candidate blocks. Exact per-point degrees (10 for one point,
9 for the rest) force the link to have exactly 20 blocks, with no cardinality
constraint needed. The stabiliser of that configuration is `C₂ ≀ S₅` of order
`3840 = 2⁵·5!`, which splits the 462 blocks into 6 orbits of sizes
`(80, 120, 10, 32, 160, 60)`.

Three things then have to be shown, and each is a layer of this artifact:

1. **Layer A — the case tree.** Branch on the orbit of the least block, then
   again, then again; 47 leaves survive as SAT instances, all refuted
   (`bin/gen_instances.py`).
2. **Exhaustiveness.** The branches the tree does *not* enumerate are closed by 14
   further instances — degree-region arguments, index gaps and level tails
   (`bin/gen_auxiliary.py`). Together with the 47 leaves these partition every
   case; `tests/test_auxiliary.py` checks the partition, it is not asserted.
3. **Layer B — the blockers.** The case tree is allowed to assume 20 specific link
   orbits do not occur. That is not free: for each of the 20, a *residual*
   instance asks whether that link extends to a 40-block cover, and each is
   refuted (`bin/gen_extensions.py`). In any hypothetical 40-block cover every
   point has one degree-10 partner and ten degree-9 partners, so the six
   degree-10 pairs form a perfect matching. After normalising that matching, each
   extension instance imposes 55 exact residual pair-degree equations: total
   degree 10 on the five matching edges among the 11 link points and 9 on every
   other pair, minus the multiplicity already contributed by the fixed link.
   The instances contain **zero unit clauses** because the link is substituted
   into those residual bounds. `bin/audit_blocker.py` checks that each blocker is
   a union of complete orbits and that every orbit has such a refutation.

## Layout

    reproduce.sh              one-command tier 1 + tier 2 + tier 2b
    Makefile                  the tiers as individual targets
    requirements.txt          exact pins; the hashes depend on them
    MANIFEST.sha256           a hash per deposited file: `shasum -c MANIFEST.sha256`.
                              A clone carries the source form (91 files); the
                              archival zip carries a longer one covering the
                              pre-generated CNFs it also ships.

    src/c1264/
      group.py                C2 wr S5, order 3840; orbits of blocks
      blocks.py               the 462 primary variables and their layout
      orbits.py               root/secondary/tertiary orbit partitions; blocker parsing
      encode.py               (blocker, leaf) -> DIMACS; claim becomes clause
      auxiliary.py            the 14 exhaustiveness instances
      extend.py               Layer B: residual extension instances
      blocker.py              blocked-link recovery, orbit closure, canonical digests
      frontier.py             the 47-node manifest
      cover.py                upper-bound checker A

    bin/
      gen_instances.py        rebuild the 47 frontier CNFs, check hashes
      gen_auxiliary.py        rebuild the 14 auxiliary CNFs, check hashes
      gen_extensions.py       rebuild the 20 extension CNFs, check hashes
      audit_blocker.py        blocker closure / orbit-stabiliser / licence audit
      check_encoding_provenance.py   both cardinality encodings, one problem core
      encoder_sanity.py       brute-force CardEnc.equals against ground truth
      cross_check_encoder.py  rebuild all 81 with no PySAT in the chain
      verify_cover.py         upper-bound checker A (Python, bitmask)
      verify_cover.c          upper-bound checker B (C, no shared code)
      certify.sh              solve + drat-trim + cake_lpr, fail-closed
      replay_deposit.py       map/replay the already-deposited 81 DRAT proofs
      make_manifest.sh        regenerate MANIFEST.sha256

    data/
      frontier.json           47 nodes: leaf, blocker, CNF hash, certificate hashes
      auxiliary.json          14 instances, same shape
      extensions.json         20 orbits: witness, CNF hash, certificate hashes
      blockers/*.cnf          the staged orbit blockers (9, 13, 20 orbits)
      links/link-*.txt        the 20 link witnesses the extension proofs used
      design-*-41.txt         two 41-block covers
      coverdata-2026-07-24.json   snapshot of the best-known-values table; the
                              source of truth for what was known before (this
                              artifact closes C(12,6,4) from low_bd 40 to 41)

    docs/
      PROOF-MAP.md            paper claim -> script -> artifact, item by item
      REPRODUCIBILITY.md      what makes hashes reproduce, and the known traps
      TOOLCHAIN.md            external solver versions and how to build them

    verify/
      README.md               what each independent audit established
      independent_seq_encoder.py     clean-room Sinz 2005 encoder; no PySAT
      independent-*.json      the campaign's own audit verdicts, incl. the r1 recount

## Certificate inventory

81 instances, every one `s VERIFIED UNSAT` under `cake_lpr`:

| Layer | Count | Vars | Clauses | Manifest |
|---|---|---|---|---|
| Frontier nodes | 47 | 40,642 | 84,000–95,900 | `data/frontier.json` |
| Auxiliary | 14 | 40,642 (one 1,826) | 3,555–95,845 | `data/auxiliary.json` |
| Extension | 20 | ~72,700 | ~144,800 | `data/extensions.json` |

All 47 frontier nodes were additionally solved and `drat-trim`-replayed under a
*second*, independently structured cardinality encoding (`kmtotalizer` beside
`seqcounter`), with `bin/check_encoding_provenance.py` confirming both encodings
share a `non_cardinality_core_sha256` — the same combinatorial problem, two
different translations. Raw DRAT across both encodings totals about 28 GB; the
manifests record every proof object's SHA-256 and size, so a re-derivation can be
compared without storing them.

One asymmetry is called out rather than smoothed over: for node `s-r0-2` the
`cake_lpr` certificate is against the `kmtotalizer` instance, because the
sequential proof (2.2 GB raw) was replayed but not retained. The exact
kmtotalizer CNF is deposited in `data/cnf-checked/`; `data/frontier.json`
records the encoding in the node's `certificate.note`, and
`tests/test_manifests.py::test_exactly_one_node_is_certified_under_the_second_encoding`
pins it so it cannot be quietly lost.

## Scope: what each layer establishes

* Tier 2 establishes that these are, byte for byte, the files the deposited
  certificates certify. The certificates themselves are the proof of the lower
  bound, and every one of them is machine-checked by `cake_lpr`, a checker
  extracted from a HOL4 correctness proof.
* The encoder is checked three ways: `bin/encoder_sanity.py` brute-forces
  `CardEnc.equals` against ground truth; `bin/check_encoding_provenance.py`
  shows the two cardinality translations state the same problem; and
  `make cross-check` rebuilds all 81 instances, byte for byte, with an
  independent encoder that imports no PySAT. The translation from combinatorial
  claim to clauses lives in one ~200-line file, `src/c1264/encode.py`, written
  to be read end to end and checked by §2 and §5–6 of `docs/PROOF-MAP.md`.
* The two designs proving the upper bound are prior art, not new here; the
  contribution is the lower bound.

## Byte-exact reproduction

The published SHA-256 hashes are tied to the pinned `python-sat==1.9.dev7`;
`requirements.txt` installs exactly that version, and with it every instance
regenerates byte for byte on an independent machine. A different PySAT version
produces semantically equivalent instances with different bytes, which the
certificates then no longer name — `reproduce.sh` detects this and says so, and
`docs/REPRODUCIBILITY.md` covers that case. The same document records the
reproduction pitfalls this deposit's drivers already engineer around, including
the `drat-trim` verdict line that begins with a carriage return, which every
verdict-matching script here strips before matching.

## Licence and citation

Code and data in this repository are released under the MIT Licence (`LICENSE`).
The two 41-block designs are prior art and are included for verification only.
See `CITATION.cff` for citation metadata.
