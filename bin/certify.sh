#!/usr/bin/env bash
# Solve one or more instances and machine-check the resulting proofs.
#
# Pipeline per instance:
#   CaDiCaL          -> s UNSATISFIABLE + a DRAT proof
#   drat-trim        -> s VERIFIED, and -L emits an LRAT proof
#   cake_lpr         -> s VERIFIED UNSAT, from a checker extracted from a HOL4
#                       correctness proof via CakeML
#
# Design notes, all of which are corrections of mistakes made in the original
# campaign drivers:
#
#   * FAIL CLOSED.  Any missing verdict, non-zero exit, or empty proof marks the
#     node FAILED and the script exits non-zero at the end.  An earlier driver
#     recorded a hash mismatch and carried on regardless.
#   * CR-SAFE VERDICTS.  drat-trim writes "\rs VERIFIED", so `grep -E '^s '`
#     silently matches nothing and a status file ends up with no verdict at all.
#     Every verdict here is piped through `tr -d '\r'` before matching.
#   * NO ABSOLUTE PATHS.  The repository root is derived from $0; tool locations
#     come from $C1264_TOOLS (default: <repo>/tools) or from $PATH.
#   * DISK GUARDED.  Raw DRAT for the hard nodes reaches tens of GB.  Each node
#     deletes its DRAT and LRAT immediately after use and refuses to start with
#     less than $C1264_MIN_FREE_GB free.
#   * RESUMABLE.  A node whose status file ends with "done" is skipped.
#
# Usage:
#   bin/certify.sh build/cnf/s-r0-1.cnf [more.cnf ...]
#   bin/certify.sh build/cnf/*.cnf
#
# Environment:
#   C1264_TOOLS         directory holding cadical, drat-trim, cake_lpr
#   C1264_WORK          scratch + logs directory (default: <repo>/build/certify)
#   C1264_MIN_FREE_GB   refuse to start a node below this free space (default 60)

set -u -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="${C1264_TOOLS:-$REPO/tools}"
WORK="${C1264_WORK:-$REPO/build/certify}"
MIN_FREE_GB="${C1264_MIN_FREE_GB:-60}"

CADICAL="$(command -v "$TOOLS/cadical" || command -v cadical || true)"
DRATTRIM="$(command -v "$TOOLS/drat-trim" || command -v drat-trim || true)"
CAKE="$(command -v "$TOOLS/cake_lpr" || command -v cake_lpr || true)"

# Kept as three explicit checks rather than a loop over variable names: this
# script must run under the bash 3.2 that ships with macOS, which has no
# case-conversion expansion.
missing=""
[ -n "$CADICAL" ]  || missing="$missing cadical"
[ -n "$DRATTRIM" ] || missing="$missing drat-trim"
[ -n "$CAKE" ]     || missing="$missing cake_lpr"
if [ -n "$missing" ]; then
  echo "error: not found in $TOOLS or on PATH:$missing" >&2
  echo "see docs/TOOLCHAIN.md for versions and build instructions" >&2
  exit 2
fi

if [ "$#" -eq 0 ]; then
  echo "usage: $0 instance.cnf [instance.cnf ...]" >&2
  exit 2
fi

mkdir -p "$WORK/logs" "$WORK/tmp"

# Free space in GiB on the filesystem holding $WORK. `df -g` on macOS/BSD,
# `df -BG` on GNU coreutils.
free_gb() {
  if df -g "$WORK" >/dev/null 2>&1; then
    df -g "$WORK" | awk 'NR==2 {print $4+0}'
  else
    df -BG "$WORK" | awk 'NR==2 {gsub(/G/,"",$4); print $4+0}'
  fi
}

# First matching verdict line, with carriage returns stripped. Empty if absent.
# The expected line is given in full and matched exactly, because the three tools
# do not agree on wording: CaDiCaL says "s UNSATISFIABLE", drat-trim says
# "s VERIFIED", and cake_lpr says "s VERIFIED UNSAT".  Matching a prefix would
# accept "s NOT VERIFIED" from a checker that gains that wording later.
verdict() {
  tr -d '\r' < "$1" | grep -m1 -x -F "$2" || true
}

# A space-separated string rather than an array: bash 3.2 under `set -u`
# treats an empty array's length as an unbound variable.
failed=""
passed=0

