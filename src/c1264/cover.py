"""Upper bound: verification that an explicit 41-block design is a (12,6,4) cover.

This is the easy half of ``C(12,6,4) = 41`` and needs no solver: exhibit 41
6-subsets of {1,...,12} and check that all C(12,4) = 495 quadruples are covered.
The check is done twice in this artifact by deliberately different means --
the bitmask sweep here, and an independently written C program in
``bin/verify_cover.c`` -- so that a bug in one implementation cannot pass
unnoticed.
"""

from __future__ import annotations

import itertools
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

GROUND_POINTS = 12
BLOCK_SIZE = 6
COVER_SIZE = 4
EXPECTED_BLOCKS = 41
EXPECTED_QUADRUPLES = 495


def read_design(path: Path) -> List[Tuple[int, ...]]:
    """Read a design file: one block per line, ``BLOCK_SIZE`` integers.

    Blank lines and ``#`` comments are ignored.  No validation of block content
    happens here -- that is :func:`check_design`'s job, so that malformed input
    is reported as a finding rather than as a parse traceback.
    """
    blocks: List[Tuple[int, ...]] = []
    for line in Path(path).read_text(encoding="ascii").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        blocks.append(tuple(int(value) for value in line.split()))
    return blocks


def check_design(blocks: Sequence[Sequence[int]]) -> List[str]:
    """Return a list of problems with ``blocks``; empty means it is a valid cover."""
    errors: List[str] = []
    if len(blocks) != EXPECTED_BLOCKS:
        errors.append(f"block count {len(blocks)} != {EXPECTED_BLOCKS}")

    masks: List[int] = []
    for index, block in enumerate(blocks):
        if (
            len(block) != BLOCK_SIZE
            or len(set(block)) != BLOCK_SIZE
            or not all(1 <= point <= GROUND_POINTS for point in block)
        ):
            errors.append(
                f"block {index} is not a {BLOCK_SIZE}-subset of 1..{GROUND_POINTS}: {list(block)}"
            )
            continue
        mask = 0
        for point in block:
            mask |= 1 << (point - 1)
        masks.append(mask)

    if len(set(tuple(sorted(block)) for block in blocks)) != len(blocks):
        errors.append("duplicate blocks present")

    total = 0
    uncovered: List[Tuple[int, ...]] = []
    for quadruple in itertools.combinations(range(1, GROUND_POINTS + 1), COVER_SIZE):
        total += 1
        target = 0
        for point in quadruple:
            target |= 1 << (point - 1)
        if not any(mask & target == target for mask in masks):
            uncovered.append(quadruple)

    if total != EXPECTED_QUADRUPLES:
        errors.append(f"enumerated {total} quadruples, expected {EXPECTED_QUADRUPLES}")
    if uncovered:
        shown = ", ".join(str(list(q)) for q in uncovered[:5])
        errors.append(f"{len(uncovered)} uncovered quadruples, first: {shown}")
    return errors


def coverage_multiplicity(blocks: Sequence[Sequence[int]]) -> Dict[Tuple[int, ...], int]:
    """How many blocks cover each quadruple.

    A 41-block cover is not a Steiner system: 41 blocks contribute
    ``41 * C(6,4) = 615`` covered slots to 495 quadruples, so 120 slots are
    necessarily surplus and some quadruples are covered more than once.  Stating
    that explicitly matters because "the design is optimal" is sometimes
    misremembered as "every quadruple is covered exactly once", which would make
    the counting arguments in the paper wrong.
    """
    counts: Counter = Counter()
    for block in blocks:
        for quadruple in itertools.combinations(sorted(block), COVER_SIZE):
            counts[quadruple] += 1
    return dict(counts)
