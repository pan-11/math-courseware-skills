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
- `run-configure --project P --settings FILE`: evidence-backed partial preference/limit update for an existing run; no queue creation or rebuilding. Conflicts and missing fields are returned by run-status.
- `run-extend --project P --plan PLAN`: append newly known tasks within actual scope. Repeated identical tasks are idempotent; existing definitions cannot be overwritten. Include activation_evidence for the actual extension scope. Prefer new versioned task IDs after a substantive plan revision.
- `run-next --project P --actor ID`: claims one production/review action under an OS file lock; returns waiting human tasks immediately even while another branch can proceed. Repeat calls return recover for an outstanding claim, not a new dispatch.
- `run-record --project P --result RESULT`: produced outputs require exactly the declared role set, current source versions and current legacy gate. The command creates a review packet; it does not claim the independent review happened.
- `run-status --project P`: read-only mode/task/stale overview. queue_complete is not whole-course completion.
- `run-mode --project P --mode manual|automatic --evidence TEXT`: retain progress and switch dispatch mode. Existing projects default manual. Mode choice does not grant new production scope.
- `run-pause` / `run-resume --project P --evidence TEXT`: pause or resume dispatch without canceling live agents/platform jobs. Mode remains separate.
- `run-reconcile --project P --evidence TEXT`: explicitly accept the currently authorized course/task scope as the queue basis after a real scope change; all workflow gates still apply. It does not rewrite outputs, approvals or stale evidence.
- `run-retry --project P --task-id ID --evidence TEXT`: retry a resolved local failure/stale version/review issue within the attempt bound. Unknown or external submission work cannot use this to resubmit.
- `run-recheck --project P --task-id ID --evidence TEXT`: when a report was unverified and the same unchanged files can now actually be inspected, create a fresh independent packet without recreating the output. At most two review attempts per production attempt; old packets remain. Changed inputs/outputs need actual revision, not this shortcut. Missing additional files require a properly scoped new task/standalone review with those real sources.

## Image count limit

New runs default to `limits.max_images:60` (positive integer, not a boolean). This is an image count, not a price or paid-generation grant. An optional plan `limits` supplies `max_images` and actual `evidence`. All purposes share one cumulative ledger: cover, assets, video previews/boards, page samples/pages, erase, repair, connection tests and new versions/rework. A 25-cell composite is one image; four separate covers are four. Extending a queue, changing job/batch IDs, switching routes/modes or repeating run-start never resets the ledger. No-run manual behavior is unchanged; an existing run in manual mode still enforces its budget.

Image-producing tasks declare positive integer `image_count` or concrete `image_requests` (each request is one image). When both are supplied they must match. The normal image-producing steps require a declaration; an explicitly text-only task may use `requires_preferences:[]` without declaring images. Explicit image requests/counts always require image consent and the external retry guard, regardless of step or that override. B full editable handoff also declares its actual erase-image count. `run-next` waits if the declaration exceeds remaining capacity, including at the cap; it can continue unrelated text work, review and recovery. It does not reserve builtin quota or infer image count from page count or instruction prose.

API generation checks the entire pending batch before execution and atomically charges that entire batch under the shared run lock before any outbound generation. Remaining 2/requested 4 means zero generation requests and zero new charges. The current adapter generates one output per job, so each new attempted job charges one. A direct job uses the same guard. Reservations, failed and unknown submissions retain their charges; query/download/repeated execution do not recount or resubmit. A retained reservation with an unwritten pending job is an uncertain attempt: stop and reconcile real provider evidence, never silently submit again or refund. Existing job locks protect the batch while workers use its bound reservation.

Builtin is a **soft limit**: the host checks declared quantity/remaining budget before calling the tool, then `image-register` counts each actual successful job/input once. No image-reserve command, token or receipt is required. Registration preserves an already generated valid result even if it exceeds the limit, records the actual overshoot and blocks future new generation. Direct unregistered tool calls and failed/unknown builtin attempts cannot be counted or prevented by Python; report this limitation and retain real tool evidence. Existing downloaded results are not scanned into a historical estimate.

`run-status` exposes read-only `image_budget_status` including configured/max_images/used/remaining/overshoot/accounting_started_at/history_unknown. An old run lacking budget configuration stays unconfigured; it cannot dispatch/submit new generation until an explicit `run-configure` limit update. Do not scan or estimate a legacy baseline. Accounting begins with that configuration (or an observed subsequent builtin registration), with unknown earlier usage stated. Previously submitted API tasks remain recoverable, and actual builtin results remain registerable even while unconfigured or capped.

To expand a cap, record the actual authorization in settings, e.g. `{"limits":{"max_images":80,"evidence":"实际授权总上限80张的原话"}}`. Preference updates may accompany it; omitted settings and all ledger entries persist. `run-resume` alone does not increase capacity; raising a limit never retries failed/unknown external work. Limit configuration does not replace image authorization or user adoption.

