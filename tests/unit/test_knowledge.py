from pathlib import Path

import yaml

from camera_preflight.knowledge import ModelEntry, derive_record, load_kb, resolve_af_point_count
from camera_preflight.synth import SynthCamera, build_frames

GOOD = {
    "brand": "Canon",
    "model": "EOS Test",
    "aliases": ["Test"],
    "release_year": 2019,
    "release_year_source": "https://example.test/a",
    "shutter": {
        "rated_life": {"value": 100000, "source": "https://example.test/b", "confidence": "medium"}
    },
    "af": {"point_count": 9},
}


def _write(root: Path, brand: str, name: str, data: dict) -> None:
    (root / brand).mkdir(parents=True, exist_ok=True)
    (root / brand / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_valid_entry_loads_and_matches_metadata_names(tmp_path):
    _write(tmp_path, "canon", "eos-test", GOOD)
    kb, problems = load_kb(tmp_path)
    assert not problems and len(kb.entries) == 1
    assert kb.find("Canon", "Canon EOS Test") is kb.entries[0]
    assert kb.find(None, "EOS Test") is kb.entries[0]
    assert kb.find("Sony", "ILCE-7") is None


def test_missing_source_is_rejected(tmp_path):
    bad = dict(GOOD, shutter={"rated_life": {"value": 1, "source": "", "confidence": "low"}})
    _write(tmp_path, "canon", "bad", bad)
    _kb, problems = load_kb(tmp_path)
    assert problems and "source" in problems[0]


def test_unknown_key_and_wrong_folder_and_year_without_source(tmp_path):
    _write(tmp_path, "canon", "typo", dict(GOOD, shutterr={}))
    _write(tmp_path, "nikon", "wrong", GOOD)
    no_src = {k: v for k, v in GOOD.items() if k != "release_year_source"}
    _write(tmp_path, "canon", "nosrc", no_src)
    _kb, problems = load_kb(tmp_path)
    text = "\n".join(problems)
    assert "shutterr" in text and "does not match folder" in text and "release_year_source" in text


def test_yaml_is_loaded_safely(tmp_path):
    (tmp_path / "canon").mkdir()
    (tmp_path / "canon" / "evil.yaml").write_text(
        "brand: !!python/object/apply:os.system ['echo x']", encoding="utf-8"
    )
    _kb, problems = load_kb(tmp_path)
    assert problems


def test_derived_tier_and_resolution():
    frames = [f for fs in build_frames(SynthCamera()).values() for f in fs][:5]
    derived = derive_record(frames)
    assert derived.model == "SC-1"
    assert resolve_af_point_count(None, derived).tier == "none"
    entry = ModelEntry.model_validate(GOOD)
    assert resolve_af_point_count(entry, derived).tier == "curated"


def test_repository_base_validates():
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from tools_path import run_validate

    assert run_validate() == 0
