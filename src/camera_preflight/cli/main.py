"""Command-line entry points: analyse files, run the demo, self-test, start the GUI (WP-21)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .. import __version__, i18n
from ..checks import BY_ID
from ..domain import Level, Message, Mode
from ..wizard import Wizard


def _line(result_level: Level, check_id: str, text: str, extra: str) -> str:
    title = i18n.render(Message(code=f"check.{check_id}.title"))
    name = i18n.render(Message(code=f"level.{result_level.value}"))
    return f"{check_id:<4} {title:<34} {name:<14} {text}{extra}"


def print_results(wizard: Wizard) -> None:
    for r in wizard.ordered_results():
        extra = ""
        if r.confidence:
            extra += f"  [{i18n.render(Message(code=f'confidence.{r.confidence.value}'))}]"
        if r.severity:
            extra += f"  [{i18n.render(Message(code=f'severity.{r.severity.value}'))}]"
        print(_line(r.level, r.check_id, i18n.render(r.explanation), extra))


def cmd_analyse(args: argparse.Namespace) -> int:
    ids = [c.strip().upper() for c in args.check.split(",")] if args.check != "all" else None
    wizard = Wizard(Mode.UPLOAD, Path(args.out), language=args.lang)
    try:
        check_ids = ids or [cid for s in wizard.plan for cid in s.checks if s.requirements]
        unknown = [c for c in check_ids if c not in BY_ID]
        if unknown:
            print(f"unknown check: {', '.join(unknown)}", file=sys.stderr)
            return 2
        outcomes = wizard.upload_for_checks([Path(f) for f in args.files], check_ids)
        for o in outcomes:
            if not o.accepted and o.rejection:
                print(f"rejected {o.file.name}: {i18n.render(o.rejection.message)}")
        for cid in check_ids:
            wizard.run_checks([cid])
        print_results(wizard)
        report = wizard.save_report(args.lang)
        print(f"report: {report}")
    finally:
        wizard.close()
    return 0


def run_demo(out: Path, lang: str, *, quiet: bool = False) -> Wizard:
    """Run the whole wizard on a synthetic camera with a few injected faults (N-09)."""
    from ..checks import ManualAnswer
    from ..synth import Defects, SidecarReader, SynthCamera, write_session

    cam = SynthCamera(
        defects=Defects(
            hot=[(100, 100), (100, 102), (102, 100)],
            hot_rate_e_s=2000.0,
            dust=[(80, 120, 7.0)],
        ),
        af_soft_points={"left": 3.0},
    )
    src = out / "demo-files"
    files = write_session(cam, src)
    wizard = Wizard(Mode.UPLOAD, out / "sessions", reader=SidecarReader(src), language=lang)
    for step in wizard.plan:
        if not step.requirements:
            continue
        for req in step.requirements:
            paths = files.get(req.key)
            if paths:
                wizard.upload(paths, step.id, req.key)
    for cid in ("F1", "F2", "F3", "F4"):
        wizard.answer(cid, ManualAnswer(Level.PASS))
    wizard.finalize()
    if not quiet:
        print_results(wizard)
    return wizard


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    wizard = run_demo(out, args.lang)
    print(f"report: {wizard.save_report(args.lang)}")
    wizard.close()
    return 0


def cmd_self_test(_args: argparse.Namespace) -> int:
    """Analyse the bundled synthetic session and check the expected outcome (NFR-13 packaging)."""
    with tempfile.TemporaryDirectory() as tmp:
        wizard = run_demo(Path(tmp), "en", quiet=True)
        by_id = {r.check_id: r for r in wizard.ordered_results()}
        ok = (
            by_id["B1"].level is Level.SUSPECT
            and by_id["B2"].level is Level.PASS
            and by_id["C5"].level is Level.NOT_TESTED
            and "Camera check report" in wizard.render_report("en")
            and "Báo cáo" in wizard.render_report("vi")
        )
        wizard.close()
    print("self-test: ok" if ok else "self-test: FAILED")
    return 0 if ok else 1


def cmd_gui(args: argparse.Namespace) -> int:
    # Loaded by name so the command-line layer has no static dependency on the GUI layer.
    import importlib

    gui = importlib.import_module("camera_preflight.gui.app")
    return int(gui.run(args.lang if hasattr(args, "lang") else None))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="camera-preflight", description="Used-camera diagnostics wizard"
    )
    p.add_argument("--version", action="version", version=f"camera-preflight {__version__}")
    p.add_argument("--self-test", action="store_true", help="run the built-in synthetic session")
    sub = p.add_subparsers(dest="command")
    a = sub.add_parser("analyse", help="analyse photos for chosen checks")
    a.add_argument("--check", default="all", help="check ids separated by commas, or all")
    a.add_argument("--lang", choices=i18n.SUPPORTED, default="en")
    a.add_argument("--out", default="sessions", help="folder for the session")
    a.add_argument("files", nargs="+")
    a.set_defaults(func=cmd_analyse)
    d = sub.add_parser("demo", help="run the wizard on a synthetic camera")
    d.add_argument("--lang", choices=i18n.SUPPORTED, default="en")
    d.add_argument("--out", default="demo")
    d.set_defaults(func=cmd_demo)
    g = sub.add_parser("gui", help="start the graphical wizard")
    g.add_argument("--lang", choices=i18n.SUPPORTED, default=None)
    g.set_defaults(func=cmd_gui)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--backend-host"]:
        # The packaged app has no ``python -m``; it starts its own backend host this way.
        import importlib

        host = importlib.import_module("camera_preflight.backends.host")
        return int(host.main(argv[1:]))
    args = build_parser().parse_args(argv)
    if args.self_test:
        return cmd_self_test(args)
    if not getattr(args, "func", None):
        args.lang = None
        return cmd_gui(args)
    i18n.set_language(getattr(args, "lang", None))
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
