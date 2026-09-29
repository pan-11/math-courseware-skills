"""Check file and format integrity of a Xiaohongshu post package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


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


def check_image(base: Path, value: str, label: str, errors: list[str]) -> None:
    path = check_file(base, value, label, errors)
    if path is None:
        return
    if path.suffix.lower() != ".png":
        errors.append(f"{label}: deliver a PNG image")
    try:
        with Image.open(path) as image:
            width, height = image.size
            if width < 720 or abs(width / height - 0.75) > 0.005:
                errors.append(f"{label}: expected readable 3:4 image, got {width}x{height}")
            image.verify()
    except Exception as exc:
        errors.append(f"{label}: image cannot be opened: {exc}")


def check_text(base: Path, value: str, label: str, errors: list[str], copy: bool = False) -> None:
    path = check_file(base, value, label, errors)
    if path is None:
        return
    body = path.read_text(encoding="utf-8-sig")
    if len(body.strip()) < 50:
        errors.append(f"{label}: text is too short for a usable deliverable")
    if copy and not body.lstrip().startswith("# "):
        errors.append(f"{label}: start the copy with one '# title' line")


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
        check_text(base, note.get("copy"), label + ".copy", errors, copy=True)
        fmt = note.get("format")
        if fmt == "image":
            cards = note.get("cards")
            if not isinstance(cards, list) or not cards:
                errors.append(f"{label}: image post needs ordered content cards")
            else:
                for card_index, card in enumerate(cards, 1):
                    check_image(base, card, f"{label}.card {card_index}", errors)
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
            errors.append(f"{label}: format must be image or video-edit-kit")
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
