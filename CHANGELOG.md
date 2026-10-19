# Changelog

All notable changes are recorded here. Format follows Keep a Changelog; versions follow SemVer.

## Unreleased

- Project skeleton, tooling, CI and the translation check (WP-00 to WP-05).
- RAW decoding, metadata, session folder and upload (WP-10 to WP-12).
- Frame gate, analysis for groups B to E, checks A to F, HTML report, command line (WP-13 to WP-21).
- Qt wizard in upload mode with animations and a demo session (WP-30 to WP-38).
- Connected mode: backend host, PTP core, SDK loader, runner with fallback, helpers (WP-41 to WP-4A).
- Knowledge base schema and validator, PyInstaller build (WP-53, WP-02).
- Canon SDK adapter on EDSDK 2.13 (WP-46); SDK discovery now skips the library built for the other CPU.
- Nikon D-SLR adapter on the MAID3 `Type00xx.md3` modules (D7200: `Type0017.md3`). Shots go to
  the computer only; RAW and long exposure NR off for the session, restored on close.
- Detection now uses the SDKs: USB vendor scan, then each SDK library of the brands found, each
  in its own host process; clear message when a camera is seen but cannot be controlled.
- Fixes: capture timeout scaled to the exposure (30 s dark frames timed out after 5 s); host
  calls time out instead of hanging; native stdout no longer corrupts the host protocol; the
  windowed build's host works; SDK folders given as relative paths load; the knowledge base is
  loaded by default.
- Light theme only (D-48); flat checklist on the left (D-49).
- Knowledge base: 17 models with sourced known issues, matched by serial range, serial digit rule
  or firmware (D-50).
