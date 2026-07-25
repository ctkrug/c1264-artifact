"""Tests over the orbit blockers.

Only ``catalog-9-blocking.cnf`` is orbit-partitioned here -- it is the smallest of
the three and the partition is the slow step (3840 group elements per orbit).
``bin/audit_blocker.py`` does all three, plus the chain property.
"""

from __future__ import annotations

import json

import pytest

from c1264 import blocker, frontier
from c1264.group import GROUP_ORDER, group_maps, image

BLOCKERS = frontier.REPO_ROOT / "data" / "blockers"
EXTENSIONS = json.loads((frontier.REPO_ROOT / "data" / "extensions.json").read_text())

EXPECTED_LINKS = {
    "catalog-9-blocking.cnf": 3776,
    "catalog-13-blocking.cnf": 6096,
    "blocker-20.cnf": 15120,
}


@pytest.mark.parametrize("name,count", sorted(EXPECTED_LINKS.items()))
def test_blocked_link_counts(name, count):
    links = blocker.blocked_links(BLOCKERS / name)
    assert len(links) == count
    assert all(len(link) == 20 for link in links)
    assert all(len(set(link)) == 20 for link in links)


def test_staged_blockers_are_nested():
    # A staged blocker is only legitimate if it is a weakening of the final one:
    # otherwise the earlier SAT runs assumed something the final blocker does not.
    nine = set(blocker.blocked_links(BLOCKERS / "catalog-9-blocking.cnf"))
    thirteen = set(blocker.blocked_links(BLOCKERS / "catalog-13-blocking.cnf"))
    twenty = set(blocker.blocked_links(BLOCKERS / "blocker-20.cnf"))
    assert nine < thirteen < twenty


def test_empty_blocker_blocks_nothing():
    assert blocker.blocked_links(BLOCKERS / "empty.cnf") == []


def test_catalog_nine_partitions_into_nine_closed_orbits():
    # orbit_partition raises if an orbit leaves the blocked set, so reaching the
    # assertions below is itself the closure check.
    records = blocker.orbit_partition(BLOCKERS / "catalog-9-blocking.cnf")
    assert len(records) == 9
    assert sum(int(r["orbit_size"]) for r in records) == 3776
    for record in records:
        assert int(record["orbit_size"]) * int(record["stabilizer_order"]) == GROUP_ORDER
        assert record["canonical_sha256"] in EXTENSIONS


def test_canonical_representative_is_the_orbit_minimum():
    records = blocker.orbit_partition(BLOCKERS / "catalog-9-blocking.cnf")
    maps = list(group_maps())
    for record in records[:3]:
        seed = tuple(tuple(block) for block in record["canonical_blocks"])
        orbit = {tuple(sorted(image(m, block) for block in seed)) for m in maps}
        assert min(orbit) == seed
        assert len(orbit) == int(record["orbit_size"])


def test_canonical_text_format_is_the_published_one():
    # The digests in data/extensions.json are hashes of this exact text, so the
    # format is part of the published record, not an implementation detail.
    link = blocker.blocked_links(BLOCKERS / "catalog-9-blocking.cnf")[0]
    text = blocker.canonical_text(link)
    lines = text.splitlines()
    assert len(lines) == 20
    assert text.endswith("\n") and not text.endswith("\n\n")
    for line, block in zip(lines, link):
        assert line == " ".join(str(point) for point in block)
        assert all(1 <= point <= 11 for point in block)


def test_digest_changes_if_a_block_is_reordered():
    link = blocker.blocked_links(BLOCKERS / "catalog-9-blocking.cnf")[0]
    shuffled = (link[1], link[0], *link[2:])
    assert blocker.canonical_digest(shuffled) != blocker.canonical_digest(link)


@pytest.mark.parametrize(
    "header,clause",
    [
        # Twenty literals, but one repeated: only nineteen distinct blocks.
        ("p cnf 462 1", [-i for i in range(1, 20)] + [-19]),
        # A positive literal: this would *assert* a block, not forbid a link.
        ("p cnf 462 1", [-i for i in range(1, 20)] + [20]),
        # Nineteen literals: a weaker constraint than the one claimed.
        ("p cnf 462 1", [-i for i in range(1, 20)]),
        # Header disagrees with the body.
        ("p cnf 462 2", [-i for i in range(1, 21)]),
        # Wrong variable count: not a blocker over the primary variables.
        ("p cnf 463 1", [-i for i in range(1, 21)]),
    ],
)
def test_malformed_blocking_clause_is_rejected(tmp_path, header, clause):
    # Every rejection here happens in orbits.parse_blockers, which is stricter
    # than blocked_links needs; the width check inside blocked_links is a
    # second line of defence and is not what these cases reach.
    path = tmp_path / "bad.cnf"
    path.write_text(header + "\n" + " ".join(map(str, clause)) + " 0\n")
    with pytest.raises(ValueError):
        blocker.blocked_links(path)


def test_a_well_formed_single_clause_blocker_is_accepted(tmp_path):
    path = tmp_path / "one.cnf"
    literals = " ".join(f"-{i}" for i in range(1, 21))
    path.write_text(f"p cnf 462 1\n{literals} 0\n")
    assert len(blocker.blocked_links(path)) == 1
