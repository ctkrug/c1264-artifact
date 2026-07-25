"""The case-tree frontier: which nodes exist, and what pins each one.

``data/frontier.json`` is the machine-readable statement of the case
distinction the proof closes.  For each of the 47 frontier nodes it records

  * ``leaf``           -- the (root, secondary, tertiary) orbit indices;
  * ``blocker``        -- which orbit blocker CNF is conjoined, as a path
                          relative to the repository root;
  * ``blocker_orbits`` -- how many blocked orbits that file represents (9, 13
                          or 20; the blocker grew as the campaign progressed,
                          and a node must be regenerated with the blocker it
                          was actually solved against);
  * ``cnf_sha256``     -- the published DIMACS hash, from the campaign ledger.

Node naming
-----------
``s-rR-N``  two-block node: primary orbit ``R``, secondary orbit ``N``.
``t-N``     three-block node under ``(r=0, s=0)``: tertiary orbit ``N``.

The 47 nodes are 6 ``s-r0-*`` + 8 ``s-r1-*`` + 33 ``t-*``.  Exhaustiveness of
this set is not asserted here -- it is established by the auxiliary tail
instances (see ``docs/PROOF-MAP.md``), which refute the complementary regions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

#: Repository root, derived from this file's location.  No absolute paths appear
#: anywhere in this artifact; everything resolves relative to here.
REPO_ROOT = Path(__file__).resolve().parents[2]

FRONTIER_PATH = REPO_ROOT / "data" / "frontier.json"

#: Expected node counts, checked on load so a truncated data file cannot pass.
EXPECTED_NODES = 47
EXPECTED_BY_PREFIX = {"s-r0-": 6, "s-r1-": 8, "t-": 33}


def load_frontier(path: Path | None = None) -> Dict[str, dict]:
    """Load and validate the frontier definition."""
    path = Path(path) if path is not None else FRONTIER_PATH
    nodes = json.loads(path.read_text(encoding="utf-8"))
    if len(nodes) != EXPECTED_NODES:
        raise AssertionError(f"{path}: {len(nodes)} nodes, expected {EXPECTED_NODES}")
    for prefix, expected in EXPECTED_BY_PREFIX.items():
        found = sum(1 for name in nodes if name.startswith(prefix))
        if found != expected:
            raise AssertionError(f"{path}: {found} {prefix}* nodes, expected {expected}")
    for name, record in nodes.items():
        missing = {"leaf", "blocker", "blocker_orbits", "cnf_sha256"} - set(record)
        if missing:
            raise AssertionError(f"{path}: node {name} is missing {sorted(missing)}")
        if not (REPO_ROOT / record["blocker"]).is_file():
            raise FileNotFoundError(f"node {name} references missing blocker {record['blocker']}")
    return nodes


def blocker_path(record: dict) -> Path:
    """Absolute path to the blocker CNF a node was solved against."""
    return REPO_ROOT / record["blocker"]
