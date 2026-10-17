import pytest

from camera_preflight.cli.main import main
from camera_preflight.io import find_exiftool
from camera_preflight.synth import Defects, SynthCamera, write_session


def test_self_test_passes(capsys):
    assert main(["--self-test"]) == 0
    assert "self-test: ok" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "camera-preflight" in capsys.readouterr().out


@pytest.mark.skipif(find_exiftool() is None, reason="ExifTool not installed")
def test_analyse_flat_files(tmp_path, capsys):
    cam = SynthCamera(defects=Defects(stuck_bright=[(50, 60)]))
    files = write_session(cam, tmp_path / "files")
    paths = [str(p) for p in files["flat/b2/f8"]]
    code = main(
        ["analyse", "--check", "B2,B5", "--out", str(tmp_path / "out"), "--lang", "en", *paths]
    )
    out = capsys.readouterr().out
    assert code == 0 and "B2" in out and "report:" in out
    assert next((tmp_path / "out").glob("*/report.html")).exists()


def test_unknown_check_is_an_error(tmp_path, capsys):
    f = tmp_path / "x.dng"
    f.write_bytes(b"x")
    assert main(["analyse", "--check", "Z9", "--out", str(tmp_path / "o"), str(f)]) == 2
