"""The CNF encoder: the residual trust assumption of the proof.

Read this file closely.  Everything downstream of it is machine-checked: the
solver emits a DRAT proof, ``drat-trim`` checks it and converts it to LRAT, and
``cake_lpr`` -- a checker extracted from a HOL4 correctness proof via CakeML --
checks the LRAT.  What no machine checks is the step performed *here*: the
translation from the combinatorial claim about coverings into propositional
clauses.  The paper says so explicitly, and this module is deliberately small,
dependency-light and comment-heavy so that a referee can read it end to end.

Instance anatomy
----------------
Every link instance is the concatenation, in this order, of

  1. **coverage** -- 165 positive clauses, one per 3-subset of {1..11}
     (:func:`c1264.blocks.coverage_clauses`);
  2. **cardinality** -- for each point 1..11 in ascending order, a clause set
     encoding an *exact* degree equality (10 for point 1, 9 otherwise) via
     PySAT's ``CardEnc.equals``;
  3. **tail** -- the orbit blocker, plus the case-tree units that pin this node.

Clause order matters.  The published SHA-256 hashes are over the DIMACS bytes,
so any reordering, any change to the variable layout, and any change to the
PySAT version that alters ``CardEnc`` output will change them.  See
``docs/REPRODUCIBILITY.md``.

Why exact degrees and no |L| constraint
--------------------------------------
The eleven equalities already force |L| = 20 (degree sum 100, block size 5), so
adding a global cardinality constraint would be redundant.  Keeping the
architecture per-point makes the encoding local and auditable: each clause
group is a statement about one point, and ``bin/encoder_sanity.py`` brute-forces
``CardEnc.equals`` against ground truth on small cases to check the one library
primitive being trusted.
"""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pysat.card import CardEnc, EncType
from pysat.formula import CNF

from .blocks import (
    BLOCKS,
    POSITION,
    PRIMARY_VARIABLES,
    coverage_clauses,
    implied_block_count,
    point_degree,
    point_literals,
)
from .group import LINK_ROOTS
from .orbits import negate, parse_blockers, root_orbits, secondary_orbits, tertiary_orbits

Clause = List[int]

#: The two cardinality translations used for the cross-encoding check.  Both
#: encode the same eleven equalities; agreement of their non-cardinality cores
#: proves they state the same problem, and independent UNSAT results on both
#: means a bug in one translation cannot carry the theorem.
ENCODINGS: Dict[str, int] = {
    "sequential": EncType.seqcounter,
    "kmtotalizer": EncType.kmtotalizer,
}

#: Schema version of the receipt emitted alongside each instance.
RECEIPT_SCHEMA_VERSION = 1


def digest_clauses(clauses: List[Clause]) -> str:
    """SHA-256 over clauses rendered in DIMACS body form.

    Used for the ``non_cardinality_core_sha256`` receipt field, which is how the
    artifact demonstrates that two differently-encoded instances state the same
    combinatorial problem.
    """
    payload = "".join(" ".join(map(str, clause)) + " 0\n" for clause in clauses)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def non_cardinality_core(
    blocker_path: Path,
    root_index: int,
    secondary_index: int,
    tertiary_index: Optional[int],
) -> Tuple[List[Clause], List[Clause], dict]:
    """Build every clause of a node that is *not* a cardinality clause.

    Returns ``(coverage, tail, metadata)``.  The split matters because the
    cardinality clauses are the only part that differs between the two
    encodings; hashing ``coverage + tail`` therefore identifies the
    combinatorial problem independently of its arithmetic translation.

    The tail is assembled in a fixed order:

      * the orbit blocker clauses, verbatim from ``blocker_path``;
      * for each earlier primary orbit, units forcing its blocks false;
      * a unit asserting the canonical primary root true;
      * likewise for the secondary level, then (optionally) the tertiary level.
    """
    coverage = coverage_clauses()
    tail = parse_blockers(blocker_path, PRIMARY_VARIABLES)
    blocker_clause_count = len(tail)

    primary_partition = root_orbits()
    earlier_primary = set().union(*primary_partition[:root_index]) if root_index else set()
    tail.extend(negate(earlier_primary))
    primary = LINK_ROOTS[root_index]
    tail.append([POSITION[primary]])

    secondaries = secondary_orbits(root_index)
    earlier_secondary = set().union(*secondaries[:secondary_index]) if secondary_index else set()
    tail.extend(negate(earlier_secondary))
    secondary = min(secondaries[secondary_index])
    tail.append([POSITION[secondary]])

    tertiary = None
    earlier_tertiary: set = set()
    if tertiary_index is not None:
        tertiaries = tertiary_orbits(root_index, secondary_index)
        earlier_tertiary = set().union(*tertiaries[:tertiary_index]) if tertiary_index else set()
        tail.extend(negate(earlier_tertiary))
        tertiary = min(tertiaries[tertiary_index])
        tail.append([POSITION[tertiary]])

    metadata = {
        "root_index": root_index,
        "secondary_index": secondary_index,
        "tertiary_index": tertiary_index,
        "primary_canonical_block": list(primary),
        "secondary_canonical_block": list(secondary),
        "tertiary_canonical_block": None if tertiary is None else list(tertiary),
        "coverage_clause_count": len(coverage),
        "blocker_clause_count": blocker_clause_count,
        "earlier_primary_units": len(earlier_primary),
        "earlier_secondary_units": len(earlier_secondary),
        "earlier_tertiary_units": len(earlier_tertiary),
    }
    return coverage, tail, metadata


