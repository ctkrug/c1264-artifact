"""Variable layout and coverage clauses for the link instances.

The proof reduces C(12,6,4) to the link of a point: a 6-set through point 12
restricted to the other eleven points is a 5-set, and a 4-set through point 12
restricts to a 3-set, so the link of a point is a C(11,5,3) covering problem.

Variable layout (fixed, and part of the reproducibility contract)
----------------------------------------------------------------
Primary variables 1..462 are the C(11,5) = 462 five-subsets of {1,...,11}, in
``itertools.combinations`` order.  Variable ``i`` is true iff block
``BLOCKS[i-1]`` is used.  Any auxiliary variables introduced by a cardinality
encoding are numbered from 463 upwards; nothing outside this module may assume
anything about them.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Tuple

Block = Tuple[int, ...]

#: Number of points in the link.
LINK_POINTS = 11
#: Block size in the link (6-sets through the deleted point, minus that point).
LINK_BLOCK_SIZE = 5
#: Subset size to cover in the link (4-sets through the deleted point, minus it).
LINK_COVER_SIZE = 3

#: The 462 primary blocks, in variable order.
BLOCKS: Tuple[Block, ...] = tuple(
    itertools.combinations(range(1, LINK_POINTS + 1), LINK_BLOCK_SIZE)
)

#: Number of primary variables.  Named constant so instance readers can assert it.
PRIMARY_VARIABLES = len(BLOCKS)

#: Block -> 1-based variable number.
POSITION: Dict[Block, int] = {block: index for index, block in enumerate(BLOCKS, 1)}

#: Per-point exact degrees in the link.  Point 1 is the distinguished point of
#: the outer argument and carries degree 10; the other ten points carry 9.
#: These eleven equalities are the *architecture* of the encoding: there is
#: deliberately no global cardinality constraint on |L|.  |L| = 20 follows,
#: since sum of degrees = 5|L| = 10 + 10*9 = 100.
POINT_ONE_DEGREE = 10
OTHER_POINT_DEGREE = 9


def point_degree(point: int) -> int:
    """Exact link degree required of ``point``."""
    if not 1 <= point <= LINK_POINTS:
        raise ValueError(f"point {point} outside 1..{LINK_POINTS}")
    return POINT_ONE_DEGREE if point == 1 else OTHER_POINT_DEGREE


def implied_block_count() -> int:
    """|L|, derived from the degree sequence rather than asserted."""
    total = sum(point_degree(p) for p in range(1, LINK_POINTS + 1))
    if total % LINK_BLOCK_SIZE:
        raise AssertionError("degree sum is not divisible by the block size")
    return total // LINK_BLOCK_SIZE


def coverage_clauses() -> List[List[int]]:
    """One positive clause per 3-subset: some chosen block must contain it.

    Returns C(11,3) = 165 clauses in ``itertools.combinations`` order over the
    triples, each listing the containing blocks in increasing variable order.
    """
    return [
        [POSITION[block] for block in BLOCKS if set(triple) <= set(block)]
        for triple in itertools.combinations(range(1, LINK_POINTS + 1), LINK_COVER_SIZE)
    ]


def point_literals(point: int) -> List[int]:
    """Variables of the blocks containing ``point``, in increasing order."""
    return [index for index, block in enumerate(BLOCKS, 1) if point in block]
