"""Auditing the orbit blockers: recovery of blocked links and orbit closure.

An orbit blocker is a CNF over the 462 primary variables whose clauses are each
twenty negative literals.  Read as a statement about links, one clause says
"these twenty blocks are not all present simultaneously" -- it forbids one
particular 20-block C(11,5,3) link.

The blockers are the one place in the proof where a *search* result enters a
*deductive* argument, so they need to be auditable without trusting the search.
They are, because of the following two properties, both checked here:

1.  The set of forbidden links is a union of complete orbits under the group
    (:func:`orbit_partition` asserts this, since ``_orbit_of_link`` refuses an
    orbit that leaves the blocked set).  A blocker that were *not* orbit-closed
    would be asserting something stronger about some labellings than others,
    which the symmetry reduction is not entitled to do.

2.  Each orbit is identified by the SHA-256 of its canonical (lexicographically
    least) representative, written one block per line.  Those digests are the
    published identity of the blocked links: given only the blocker CNF you can
    recover the twenty representatives and check the digests, with no reference
    to the SAT runs that originally produced them.

The soundness of *forbidding* a link is a separate matter, discharged by the
extension instances of :mod:`c1264.extend`: link L is forbidden only because the
residual problem "extend L to a 41-block cover of the 4-subsets of a 12-set" was
refuted.  This module establishes *which* links are forbidden; that module
establishes that each one deserved to be.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .blocks import BLOCKS
from .group import group_maps, image
from .orbits import BLOCKER_CLAUSE_WIDTH, parse_blockers

Block = Tuple[int, ...]
#: A link is a sorted tuple of twenty 5-blocks.
Link = Tuple[Block, ...]


def blocked_links(path: Path) -> List[Link]:
    """Recover the links forbidden by a blocker CNF, in sorted order.

    Literal ``-i`` refers to ``BLOCKS[i - 1]``, so a clause of twenty negative
    literals decodes to a set of twenty blocks.
    """
    links = set()
    for clause in parse_blockers(path):
        blocks = tuple(sorted(BLOCKS[-literal - 1] for literal in clause))
        if len(blocks) != BLOCKER_CLAUSE_WIDTH:
            raise AssertionError(f"{path}: blocking clause repeats a block")
        links.add(blocks)
    return sorted(links)


def canonical_text(link: Sequence[Block]) -> str:
    """The published serialisation of a link: one block per line, points 1-11.

    The SHA-256 of this text is an orbit's identity in the deposited manifests,
    so the format is fixed: space-separated points, ascending, newline-terminated
    lines, no trailing blank line.
    """
    return "".join(" ".join(map(str, block)) + "\n" for block in link)


def canonical_digest(link: Sequence[Block]) -> str:
    """SHA-256 of :func:`canonical_text`."""
    return hashlib.sha256(canonical_text(link).encode("ascii")).hexdigest()


def orbit_partition(path: Path) -> List[Dict[str, object]]:
    """Split the blocked links into complete group orbits.

    Returns one record per orbit -- canonical representative, orbit size,
    stabiliser order and canonical digest -- ordered by canonical representative,
    which makes the output a deterministic function of the blocker file alone.

    Raises ``AssertionError`` if any orbit is not wholly contained in the blocked
    set, i.e. if the blocker is not orbit-closed.
    """
    maps = list(group_maps())
    unseen = set(blocked_links(path))
    records: List[Dict[str, object]] = []
    while unseen:
        seed = min(unseen)
        # ``seed`` is the least element of the whole remaining set, and the orbit
        # is contained in it, so ``seed`` is also this orbit's canonical form.
        orbit = {tuple(sorted(image(m, block) for block in seed)) for m in maps}
        if not orbit <= unseen:
            missing = len(orbit - unseen)
            raise AssertionError(
                f"{path}: blocker is not orbit-closed; {missing} image(s) of "
                f"{seed} are not blocked"
            )
        stabilizer_order = sum(
            1 for m in maps if tuple(sorted(image(m, block) for block in seed)) == seed
        )
        if len(orbit) * stabilizer_order != len(maps):
            raise AssertionError(f"{path}: orbit-stabilizer check failed for {seed}")
        records.append(
            {
                "canonical_blocks": [list(block) for block in seed],
                "canonical_sha256": canonical_digest(seed),
                "orbit_size": len(orbit),
                "stabilizer_order": stabilizer_order,
            }
        )
        unseen -= orbit
    return records
