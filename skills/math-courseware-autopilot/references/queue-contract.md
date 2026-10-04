# Queue contract

All commands use the existing `math-courseware-studio/scripts/courseware.py` and an existing compatible Python. Paths inside JSON are project-relative; CLI JSON input paths may be absolute. Never put credentials in plans, evidence or command arguments. These commands schedule work; the active Codex host performs the actions using the original Skills/tools.

On Windows use the existing interpreter with `-B -X utf8`. Save JSON as UTF-8 files and pass their paths instead of constructing Chinese JSON through a shell pipeline. Capture exit code, stdout and stderr separately with UTF-8 decoding, or use `2>&1` when retaining a combined PowerShell log. CLI failures are written to stderr; an empty stdout file is not a successful result. If an earlier capture failed, preserve that fact and identify any transcript-based reconstruction.

## Task and plan

Save a versioned plan in the course planning directory after applying its rules. Example for a known source (replace the path and actual user words):

```json
{
  "activation_evidence": "用户实际要求为本课启用自动推进的原话",
  "tasks": [{
    "id": "analysis-v001",
    "step": "analysis",
    "kind": "produce",
    "depends_on": [],
    "inputs": ["inputs/source.pdf"],
    "outputs": ["analysis", "source_review"],
    "instruction": "读取原课，完成现行分析模块要求的报告及来源清单。",
    "side_effects": "local",
    "max_attempts": 2
  }]
}
```

`outputs` names required file roles, not assumed filenames. Return real versioned paths after production. `inputs` must include all actual upstream content/version records; dependencies additionally bind their output hashes. Mutable selection references are retained so selecting a newer blueprint invalidates an old review even when old files remain. A dependency must finish its review before its child starts. The legacy workflow-check independently enforces current scope and adoption.

`kind:human` means actual user adoption/operation/return. Explain the operation and required return in instruction, and include the delivered material in inputs. For an adoption task, use the already producible step being adopted, not a downstream step whose gate already requires that adoption. The returned evidence file is created from the user's real response by the host using existing adoption rules. A queue receipt itself does not grant adoption.

`side_effects:external` is required for media/platform submissions including hosted image generation. The host separately enforces the existing batch/fee authorization before calling tools. The queue does not execute or price those calls. Local corrections may be retried automatically after changes_required; external work and unknown submission outcomes never are.

Potentially media-generating steps (cover, asset, page-image, video-script/assets/board/upload and editable-handoff) always receive the external retry guard even if a plan incorrectly says local. Human adoption receipts should be individual evidence files, not the growing decisions.jsonl log; later legitimate approvals must not invalidate an earlier receipt merely by appending to that log.

## Step mapping

Use workflow action names, not stage-record labels. Do not hardcode lesson page/video counts.

| Work | Step / owner | Stored result and review |
|---|---|---|
| C1 analysis | analysis / analyze | visible analysis and source inventory; source rubric |
| C2 blueprint | blueprint / plan | whole-course plan and shared core; teaching rubric |
| Style/cover/assets | cover or asset / plan | actual reference images; visual rubric |
| Video script/preview | video-script / video-writer | script, voice and applicable preview; video rubric |
| Video assets | video-assets / video-assets | actual assets/first frame; video rubric |
| Shots-only direction/board/style | video-director, video-board, video-style | director, storyboard, frozen style; video rubric |
| Video packet / human generation | video-prompts, video-upload | full prompts/materials, then actual returned media; video rubric for produced packets |
| Whole-course video preparation | video-upload task per real video, then plan/studio consolidation | register real video-preparation and all-video handoff; existing pages gate checks it |
| C4–C5 pages/images/export | pages, page-image, image-export | canonical page mapping, versioned page data/images and full export; teaching/visual/delivery rubric respectively |
| C6 handoff/import/refill | editable-handoff, editable-import, editable-build | full handoff, actual returned PPTX, full text refill; delivery rubric |
| C7 documents/blackboard | documents / documents | four real Word documents and separate blackboard assets, each explicitly queued; teaching rubric plus final delivery review |
| C8 collection/check | collect; complete must be human | actual current delivery inventory and actual playback evidence; no automatic whole-course certification |

For fixed talking, preserve its continuous authoring process and grouped packet review; do not queue shots-only steps or invent intermediate user approvals. The host may complete the continuous substeps inside one video-script task, then register the actual products so downstream legacy checks work. Independent review is not a new user approval gate.

## Commands and lifecycle

- `run-start --project P --plan PLAN`: explicit opt-in; same plan is idempotent. No queue means manual and run-status/run-next do not create one.
- `run-extend --project P --plan PLAN`: append newly known tasks within actual scope. Repeated identical tasks are idempotent; existing definitions cannot be overwritten. Include activation_evidence for the actual extension scope. Prefer new versioned task IDs after a substantive plan revision.
- `run-next --project P --actor ID`: claims one production/review action under an OS file lock; returns waiting human tasks immediately even while another branch can proceed. Repeat calls return recover for an outstanding claim, not a new dispatch.
- `run-record --project P --result RESULT`: produced outputs require exactly the declared role set, current source versions and current legacy gate. The command creates a review packet; it does not claim the independent review happened.
- `run-status --project P`: read-only mode/task/stale overview. queue_complete is not whole-course completion.
- `run-mode --project P --mode manual|automatic --evidence TEXT`: retain progress and switch dispatch mode. Existing projects default manual. Mode choice does not grant new production scope.
- `run-pause` / `run-resume --project P --evidence TEXT`: pause or resume dispatch without canceling live agents/platform jobs. Mode remains separate.
- `run-reconcile --project P --evidence TEXT`: explicitly accept the currently authorized course/task scope as the queue basis after a real scope change; all workflow gates still apply. It does not rewrite outputs, approvals or stale evidence.
- `run-retry --project P --task-id ID --evidence TEXT`: retry a resolved local failure/stale version/review issue within the attempt bound. Unknown or external submission work cannot use this to resubmit.
- `run-recheck --project P --task-id ID --evidence TEXT`: when a report was unverified and the same unchanged files can now actually be inspected, create a fresh independent packet without recreating the output. At most two review attempts per production attempt; old packets remain. Changed inputs/outputs need actual revision, not this shortcut. Missing additional files require a properly scoped new task/standalone review with those real sources.

Produced result:

```json
{"task_id":"analysis-v001","claim":"copy-exact-returned-claim","status":"produced","artifacts":{"analysis":"planning/analysis-v001.md","source_review":"planning/source-review-v001.json"}}
```

Human result uses `status:completed`, the real returned artifact roles and `user_evidence` with actual completion/adoption evidence. Do not mark completion because a file was requested or the user said generation was in progress. A production failure uses failed plus message; uncertain external outcome uses unknown plus message. Unknown can only be resolved by recovered actual outputs in this version, not by a new submission. Record calls with the same claim/content are idempotent. Revised production outputs need new paths, preserving prior attempts.

The queue stores progress only under `_state/automation`; original workflow/state semantics stay unchanged. A completed task becomes stale if referenced files change, a recorded source selection moves, or the user rejects its exact version. Downstream tasks inherit staleness. Recheck and re-review the affected current versions; never refresh old hashes without actual inspection.

For an abandoned review claim, first verify the previous agent is stopped. Its original packet may be assigned to a new independent reviewer (no production side effect), then record that real result; run-next resumes from the packet. Do not spawn a second reviewer while the first is still running. For abandoned production, inspect the actual files and recover via the current claim; only use failed/retry after a verified local failure. No automatic expiration or duplicate dispatch.
