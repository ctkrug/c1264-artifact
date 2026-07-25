"""The auxiliary instances that make the case tree exhaustive.

The 47 frontier nodes of :mod:`c1264.frontier` refute the *live* branches of the
case tree.  They do not, by themselves, prove there are no other branches.  The
fourteen instances defined here close that gap: each one refutes a whole region
of the tree at once, and together with the 47 they account for every branch.

Naming follows the ledger, so a reader can match these to the certificates:

``r2plus-b20``
    The entire ``r >= 2`` region.  Built with the 20-orbit blocker conjoined and
    with **no canonical assertion at all** -- it is symmetry-free, so it does not
    depend on the orbit machinery it is being used to justify.
``r345-tail``
    The ``r >= 3`` region with no blocker.  Every block through point 1 is
    forbidden, so point 1 cannot reach degree 10 and the instance is UNSAT for an
    elementary reason.  Kept as a certificate anyway because it is cheap and it
    pins the arithmetic.
``r0-sec-tail``, ``r1-sec-tail``
    Within a fixed primary orbit, every secondary orbit at or above the largest
    live index is empty, killing all higher branches in one instance.
``r1-gap-s{6,7,9,10,11,12,13,14}``
    The eight secondary indices under ``r = 1`` that are below the largest live
    index but have no frontier node of their own: gaps in the live set must be
    refuted individually, one instance each.
``r0s0-ter-tail``
    The same tail argument one level down, for the tertiary orbits of ``(0, 0)``.
``lb-c1042-8-deg3``
    A warm-up of the whole method on a known value, ``C(10,4,2) = 9``, with an
    elementary WLOG reduction (see :func:`lower_bound_c1042_deg3`).  It is not
    needed for the C(12,6,4) theorem; it is there because a pipeline that cannot
    reproduce a known result should not be believed about a new one.

``root-tail`` from the campaign ledger is deliberately absent: it was built but
never certified, having been superseded by ``r2plus-b20`` plus ``r345-tail``,
which cover the same region with a weaker set of assumptions.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from pysat.card import CardEnc, EncType
from pysat.formula import CNF

from .blocks import POSITION
from .encode import base_cnf, non_cardinality_core
from .group import LINK_ROOTS
from .orbits import negate, parse_blockers, root_orbits, secondary_orbits, tertiary_orbits

Clause = List[int]

#: Largest live secondary index under primary orbit 0, and under orbit 1.  The
#: tail instances refute everything strictly above these.
LIVE_SECONDARY_LIMIT = {0: 7, 1: 16}
#: Largest live tertiary index under the (0, 0) branch.
LIVE_TERTIARY_LIMIT = 33
#: Secondary indices under r = 1 that are below the limit but carry no frontier
#: node, and so need an instance apiece.
R1_GAP_SECONDARY = (6, 7, 9, 10, 11, 12, 13, 14)


def _canonical_unit(block) -> Clause:
    return [POSITION[block]]


def secondary_tail_units(root_index: int) -> List[Clause]:
    """Units for "primary orbit is ``root_index`` and its secondary index is high".

    Earlier primary orbits are negated, the canonical primary block is asserted,
    and every secondary orbit below the live limit is negated -- which leaves
    exactly the branches the frontier does not cover.
    """
    partition = root_orbits()
    limit = LIVE_SECONDARY_LIMIT[root_index]
    units: List[Clause] = []
    if root_index:
        units.extend(negate(set().union(*partition[:root_index])))
    units.append(_canonical_unit(LINK_ROOTS[root_index]))
    units.extend(negate(set().union(*secondary_orbits(root_index)[:limit])))
    return units


def tertiary_tail_units(root_index: int, secondary_index: int) -> List[Clause]:
    """The same construction one level down, for tertiary orbits."""
    secondaries = secondary_orbits(root_index)
    units = [
        _canonical_unit(LINK_ROOTS[root_index]),
        _canonical_unit(min(secondaries[secondary_index])),
    ]
    tertiaries = tertiary_orbits(root_index, secondary_index)
    units.extend(negate(set().union(*tertiaries[:LIVE_TERTIARY_LIMIT])))
    return units


def gap_units(blocker_path: Path, root_index: int, secondary_index: int) -> List[Clause]:
    """Units pinning one single dead secondary index, via the node encoder.

    Reuses :func:`c1264.encode.non_cardinality_core` with an *empty* blocker so
    that a gap instance is literally the frontier node that would have sat at
    that index, minus the blocker.  Sharing the code path is the point: a gap and
    a live node differ only in whether a blocker is conjoined.
    """
    _, tail, _ = non_cardinality_core(blocker_path, root_index, secondary_index, None)
    return tail


def region_units(through: int) -> List[Clause]:
    """Negate every block in primary orbits ``0..through-1``.

    ``through=2`` leaves the ``r >= 2`` region; ``through=3`` leaves ``r >= 3``,
    which forbids every block containing point 1.  No canonical block is
    asserted, so these two instances are free of the symmetry reduction.
    """
    partition = root_orbits()
    return negate(set().union(*partition[:through]))


def lower_bound_c1042_deg3() -> CNF:
    """``C(10,4,2) >= 9``: no eight 4-subsets of a 10-set cover all 45 pairs.

    The WLOG reduction is elementary and worth stating in full, because it is the
    only place in the artifact where a symmetry argument is made by hand rather
    than by orbit enumeration:

    (a) Every point ``p`` has degree at least 3.  The nine pairs ``{p, x}`` must
        be covered, and each block through ``p`` covers exactly three of them, so
        ``deg(p) >= ceil(9/3) = 3``.
    (b) The degree sum is ``4 * 8 = 32`` over ten points, so the minimum degree is
        at most ``floor(32/10) = 3``.
    (c) Hence some point has degree exactly 3; relabel it to 1.  Its three blocks
        cover the nine pairs ``{1, x}`` three at a time with no repetition, so
        their non-1 parts partition ``{2..10}`` into three 3-sets; relabel those
        to ``{2,3,4}``, ``{5,6,7}``, ``{8,9,10}``.

    The instance asserts those three blocks, forbids any other block through
    point 1, and caps the design at eight blocks.
    """
    v, k, t, maximum_blocks = 10, 4, 2, 8
    all_blocks = list(itertools.combinations(range(1, v + 1), k))
    position = {block: index for index, block in enumerate(all_blocks, 1)}
    fixed = [(1, 2, 3, 4), (1, 5, 6, 7), (1, 8, 9, 10)]

    cnf = CNF()
    cnf.extend([
        [position[block] for block in all_blocks if set(subset) <= set(block)]
        for subset in itertools.combinations(range(1, v + 1), t)
    ])
    cnf.extend(
        CardEnc.atmost(
            lits=list(range(1, len(all_blocks) + 1)),
            bound=maximum_blocks,
            top_id=len(all_blocks),
            encoding=EncType.seqcounter,
        ).clauses
    )
    for block in fixed:
        cnf.append([position[block]])
    for block in all_blocks:
        if 1 in block and block not in fixed:
            cnf.append([-position[block]])
    return cnf


def instances(blockers: Path) -> Dict[str, Callable[[], Tuple[CNF, Dict[str, object]]]]:
    """The fourteen auxiliary instances, as name -> builder.

    ``blockers`` is the directory holding ``blocker-20.cnf`` and ``empty.cnf``.
    Builders are returned lazily because each one costs a few seconds of orbit
    enumeration and callers usually want a subset.
    """
    blocker_20 = blockers / "blocker-20.cnf"
    empty = blockers / "empty.cnf"

    def link_instance(name, extra_clauses, description, blocker=None):
        def build():
            cnf, _ = base_cnf("sequential")
            blocker_clauses = parse_blockers(blocker) if blocker is not None else []
            cnf.extend(blocker_clauses)
            units = extra_clauses()
            cnf.extend(units)
            receipt = {
                "name": name,
                "description": description,
                "variables": cnf.nv,
                "clause_count": len(cnf.clauses),
                "blocker": None if blocker is None else blocker.name,
                "blocker_clause_count": len(blocker_clauses),
                "unit_clause_count": sum(1 for clause in units if len(clause) == 1),
                "tail_clause_count": len(units),
            }
            return cnf, receipt
        return build

    built: Dict[str, Callable[[], Tuple[CNF, Dict[str, object]]]] = {
        "r2plus-b20": link_instance(
            "r2plus-b20",
            lambda: region_units(2),
            "the whole r >= 2 region, blocker conjoined, no canonical assertion",
            blocker=blocker_20,
        ),
        "r345-tail": link_instance(
            "r345-tail",
            lambda: region_units(3),
            "the r >= 3 region; UNSAT because point 1 cannot reach degree 10",
        ),
        "r0-sec-tail": link_instance(
            "r0-sec-tail",
            lambda: secondary_tail_units(0),
            "kills r=0 secondary indices 7 and above",
        ),
        "r1-sec-tail": link_instance(
            "r1-sec-tail",
            lambda: secondary_tail_units(1),
            "kills r=1 secondary indices 16 and above",
        ),
        "r0s0-ter-tail": link_instance(
            "r0s0-ter-tail",
            lambda: tertiary_tail_units(0, 0),
            "kills (r=0, s=0) tertiary indices 33 and above",
        ),
    }
    for index in R1_GAP_SECONDARY:
        built[f"r1-gap-s{index}"] = link_instance(
            f"r1-gap-s{index}",
            lambda index=index: gap_units(empty, 1, index),
            f"kills the single dead branch r=1 s={index}",
        )

    def build_lower_bound():
        cnf = lower_bound_c1042_deg3()
        return cnf, {
            "name": "lb-c1042-8-deg3",
            "description": "warm-up: UNSAT means C(10,4,2) >= 9, a known value",
            "variables": cnf.nv,
            "clause_count": len(cnf.clauses),
            "blocker": None,
            "blocker_clause_count": 0,
            "unit_clause_count": sum(1 for clause in cnf.clauses if len(clause) == 1),
            "tail_clause_count": None,
        }

    built["lb-c1042-8-deg3"] = build_lower_bound
    return built
