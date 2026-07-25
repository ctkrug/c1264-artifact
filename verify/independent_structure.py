"""Item 2, part 1: re-derive the branch-space structure FROM SCRATCH.

Imports nothing from the campaign codebase. Everything below is rebuilt from the
definition of the problem:
  - links live on points {1..11}; blocks are 5-subsets; G = C2 wr S5 fixes point 1
    and permutes the five pairs {2,3},{4,5},{6,7},{8,9},{10,11}.
Checks, in order:
  (A) G is a genuine group of order 3840 acting faithfully on {1..11}, fixing 1.
  (B) the 6 root orbits on the 462 blocks, their sizes, and the identity
      "the orbits consisting of blocks through point 1 are exactly 3 orbits, 210 blocks".
  (C) secondary orbit counts under the setwise stabiliser of each root representative.
  (D) tertiary orbit count under the joint stabiliser of (root rep, secondary rep) for (r0,s0).
  (E) the branch-space arithmetic and the closure attribution partition.
  (F) blocker-20's 15120 clauses are exactly the G-images of 20 links, and G-invariant.
"""
import json, itertools, hashlib
from pathlib import Path

R = Path("/Users/Krug/c1264-ledger-preserved")
OUT = {}

# ---------------------------------------------------------------- (A) the group
PAIRS = [(2,3),(4,5),(6,7),(8,9),(10,11)]

def group_elements():
    els = set()
    for perm in itertools.permutations(range(5)):          # S5 on the pairs
        for flips in itertools.product((0,1), repeat=5):   # C2^5 within pairs
            m = {1:1}
            for src in range(5):
                dst = perm[src]
                a,b = PAIRS[src]
                c,d = PAIRS[dst]
                if flips[src]: c,d = d,c
                m[a],m[b] = c,d
            els.add(tuple(m[i] for i in range(1,12)))
    return sorted(els)

G = group_elements()
def apply(g, pt):  return g[pt-1]
def act_block(g, blk): return tuple(sorted(apply(g,p) for p in blk))

ident = tuple(range(1,12))
Gset = set(G)
checks = {
    "order": len(G),
    "order_is_3840": len(G) == 3840,
    "all_distinct": len(Gset) == len(G),
    "all_bijections": all(sorted(g) == list(range(1,12)) for g in G),
    "all_fix_point_1": all(g[0] == 1 for g in G),
    "contains_identity": ident in Gset,
    "closed_under_composition": all(
        tuple(g[h[i]-1] for i in range(11)) in Gset
        for g in G[::37] for h in G[::53]),
    "closed_under_inverse": all(
        tuple(sorted(range(1,12), key=lambda p: g[p-1])) in Gset for g in G),
}
OUT["A_group"] = checks
print("(A) group:", json.dumps(checks))

# ------------------------------------------------------- (B) root orbits on blocks
BLOCKS = sorted(itertools.combinations(range(1,12), 5))
assert len(BLOCKS) == 462

def orbits_of(group, items):
    """Orbits of `group` on `items`, seeded by minimum element; returns list of sorted tuples."""
    remaining = set(items)
    out = []
    while remaining:
        seed = min(remaining)
        orb = set()
        frontier = [seed]
        while frontier:
            x = frontier.pop()
            if x in orb: continue
            orb.add(x)
            for g in group:
                y = act_block(g, x)
                if y not in orb: frontier.append(y)
        out.append(tuple(sorted(orb)))
        remaining -= orb
    return sorted(out, key=lambda o: (min(o),))

root_orbits = orbits_of(G, BLOCKS)
sizes = [len(o) for o in root_orbits]
through1 = [o for o in root_orbits if all(1 in b for b in o)]
mixed    = [o for o in root_orbits if any(1 in b for b in o) and not all(1 in b for b in o)]
n_through1_blocks = sum(len(o) for o in through1)
b = {
    "n_root_orbits": len(root_orbits),
    "sizes_sorted": sorted(sizes),
    "sizes_sum": sum(sizes),
    "partitions_462": sum(sizes) == 462 and len(set().union(*[set(o) for o in root_orbits])) == 462,
    "orbits_entirely_through_point_1": len(through1),
    "orbits_mixed_on_point_1": len(mixed),
    "blocks_through_point_1": n_through1_blocks,
    "equals_C_10_4": n_through1_blocks == 210,
    "orbit_stabilizer_holds": all(3840 % len(o) == 0 for o in root_orbits),
}
OUT["B_root"] = b
print("(B) root orbits:", json.dumps(b))

# ------------------------------------------- (C) secondary orbits under root stabiliser
def stabiliser(group, blk):
    return [g for g in group if act_block(g, blk) == tuple(sorted(blk))]

sec = {}
for orb in root_orbits:
    rep = orb[0]
    S = stabiliser(G, rep)
    assert len(S) * len(orb) == 3840, (len(S), len(orb))
    rest = [x for x in BLOCKS if x != rep]
    so = orbits_of(S, rest)
    sec[len(orb)] = {"rep": list(rep), "stab_order": len(S), "n_secondary_orbits": len(so),
                     "orbit_stabilizer_identity": len(S)*len(orb) == 3840}
    print(f"(C) root orbit size {len(orb):3}  |stab|={len(S):4}  secondary orbits = {len(so)}", flush=True)
    if len(orb) == 80:
        sec80_orbits, sec80_rep_stab, sec80_rep = so, S, rep
OUT["C_secondary"] = sec

# --------------------------------- (D) tertiary orbits under joint stabiliser of (r0, s0)
s0 = sec80_orbits[0]
s0rep = s0[0]
S2 = [g for g in sec80_rep_stab if act_block(g, s0rep) == tuple(sorted(s0rep))]
rest2 = [x for x in BLOCKS if x != sec80_rep and x != s0rep]
ter = orbits_of(S2, rest2)
d = {"root_rep": list(sec80_rep), "secondary_rep": list(s0rep),
     "joint_stab_order": len(S2), "n_tertiary_orbits": len(ter)}
OUT["D_tertiary"] = d
print("(D) tertiary:", json.dumps(d), flush=True)

Path(R/"final"/"independent-structure.json").write_text(json.dumps(OUT, indent=1))
print("WROTE independent-structure.json")
