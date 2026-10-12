"""Render ordered courseware page images with an unchanged local layout template."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image

TEMPLATE = "direct-1222-3-3"
SCRIPTS = Path(__file__).resolve().parent
DEFAULT_SETTINGS = SCRIPTS.parents[2] / "sources/xhs-layout-tool.local.json"
sys.path.insert(0, str(SCRIPTS))
from layout_profiles import TEMPLATES, layout_config, layout_outputs


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def resolve(base: Path, value, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError(f"Missing {label} path")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def prepare_job(job_path, tool_root=None, settings=None) -> dict:
    job_path = Path(job_path).resolve()
    job = read_object(job_path)
    template_id = job.get("template", TEMPLATE)
    config, native_config = layout_config(template_id, job.get("config", {}))
    local = {}
    settings_path = Path(settings).resolve() if settings else DEFAULT_SETTINGS
    if tool_root is None:
        local = read_object(settings_path)
        tool_root = resolve(settings_path.parent, local.get("tool_root"), "tool_root")
    tool_root = Path(tool_root).resolve()
    template = tool_root / "legacy-tools" / TEMPLATES[template_id]
    if not template.is_file():
        raise ValueError(f"Local tool template not found: {template}")
    electron = (resolve(settings_path.parent, local["electron"], "electron") if local.get("electron")
                else tool_root / "desktop/node_modules/electron/dist/electron.exe")
    if not electron.is_file():
        raise ValueError(f"Electron not found: {electron}; specify an existing runtime in local settings")
    output = resolve(job_path.parent, job.get("output_dir"), "output_dir")
    if output.exists():
        raise ValueError(f"Output directory already exists; choose a new version: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"Declare and create the output parent first: {output.parent}")
    if output.is_relative_to(tool_root):
        raise ValueError("Output must be outside the external tool directory")

    raw_images = job.get("images")
    if not isinstance(raw_images, list) or not raw_images:
        raise ValueError("images must be a nonempty ordered list")
    images, slides = [], set()
    for item in raw_images:
        if not isinstance(item, dict):
            raise ValueError("Each image needs path and slide")
        slide = item.get("slide")
        if type(slide) is not int or slide < 1 or slide in slides:
            raise ValueError("Each image needs a unique positive slide number")
        slides.add(slide)
        path = resolve(job_path.parent, item.get("path"), "image")
        try:
            with Image.open(path) as image:
                width, height = image.size
                fmt = image.format
                image.verify()
            if (fmt, path.suffix.lower()) not in {("PNG", ".png"), ("JPEG", ".jpg"), ("JPEG", ".jpeg")}:
                raise ValueError("Use genuine PNG/JPEG page images with matching extensions")
            digest = sha256(path)
            if item.get("sha256") and item["sha256"].lower() != digest:
                raise ValueError("Source image SHA256 mismatch")
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid image {path}: {exc}") from exc
        images.append({"path": str(path), "name": path.name, "slide": slide,
                       "width": width, "height": height, "sha256": digest})

    outputs = layout_outputs(template_id, images)
    tool_files = [{"path": str(template), "sha256": sha256(template)}]
    helper = template.parent / "export-directory-helper.js"
    if helper.is_file():
        tool_files.append({"path": str(helper), "sha256": sha256(helper)})
    prepared = {"kind": "courseware-layout", "template": template_id,
                "tool_root": str(tool_root), "template_file": str(template),
                "tool_files": tool_files, "electron": str(electron),
                "output_dir": str(output), "config": config, "render_config": native_config, "images": images,
                "outputs": outputs, "job_sha256": sha256(job_path)}
    if job.get("source_pptx"):
        deck = resolve(job_path.parent, job["source_pptx"], "source_pptx")
        if not deck.is_file() or deck.suffix.lower() != ".pptx":
            raise ValueError("source_pptx must identify the existing source deck")
        prepared["source_pptx"] = {"path": str(deck), "sha256": sha256(deck)}
    return prepared


def write_json(path: Path, data) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def render(job_path, tool_root=None, settings=None, timeout=90) -> dict:
    prepared = prepare_job(job_path, tool_root, settings)
    output = Path(prepared["output_dir"])
    output.mkdir()
    (output / "AGENTS.md").write_text(
        "# Retained local layout output\nNumbered JPEGs are unchanged renderer outputs. "
        "layout-request.json stores ordered inputs/config; render-manifest.json records verified integrity only. "
        "runtime/ holds isolated Electron profile/cache/logs and its render result. failure.json records failures. "
        "No overwrite, deletion, publication or inferred lesson acceptance.\n", encoding="utf-8")
    runtime = output / "runtime"
    runtime.mkdir()
    (runtime / "AGENTS.md").write_text(
        "# Isolated Electron runtime\nprofile/, crashes/ and logs/ are generated only for this run. "
        "renderer-result.json and process.json retain actual results. No personal application settings. No cleanup.\n",
        encoding="utf-8")
    request = output / "layout-request.json"
    write_json(request, prepared)
    try:
        env = os.environ.copy()
        env.pop("ELECTRON_RUN_AS_NODE", None)
        process = subprocess.run(
            [prepared["electron"], str(SCRIPTS / "layout-tool-runner.cjs"), str(request)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        write_json(runtime / "process.json", {"returncode": process.returncode,
                   "stdout": process.stdout, "stderr": process.stderr})
        if process.returncode:
            raise RuntimeError(f"Layout renderer exited {process.returncode}: {process.stderr.strip()}")
        result = read_object(runtime / "renderer-result.json")
        if result.get("files") != [item["file"] for item in prepared["outputs"]]:
            raise RuntimeError("Renderer returned an incomplete or reordered output list")
        for item in prepared["outputs"]:
            path = output / item["file"]
            with Image.open(path) as image:
                width, height = image.size
                fmt = image.format
                image.verify()
            expected = item.get("expected_size")
            if (fmt != "JPEG" or width < 720 or height <= 0
                    or (expected is not None and [width, height] != expected)
                    or (expected is None and width != prepared["config"]["width"])):
                raise RuntimeError(f"Invalid layout output: {path.name}")
            item.update(width=width, height=height, format=fmt, sha256=sha256(path))
        sources = prepared["images"] + prepared["tool_files"]
        if "source_pptx" in prepared:
            sources = sources + [prepared["source_pptx"]]
        for item in sources:
            if sha256(Path(item["path"])) != item["sha256"]:
                raise RuntimeError(f"Source changed during rendering: {item['path']}")
        prepared.update(status="PASS", verification="render_integrity_only")
        write_json(output / "render-manifest.json", prepared)
        return prepared
    except Exception as exc:
        write_json(output / "failure.json", {"status": "FAIL", "error": str(exc)})
        raise RuntimeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--tool-root", type=Path)
    parser.add_argument("--settings", type=Path)
    args = parser.parse_args()
    try:
        result = render(args.job, args.tool_root, args.settings)
        print(json.dumps({"status": result["status"], "output_dir": result["output_dir"],
                          "files": [item["file"] for item in result["outputs"]]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
