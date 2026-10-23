# Fixed regression fixtures

- `manual-mode-baseline-v001.json` is the reviewed workflow-check snapshot captured from commit 643701823368991d9dc78c2b65e8804721ab173e before P0 runtime edits.
- `tests/test_manual_mode_baseline.py` defines the synthetic scenarios and explicit one-time capture procedure. Normal tests only read the expected snapshot; never regenerate it to make a failure pass.
- No real lesson data, user decisions, credentials or paid media belong here.
- Keep existing fixtures. A deliberate future contract change requires its own reviewed baseline version; do not silently replace or delete this one.
- `manual-mode-baseline-v002.json` is the 2026-10-23 approved full-course material-role overlay. It binds v001's exact SHA and changes only the missing-documents issue list in `video-files-still-required`: three teacher roles plus worksheet and blackboard. All other baseline behavior remains frozen; the original capture command cannot overwrite v001.
