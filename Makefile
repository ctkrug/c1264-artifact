# Reproduction driver for C(12,6,4) = 41.
#
# Targets are ordered by cost.  `make check` is seconds, `make regenerate` is
# minutes, `make certify` is CPU-days and needs ~200 GB of scratch disk.  See
# README.md for what each tier establishes and docs/TOOLCHAIN.md for the external
# solvers `certify` needs.

PYTHON ?= python3
CC     ?= cc
OUT    ?= build

export PYTHONPATH := $(CURDIR)/src

.PHONY: all check regenerate cross-check certify manifest \
        test instances auxiliary extensions blockers provenance encoder \
        upper-bound clean help

help:
	@echo "make check       structural tests + upper bound + encoder sanity   (~1 min)"
	@echo "make regenerate  rebuild all 81 CNF instances and check hashes     (~2 min)"
	@echo "make cross-check rebuild all 81 without PySAT, clean-room encoder  (~3 min)"
	@echo "make certify     solve and machine-check every instance      (CPU-days)"
	@echo "make all         check + regenerate + cross-check"
	@echo "make manifest    regenerate MANIFEST.sha256 over the deposit"

all: check regenerate cross-check

# --- tier 1: no solver, no large disk ------------------------------------

check: test upper-bound encoder

test:
	$(PYTHON) -m pytest -q

# The upper bound C(12,6,4) <= 41, checked twice by deliberately unrelated
# implementations: a Python bitmask sweep and a C nested-loop scan.
upper-bound: $(OUT)/verify_cover
	$(PYTHON) bin/verify_cover.py data/design-stored-41.txt
	$(PYTHON) bin/verify_cover.py data/design-lajolla-41.txt
	$(OUT)/verify_cover data/design-stored-41.txt
	$(OUT)/verify_cover data/design-lajolla-41.txt

$(OUT)/verify_cover: bin/verify_cover.c
	@mkdir -p $(OUT)
	$(CC) -O2 -Wall -Wextra -std=c99 -o $@ $<

# Brute-forces PySAT's CardEnc.equals against ground truth on small (n,k).
encoder:
	$(PYTHON) bin/encoder_sanity.py

# --- tier 2: regenerate every instance the proof depends on ---------------

regenerate: instances auxiliary extensions blockers provenance

# The 47 frontier nodes of the case tree.
instances:
	$(PYTHON) bin/gen_instances.py --out $(OUT)/cnf

# The 14 instances that make the case tree exhaustive.
auxiliary:
	$(PYTHON) bin/gen_auxiliary.py --out $(OUT)/cnf-aux

# The 20 extension refutations that license the orbit blocker.
extensions:
	$(PYTHON) bin/gen_extensions.py --out $(OUT)/cnf-ext

# The blockers themselves: orbit closure, orbit-stabiliser, licence to block.
blockers:
	$(PYTHON) bin/audit_blocker.py --json $(OUT)/audit.json

# Each node under both cardinality translations, sharing one problem core.
provenance:
	$(PYTHON) bin/check_encoding_provenance.py --out $(OUT)/provenance.json

# Rebuilds all 81 instances with verify/independent_seq_encoder.py -- a
# clean-room sequential-counter encoder that imports no PySAT -- and requires
# byte equality with the published hashes.  See verify/README.md.
cross-check:
	$(PYTHON) bin/cross_check_encoder.py --out $(OUT)/cross-check.json

# MANIFEST.sha256 covers every deposited file; regenerate it after editing any.
manifest:
	bin/make_manifest.sh

# --- tier 3: the full certification ---------------------------------------

certify: regenerate
	bin/certify.sh $(OUT)/cnf/*.cnf $(OUT)/cnf-aux/*.cnf $(OUT)/cnf-ext/*.cnf

clean:
	rm -rf $(OUT) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
