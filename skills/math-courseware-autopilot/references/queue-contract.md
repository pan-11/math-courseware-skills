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

### Startup preferences (H05 / H10 / H16)

Before a new run the host reuses this course's actual settings and conversation evidence, then asks the remaining three groups together once: image route and authorized purposes/scope/paid generation; video platform/model/sound; editable A/B and full/returned entry. Do not import another course's choices or treat activation, a route choice, silence or a default as generation/fee authorization. CLI `run-start --plan` remains noninteractive. Unknown preferences do not block analysis, blueprint or unrelated tasks.

An optional plan `preferences` object and `run-configure --project P --settings FILE` use the same partial object:

```json
{
  "image": {
    "route": "builtin",
    "evidence": "实际本课生图路线原话",
    "authorization": {
      "scope": "run",
      "purposes": ["cover", "asset", "page"],
      "paid_generation": false,
      "include_rework": false,
      "scope_evidence": "实际授权本课上述用途首次生成的原话"
    }
  },
  "video": {"platform": "实际平台", "model": "实际模型", "sound": "实际声音要求", "evidence": "实际选择依据"},
  "editable": {"route": "B", "entry": "full", "evidence": "实际B路线及从整套交接开始的依据"}
}
```

Only supplied fields change; omitted values persist across resume and manual/automatic switches. Every changed group needs nonempty actual `evidence`; an image authorization update needs its own `scope_evidence`. Empty/null/unknown/invalid values are rejected. `image.route` is builtin/openai_image_api, editable route is A/B, and entry is full/returned. Existing project.image_route and evidenced workflow.route_choice are reused; their stored values are sources, never invented fee evidence. A later conflicting canonical choice is reported and must be reconciled with an explicit evidenced update. New choices do not rewrite already prepared/submitted jobs or their route.

Run ownership is orchestration metadata, not an image input: unchanged manual jobs remain reusable with identical job bytes/digests after run-start. Re-preparing an unchanged pending manual job records its job ID/input digest binding in run.json; current run consent is still checked before submission. Already submitted/downloaded jobs are not rebound and retain original recovery semantics. Canonical choice evidence is part of the comparison basis, so a later actual choice can conflict even when its value matches the pre-run value; unchanged evidence and unrelated metadata do not create a new choice.

The existing project.image_route is only a scalar: an identical value does not prove a new image choice. Use actual evidenced run-configure for that choice; do not infer it from unrelated project revisions or scan historical changes into new authorization.

`scope:run` binds consent to this run, its course/module scope and chosen image route; normal stage/focus progress does not revoke it. It covers newly determined first-production jobs only for the listed purposes after all original gates pass. Purpose values are test/cover/asset/page/erase/repair. A narrower authorization uses `scope:targets` and `targets:[{"target_id":"P001","version":"v001"}]`. Version v002 or later and repair jobs are rework; these require explicit `include_rework:true` even under run scope. Grsai generation additionally requires `paid_generation:true`. Broad free text alone cannot provide either permission. New true course/module scope, a different route, additional purposes or out-of-scope target/version require actual applicable authorization; reuse already sufficient user instructions rather than asking again.

`run-status` returns effective `preferences`, `missing_preferences` and `preference_issues`; run revisions retain evidence and prior settings. A task may declare `requires_preferences:["image","video","editable"]` and, for narrow image scope, `image_requests:[{"purpose":"asset","target_id":"CHAR001","version":"v001"}]`. Default production requirements are image for cover/asset/page-image/video-script/video-assets/video-board, video for video-upload, editable for editable-*; B full handoff also needs image/erase. A genuinely text-only task may explicitly use an empty requirements list; this does not bypass runtime image authorization or any workflow gate. Preparation-only video prompts can continue while platform is unknown; a final platform-specific packet declares video. Human adoption/return tasks do not acquire generation permission; explicitly declared requirements still apply, and actual video-upload operations require video settings. Declared image_requests always require image settings, even with an empty requirements list.

The host reads the returned effective preferences before invoking each original Skill. For builtin images it checks the applicable structured authorization before the actual tool call; registration records an existing tool result, not consent. API CLI and runtime enforce applicable run authorization or the existing explicit batch evidence before new submission. Within an active run, resume/query/download of already submitted jobs preserves their original route and never resubmits pending work; the no-run manual batch authorization contract remains unchanged.

- `run-start --project P --plan PLAN`: explicit opt-in; same plan is idempotent. No queue means manual and run-status/run-next do not create one.
- `run-configure --project P --settings FILE`: evidence-backed partial preference update for an existing run; no queue creation or rebuilding. Conflicts and missing fields are returned by run-status.
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
