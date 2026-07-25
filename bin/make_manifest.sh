#!/usr/bin/env bash
# Regenerate MANIFEST.sha256 -- a SHA-256 for every file in the deposit.
#
# The manifest is what a referee checks the download against:
#
#   shasum -c MANIFEST.sha256
#
# It is not part of the proof.  The hashes that carry mathematical weight are the
# per-instance `cnf_sha256` fields inside data/*.json, checked by `make
# regenerate`.  This one only says "the files you have are the files that were
# deposited".
#
# Two forms, because there are two distributions:
#
#   bin/make_manifest.sh               source tree only -- what a git clone has.
#                                      Build products under build/ are excluded,
#                                      so the manifest is stable across runs.
#   bin/make_manifest.sh --with-build  additionally hash the generated CNFs and
#                                      run logs under build/.  This is for
#                                      assembling an archival bundle (Zenodo),
#                                      which ships the 81 instances so a referee
#                                      need not regenerate them.  Run
#                                      `make regenerate` first, or the CNFs will
#                                      be missing rather than wrong.
#
# Run it after any edit to a deposited file, and run it last, so it covers the
# edit.

set -eu -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

with_build=0
case "${1:-}" in
  "")           ;;
  --with-build) with_build=1 ;;
  *)            echo "usage: $0 [--with-build]" >&2; exit 2 ;;
esac

collect() {
  find . -type f \
    ! -path './.git/*' \
    ! -path './build/*' \
    ! -path './.pytest_cache/*' \
    ! -path './tools/*' \
    ! -path './.venv/*' \
    ! -name '*.pyc' \
    ! -path '*/__pycache__/*' \
    ! -name 'MANIFEST.sha256' \
    ! -name '.DS_Store' \
    -print

  if [ "$with_build" -eq 1 ]; then
    # The instances plus the four run records the bundle ships as evidence.  The
    # compiled verify_cover binary and provenance scratch are deliberately not
    # included: both regenerate, and one is platform-specific.
    find build/cnf build/cnf-aux build/cnf-ext -type f -name '*.cnf' -print
    for record in audit.json provenance.json reproduce.log reproduce-summary.tsv; do
      [ -f "build/$record" ] && printf 'build/%s\n' "$record"
    done
  fi
}

collect | sed 's|^\./||' | LC_ALL=C sort | xargs shasum -a 256 > MANIFEST.sha256

printf 'MANIFEST.sha256: %s files%s\n' \
  "$(wc -l < MANIFEST.sha256 | tr -d ' ')" \
  "$([ "$with_build" -eq 1 ] && echo ' (bundle form, includes build/)' || echo ' (source tree)')"
