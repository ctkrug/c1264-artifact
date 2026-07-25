"""Layer B: the residual extension instances that justify blocking a link.

Layer A (:mod:`c1264.encode`) works inside the link of a point and refutes
candidate links.  Layer B asks the complementary question about a link that
*does* exist: given a valid 20-block C(11,5,3) link L, can L be completed to a
40-block cover of all 4-subsets of a 12-set?  If that is refuted, L can never
occur in a 40-block design, and L's whole orbit may be added to the blocker used
by Layer A.  Each of the twenty blocker orbits has exactly one such refutation.

Geometry
--------
Label the twelve points ``0..11`` and distinguish point ``0``.  A block of the
design is a 6-subset.  The blocks through point 0 correspond to the 5-subsets of
``{1..11}``: those twenty blocks are the link L.  The remaining twenty blocks
avoid point 0, so they range over the C(11,6) = 462 six-subsets of ``{1..11}``.
Those 462 are the variables of the residual instance -- the same count as Layer A
but a different object, which is worth stating because the coincidence is easy to
misread: Layer A's variables are 5-subsets, Layer B's are 6-subsets.

The instance is *residual*: L is not encoded as units, it is substituted away.

* Coverage.  Only the 4-subsets not already covered by L get a clause, and each
  such clause is over the residual variables alone.  Quadruples containing point
  0 are all covered by L (a valid link covers every triple of ``{1..11}``), so no
  clause mentions point 0 and every clause has width 21 -- the number of 6-subsets
  of ``{1..11}`` containing a given 4-subset is C(7,2) = 21.
* Degrees.  In a hypothetical 40-block cover every point has one degree-10
  partner and ten degree-9 partners, so the degree-10 pairs form a perfect
  matching.  After normalising that matching, every pair of link points must lie
  in a fixed number of blocks; the pair's residual bound is that number minus
  its multiplicity in L.  Consequently the
  instance has **zero unit clauses**: nothing about L is asserted, everything
  about L is subtracted.  That is what makes these instances independent of the
  Layer-A canonicalisation, and hence usable as its justification.

``MATCHING`` below is 0-based and includes ``(0, 1)``; pairs are drawn from
``{1..11}``, so ``(0, 1)`` never arises and the effect is simply that the five
matched pairs of ``{2..11}`` carry bound 10 and every other pair carries 9.
"""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from pysat.card import CardEnc, EncType
from pysat.formula import CNF

Block = Tuple[int, ...]

#: Points, 0-based.  Point 0 is the one whose link is fixed.
POINTS = 12
#: Pairs whose total degree in the design is 10 rather than 9.
MATCHING = {(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11)}
#: The residual blocks: 6-subsets of {1..11}, i.e. the blocks avoiding point 0.
RESIDUAL_BLOCKS: Tuple[Block, ...] = tuple(itertools.combinations(range(1, POINTS), 6))
RESIDUAL_VARIABLES = len(RESIDUAL_BLOCKS)  # C(11,6) = 462
#: Width of every residual coverage clause: C(7,2) = 21.
RESIDUAL_COVERAGE_WIDTH = 21


