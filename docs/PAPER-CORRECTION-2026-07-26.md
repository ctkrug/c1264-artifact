# Paper correction prepared 2026-07-26

The proof of `C(12,6,4)=41` is unchanged. A takeover audit found two
publication-record defects that should be corrected together:

1. G. H. J. van Rees, *Three Constructions of Covers*, J. Combin. Math.
   Combin. Comput. 16 (1994), p. 22 explicitly records both
   `C(11,5,3)=20` and uniqueness, crediting Mills's three base blocks. The
   paper must cite W. H. Mills, *The covering number C(11,5,3)*, Utilitas
   Math. 41 (1992), 63 for the exact value and van Rees for the published
   uniqueness statement. The computation in the paper is a
   certificate-backed reproof, not a first uniqueness result.
2. Artifact v1.0.0 omitted the exact `kmtotalizer` CNF checked by the retained
   `s-r0-2` proof. Version 1.0.1 adds that formula at
   `data/cnf-checked/s-r0-2.kmtotalizer.cnf` and adds
   `bin/replay_deposit.py`, which maps all 81 deposited proofs to their exact
   checked CNFs before replay.

The local corrected manuscript candidate is
`/Users/Krug/dev/c1264-paper-revision/c1264.tex`, SHA-256
`4e97e7f5073e8c06a367eead5e594160f4c0c9a84e318c3ad1a9d7aacedc9f29`.
Its rendered PDF has SHA-256
`72c4837021d7c1249db36fe34be1c3fb13ecbc2a01702a7aef1b3d227421be8c`.
These are staging files, not release objects. The exact single-file source
uploaded to arXiv submission `submit/7868842` must be downloaded and diffed
before the correction is submitted.

Do not modify or replace the immutable v1.0.0 Zenodo records. Publish versioned
successors and link the correction explicitly.
