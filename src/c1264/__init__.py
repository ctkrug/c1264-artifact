"""Reproduction library for the machine-checked proof that C(12,6,4) = 41.

Modules
-------
group      the symmetry group C2 (wr) S5 of order 3840 -- single source of truth
blocks     variable layout, coverage clauses, exact per-point degrees
orbits     case-tree orbit partitions and orbit-blocker parsing
encode     the CNF encoder: the proof's residual trust assumption
frontier   the 47 frontier nodes and their published CNF hashes
cover      upper-bound verification of an explicit 41-block design
"""

__version__ = "1.0.0"