For a pre-B pending image task that has no quantity declaration, use the same `run-configure --settings` entry with `{"image_declarations":[{"task_id":"legacy-cover","image_count":4,"evidence":"现有待办明确计划生成四张独立封面的实际依据"}]}`. A limit update may be included in that settings file. This only supplies a known **future** quantity: do not infer historical image usage or derive a count from instruction prose. Each ID must exist once in the update and identify a pending, never attempted/claimed task without any existing image_count/image_requests or prior amendment. The count must be a positive integer, not a boolean; missing evidence, unknown fields, repeated IDs and changes to an existing declaration are rejected atomically. Claimed, retried or completed tasks cannot be amended.

The amendment is retained as task.image_declaration metadata; the original task spec, ID, dependencies, instruction, inputs/output roles, plan identity and image ledger remain unchanged. Repeating the original run-start/run-extend remains idempotent; run-extend still cannot rewrite existing content or declarations. The dispatched action's task includes the effective image_count and image_declaration evidence; capacity, image authorization and external retry protection use the same effective declaration. This does not execute/reset the task or authorize a generation by itself.

`image_declarations.evidence` records the host's actual production-plan basis for the future quantity; it does not claim a fresh user approval or require asking again for already known facts. This differs from `limits.evidence`, which records actual user authorization for the configured/expanded cap. A settings file mixing declarations, preferences and limits is all-or-nothing: one invalid field/item saves none of those changes.

Produced result:

```json
{"task_id":"analysis-v001","claim":"copy-exact-returned-claim","status":"produced","artifacts":{"analysis":"planning/analysis-v001.md","source_review":"planning/source-review-v001.json"}}
```

Human result uses `status:completed`, the real returned artifact roles and `user_evidence` with actual completion/adoption evidence. Do not mark completion because a file was requested or the user said generation was in progress. A production failure uses failed plus message; uncertain external outcome uses unknown plus message. Unknown can only be resolved by recovered actual outputs in this version, not by a new submission. Record calls with the same claim/content are idempotent. Revised production outputs need new paths, preserving prior attempts.

The queue stores progress only under `_state/automation`; original workflow/state semantics stay unchanged. A completed task becomes stale if referenced files change, a recorded source selection moves, or the user rejects its exact version. Downstream tasks inherit staleness. Recheck and re-review the affected current versions; never refresh old hashes without actual inspection.

For an abandoned review claim, first verify the previous agent is stopped. Its original packet may be assigned to a new independent reviewer (no production side effect), then record that real result; run-next resumes from the packet. Do not spawn a second reviewer while the first is still running. For abandoned production, inspect the actual files and recover via the current claim; only use failed/retry after a verified local failure. No automatic expiration or duplicate dispatch.

## Human calibration records

An active run records actual human events even when its mode is manual. Without a run, record-approval follows its original path: no automation/calibration files or new waits. Reviewers cannot write adoption, extend budgets or change gates through calibration.

At the first recording of an actual decision, optionally supply `review_packet` (one saved path) or `review_packets` (unique saved paths) for the reports actually displayed to the user. The host must not scan reports and pick a favorable verdict. A report must already be saved and pass existing project, artifact/source hash, source selection, identity and report-integrity checks. All explicitly selected reports together must cover exactly the entire decided artifact bundle. Extra/partial coverage, changed versions, invalid reports, any unverified result or absent references remain unpaired. A valid fully covered bundle has changes_required if any selected report requires changes, otherwise pass. Settings, operation returns and partial choices are not binary adoption votes.

Both record-approval JSON and human run-record JSON may carry `stage`, `human_node`, `human_reason` (actual text or null), and explicit report references. The task's optional stage/human_node/video_id supply defaults; a task's workflow step supplies C1–C8 when known, otherwise stage is unspecified. An approval can identify task_id/video_id. Do not infer a reason from rejection or demand an explanation. A missing report causes no additional human wait.

Human `completed` still requires every declared artifact role and actual user_evidence; its default human_decision is operation_completed, which does not grant adoption. Explicit approved is a binary human observation, but canonical adoption still requires record-approval. Rejected/changes_required/partial decisions cannot use completed. Use `status:returned` with a nonempty human_decision and actual evidence/files to record such a reply while retaining waiting_external. Returned is restricted to waiting human tasks; producers and unknown external submissions cannot use it. Exact replay adds nothing; a later actual different response is a new event. Returned checks current input/output versions and source selections; it can retain a rejection already written by record-approval without pretending that rejected files pass a production gate.

