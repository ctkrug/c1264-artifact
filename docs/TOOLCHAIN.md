# External toolchain

Tiers 1 and 2 (`./reproduce.sh`) need only Python and the pins in
`requirements.txt`. Tier 3 — re-deriving the 81 refutations — needs three external
tools, none of which is bundled here. This page records the versions the deposited
certificates were produced with, how to obtain them, and what tier 3 costs.

## The interpreter

Everything deposited here was produced with **CPython 3.14.6** on macOS
(darwin/arm64). The source uses no syntax or standard-library feature newer than
3.9 — no `match`, no `itertools.batched`, and `from __future__ import annotations`
throughout — so an older interpreter should work, but only 3.14.6 has actually
been exercised, and `python-sat==1.9.dev7` imposes its own floor.

The interpreter version is *not* a variable the CNF hashes depend on. Those bytes
come from PySAT's `CardEnc` and `CNF.to_file`, which is why `requirements.txt` is
pinned exactly and the Python version is not. `make regenerate` and
`bin/audit_blocker.py` have both been run under several `PYTHONHASHSEED` values
and produce identical bytes, so nothing in the generators leaks set-iteration
order into the output.

## The three tools

| Tool | Version used | Role | Success line |
|---|---|---|---|
| CaDiCaL | 3.0.1 | SAT solver; emits a DRAT proof | `s UNSATISFIABLE` (exit 20) |
| `drat-trim` | 2023 release (`marijnheule/drat-trim`) | replays the DRAT proof; `-L` converts it to LRAT | `s VERIFIED` |
| `cake_lpr` | CakeML/HOL4 build (`tanyongkiam/cake_lpr`) | machine-checks the LRAT proof | `s VERIFIED UNSAT` |

`cake_lpr` is the reason the chain is worth anything: it is a checker extracted by
CakeML from a correctness proof in HOL4, so accepting a proof is backed by a
machine-checked theorem rather than by trust in a solver. CaDiCaL and `drat-trim`
sit upstream of it and do not have to be trusted — a bug in either produces a proof
`cake_lpr` rejects, not a false verdict.

Any DRAT-emitting solver may be substituted for CaDiCaL; the artifact's claim is
that the instances are UNSAT, not that CaDiCaL in particular refutes them. Do not
substitute anything for `cake_lpr` without saying so — it is the verified link.

## Building them

Each builds standalone with a C/C++ compiler and `make`. Put the three binaries on
`$PATH`, or in `<repo>/tools/` where `bin/certify.sh` looks first (`tools/` is
`.gitignore`d, so binaries never enter the deposit).

```bash
mkdir -p tools && cd tools

git clone https://github.com/arminbiere/cadical.git
cd cadical && git checkout rel-3.0.1 && ./configure && make && cd ..
cp cadical/build/cadical .

git clone https://github.com/marijnheule/drat-trim.git
cd drat-trim && make && cd ..
cp drat-trim/drat-trim .

git clone https://github.com/tanyongkiam/cake_lpr.git
# cake_lpr ships prebuilt CakeML-generated binaries per platform; follow its
# README for the current layout rather than assuming a path here.
```

Confirm the tools are visible before starting a long run:

```bash
bin/certify.sh
```

With no arguments it prints usage after checking for all three, so a missing tool
surfaces immediately rather than an hour into a batch.

## Environment

`bin/certify.sh` reads three variables:

| Variable | Default | Meaning |
|---|---|---|
| `C1264_TOOLS` | `<repo>/tools` | directory searched for `cadical`, `drat-trim`, `cake_lpr` before `$PATH` |
| `C1264_WORK` | `<repo>/build/certify` | scratch for proof objects, plus `logs/` and per-node `.status` files |
| `C1264_MIN_FREE_GB` | `60` | a node will not start below this much free space on `C1264_WORK`'s filesystem; it waits |

Point `C1264_WORK` at a large, fast, local disk. Proof objects are written and
read once, sequentially, at multi-GB sizes — a network filesystem will dominate the
runtime.

## Cost

| Layer | Instances | Typical per node | Peak disk per node |
|---|---|---|---|
| Frontier | 47 | minutes to hours | up to 3.3 GB DRAT, 3.6 GB LRAT |
| Auxiliary | 14 | seconds to minutes | small, except the two region instances |
| Extension | 20 | minutes | ~25 MB DRAT |

Totals for a full run: order of CPU-days, about 28 GB of raw DRAT and 14 GB of
LRAT written and deleted as it goes. `certify.sh` removes each node's DRAT the
moment `drat-trim` accepts it and its LRAT the moment `cake_lpr` accepts it, which
is why 60 GB free is enough even though the cumulative write volume is ~40 GB.

Runs are resumable: a node whose `.status` file ends in `done` is skipped, so
`bin/certify.sh build/cnf/*.cnf` can be interrupted and re-issued.

Start with one cheap node to validate the toolchain end to end before committing
days of CPU:

```bash
make regenerate && bin/certify.sh "$(ls build/cnf-ext/*.cnf | head -1)"
```

Extension instances are named `ext-<first 12 hex of the orbit's canonical link
digest>.cnf`, so the exact filenames come from `data/extensions.json` rather than
being sequential.

## Recording what you used

If you re-derive certificates, record your own tool versions alongside the
`.status` files — `certify.sh` already writes the resolved binary paths into each
one. `cake_lpr` builds differ in their CakeML provenance, and a referee comparing
your run to the deposit needs to know which build accepted what.