def base_cnf(encoding_name: str) -> Tuple[CNF, List[dict]]:
    """The part of every link instance that does not depend on the case node.

    That is: the 165 coverage clauses followed by the eleven exact-degree
    constraints, in ascending point order.  Both the case-tree nodes
    (:func:`build_cnf`) and the auxiliary tail instances
    (:mod:`c1264.auxiliary`) start from exactly this formula, so it lives in one
    function -- in the campaign code it was retyped in four separate builders.

    Returns the formula and the eleven per-point segment records.
    """
    if encoding_name not in ENCODINGS:
        raise ValueError(f"unknown encoding {encoding_name!r}; expected one of {sorted(ENCODINGS)}")

    cnf = CNF()
    cnf.extend(coverage_clauses())

    segments = []
    for point in range(1, 12):
        literals = point_literals(point)
        bound = point_degree(point)
        clause_first = len(cnf.clauses)
        prior_top = cnf.nv
        encoded = CardEnc.equals(
            lits=literals,
            bound=bound,
            top_id=cnf.nv,
            encoding=ENCODINGS[encoding_name],
        )
        cnf.extend(encoded.clauses)
        segment_clauses = cnf.clauses[clause_first:]
        segments.append({
            "point": point,
            "bound": bound,
            "primary_literal_count": len(literals),
            "primary_literals_sha256": hashlib.sha256(
                (" ".join(map(str, literals)) + "\n").encode("ascii")
            ).hexdigest(),
            "clause_first_zero_based": clause_first,
            "clause_count": len(segment_clauses),
            "clause_sha256": digest_clauses(segment_clauses),
            "auxiliary_first": prior_top + 1,
            "auxiliary_last": encoded.nv,
            "auxiliary_count": encoded.nv - prior_top,
        })
    return cnf, segments


def build_cnf(blocker_path: Path, leaf: dict, encoding_name: str) -> Tuple[CNF, dict]:
    """Build one case-tree node's CNF, with a per-segment provenance receipt.

    ``leaf`` carries ``root_index``, ``secondary_index`` and an optional
    ``tertiary_index`` (``None`` for two-block nodes).  ``encoding_name`` is a
    key of :data:`ENCODINGS`.

    The receipt records, for each of the eleven degree constraints, the exact
    clause range it occupies, its own hash, and the auxiliary variable range it
    claimed.  That is what lets a reviewer confirm the cardinality clauses are
    the *only* difference between the two encodings without re-deriving them.
    """
    if encoding_name not in ENCODINGS:
        raise ValueError(f"unknown encoding {encoding_name!r}; expected one of {sorted(ENCODINGS)}")
    root_index = int(leaf["root_index"])
    secondary_index = int(leaf["secondary_index"])
    tertiary_raw = leaf.get("tertiary_index")
    tertiary_index = None if tertiary_raw is None else int(tertiary_raw)

    coverage, tail, root_metadata = non_cardinality_core(
        blocker_path, root_index, secondary_index, tertiary_index
    )

    cnf, segments = base_cnf(encoding_name)
    if cnf.clauses[: len(coverage)] != coverage:
        raise AssertionError("base formula does not start with the coverage clauses")

    tail_first = len(cnf.clauses)
    cnf.extend(tail)

    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "encoding": encoding_name,
        "primary_variables": PRIMARY_VARIABLES,
        "implied_block_count": implied_block_count(),
        "coverage_clause_count": len(coverage),
        "cardinality_clause_count": sum(int(row["clause_count"]) for row in segments),
        "tail_clause_first_zero_based": tail_first,
        "tail_clause_count": len(tail),
        "non_cardinality_core_sha256": digest_clauses(coverage + tail),
        "coverage_sha256": digest_clauses(coverage),
        "tail_sha256": digest_clauses(tail),
        "segments": segments,
        "root": root_metadata,
    }
    return cnf, receipt


def write_cnf(cnf: CNF, path: Path) -> str:
    """Write ``cnf`` in DIMACS form and return its SHA-256.

    Serialisation goes through PySAT's own ``to_file`` so that the bytes match
    the published hashes exactly; do not hand-roll the DIMACS writer here.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cnf.to_file(str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_blocks(model: List[int]) -> Tuple[Tuple[int, ...], ...]:
    """The link implied by a satisfying assignment, ignoring auxiliary variables."""
    positives = {literal for literal in model if 0 < literal <= PRIMARY_VARIABLES}
    return tuple(BLOCKS[index - 1] for index in sorted(positives))
