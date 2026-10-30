from collections import Counter

from scripts.prepare_diverse_dataset import select_per_source_class


def test_select_per_source_class_covers_every_unknown_class_and_deduplicates_hashes(tmp_path):
    split = tmp_path / "train"
    for class_id in ("0001", "0002"):
        folder = split / class_id
        folder.mkdir(parents=True)
        (folder / "a.jpg").write_bytes(f"{class_id}-a".encode())
        (folder / "b.jpg").write_bytes(f"{class_id}-b".encode())
        (folder / "c.jpg").write_bytes(b"shared-duplicate")

    selected, hashes = select_per_source_class(
        split,
        ["0001", "0002"],
        per_class=2,
        seed=7,
        blocked_hashes=set(),
    )

    assert Counter(class_id for class_id, _ in selected) == {"0001": 2, "0002": 2}
    assert len(hashes) == 4
