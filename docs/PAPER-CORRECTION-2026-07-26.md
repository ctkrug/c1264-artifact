# Paper correction prepared 2026-07-26

The proof of `C(12,6,4)=41` is unchanged. A post-submission audit found two
publication-record defects, corrected together in this version:

1. The submitted paper attributed `C(11,5,3)=20` to Mills's 1979 survey and
   stated that no published statement of the uniqueness result had been
   located. Both statements were wrong. The exact value has its own paper:
   W. H. Mills, *The covering number C(11,5,3)*, Utilitas Math. 41 (1992),
   63 (Zbl 0754.05029). The uniqueness of the 20-block covering is also
   published: G. H. J. van Rees, *A note on C(10,4,2) and C(11,5,3)*,
   Congr. Numer. 99 (1994), 271-275 (Zbl 0809.05028) proves both
   `C(11,5,3)=20` and uniqueness up to isomorphism. The corrected paper
   cites both and presents its uniqueness proposition as a
   certificate-backed reproof, claiming no priority.
2. Artifact v1.0.0 omitted the exact `kmtotalizer` CNF checked by the retained
   `s-r0-2` proof. Version 1.0.1 adds that formula at
   `data/cnf-checked/s-r0-2.kmtotalizer.cnf` and adds
   `bin/replay_deposit.py`, which maps all 81 deposited proofs to their exact
   checked CNFs before replay.

The corrected manuscript `c1264.tex` has SHA-256
`6d5bb175440b4298089f39a998b5a3a3edabcd5475a17ab40c7aa3551fcc3132`;
its rendered PDF has SHA-256
`942e46ae1a66485b8404988de7e3b3a155a8f16ab7abe69293c8e781615e1f83`.
The correction basis was verified before editing: the manuscript the
corrections were applied to is byte-identical (SHA-256
`7298ec7c26de0e54b07815a6d7f940b7efbedb76c190962e46317e4390ae74db`) to the
preserved copy of the single-file source uploaded to arXiv submission
`submit/7868842`, which was withdrawn before announcement on 2026-07-26 so
that the corrected source could be resubmitted in its place.

Do not modify or replace the immutable v1.0.0 Zenodo records
(10.5281/zenodo.21572070, 10.5281/zenodo.21573716, 10.5281/zenodo.21573863).
Publish versioned successors and link the correction explicitly.
