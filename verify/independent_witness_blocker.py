"""Item 2, part 2: (E) validate the root-tail SAT witness against MY OWN orbit
computation, and (F) audit blocker-20 as a G-invariant union of complete orbits.

Nothing is imported from the campaign codebase; the group and the orbits are rebuilt here.
"""
import itertools, json, hashlib
from pathlib import Path

R = Path("/Users/Krug/c1264-ledger-preserved")
PAIRS = [(2,3),(4,5),(6,7),(8,9),(10,11)]
def group_elements():
    els=set()
    for perm in itertools.permutations(range(5)):
        for flips in itertools.product((0,1),repeat=5):
            m={1:1}
            for src in range(5):
                a,b=PAIRS[src]; c,d=PAIRS[perm[src]]
                if flips[src]: c,d=d,c
                m[a],m[b]=c,d
            els.add(tuple(m[i] for i in range(1,12)))
    return sorted(els)
G=group_elements()
def act(g,blk): return tuple(sorted(g[p-1] for p in blk))
BLOCKS=sorted(itertools.combinations(range(1,12),5))

def orbits_of(group, items):
    rem=set(items); out=[]
    while rem:
        seed=min(rem); orb=set(); fr=[seed]
        while fr:
            x=fr.pop()
            if x in orb: continue
            orb.add(x)
            for g in group:
                y=act(g,x)
                if y not in orb: fr.append(y)
        out.append(frozenset(orb)); rem-=orb
    return out

root_orbits = orbits_of(G, BLOCKS)
# reconcile to the campaign's indexing, which is by orbit SIZE: r0=80, r1=120, r2=10
by_size = {len(o): o for o in root_orbits}
CAMPAIGN = {0: by_size[80], 1: by_size[120], 2: by_size[10]}
OUT = {}

# ---------------------------------------------------------------- (E) the SAT witness
lits=[]
for line in open(R/"completeness/logs/root-tail.solve"):
    if line.startswith("v "): lits += [int(x) for x in line.split()[1:]]
model = set(l for l in lits if 0 < l <= 462)
sel = sorted(BLOCKS[l-1] for l in model)
tri = list(itertools.combinations(range(1,12),3))
uncov = [t for t in tri if not any(set(t) <= set(b) for b in sel)]
deg = [sum(1 for b in sel if p in b) for p in range(1,12)]
S = set(sel)
hit = sorted(i for i,o in CAMPAIGN.items() if S & set(o))
allhit = sorted(len(o) for o in root_orbits if S & set(o))
w = {
  "blocks": len(sel),
  "distinct_blocks": len(set(sel)),
  "is_20_block_cover": len(sel)==20 and len(uncov)==0,
  "triples": len(tri), "uncovered_triples": len(uncov),
  "degrees": deg,
  "degrees_are_forced_vector": sorted(deg)==[9]*10+[10],
  "campaign_root_orbits_hit": hit,
  "first_hit_r": min(hit) if hit else None,
  "hits_r0_or_r1": bool(set(hit) & {0,1}),
  "orbit_sizes_hit": allhit,
  "model_sha256": hashlib.sha256(json.dumps(sel).encode()).hexdigest(),
}
w["falsifies_inherited_frontier"] = (w["is_20_block_cover"] and w["degrees_are_forced_vector"]
                                     and not w["hits_r0_or_r1"] and w["first_hit_r"]==2)
OUT["E_witness"]=w
print("(E) witness:", json.dumps(w))

# ------------------------------------------------------------------ (F) blocker-20
bl = R/"work/loop/blocker-20.cnf"
clauses=[]
for line in open(bl):
    line=line.strip()
    if not line or line[0] in "cp": continue
    ls=[int(x) for x in line.split()]
    assert ls[-1]==0; clauses.append(tuple(sorted(ls[:-1])))
# each clause should be a 20-wide all-negative clause over block variables 1..462:
# "not all of these 20 blocks are simultaneously selected" = the negation of one link
widths=set(len(c) for c in clauses)
allneg=all(all(l<0 for l in c) for c in clauses)
links=set(frozenset(-l for l in c) for c in clauses)
inrange=all(all(1 <= -l <= 462 for l in c) for c in clauses)
# G-closure via three GENERATORS of C2 wr S5. Closure under a generating set is
# equivalent to closure under the whole group, and is what makes this tractable.
IDX = {b:i+1 for i,b in enumerate(BLOCKS)}
def perm_from(pairperm, flips):
    m={1:1}
    for src in range(5):
        a,b=PAIRS[src]; c,d=PAIRS[pairperm[src]]
        if flips[src]: c,d=d,c
        m[a],m[b]=c,d
    return tuple(m[i] for i in range(1,12))
GENS = [perm_from((1,0,2,3,4),(0,0,0,0,0)),   # swap pair 1 and pair 2
        perm_from((1,2,3,4,0),(0,0,0,0,0)),   # 5-cycle of the pairs
        perm_from((0,1,2,3,4),(1,0,0,0,0))]   # flip inside pair 1
assert all(g in set(G) for g in GENS)
BLKTAB = [{v: IDX[act(g, BLOCKS[v-1])] for v in range(1,463)} for g in GENS]
def act_link(gi, lk): 
    t = BLKTAB[gi]
    return frozenset(t[v] for v in lk)
closed = all(act_link(gi, lk) in links for gi in range(3) for lk in links)
# orbit decomposition under the generators (== orbits under the full group)
seen=set(); orbit_reps=[]
for lk in links:
    if lk in seen: continue
    orb={lk}; fr=[lk]
    while fr:
        x=fr.pop()
        for gi in range(3):
            y=act_link(gi,x)
            if y not in orb: orb.add(y); fr.append(y)
    seen |= orb; orbit_reps.append(len(orb))
f = {
  "clauses": len(clauses), "distinct_clauses": len(set(clauses)),
  "clause_widths": sorted(widths), "all_negative": allneg,
  "vars_in_block_range": inrange,
  "distinct_blocked_links": len(links),
  "orbit_count": len(orbit_reps), "orbit_sizes": sorted(orbit_reps),
  "orbit_sizes_sum": sum(orbit_reps),
  "closed_under_all_three_generators": closed,
  "is_union_of_complete_G_orbits": closed and sum(orbit_reps)==len(links),
  "sha256": hashlib.sha256(bl.read_bytes()).hexdigest(),
}
OUT["F_blocker20"]=f
print("(F) blocker-20:", json.dumps(f))
Path(R/"final"/"independent-witness-blocker.json").write_text(json.dumps(OUT, indent=1))
print("WROTE independent-witness-blocker.json")
