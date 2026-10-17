# Working conventions for Claude Code

The shared rules for all coding agents are in AGENTS.md:

@AGENTS.md

The rules below are specific to working with the maintainer.

## Language (decisions D-07, D-14, D-15, D-16 in docs/DECISIONS.md)

- The maintainer writes to Claude in Vietnamese. Reply to the maintainer in Vietnamese.
- The maintainer does not read the English documents. Every approval or decision must be asked in the chat, in Vietnamese, with enough context to decide without opening a document (D-17). Never assume a Proposed item is approved because it is written in docs/DECISIONS.md.
- Everything published on GitHub is in English: code, comments, docs, commit messages, branch names, issues, pull requests, review replies, release notes. Translate the maintainer's Vietnamese input into English; do not paste Vietnamese text into these places.
- The one exception is the Vietnamese translation catalogue (`src/camera_preflight/locale/vi/`) and Vietnamese entries in UI vocabulary tables, which hold user-facing Vietnamese text.
- The software is bilingual from the start. Every user-visible string (GUI, messages, report) goes through gettext and gets both an English source text and a Vietnamese translation in the same change. Use the vocabulary in docs/UX.md section 9.1.
- On-screen text is short and complete in meaning, without long notes or explanations (D-44, docs/UX.md section 9).

## Evidence labels

Keep the labels `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]` defined in docs/archive/handoff.md section 0. Never present an inference, guess or unverified item as fact in code comments, docs or reports.

## Design baseline

Read docs/SRS.md, docs/ARCHITECTURE.md and docs/DECISIONS.md before changing behaviour. Items marked Proposed in docs/DECISIONS.md are not yet approved. Implementation follows docs/WORK-PACKAGES.md.
