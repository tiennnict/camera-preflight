# Working conventions for Claude Code

## Language (decisions D-07, D-14, D-15, D-16 in docs/DECISIONS.md)

- The maintainer writes to Claude in Vietnamese. Reply to the maintainer in Vietnamese.
- Everything published on GitHub is in English: code, comments, docs, commit messages, branch names, issues, pull requests, review replies, release notes. Translate the maintainer's Vietnamese input into English; do not paste Vietnamese text into these places.
- The one exception is the Vietnamese translation catalogue (`src/camera_preflight/locale/vi/`) and Vietnamese entries in UI vocabulary tables, which hold user-facing Vietnamese text.
- The software is bilingual from the start. Every user-visible string (GUI, messages, report, field kit, remote pack) goes through gettext and gets both an English source text and a Vietnamese translation in the same change. Use the vocabulary in docs/UX.md section 7.1.

## Evidence labels

Keep the labels `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]` defined in docs/archive/handoff.md section 0. Never present an inference, guess or unverified item as fact in code comments, docs or reports.

## Design baseline

Read docs/SRS.md, docs/ARCHITECTURE.md and docs/DECISIONS.md before changing behaviour. Items marked Proposed in docs/DECISIONS.md are not yet approved.