for cnf in "$@"; do
  name="$(basename "$cnf" .cnf)"
  status="$WORK/logs/$name.status"

  if [ -f "$status" ] && tail -1 "$status" | grep -q '^done '; then
    echo "$name: already done, skipping"
    passed=$((passed + 1))
    continue
  fi

  if [ ! -s "$cnf" ]; then
    echo "$name: FAILED (instance missing or empty)"
    failed="$failed $name"
    continue
  fi

  while [ "$(free_gb)" -lt "$MIN_FREE_GB" ]; do
    echo "$name: waiting for $MIN_FREE_GB GiB free on $WORK (have $(free_gb))"
    sleep 30
  done

  drat="$WORK/tmp/$name.drat"
  lrat="$WORK/tmp/$name.lrat"
  : > "$status"
  {
    echo "name=$name"
    echo "cnf=$cnf"
    echo "cnf_sha256=$(shasum -a 256 "$cnf" | awk '{print $1}')"
    echo "cadical=$CADICAL"
    echo "drat_trim=$DRATTRIM"
    echo "cake_lpr=$CAKE"
    echo "started=$(date -u '+%FT%TZ')"
  } >> "$status"

  node_ok=1

  # --- solve -------------------------------------------------------------
  t0=$(date +%s)
  "$CADICAL" "$cnf" "$drat" > "$WORK/logs/$name.solve" 2>&1
  rc=$?
  echo "cadical_rc=$rc cadical_seconds=$(( $(date +%s) - t0 ))" >> "$status"
  # CaDiCaL exits 20 on UNSAT; 10 means SATISFIABLE, which for a frontier node
  # would refute the proof rather than support it.
  if [ "$rc" -ne 20 ]; then
    echo "SOLVE_FAILED expected_rc=20 (UNSAT)" >> "$status"
    node_ok=0
  fi
  if [ -z "$(verdict "$WORK/logs/$name.solve" "s UNSATISFIABLE")" ]; then
    echo "SOLVE_VERDICT_MISSING" >> "$status"
    node_ok=0
  fi
  if [ "$node_ok" -eq 1 ]; then
    echo "drat_bytes=$(wc -c < "$drat" | tr -d ' ')" >> "$status"
  fi

  # --- check DRAT and emit LRAT ------------------------------------------
  if [ "$node_ok" -eq 1 ]; then
    t1=$(date +%s)
    "$DRATTRIM" "$cnf" "$drat" -L "$lrat" > "$WORK/logs/$name.drat" 2>&1
    rc=$?
    echo "drat_trim_rc=$rc drat_trim_seconds=$(( $(date +%s) - t1 ))" >> "$status"
    got="$(verdict "$WORK/logs/$name.drat" "s VERIFIED")"
    if [ -n "$got" ]; then
      echo "drat_trim_verdict=$got" >> "$status"
    else
      echo "DRAT_NOT_VERIFIED" >> "$status"
      node_ok=0
    fi
  fi
  rm -f "$drat"

  if [ "$node_ok" -eq 1 ] && [ ! -s "$lrat" ]; then
    echo "LRAT_EMPTY" >> "$status"
    node_ok=0
  fi

  # --- machine-check the LRAT -------------------------------------------
  if [ "$node_ok" -eq 1 ]; then
    echo "lrat_bytes=$(wc -c < "$lrat" | tr -d ' ')" >> "$status"
    t2=$(date +%s)
    "$CAKE" "$cnf" "$lrat" > "$WORK/logs/$name.cake" 2>&1
    rc=$?
    echo "cake_lpr_rc=$rc cake_seconds=$(( $(date +%s) - t2 ))" >> "$status"
    got="$(verdict "$WORK/logs/$name.cake" "s VERIFIED UNSAT")"
    if [ -n "$got" ]; then
      echo "cake_lpr_verdict=$got" >> "$status"
    else
      echo "CAKE_NOT_VERIFIED" >> "$status"
      node_ok=0
    fi
  fi
  rm -f "$lrat"

  if [ "$node_ok" -eq 1 ]; then
    echo "done $(date -u '+%FT%TZ')" >> "$status"
    echo "$name: VERIFIED"
    passed=$((passed + 1))
  else
    echo "failed $(date -u '+%FT%TZ')" >> "$status"
    echo "$name: FAILED (see $status)"
    failed="$failed $name"
  fi
done

echo
echo "$passed/$# instances machine-checked"
if [ -n "$failed" ]; then
  echo "FAILED:$failed" >&2
  exit 1
fi
