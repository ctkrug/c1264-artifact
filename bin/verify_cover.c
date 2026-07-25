/* Upper-bound checker B (C, nested-loop membership algorithm — no bitmasks,
 * no code shared with checker A).
 * Reads a design file (one block per line, 6 integers). Verifies exactly 41
 * blocks, each 6 distinct integers in 1..12, and that every 4-subset
 * {a<b<c<d} of {1..12} lies inside some block, testing membership by direct
 * per-element scan. Prints VALID and exits 0 only if all checks pass. */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: %s design.txt\n", argv[0]); return 2; }
    FILE *f = fopen(argv[1], "r");
    if (!f) { perror("open"); return 2; }
    int blk[64][6], nb = 0, x;
    while (nb < 64) {
        int got = 0;
        for (got = 0; got < 6; got++) {
            if (fscanf(f, "%d", &x) != 1) break;
            blk[nb][got] = x;
        }
        if (got == 0) break;
        if (got != 6) { printf("ERROR: trailing partial block\nINVALID\n"); return 1; }
        nb++;
    }
    fclose(f);
    int bad = 0;
    if (nb != 41) { printf("ERROR: block count %d != 41\n", nb); bad = 1; }
    for (int i = 0; i < nb; i++)
        for (int j = 0; j < 6; j++) {
            if (blk[i][j] < 1 || blk[i][j] > 12) { printf("ERROR: block %d element %d out of range\n", i, blk[i][j]); bad = 1; }
            for (int k = j + 1; k < 6; k++)
                if (blk[i][j] == blk[i][k]) { printf("ERROR: block %d repeats %d\n", i, blk[i][j]); bad = 1; }
        }
    long total = 0, uncovered = 0;
    for (int a = 1; a <= 12; a++)
     for (int b = a + 1; b <= 12; b++)
      for (int c = b + 1; c <= 12; c++)
       for (int d = c + 1; d <= 12; d++) {
        total++;
        int quad[4] = {a, b, c, d}, cov = 0;
        for (int i = 0; i < nb && !cov; i++) {
            int inside = 1;
            for (int q = 0; q < 4 && inside; q++) {
                int found = 0;
                for (int j = 0; j < 6; j++) if (blk[i][j] == quad[q]) found = 1;
                if (!found) inside = 0;
            }
            if (inside) cov = 1;
        }
        if (!cov) { printf("ERROR: uncovered %d %d %d %d\n", a, b, c, d); uncovered++; }
    }
    printf("checker=B-c-nestedloops blocks=%d quadruples=%ld uncovered=%ld\n", nb, total, uncovered);
    if (bad || uncovered) { printf("INVALID\n"); return 1; }
    printf("VALID: 41 genuine 6-subsets of {1..12} covering all 495 quadruples\n");
    return 0;
}