def load_link(path: Path) -> List[Block]:
    """Read a link witness and validate it as a C(11,5,3) covering.

    The file format is one block per line, five ascending points in ``1..11``,
    which is the format :func:`c1264.blocker.canonical_text` writes.  Points are
    converted to 0-based and each block is returned with point 0 prepended, i.e.
    as a block of the twelve-point design.

    Every condition below is a property the Layer-A argument already assumes of a
    link, so checking them here is not redundant: it makes the extension instance
    meaningful on its own, without trusting the file's provenance.
    """
    source = [
        tuple(int(value) - 1 for value in line.split())
        for line in Path(path).read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    return link_from_blocks(source)


def link_from_blocks(source: Sequence[Sequence[int]]) -> List[Block]:
    """Validate 0-based 5-blocks over ``{0..10}`` and lift them onto point 0."""
    source = [tuple(block) for block in source]
    if len(source) != 20 or len(set(source)) != 20:
        raise ValueError("link witness must contain 20 distinct blocks")
    for block in source:
        if len(block) != 5 or tuple(sorted(block)) != block or block[0] < 0 or block[-1] >= 11:
            raise ValueError(f"invalid C(11,5,3) link block: {block}")
    triples = set().union(*(set(itertools.combinations(block, 3)) for block in source))
    if len(triples) != 165:
        raise ValueError(f"link witness covers {len(triples)} of 165 triples")
    degrees = [sum(point in block for block in source) for point in range(11)]
    if degrees != [10] + [9] * 10:
        raise ValueError(f"link witness has degrees {degrees}, expected 10 then nine 9s")
    return [tuple([0, *(point + 1 for point in block)]) for block in source]


def build_extension(link: Sequence[Block]) -> Tuple[CNF, Dict[str, object]]:
    """Encode "the given link extends to a 40-block C(12,6,4) cover".

    UNSAT means the link cannot occur in any 40-block design, which is exactly
    the licence to block its orbit.  Returns the formula and a receipt recording
    the shape of the instance so a reviewer can check it without re-deriving it.
    """
    cnf = CNF()

    coverage: List[List[int]] = []
    for target in itertools.combinations(range(POINTS), 4):
        if any(set(target).issubset(block) for block in link):
            continue
        variables = [
            position + 1
            for position, block in enumerate(RESIDUAL_BLOCKS)
            if set(target).issubset(block)
        ]
        if not variables:
            # Unreachable for a valid link, but a silent empty clause here would
            # make the instance trivially UNSAT and the refutation worthless.
            raise AssertionError(f"uncovered quadruple has no residual block: {target}")
        coverage.append(variables)
    cnf.extend(coverage)

    segments: List[Dict[str, int | str]] = []
    for pair in itertools.combinations(range(1, POINTS), 2):
        multiplicity = sum(set(pair).issubset(block) for block in link)
        bound = (10 if pair in MATCHING else 9) - multiplicity
        variables = [
            position + 1
            for position, block in enumerate(RESIDUAL_BLOCKS)
            if set(pair).issubset(block)
        ]
        first_auxiliary = cnf.nv + 1
        encoded = CardEnc.equals(
            lits=variables, bound=bound, top_id=cnf.nv, encoding=EncType.seqcounter
        )
        cnf.extend(encoded.clauses)
        segments.append(
            {
                "pair": f"{pair[0]}-{pair[1]}",
                "link_multiplicity": multiplicity,
                "residual_bound": bound,
                "auxiliary_first": first_auxiliary,
                "auxiliary_last": encoded.nv,
            }
        )

    previous_last = RESIDUAL_VARIABLES
    for segment in segments:
        if int(segment["auxiliary_first"]) <= previous_last:
            raise AssertionError("overlapping auxiliary-variable range")
        if int(segment["auxiliary_last"]) < int(segment["auxiliary_first"]):
            raise AssertionError("empty auxiliary-variable range")
        previous_last = int(segment["auxiliary_last"])

    if any(len(clause) != RESIDUAL_COVERAGE_WIDTH for clause in coverage):
        raise AssertionError("residual coverage clause has unexpected width")
    if any(len(clause) == 1 for clause in cnf.clauses):
        raise AssertionError("extension instance must contain no unit clauses")

    receipt = {
        "variables": cnf.nv,
        "clause_count": len(cnf.clauses),
        "residual_variables": RESIDUAL_VARIABLES,
        "coverage_clause_count": len(coverage),
        "coverage_clause_width": RESIDUAL_COVERAGE_WIDTH,
        "unit_clause_count": 0,
        "link_blocks": [list(block) for block in link],
        "segments": segments,
    }
    return cnf, receipt


def write_extension(cnf: CNF, path: Path) -> str:
    """Serialise via PySAT and return the SHA-256 of the bytes written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cnf.to_file(str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()
