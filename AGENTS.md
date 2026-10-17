# AGENTS.md

Entrypoint for any AI agent working in this repository. This repo holds
two independent tool families; each has its own agent folder and rules.

## Layout

- `networking-tools/` — network troubleshooting tools. Has its own
  `AGENTS.md` + `.agents/` (roles, workflows, board, status). Read
  `networking-tools/AGENTS.md` before working there; its rules win inside
  that folder.
- `image-tools/` — image utilities (currently the Image Scrubber). No
  `.agents/` scaffolding yet; keep changes small and follow the repo-wide
  hard rules below.

## Hard rules (whole repo)

- Show evidence before claiming done: exact commands run, their output or
  summary, and exit status. "Should work" is not evidence.
- Never write a secret, token, password, or real personal data into any
  committed file. Placeholders only (John Doe / Jane Doe in examples).
- Do not commit directly in a spammy series. Hold changes and batch them;
  the owner reviews at push time and holds back anything broken,
  superseded, or pending. Never merge to main for the owner — feature
  branches only.
- Keep diffs small and focused. Preserve existing architecture and code
  style unless the task is explicitly a redesign.
- Local-only tools stay local-only: bind 127.0.0.1, no telemetry, no
  external calls except the ones the tool's UI explicitly describes.

## Repo commands

- Networking install: `python -m pip install -r networking-tools/requirements-dev.txt`
- Networking run: `cd networking-tools && python run_networking_tools.py`
- Networking test: `cd networking-tools && python -m pytest`
- Image install: `python -m pip install Pillow`
- Image run: `cd image-tools && python run_image_scrubber.py`
- Image test: `cd image-tools && python tests/test_scrub.py`
- Lint: none configured; syntax-check changed Python with `python -m py_compile`
