import json
from pathlib import Path

import pytest

from bench.split import (
    SPLIT_PATH,
    Plate,
    count_band,
    dev_quotas,
    load_labels,
    load_plates,
    make_split,
)


def plate(plate_id: str, count: int) -> Plate:
    return Plate(id=plate_id, image=Path(f"{plate_id}.jpg"), true_count=count)


def sample_plates() -> dict[str, Plate]:
    """The audited band sizes: 8, 30 and 1."""
    counts = [5] * 8 + [50] * 30 + [298]
    return {str(i): plate(str(i), count) for i, count in enumerate(counts)}


def test_loader_uses_filename_and_skips_uncounted_plates(tmp_path):
    (tmp_path / "bright").mkdir()
    (tmp_path / "bright" / "971.json").write_text(
        json.dumps({"sample_id": 972, "colonies_number": 130}), encoding="utf-8"
    )
    (tmp_path / "1399.json").write_text(json.dumps({"colonies_number": -1}), encoding="utf-8")
    plates = load_plates(tmp_path)
    assert list(plates) == ["971"]
    assert plates["971"].true_count == 130
    assert plates["971"].image == tmp_path / "bright" / "971.jpg"


def test_loader_rejects_two_plates_with_one_filename(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "1.json").write_text('{"colonies_number": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="two plates"):
        load_plates(tmp_path)


@pytest.mark.parametrize(
    ("count", "band"),
    [(0, "<15"), (14, "<15"), (15, "15-150"), (150, "15-150"), (151, "151-300"), (300, "151-300")],
)
def test_count_bands(count, band):
    assert count_band(count) == band


def test_count_over_300_has_no_band():
    with pytest.raises(ValueError):
        count_band(301)


def test_quotas_sum_to_dev_size_by_largest_remainder():
    assert dev_quotas({"<15": 8, "15-150": 30, "151-300": 1}, 16) == {
        "<15": 3,
        "15-150": 12,
        "151-300": 1,
    }


def test_load_labels_makes_inclusive_boxes_at_the_image_size(tmp_path):
    label = {"id": 7, "x": 10, "y": 20, "width": 5, "height": 3, "class": "S.aureus"}
    (tmp_path / "1.json").write_text(json.dumps({"labels": [label]}), encoding="utf-8")
    plate_1 = Plate(id="1", image=tmp_path / "1.jpg", true_count=1)
    [box] = load_labels(plate_1, 3000, 4000)
    assert (box.x1, box.y1, box.x2, box.y2) == (10, 20, 14, 22)
    assert (box.w, box.h) == (3000, 4000)


def test_load_labels_leaves_out_contamination(tmp_path):
    box = {"id": 1, "x": 1, "y": 1, "width": 5, "height": 5}
    labels = [{**box, "class": "E.coli"}, {**box, "id": 2, "class": "Contamination"}]
    (tmp_path / "1.json").write_text(json.dumps({"labels": labels}), encoding="utf-8")
    plate_1 = Plate(id="1", image=tmp_path / "1.jpg", true_count=1)
    assert [b.id for b in load_labels(plate_1, 100, 100)] == [1]


def test_split_is_seeded_stratified_and_disjoint():
    plates = sample_plates()
    split = make_split(plates, seed=1, dev_size=16)
    assert split == make_split(plates, seed=1, dev_size=16)
    assert split != make_split(plates, seed=2, dev_size=16)
    assert len(split["dev"]) == 16
    assert len(split["test"]) == 23
    assert sorted(split["dev"] + split["test"]) == sorted(plates)
    assert sum(plates[i].true_count == 5 for i in split["dev"]) == 3


def test_frozen_split_file_is_disjoint_16_and_23():
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    assert len(split["dev"]) == len(set(split["dev"])) == 16
    assert len(split["test"]) == len(set(split["test"])) == 23
    assert not set(split["dev"]) & set(split["test"])
    assert "1399" not in split["dev"] + split["test"]
