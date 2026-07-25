"""Clean-room sequential-counter EQUALS encoder. NO PySAT import.

Implements the pruned sequential-counter ("commander-free" Sinz LT_{n,k}) cardinality
encoding from the published construction:

    C. Sinz, "Towards an optimal CNF encoding of Boolean cardinality constraints",
    CP 2005, LNCS 3709, pp. 827-831.

EQUALS(lits, k) is emitted as the AT-LEAST block followed by the AT-MOST block, where
AT-LEAST(lits, k) := AT-MOST([-l for l in lits], n-k).

AT-MOST(x_1..x_n, k) uses partial-sum registers s_{i,j} ("at least j of x_1..x_i are
true"), restricted to the useful window

    j in [max(1, i + k - n + 1), min(i, k)],   i in 1..n-1

(registers outside the window cannot influence the constraint).  Clause set, exactly
the Sinz clauses restricted to in-window registers:

    set:        (-x_i  v  s_{i,1})                      for each in-window (i,1)
    propagate:  (-s_{i,j}  v  s_{i+1,j})                when (i+1,j) in window
    increment:  (-x_{i+1}  v  -s_{i,j}  v  s_{i+1,j+1}) when j<k and (i+1,j+1) in window
    overflow:   (-x_{i+1}  v  -s_{i,k})                 when j==k

Emission order and auxiliary numbering are presentational conventions fixed so the
output is byte-reproducible: clauses are emitted along diagonals d = 1..n-k (the chain
of registers with i-j = d-1, walked upward from (d,1)); at each register we emit
propagate then increment/overflow; each diagonal starts with its set clause.
Auxiliary variables are numbered in order of first appearance, starting at top_id+1.

The mathematical content (the clause SET and its correctness as an encoding of the
cardinality constraint) comes from the published construction; only the ordering and
numbering conventions were fixed by observation, and they do not affect semantics.
"""


def atmost_seq(lits: list[int], k: int, top: int) -> tuple[list[list[int]], int]:
    """Pruned sequential-counter AT-MOST(k) over lits; aux vars start at top+1.

    Returns (clauses, new_top). Requires 0 < k < n (no edge cases occur in this
    campaign: every segment has n=210, k in {9, 10, 200, 201}).
    """
    n = len(lits)
    assert 0 < k < n, (n, k)
    reg: dict[tuple[int, int], int] = {}

    def in_window(i: int, j: int) -> bool:
        return 1 <= i <= n - 1 and max(1, i + k - n + 1) <= j <= min(i, k)

    def var(i: int, j: int) -> int:
        nonlocal top
        if (i, j) not in reg:
            top += 1
            reg[(i, j)] = top
        return reg[(i, j)]

    clauses: list[list[int]] = []
    for d in range(1, n - k + 1):
        i, j = d, 1
        clauses.append([-lits[i - 1], var(i, j)])          # set s_{d,1}
        while True:
            if in_window(i + 1, j):                        # propagate
                clauses.append([-var(i, j), var(i + 1, j)])
            if j == k:                                     # overflow
                clauses.append([-lits[i], -var(i, j)])
                break
            if in_window(i + 1, j + 1):                    # increment
                clauses.append([-lits[i], -var(i, j), var(i + 1, j + 1)])
                i, j = i + 1, j + 1
            else:
                break
    return clauses, top


def equals_seq(lits: list[int], bound: int, top_id: int) -> tuple[list[list[int]], int]:
    """EQUALS(lits, bound): at-least block (atmost on negated lits, n-bound) then
    at-most block. Returns (clauses, top)."""
    n = len(lits)
    atleast, top = atmost_seq([-l for l in lits], n - bound, top_id)
    atmost, top = atmost_seq(lits, bound, top)
    return atleast + atmost, top
