"""Check file and format integrity of a Xiaohongshu post package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_profiles import TEMPLATES


def resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def check_file(base: Path, value: str, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: missing path")
        return None
    path = resolve(base, value)
    if not path.is_file() or path.stat().st_size == 0:
        errors.append(f"{label}: missing or empty file: {path}")
        return None
    return path


def check_image(base: Path, value: str, label: str, errors: list[str], layout: dict | None = None) -> None:
    path = check_file(base, value, label, errors)
    if path is None:
        return
    if layout is None and path.suffix.lower() != ".png":
        errors.append(f"{label}: deliver a PNG image")
    try:
        with Image.open(path) as image:
            width, height = image.size
            if layout is not None:
                if (image.format != "JPEG" or path.suffix.lower() not in {".jpg", ".jpeg"}
                        or width < 720 or [width, height] != [layout.get("width"), layout.get("height")]
                        or layout.get("format") != "JPEG"):
                    errors.append(f"{label}: layout dimensions/encoding do not match the render record")
                with path.open("rb") as handle:
                    actual_hash = hashlib.file_digest(handle, "sha256").hexdigest()
                if actual_hash != layout.get("sha256"):
                    errors.append(f"{label}: layout output SHA256 mismatch")
            elif image.format != "PNG":
                errors.append(f"{label}: actual encoding must be PNG")
            if layout is None and (width < 720 or abs(width / height - 0.75) > 0.005):
                errors.append(f"{label}: expected readable 3:4 image, got {width}x{height}")
            image.verify()
    except Exception as exc:
        errors.append(f"{label}: image cannot be opened: {exc}")


def check_card(base: Path, card, label: str, errors: list[str]) -> str | None:
    if isinstance(card, str):
        check_image(base, card, label, errors)
        return "legacy"
    if isinstance(card, dict) and card.get("kind") == "teaching-companion":
        check_image(base, card.get("file"), label, errors)
        material = card.get("material_type")
        if (not isinstance(material, str)
                or material not in {"teaching-design", "verbatim-script", "lesson-presentation",
                                    "worksheet", "blackboard-stickers", "blackboard-layout"}):
            errors.append(f"{label}: unsupported companion material_type")
        sources = card.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{label}: companion needs actual source files and references")
        else:
            for index, source in enumerate(sources, 1):
                source_label = f"{label}.source {index}"
                if not isinstance(source, dict):
                    errors.append(f"{source_label}: expected an object")
                    continue
                check_file(base, source.get("file"), source_label, errors)
                if not isinstance(source.get("ref"), str) or not source["ref"].strip():
                    errors.append(f"{source_label}: missing excerpt/sticker reference and related courseware page")
        return "teaching-companion"
    if not isinstance(card, dict) or card.get("kind") != "courseware-layout":
        errors.append(f"{label}: unsupported content card type")
        return
    manifest_path = check_file(base, card.get("render_manifest"), label + ".render_manifest", errors)
    if manifest_path is None:
        return
    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if (not isinstance(record, dict) or record.get("status") != "PASS"
                or record.get("kind") != "courseware-layout"
                or not isinstance(record.get("template"), str) or record["template"] not in TEMPLATES
                or not isinstance(record.get("config"), dict)
                or record["config"].get("fitMode") != "contain"):
            raise ValueError("expected a successful supported-layout contain render record")
        outputs = record.get("outputs")
        if not isinstance(outputs, list) or not isinstance(card.get("render_output"), str):
            raise ValueError("missing render output mapping")
        matches = [item for item in outputs if isinstance(item, dict) and item.get("file") == card["render_output"]]
        if len(matches) != 1:
            raise ValueError("render_output must match exactly one recorded output")
        check_image(base, card.get("file"), label, errors, layout=matches[0])
        return record["template"]
    except (OSError, ValueError) as exc:
        errors.append(f"{label}: invalid render manifest: {exc}")


def check_text(base: Path, value: str, label: str, errors: list[str], copy: bool = False,
               hashtags: bool = False) -> None:
    path = check_file(base, value, label, errors)
    if path is None:
        return
    body = path.read_text(encoding="utf-8-sig")
    if len(body.strip()) < 50:
        errors.append(f"{label}: text is too short for a usable deliverable")
    if copy and not body.lstrip().startswith("# "):
        errors.append(f"{label}: start the copy with one '# title' line")
    if hashtags:
        lines = body.strip().splitlines()
        if not lines or not lines[0].strip()[2:].strip():
            errors.append(f"{label}: include a nonempty title")
        if not lines or re.fullmatch(r"#[^\s#]+(?:\s+#[^\s#]+)*", lines[-1].strip()) is None:
            errors.append(f"{label}: end the copy with space-separated #hashtags")
        if not any(line.strip() and not line.lstrip().startswith("#") for line in lines[1:-1]):
            errors.append(f"{label}: include body copy between the title and hashtags")


def check_clip(base: Path, clip: dict, label: str, errors: list[str]) -> None:
    source = check_file(base, clip.get("source"), label + ".source", errors)
    if source is None:
        return
    suffix = source.suffix.lower()
    if suffix in {".mp4", ".mov", ".mkv"}:
        start, end = clip.get("in_seconds"), clip.get("out_seconds")
        if (not isinstance(start, (int, float)) or isinstance(start, bool)
                or not isinstance(end, (int, float)) or isinstance(end, bool)
                or start < 0 or end <= start):
            errors.append(f"{label}: real video needs valid in_seconds/out_seconds")
    elif suffix == ".pptx":
        slide = clip.get("slide")
        if not isinstance(slide, int) or isinstance(slide, bool) or slide < 1:
            errors.append(f"{label}: PPTX needs a positive slide number")
    elif suffix in {".png", ".jpg", ".jpeg"}:
        hold = clip.get("hold_seconds")
        if not isinstance(hold, (int, float)) or isinstance(hold, bool) or hold <= 0:
            errors.append(f"{label}: still image needs positive hold_seconds")
    else:
        errors.append(f"{label}: unsupported source type {suffix}")
    expected_hash = clip.get("sha256")
    if expected_hash:
        with source.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual.lower() != str(expected_hash).lower():
            errors.append(f"{label}: source SHA256 mismatch")


def check(manifest: dict, base: Path, expected_count: int | None) -> dict:
    errors: list[str] = []
    notes = manifest.get("notes")
    if not isinstance(notes, list) or not notes:
        return {"status": "FAIL", "notes": 0, "errors": ["notes must be a nonempty list"]}
    if expected_count is not None and len(notes) != expected_count:
        errors.append(f"expected {expected_count} notes, got {len(notes)}")
    ids, topics = set(), set()
    image_styles = []
    for index, note in enumerate(notes, 1):
        label = f"note {index}"
        if not isinstance(note, dict):
            errors.append(f"{label}: expected an object")
            continue
        note_id, topic = str(note.get("id", "")).strip(), str(note.get("topic", "")).strip()
        if not note_id or note_id in ids:
            errors.append(f"{label}: missing or duplicate id")
        if not topic or topic in topics:
            errors.append(f"{label}: missing or duplicate topic")
        ids.add(note_id)
        topics.add(topic)
        check_image(base, note.get("cover"), label + ".cover", errors)
        check_text(base, note.get("copy"), label + ".copy", errors, copy=True,
                   hashtags=note.get("format") == "video-cover-copy")
        fmt = note.get("format")
        if fmt == "image":
            cards = note.get("cards")
            if not isinstance(cards, list) or not cards:
                errors.append(f"{label}: image post needs ordered content cards")
            else:
                styles = []
                for card_index, card in enumerate(cards, 1):
                    styles.append(check_card(base, card, f"{label}.card {card_index}", errors))
                image_styles.append(set(styles))
        elif fmt == "video-cover-copy":
            extra = {"cards", "clips", "edit_list", "asset_list", "narration",
                     "captions", "timeline", "planned_seconds"}.intersection(note)
            if extra:
                errors.append(f"{label}: cover/copy-only scope cannot include editing fields: {', '.join(sorted(extra))}")
        elif fmt == "video-edit-kit":
            check_text(base, note.get("edit_list"), label + ".edit_list", errors)
            check_text(base, note.get("asset_list"), label + ".asset_list", errors)
            if "narration" in note:
                check_text(base, note["narration"], label + ".narration", errors)
            clips = note.get("clips")
            if not isinstance(clips, list) or not clips:
                errors.append(f"{label}: video kit needs actual source clips")
            else:
                for clip_index, clip in enumerate(clips, 1):
                    if isinstance(clip, dict):
                        check_clip(base, clip, f"{label}.clip {clip_index}", errors)
                    else:
                        errors.append(f"{label}.clip {clip_index}: expected an object")
        else:
            errors.append(f"{label}: format must be image, video-cover-copy or video-edit-kit")
    profile = manifest.get("series_profile")
    if profile is not None:
        formats = [note.get("format") if isinstance(note, dict) else None for note in notes]
        if profile != "three-image-two-video":
            errors.append("unsupported series_profile")
        elif (len(formats) != 5 or formats[:3] != ["image"] * 3
                or any(fmt not in ("video-cover-copy", "video-edit-kit") for fmt in formats[3:])):
            errors.append("series requires three image posts followed by two video notes (cover-copy or explicit editing kits)")
        elif (len(image_styles) != 3 or image_styles[0] - {"teaching-companion"} != {"watermark"}
                or len(image_styles[1] - {"teaching-companion"}) != 1
                or not image_styles[1] - {"teaching-companion"} <= {"product", "direct-133-33", "direct-1222-3-3"}
                or not image_styles[2] <= {"legacy", "teaching-companion"}):
            errors.append("series image styles must be layout1, one of layout2/3/4, then original explanatory cards")
    return {"status": "PASS" if not errors else "FAIL", "notes": len(notes), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    path = args.manifest.resolve()
    report = check(json.loads(path.read_text(encoding="utf-8")), path.parent, args.expected_count)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
