"""Uniqueness of the optimal 3-(11,5,1) covering: the S11-orbit computation.

Backs Proposition (uniqueness) of paper/c1264.tex:
  - BFS the S11-orbit of the witness E (adjacent transpositions generate S11).
  - Assert orbit size 166,320 = 11!/240.
  - Assert every one of the 15,120 blocked coverings (blocker-20.cnf) lies in the orbit.
  - Assert the orbit members whose unique degree-10 point is the point 1 are exactly
    the blocked set (166,320 / 11 = 15,120 consistency check).

Conventions identical to independent_witness_blocker.py: blocks are 5-subsets of
{1..11}; DIMACS variable i is BLOCKS[i-1] with BLOCKS = sorted 5-combinations.
Output: final/uniqueness-orbit.json
"""
import itertools, json, hashlib
from collections import deque
from pathlib import Path

R = Path(__file__).resolve().parents[1]
BLOCKS = sorted(itertools.combinations(range(1, 12), 5))

# ---- witness E, decoded exactly as in independent_witness_blocker.py
lits = []
for line in open(R / "completeness/logs/root-tail.solve"):
    if line.startswith("v "):
        lits += [int(x) for x in line.split()[1:]]
model = set(l for l in lits if 0 < l <= 462)
E = frozenset(BLOCKS[l - 1] for l in model)
assert len(E) == 20

# ---- blocked set from blocker-20.cnf (each clause = one forbidden 20-block link)
blocked = set()
for line in open(R / "work/loop/blocker-20.cnf"):
    line = line.strip()
    if not line or line[0] in "cp":
        continue
    ls = [int(x) for x in line.split()]
    assert ls[-1] == 0
    lits = ls[:-1]
    assert len(lits) == 20 and all(l < 0 for l in lits)
    blocked.add(frozenset(BLOCKS[-l - 1] for l in lits))
assert len(blocked) == 15120

# ---- BFS the S11-orbit of E under adjacent transpositions (they generate S11)
def act(t, cov):  # t = (a, b) transposition
    a, b = t
    def m(p):
        return b if p == a else a if p == b else p
    return frozenset(tuple(sorted(m(p) for p in blk)) for blk in cov)

gens = [(i, i + 1) for i in range(1, 11)]
orbit = {E}
q = deque([E])
while q:
    c = q.popleft()
    for t in gens:
        d = act(t, c)
        if d not in orbit:
            orbit.add(d)
            q.append(d)

# ---- checks
def deg10_point(cov):
    deg = {p: 0 for p in range(1, 12)}
    for blk in cov:
        for p in blk:
            deg[p] += 1
    tens = [p for p, d in deg.items() if d == 10]
    assert sorted(deg.values()) == [9] * 10 + [10]
    return tens[0]

normalised = {c for c in orbit if deg10_point(c) == 1}
out = {
    "witness_sha256": hashlib.sha256(json.dumps(sorted(E)).encode()).hexdigest(),
    "orbit_size": len(orbit),
    "orbit_size_expected": 166320,
    "orbit_size_is_11fact_over_240": len(orbit) == 39916800 // 240,
    "blocked_count": len(blocked),
    "blocked_subset_of_orbit": blocked <= orbit,
    "orbit_members_with_deg10_point_1": len(normalised),
    "normalised_equals_blocked": normalised == blocked,
    "aut_order_by_orbit_stabiliser": 39916800 // len(orbit),
}
Path(R / "final/uniqueness-orbit.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
assert out["orbit_size"] == 166320 and out["blocked_subset_of_orbit"] and out["normalised_equals_blocked"]
print("UNIQUENESS ORBIT: ALL CHECKS PASS")
