"""Bundling vendor SDK runtime files into the local binary release (D-47)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    spec = importlib.util.spec_from_file_location("cp_package", ROOT / "packaging" / "package.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DIST", tmp_path / "dist")
    monkeypatch.setattr(mod, "APP", tmp_path / "dist" / "camera-preflight")
    mod.APP.mkdir(parents=True)
    (mod.APP / "camera-preflight.exe").write_bytes(b"exe")
    return mod


def _fake_nikon(root: Path) -> None:
    win = root / "nikon" / "Z-210" / "Module" / "Win"
    binary = win / "BinaryFile"
    binary.mkdir(parents=True)
    (binary / "ControlServiceLayer.dll").write_bytes(b"dll")
    (binary / "MaidLayer.config").write_text("cfg")
    (root / "nikon" / "Z-210" / "ReadMe_En.txt").write_text("readme")
    (win / "HeaderFile").mkdir()
    (win / "HeaderFile" / "Maid3.h").write_text("h")


def test_bundle_copies_runtime_files_only(package, tmp_path: Path):
    src = tmp_path / "sdk"
    _fake_nikon(src)
    target = tmp_path / "out"
    manifest = package.bundle_sdk(src, target)
    assert (target / "nikon" / "ControlServiceLayer.dll").is_file()
    assert (target / "nikon" / "MaidLayer.config").is_file()
    assert (target / "nikon" / "vendor-docs" / "ReadMe_En.txt").is_file()
    assert not list(target.rglob("*.h"))  # headers are not shipped
    assert any("nikon/ControlServiceLayer.dll" in line for line in manifest)
    assert not (target / "sony").exists()


def test_with_sdk_needs_consent_and_is_refused_in_ci(
    package, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    src = tmp_path / "sdk"
    _fake_nikon(src)
    monkeypatch.delenv("CI", raising=False)
    assert package.main(["--with-sdk", str(src)]) == 2
    monkeypatch.setenv("CI", "true")
    assert package.main(["--with-sdk", str(src), "--accept-vendor-terms"]) == 2
    assert not (package.APP / "sdk").exists()


def test_plain_build_drops_leftover_sdk(package, monkeypatch: pytest.MonkeyPatch):
    (package.APP / "sdk" / "nikon").mkdir(parents=True)
    (package.APP / "sdk" / "nikon" / "x.dll").write_bytes(b"x")
    monkeypatch.delenv("CI", raising=False)
    assert package.main([]) == 0
    assert not (package.APP / "sdk").exists()