When a producer becomes stale after that rejection, its already waiting human task retains the same claim and waiting_external reply channel, with `blocked_by_upstream:true` and a visible `issues` explanation in run-status and run-next human_tasks. This is an unresolved reply channel, not a new adoption request: the producer remains stale, further downstream tasks remain blocked, completed remains disallowed, and production is not redispatched. A genuinely changed file hash or source selection still rejects a wrong-version returned receipt. Done and unknown human tasks do not reopen through this rule.

For the normal approval-then-receipt sequence, supply the returned approval `decision_id`. The receipt must name exactly the same artifact versions and compatible human_decision. If that content-derived ID occurs more than once (approve → reject → approve), also copy its `calibration_event.event_id` as `decision_event_id`. An ambiguous ID without that occurrence stays unpaired; do not guess. If a receipt was recorded first, a later approval may explicitly link `human_event_id` from that receipt's calibration event; the same versions and human decision are required. The original snapshot remains unchanged, including a null decision_id if canonical adoption had not yet been recorded; the canonical decision entry carries the link. A later report never retroactively upgrades that first snapshot. A link superseded by a later conflicting or partial human decision on any of those exact versions is rejected; do not use an old occurrence to revive a vote after a change of mind. Record the actual new decision instead.

With an active run, the actual approval identity is its sorted target versions, decision and user evidence. Adding/replacing review references, stage/node labels or reason annotations alone reuses the original occurrence and original pairing; a late report cannot become a second vote. The same applies to a human receipt's claim, actual status, versions, decision and evidence, including a metadata replay after completed. Unrelated decisions and unchanged subset approvals do not change an occurrence. A conflicting later decision on any same target version, including rejection of one group member or an actual returned request for changes, makes the later group reapproval a new occurrence. Explicit human_event_id/decision_event_id source links are always validated before replay; unknown or superseded links are rejected, and a valid explicitly selected source is not replaced by an older same-opinion event. No-run manual approval replay and pre-C completed receipt digest semantics stay unchanged.

Each actual startup/configuration group creates a choice event using its real evidence and effective settings snapshot. Repeating the same evidenced choice is idempotent; changing away and back keeps distinct events. Configurations use C0 with H05/H10/H16 or image-budget. `settings_hash` and `version_hash` both hash the actual settings_snapshot. Default max_images=60, inherited choices without a new user response and image_declarations host planning metadata do not create votes. Optional configure human_reason records a supplied explanation. Invalid mixed settings or invalid receipts save no partial changes or new events.

The run's calibration.jsonl stores event/run/decision IDs, event_seq, recorded_at, source, stage/node/task/video, sorted artifact path/SHA256 and bundle version_hash, explicit review references, validated review identities/packet and result paths/hashes/source versions, actual human decision/evidence/reason and agreement true/false/null. `reviews` retains every selected valid report; the top reviewer fields contain a scalar for one report or a list for several. The original human_decision is preserved; human_outcome normalizes approved to approved and rejected/changes_required to rejected, otherwise null. Pairing requires a binary outcome. Missing/invalid/unverified/mismatched/partial cases have pair_status=unpaired and a concrete unpaired_reason, excluded from the denominator.

All writers share the automation lock. A valid review snapshot is frozen before record-approval can invalidate it by writing a rejection. Existing immutable review result formats are unchanged: the report's existence and validation under that lock, with captured_at, establish that it existed before this decision. Original decisions or durable run revisions retain the event and receipt association before JSONL append. New event_seq is one greater than the maximum saved sequence across decisions and all retained revisions, including a revision whose mutable run pointer write failed. Replays and links keep the original sequence; recorded_at is display time and does not determine whether a link is superseded.

Mutation/recovery commands repair missing appends by event_id using those saved snapshots only. For an interrupted JSONL tail, recovery only appends the missing suffix when the existing bytes exactly prefix the next missing event's serialization. Complete JSON without a newline and a cut UTF-8 character can be completed without replacing any old bytes or complete lines. Unknown tails, conflicting rows or corrupted middle lines block repair with a diagnostic; they are never truncated or silently skipped. Recovery never rereads a newer review to fill an old answer. Historical rows are not revalidated against current artifact files.

`run-status.calibration` is read-only: total, comparable, agreed, disagreed, unpaired, agreement_rate, sample_status, by_stage and missing_event_ids. agreement_rate = agreed / comparable; with zero comparable samples it is null and sample_status is no_comparable_samples (display “暂无可比样本”). Every total/stage also separately reports pass_human_rejected (误放) and changes_required_human_approved. `log_complete` is false for any gap/tail/integrity issue; counts then cover only complete valid historical rows. `incomplete_tail` reports its line, byte count, recoverability and original event ID (or null); `log_issues` reports unknown/corrupt/conflicting rows. Status never repairs or writes files. No percentage or threshold changes any existing adoption or final-acceptance requirement.
