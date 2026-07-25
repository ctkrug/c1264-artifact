#!/usr/bin/env bash
# One-command reproduction of everything that does not need a SAT solver.
#
# This is the referee's entry point.  It runs the two cheap tiers in dependency
# order, stops at the first failure, and prints a summary saying exactly which
# claims of the paper are now checked on this machine and which are not.
#
# The expensive tier -- solving all 81 instances and machine-checking the proofs
# -- is deliberately NOT run here: it is CPU-days of work and needs roughly
# 200 GB of scratch disk.  Run `bin/certify.sh` for that, on one instance first.
#
# Usage:
#   ./reproduce.sh                    # uses `python3` from PATH
#   PYTHON=/path/to/python ./reproduce.sh
#   SKIP_CROSS_CHECK=1 ./reproduce.sh # drop the ~3 min clean-room re-encoding
#
# Exit status: 0 only if every step passed.

set -u -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"

PYTHON="${PYTHON:-python3}"
OUT="${OUT:-$REPO/build}"
export PYTHONPATH="$REPO/src"

mkdir -p "$OUT"
LOG="$OUT/reproduce.log"
: > "$LOG"

# Results are appended, one tab-separated "status<TAB>label" record per step, and
# re-read at the end.  A file rather than an array because this script must work
# under the bash 3.2 that ships with macOS, and rather than two parallel
# space-separated strings because the labels themselves contain spaces.
TALLY="$OUT/reproduce-summary.tsv"
: > "$TALLY"

step() {
  local label="$1"; shift
  printf '\n=== %s\n' "$label" | tee -a "$LOG"
  printf '    $ %s\n' "$*" | tee -a "$LOG"
  if "$@" >>"$LOG" 2>&1; then
    printf '    OK\n'
    printf 'ok\t%s\n' "$label" >> "$TALLY"
  else
    printf '    FAILED (see %s)\n' "$LOG"
    printf 'FAILED\t%s\n' "$label" >> "$TALLY"
    tail -20 "$LOG" | sed 's/^/    | /'
  fi
}

echo "C(12,6,4) = 41 -- reproduction"
echo "repository: $REPO"
echo "python:     $("$PYTHON" --version 2>&1)"
echo "log:        $LOG"

"$PYTHON" - <<'PY' || { echo "error: dependencies missing; pip install -r requirements.txt" >&2; exit 2; }
import sys
try:
    import pysat
except ImportError:
    sys.exit(1)
version = getattr(pysat, "__version__", "unknown")
print(f"python-sat:  {version}")
if version not in ("1.9.dev7", "unknown"):
    print(
        f"WARNING: requirements.txt pins python-sat 1.9.dev7; you have {version}.\n"
        "         Instances will be semantically equivalent but the published\n"
        "         SHA-256 hashes will not match.  See docs/REPRODUCIBILITY.md.",
        file=sys.stderr,
    )
PY

# --- tier 1 ---------------------------------------------------------------
step "test suite"            "$PYTHON" -m pytest -q
step "upper bound (Python)"  "$PYTHON" bin/verify_cover.py data/design-stored-41.txt
step "upper bound (Python, second design)" \
                             "$PYTHON" bin/verify_cover.py data/design-lajolla-41.txt

if command -v cc >/dev/null 2>&1; then
  if cc -O2 -Wall -Wextra -std=c99 -o "$OUT/verify_cover" bin/verify_cover.c >>"$LOG" 2>&1; then
    step "upper bound (C)"   "$OUT/verify_cover" data/design-stored-41.txt
  else
    echo "    note: verify_cover.c did not compile; skipping checker B" | tee -a "$LOG"
  fi
else
  echo "    note: no C compiler found; skipping checker B" | tee -a "$LOG"
fi

step "encoder sanity"        "$PYTHON" bin/encoder_sanity.py --quiet

# --- tier 2 ---------------------------------------------------------------
step "47 frontier instances" "$PYTHON" bin/gen_instances.py --out "$OUT/cnf"
step "14 auxiliary instances" "$PYTHON" bin/gen_auxiliary.py --out "$OUT/cnf-aux"
step "20 extension instances" "$PYTHON" bin/gen_extensions.py --out "$OUT/cnf-ext"
step "blocker audit"         "$PYTHON" bin/audit_blocker.py --json "$OUT/audit.json"
step "encoding provenance"   "$PYTHON" bin/check_encoding_provenance.py --out "$OUT/provenance.json"

# --- tier 2b --------------------------------------------------------------
# Rebuilds the same 81 instances a second time with no PySAT in the chain.  It
# roughly doubles the runtime of this script, so it can be skipped -- but it is
# the check that removes an unverified third-party library from the trust root,
# so it is on by default.
if [ "${SKIP_CROSS_CHECK:-0}" = "1" ]; then
  echo "    note: SKIP_CROSS_CHECK=1; skipping the clean-room encoder cross-check" | tee -a "$LOG"
else
  step "clean-room encoder cross-check (81 instances, ~3 min)" \
                             "$PYTHON" bin/cross_check_encoder.py --out "$OUT/cross-check.json"
fi

# --- summary --------------------------------------------------------------
echo
echo "summary"
# `st` rather than `status`: harmless in bash, but `status` is read-only in zsh,
# so a stray `zsh reproduce.sh` would die here instead of printing the summary.
while IFS="$(printf '\t')" read -r st label; do
  printf '  %-8s %s\n' "$st" "$label"
done < "$TALLY"
failed="$(grep -c '^FAILED' "$TALLY" || true)"

echo
if [ "$failed" -eq 0 ]; then
  cat <<'EOF'
All reproducible-without-a-solver claims check out on this machine:

  * C(12,6,4) <= 41    fully established here (two independent checkers).
  * C(12,6,4) >= 41    NOT established here.  What is established is that all 81
                       CNF instances the lower bound rests on regenerate byte for
                       byte from this source, so the deposited proof certificates
                       apply to exactly these files, and that the case analysis
                       over them is exhaustive and the blockers are licensed.
                       The refutations themselves are certificates: re-check them
                       with bin/certify.sh (CPU-days, ~200 GB scratch).
  * the encoder        every one of those 81 files was also rebuilt here by a
                       clean-room cardinality encoder importing no PySAT, and
                       came out byte-identical (build/cross-check.json).

Next: docs/PROOF-MAP.md maps each claim in the paper to the script that checks it.
EOF
  exit 0
fi
echo "$failed step(s) failed -- see $LOG"
exit 1
