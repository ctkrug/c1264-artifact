"""The symmetry group used throughout the C(12,6,4) proof.

SINGLE SOURCE OF TRUTH.  Every orbit partition, canonical-form decision and
blocking clause in this artifact derives from ``group_maps()`` below.  In the
original campaign code this definition was duplicated across two files; if the
two copies had ever drifted, canonicalisation and the orbit partition could
have disagreed silently, which would break the exhaustiveness argument without
breaking any single instance.  Do not copy this function elsewhere -- import it.

The group
---------
The proof works in the *link* of a point.  Fixing the point labelled ``1`` and
a perfect matching on the remaining ten points

    PAIRS = ((2,3), (4,5), (6,7), (8,9), (10,11))

the relevant group is the stabiliser of that matching inside Sym({2..11}),
namely the wreath product C2 (wr) S5: permute the five pairs (5! ways) and
independently swap the two points inside each pair (2^5 ways).

    |G| = 2^5 * 5! = 32 * 120 = 3840

``assert_group_order()`` re-derives this from the generated maps rather than
asserting the arithmetic, so a change to ``PAIRS`` or to the construction is
caught immediately.
"""

from __future__ import annotations

import itertools
from typing import Dict, Iterable, Iterator, Tuple

Point = int
Block = Tuple[int, ...]
Mapping = Dict[Point, Point]

#: The perfect matching on {2,...,11} whose stabiliser is the proof's symmetry
#: group.  Point 1 is fixed pointwise by every element.
PAIRS: Tuple[Tuple[int, int], ...] = ((2, 3), (4, 5), (6, 7), (8, 9), (10, 11))

#: Expected order of the group; verified, not assumed (see assert_group_order).
GROUP_ORDER = 3840

#: Canonical representatives of the primary (first-block) orbits, in the order
#: used by the case tree.  These are the ``r`` indices in node names ``s-rR-N``,
#: and the order is load-bearing: the "earlier orbits are empty" units of node
#: ``r`` negate orbits ``0..r-1``, so permuting this tuple changes every
#: instance and therefore every published hash.
#:
#: The six orbits are classified by how the block meets the five matching pairs.
#: Indices 0-2 are the blocks through point 1 (10 + 120 + 80 = 210 of them);
#: indices 3-5 are the blocks avoiding it (32 + 160 + 60 = 252).  Together they
#: partition all 462 blocks -- ``orbits.assert_root_orbits_partition()`` checks
#: this rather than trusting the comment.
#:
#:   0  (1,2,4,6,8)   point 1 + one point from each of four pairs      |orbit| 80
#:   1  (1,2,3,4,6)   point 1 + one full pair + two singletons         |orbit| 120
#:   2  (1,2,3,4,5)   point 1 + two full pairs                         |orbit| 10
#:   3  (2,4,6,8,10)  one point from every pair                        |orbit| 32
#:   4  (2,3,4,6,8)   one full pair + three singletons                 |orbit| 160
#:   5  (2,3,4,5,6)   two full pairs + one singleton                   |orbit| 60
LINK_ROOTS: Tuple[Block, ...] = (
    (1, 2, 4, 6, 8),
    (1, 2, 3, 4, 6),
    (1, 2, 3, 4, 5),
    (2, 4, 6, 8, 10),
    (2, 3, 4, 6, 8),
    (2, 3, 4, 5, 6),
)

#: Orbit sizes of :data:`LINK_ROOTS`, in the same order.  Asserted, not assumed.
LINK_ROOT_ORBIT_SIZES: Tuple[int, ...] = (80, 120, 10, 32, 160, 60)


def group_maps() -> Iterator[Mapping]:
    """Yield all 3840 elements of C2 (wr) S5 as point-to-point dictionaries.

    Each element is built from a permutation of the five pairs together with a
    five-bit mask saying which pairs get their two points swapped.  Point 1 is
    always mapped to itself.

    The iteration order is deterministic and is part of this artifact's
    reproducibility contract: orbit representatives are chosen with ``min()``
    over the resulting sets, so the order does not affect the partition, but
    keeping it stable keeps regenerated CNF files byte-identical.
    """
    for target_order in itertools.permutations(range(5)):
        for flip_mask in range(1 << 5):
            mapping: Mapping = {1: 1}
            for source_index, target_index in enumerate(target_order):
                source = PAIRS[source_index]
                target = PAIRS[target_index]
                flip = (flip_mask >> source_index) & 1
                mapping[source[0]] = target[flip]
                mapping[source[1]] = target[1 - flip]
            yield mapping


def image(mapping: Mapping, block: Iterable[int]) -> Block:
    """Apply ``mapping`` to ``block`` and return it in canonical sorted form."""
    return tuple(sorted(mapping[point] for point in block))


def orbit_of(block: Iterable[int], maps: Iterable[Mapping] | None = None) -> frozenset:
    """The orbit of ``block`` under ``maps`` (the full group by default)."""
    block = tuple(block)
    return frozenset(image(m, block) for m in (maps if maps is not None else group_maps()))


def stabilizer(*blocks: Iterable[int]) -> list[Mapping]:
    """Elements of the group fixing every block in ``blocks`` setwise."""
    targets = [tuple(sorted(b)) for b in blocks]
    return [m for m in group_maps() if all(image(m, t) == t for t in targets)]


def assert_group_order() -> int:
    """Re-derive the group order from the generated maps.

    Checks that the maps are distinct permutations of {1,...,11}, that point 1
    is fixed, that the matching is preserved, and that the count is 3840.
    Returns the order so callers can print it.
    """
    seen = set()
    universe = frozenset(range(1, 12))
    pair_set = {frozenset(p) for p in PAIRS}
    for mapping in group_maps():
        if mapping[1] != 1:
            raise AssertionError("group element does not fix point 1")
        if frozenset(mapping) != universe or frozenset(mapping.values()) != universe:
            raise AssertionError("group element is not a permutation of 1..11")
        for pair in PAIRS:
            if frozenset(mapping[x] for x in pair) not in pair_set:
                raise AssertionError("group element does not preserve the matching")
        seen.add(tuple(sorted(mapping.items())))
    if len(seen) != GROUP_ORDER:
        raise AssertionError(f"group order is {len(seen)}, expected {GROUP_ORDER}")
    return len(seen)
