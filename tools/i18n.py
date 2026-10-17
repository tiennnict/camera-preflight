"""Translation catalogue tool: extract, update, compile, check (NFR-14).

Usage: python tools/i18n.py extract|update|compile|check
"""

from __future__ import annotations

import sys
from pathlib import Path

from babel.messages import Catalog, mofile, pofile
from babel.messages.extract import extract_from_dir

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "camera_preflight"
LOCALE = PKG / "locale"
DOMAIN = "camera_preflight"
LANGS = ("en", "vi")
KEYWORDS = {"_": None, "N_": None, "tr": None, "ngettext": (1, 2)}
POT = LOCALE / f"{DOMAIN}.pot"

# Source texts that are legitimately identical in Vietnamese (terms and codes).
IDENTICAL_OK = frozenset(
    {
        "Firmware",
        "Model",
        "SHA-256",
        "ISO",
        "RAW",
        "Firmware {version}",
        "{mode}: {ev} EV",
        "ISO {iso}",
    }
)


def po_path(lang: str) -> Path:
    return LOCALE / lang / "LC_MESSAGES" / f"{DOMAIN}.po"


def mo_path(lang: str) -> Path:
    return po_path(lang).with_suffix(".mo")


def extract() -> Catalog:
    cat = Catalog(project="camera-preflight", charset="utf-8")
    for filename, lineno, message, comments, _ctx in extract_from_dir(
        str(PKG), method_map=[("**.py", "python")], keywords=KEYWORDS
    ):
        if not message:
            continue
        cat.add(
            message,
            locations=[(str(Path("src/camera_preflight") / filename).replace("\\", "/"), lineno)],
            auto_comments=comments,
        )
    return cat


def write_pot(cat: Catalog) -> None:
    LOCALE.mkdir(parents=True, exist_ok=True)
    with POT.open("wb") as fh:
        pofile.write_po(fh, cat, width=100, sort_output=True, omit_header=False)


def update() -> None:
    template = extract()
    write_pot(template)
    for lang in LANGS:
        path = po_path(lang)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("rb") as fh:
                existing = pofile.read_po(fh, locale=lang)
        else:
            existing = Catalog(locale=lang, project="camera-preflight", charset="utf-8")
        known = {str(m.id) for m in existing if m.id}
        existing.update(template, no_fuzzy_matching=True)
        for msg in existing:
            if not msg.id:
                continue
            if lang == "en" and not msg.string:
                msg.string = msg.id
            elif lang != "en" and str(msg.id) not in known:
                msg.string = ""  # new text: must be translated, never left as English
        with path.open("wb") as fh:
            pofile.write_po(fh, existing, width=100, sort_output=True)


def compile_all() -> None:
    for lang in LANGS:
        with po_path(lang).open("rb") as fh:
            cat = pofile.read_po(fh, locale=lang)
        with mo_path(lang).open("wb") as fh:
            mofile.write_mo(fh, cat)


def check() -> int:
    problems: list[str] = []
    template = extract()
    ids = {str(m.id) for m in template if m.id}
    for lang in LANGS:
        path = po_path(lang)
        if not path.exists():
            problems.append(f"{lang}: catalogue missing")
            continue
        with path.open("rb") as fh:
            cat = pofile.read_po(fh, locale=lang)
        have = {str(m.id) for m in cat if m.id}
        for missing in sorted(ids - have):
            problems.append(f"{lang}: missing {missing!r}")
        for msg in cat:
            if not msg.id or str(msg.id) not in ids:
                continue
            if msg.fuzzy:
                problems.append(f"{lang}: fuzzy {msg.id!r}")
            strings = msg.string if isinstance(msg.string, tuple) else (msg.string,)
            if not all(strings):
                problems.append(f"{lang}: untranslated {msg.id!r}")
            elif lang != "en" and msg.string == msg.id and str(msg.id) not in IDENTICAL_OK:
                problems.append(f"{lang}: still English {msg.id!r}")
        mo = mo_path(lang)
        if not mo.exists():
            problems.append(f"{lang}: compiled catalogue missing")
        elif mo.stat().st_mtime + 1 < path.stat().st_mtime:
            problems.append(f"{lang}: compiled catalogue is older than the .po file")
    for line in problems:
        print(line)
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "extract":
        write_pot(extract())
    elif cmd == "update":
        update()
    elif cmd == "compile":
        compile_all()
    elif cmd == "check":
        return check()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
