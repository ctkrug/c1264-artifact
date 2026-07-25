#!/usr/bin/env python3
"""Upper-bound checker A: confirm a design file is a (12,6,4) covering of size 41.

Independent implementation #1 of two (see verify_cover.c).  Prints VALID and
exits 0 only if every check passes; otherwise prints each finding and exits 1.

    bin/verify_cover.py data/design-stored-41.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from c1264.cover import EXPECTED_BLOCKS, EXPECTED_QUADRUPLES, check_design, read_design


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("design", type=Path, help="design file, one block of 6 integers per line")
    args = parser.parse_args()

    blocks = read_design(args.design)
    errors = check_design(blocks)
    if errors:
        for error in errors:
            print(f"INVALID: {error}")
        return 1
    print(
        f"VALID: {len(blocks)} blocks cover all {EXPECTED_QUADRUPLES} quadruples "
        f"=> C(12,6,4) <= {EXPECTED_BLOCKS}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
