"""Orbit partitions of the case tree, and reading of orbit blocker CNFs.

The case tree fixes blocks one at a time.  At each level the still-eligible
blocks are partitioned into orbits under the stabiliser of the blocks already
fixed, a canonical representative (the ``min`` of the orbit) is asserted true,
and all *earlier* orbits at that level are asserted false.  Those "earlier
orbits false" units are what make the branching exhaustive rather than merely
suggestive: branch ``k`` handles the case where the first eligible block lies
in orbit ``k``, and orbits ``0..k-1`` being empty is exactly the complement of
branches ``0..k-1``.

Every partition below asserts its own stabiliser order against the
orbit-stabiliser theorem, so a change in the group definition surfaces as an
``AssertionError`` here rather than as a wrong answer downstream.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import List, Set, Tuple

from .blocks import BLOCKS, POSITION, PRIMARY_VARIABLES
from .group import (
    GROUP_ORDER,
    LINK_ROOT_ORBIT_SIZES,
    LINK_ROOTS,
    group_maps,
    image,
    stabilizer,
)

Block = Tuple[int, ...]

#: Orbit blockers negate exactly this many distinct blocks per clause.
BLOCKER_CLAUSE_WIDTH = 20


def parse_blockers(path: Path, primary_variables: int = PRIMARY_VARIABLES) -> List[List[int]]:
    """Read an orbit blocker CNF, validating its shape strictly.

    An orbit blocker is a set of purely negative clauses over the primary
    variables only, each of width exactly 20 -- one clause per already-refuted
    20-block link, forbidding that link (up to symmetry) from recurring.  The
    strictness is deliberate: silently accepting a malformed blocker would
    weaken the instance in a way no downstream check would notice.
    """
    path = Path(path)
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if not lines or not lines[0].startswith("p cnf "):
        raise ValueError(f"{path}: blocking CNF lacks a header")
    _, _, declared_variables, declared_clauses = lines[0].split()
    if int(declared_variables) != primary_variables:
        raise ValueError(f"{path}: header declares {declared_variables} variables")
    if int(declared_clauses) != len(lines) - 1:
        raise ValueError(f"{path}: header declares {declared_clauses} clauses, file has {len(lines) - 1}")
    clauses: List[List[int]] = []
    for line in lines[1:]:
        values = [int(value) for value in line.split()]
        if not values or values[-1] != 0:
            raise ValueError(f"{path}: unterminated blocking clause")
        clause = values[:-1]
        if len(clause) != BLOCKER_CLAUSE_WIDTH or len(set(clause)) != BLOCKER_CLAUSE_WIDTH:
            raise ValueError(
                f"{path}: orbit blocker must negate exactly {BLOCKER_CLAUSE_WIDTH} distinct blocks"
            )
        if any(literal >= 0 or -literal > primary_variables for literal in clause):
            raise ValueError(f"{path}: orbit blocker is not primary-variable negative-only")
        clauses.append(clause)
    return clauses


def root_orbits() -> List[Set[Block]]:
    """Orbits of the six canonical primary roots under the full group.

    These six orbits partition all 462 blocks; see
    :func:`assert_root_orbits_partition`, which the test suite runs.
    """
    return [set(image(m, root) for m in group_maps()) for root in LINK_ROOTS]


def assert_root_orbits_partition() -> List[int]:
    """Check that the primary orbits really partition all 462 blocks.

    This is the load-bearing property of the primary case split: branch ``r``
    covers "the first block present lies in orbit ``r``", so if the six orbits
    left any block uncovered, or overlapped, the primary split would not be
    exhaustive and the whole case tree would prove nothing.  Returns the orbit
    sizes so callers can report them.
    """
    partition = root_orbits()
    sizes = [len(orbit) for orbit in partition]
    if sizes != list(LINK_ROOT_ORBIT_SIZES):
        raise AssertionError(f"primary orbit sizes are {sizes}, expected {list(LINK_ROOT_ORBIT_SIZES)}")
    union = set().union(*partition)
    if sum(sizes) != len(union):
        raise AssertionError("primary orbits overlap")
    if union != set(BLOCKS):
        raise AssertionError(f"primary orbits miss {len(set(BLOCKS) - union)} blocks")
    return sizes


def secondary_orbits(root_index: int) -> List[Set[Block]]:
    """Partition the blocks other than the primary root under its stabiliser."""
    if not 0 <= root_index < len(LINK_ROOTS):
        raise ValueError("invalid primary root index")
    canonical = LINK_ROOTS[root_index]
    stab = stabilizer(canonical)
    expected = GROUP_ORDER // len(root_orbits()[root_index])
    if len(stab) != expected:
        raise AssertionError("primary-root stabilizer order violates orbit-stabilizer")
    return _partition(stab, set(BLOCKS) - {canonical}, "secondary")


def tertiary_orbits(root_index: int, secondary_index: int) -> List[Set[Block]]:
    """Partition still-eligible third blocks under the two-block stabiliser."""
    secondary = secondary_orbits(root_index)
    if not 0 <= secondary_index < len(secondary):
        raise ValueError("secondary index is outside its complete partition")
    primary = LINK_ROOTS[root_index]
    second = min(secondary[secondary_index])
    stab = stabilizer(primary, second)
    expected = (GROUP_ORDER // len(root_orbits()[root_index])) // len(secondary[secondary_index])
    if len(stab) != expected:
        raise AssertionError("two-block stabilizer order violates orbit-stabilizer")
    forced_false = set().union(*secondary[:secondary_index]) if secondary_index else set()
    domain = set(BLOCKS) - forced_false - {primary, second}
    return _partition(stab, domain, "tertiary")


def _partition(maps, domain: Set[Block], level: str) -> List[Set[Block]]:
    """Greedily split ``domain`` into orbits under ``maps``, smallest seed first.

    Raises if an orbit escapes the eligible domain, which would mean the
    stabiliser does not actually act on it and the partition is unsound.
    """
    unseen = set(domain)
    orbits: List[Set[Block]] = []
    while unseen:
        seed = min(unseen)
        orbit = set(image(m, seed) for m in maps)
        if not orbit <= unseen:
            raise AssertionError(f"{level} orbits overlap or leave the eligible domain")
        orbits.append(orbit)
        unseen -= orbit
    return orbits


def negate(blocks) -> List[List[int]]:
    """Unit clauses asserting each block in ``blocks`` is unused, in variable order."""
    return [[-POSITION[block]] for block in sorted(blocks)]
