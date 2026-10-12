# Courseware Xiaohongshu Skill files

- `SKILL.md`: routing, scope and shared production decisions. Keep it concise.
- `agents/openai.yaml`: invocation metadata only.
- `references/`: focused instructions for planning, visual production, video editing kits, and copy/review. Read only the relevant reference during use.
- `scripts/`: deterministic card layout, the local layout4 adapter (`render_layout_tool.py`, `layout-tool-runner.cjs`, `layout-tool-preload.cjs`), and delivery checks. The adapter loads the configured external template without copying its layout implementation; it uses retained isolated runtime data. Scripts never choose teaching claims, invent source frames, or publish.
- `references/local-layout-tool.md`: local tool location, explicit job format, source/output provenance and layout4 content-image delivery. The machine-specific settings stay outside the distributable Skill.

This is an independent post-production Skill for finished courseware and actual supporting files. It must not route through disabled `k12-courseware-*` Skills or modify source lessons. Video v1 produces an editing kit, actual cover and copy; it does not render MP4. All output paths must be explicit and existing files must not be overwritten silently. Keep files in English names except user-facing course output. Do not install global dependencies, delete or roll back files, or publish user content without explicit authorization. Commit and push the Skill and its repository integration files only with the user's explicit authorization.
