# PyInstaller onedir build (P-06). Run from the repository root:
#   uv run pyinstaller packaging/pyinstaller/camera-preflight.spec --noconfirm
# Not code-signed (D-41). No vendor SDK file is added here, ever (D-31).
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]
PKG = ROOT / "src" / "camera_preflight"

datas = [
    (str(PKG / "locale"), "camera_preflight/locale"),
    (str(PKG / "report" / "templates"), "camera_preflight/report/templates"),
    (str(PKG / "gui" / "reference"), "camera_preflight/gui/reference"),
    (str(ROOT / "knowledge-base"), "knowledge-base"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "NOTICE"), "."),
]
exiftool = ROOT / "packaging" / "exiftool" / "bundle"
if exiftool.exists():
    datas.append((str(exiftool), "exiftool"))
licenses = ROOT / "packaging" / "licenses"
if licenses.exists():
    datas.append((str(licenses), "licenses"))

a = Analysis(
    [str(Path(SPECPATH) / "entry.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=[
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "camera_preflight.backends.host",
        "camera_preflight.backends.ptp.backend",
        "camera_preflight.backends.sdk.loader",
        "camera_preflight.gui.app",
    ],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtNetwork",  # the app makes no network requests (NFR-06)
        "PySide6.QtMultimedia",
        "PySide6.QtPdf",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtBluetooth",
        "matplotlib",
        "pytest",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="camera-preflight",
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="camera-preflight")
