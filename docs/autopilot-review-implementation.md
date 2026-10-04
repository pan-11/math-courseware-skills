# Optional autopilot and independent review implementation

Approved design (2026-10-04): keep current Studio/manual mode as default; add optional persistent, host-session automatic dispatch and standalone independent review. Both reuse the same real course files and existing adoption gates. No automatic approval or background service.

Implemented and verified locally: two new Skill entries, fourteen CLI commands, persistent claims/dependencies, mode and recovery controls, immutable review packets/results and same-version reinspection. The 149 existing tests and 33 new tests pass, with all fifteen Skill entries validated. A fresh operator completed a synthetic requirements-analysis queue and a separate fresh reviewer; independent negative/positive/missing-media cases also ran. No real course, paid media or whole-course WPS acceptance is implied. Usage: [mode and review guide](autopilot-review-usage.md).

## Delivery and checks

1. Add a durable task queue and mode/pause/resume controls. Check default manual, explicit activation, dependency order, human waits without blocking independent work, idempotent claims/results, bounded retries and interrupted/unknown work without blind redispatch.
2. Add immutable review packets and independently authored reports with five rubrics: source, teaching/math, visuals, video and delivery. Check missing evidence, self-review, incorrect/stale references, failed/unverified checks and unchanged adoption logs.
3. Integrate host loops in two Skills and Studio. Existing workflow-check remains the authority for starting production; no shell command from a queue is executed by the scheduler. Codex calls available authoring tools and isolated reviewers. If an independent agent is unavailable, stop at review instead of relabeling self-review.
4. Run synthetic CLI/behavior tests, unchanged manual baseline, relevant full regression, Skill metadata/link validation and isolated reader/behavior review. Update usage documentation and HANDOFF with actual results and limitations.

## Implementation boundaries

Queue tasks have stable IDs, a supported workflow step, dependencies, real input/output paths, an instruction and the mapped producing Skill/rubric. AI builds the concrete queue from the current authorized scope and adopted blueprint, extending it when previously unknown video/page decisions are available. The scheduler validates the graph and existing workflow gate, dispatches one claimed task at a time, and records actual outputs before review. Completed tasks are rechecked against current inputs, outputs and latest rejection records. Human tasks retain explicit return instructions and real receipt evidence.

Production, independent review and user adoption are separate. Reviews bind to exact inputs/outputs and reviewer identity; this checks provenance and integrity, not a security boundary against a process with the same filesystem permissions. Rubric reports derive pass/change/unverified rather than trusting a submitted pass flag. Review code cannot write decisions.jsonl or workflow adoption records.

Runs and reviews use new _state/automation subdirectories with first-written AGENTS rules, atomic records and a retained OS-locked lock file. Existing project/workflow/state schemas are not migrated. Manual switch preserves the queue; resume inspects in-flight claims and never silently retries them. Unknown external submissions stay blocked until actual outputs are recovered. Paid calls and manual Canva/video/WPS tasks retain current authorization requirements.

This phase can collect stage outputs, but does not automate whole-course final acceptance. The known final-document collection/version-binding gaps require manual delivery inspection; an exhausted queue is only queue_complete, never whole_course_complete. Four Word files, blackboard assets, all real videos and WPS/playback evidence remain explicit final checks.
