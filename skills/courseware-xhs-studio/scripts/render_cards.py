"""Render source-faithful 3:4 Xiaohongshu content cards from a JSON plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps


SIZE = (1440, 1920)
DEFAULT_PALETTE = {
    "background": "#FAF6EE",
    "ink": "#482A18",
    "muted": "#8E6647",
    "accent": "#F4E3D1",
}


def source_path(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def wrap(message: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in message.splitlines() or [message]:
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for char in paragraph:
            candidate = line + char
            if line and font.getlength(candidate) > width:
                lines.append(line)
                line = char
            else:
                line = candidate
        lines.append(line)
    return lines


def fitted_text(
    draw: ImageDraw.ImageDraw,
    message: str,
    xy: tuple[int, int],
    width: int,
    max_lines: int,
    start_size: int,
    min_size: int,
    font_path: Path,
    color: tuple[int, int, int],
) -> dict:
    for size in range(start_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(message, font, width)
        if len(lines) <= max_lines:
            line_height = round(size * 1.25)
            for index, line in enumerate(lines):
                draw.text((xy[0], xy[1] + index * line_height), line, font=font, fill=color)
            return {"font_size": size, "lines": lines}
    raise ValueError(f"Text does not fit in {max_lines} lines: {message}")


def panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    spec: dict,
    box: tuple[int, int, int, int],
    bold: Path,
    colors: dict[str, tuple[int, int, int]],
    base: Path,
) -> dict:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=24, fill="white", outline=colors["accent"], width=3)
    fitted_text(draw, spec["label"], (x1 + 28, y1 + 16), x2 - x1 - 56, 1, 34, 24, bold, colors["ink"])
    source = source_path(base, spec["file"])
    with Image.open(source) as raw:
        source_size = raw.size
        image = ImageOps.exif_transpose(raw)
        if "A" in image.getbands():
            white = Image.new("RGBA", image.size, "white")
            white.alpha_composite(image.convert("RGBA"))
            image = white.convert("RGB")
        else:
            image = image.convert("RGB")
    image.thumbnail((x2 - x1 - 70, y2 - y1 - 108), Image.Resampling.LANCZOS)
    image_x = x1 + (x2 - x1 - image.width) // 2
    image_y = y1 + 75 + (y2 - y1 - 98 - image.height) // 2
    canvas.paste(image, (image_x, image_y))
    return {
        "source": str(source),
        "source_sha256": digest(source),
        "source_size": source_size,
        "display_size": image.size,
        "display_xy": [image_x, image_y],
    }


def render(spec: dict, config: dict, base: Path) -> tuple[Image.Image, dict]:
    colors = {key: ImageColor.getrgb(value) for key, value in
              (DEFAULT_PALETTE | config.get("palette", {})).items()}
    regular = source_path(base, config["font_regular"])
    bold = source_path(base, config["font_bold"])
    canvas = Image.new("RGB", SIZE, colors["background"])
    draw = ImageDraw.Draw(canvas)
    fitted_text(draw, spec["kicker"], (96, 43), 1248, 1, 30, 22, regular, colors["muted"])
    fitted_text(draw, spec["title"], (96, 104), 1248, 2, 67, 42, bold, colors["ink"])
    fitted_text(draw, spec["intro"], (96, 275), 1248, 2, 32, 24, regular, colors["muted"])
    draw.line((96, 365, 1344, 365), fill=colors["accent"], width=4)

    layout = spec["layout"]
    if layout == "dual":
        boxes = [(90, 398, 1350, 1009), (90, 1040, 1350, 1652)]
    elif layout == "focus":
        boxes = [(90, 398, 1350, 1175)]
        draw.rounded_rectangle((90, 1210, 1350, 1652), radius=24,
                               fill="white", outline=colors["accent"], width=3)
        fitted_text(draw, spec["detail_title"], (125, 1235), 1190, 1, 39, 29,
                    bold, colors["ink"])
        for index, detail in enumerate(spec["details"], 1):
            fitted_text(draw, f"{index}. {detail}", (128, 1310 + (index - 1) * 105),
                        1180, 2, 37, 28, regular, colors["ink"])
    elif layout == "companion":
        boxes = [(90, 398, 1350, 1105), (90, 1190, 1350, 1652)]
        fitted_text(draw, spec["bridge"], (115, 1121), 1210, 1, 30, 23,
                    regular, colors["ink"])
    else:
        raise ValueError(f"Unknown layout: {layout}")
    sources = [panel(canvas, draw, item, box, bold, colors, base)
               for item, box in zip(spec["panels"], boxes, strict=True)]
    draw.rounded_rectangle((90, 1731, 1350, 1885), radius=24, fill=colors["accent"])
    fitted_text(draw, spec["footer"], (125, 1762), 1190, 2, 49, 32,
                bold, colors["ink"])
    return canvas, {"file": spec["file"], "layout": layout, "sources": sources,
                    "size": list(SIZE)}


def validate(config: dict, base: Path, output: Path) -> None:
    for field in ("font_regular", "font_bold"):
        if not source_path(base, config[field]).is_file():
            raise FileNotFoundError(f"{field}: {config[field]}")
    cards = config.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("cards must contain at least one card")
    if (output / "render-manifest.json").exists():
        raise FileExistsError(output / "render-manifest.json")
    seen = set()
    for card in cards:
        filename = card["file"]
        if Path(filename).name != filename or Path(filename).suffix.lower() != ".png":
            raise ValueError(f"Use a simple PNG filename: {filename}")
        if filename in seen or (output / filename).exists():
            raise FileExistsError(output / filename)
        seen.add(filename)
        count = {"dual": 2, "focus": 1, "companion": 2}.get(card["layout"])
        if count is None or len(card.get("panels", [])) != count:
            raise ValueError(f"Wrong panel count for {filename}")
        for field in ("kicker", "title", "intro", "footer"):
            if not str(card.get(field, "")).strip():
                raise ValueError(f"Missing {field} in {filename}")
        if card["layout"] == "companion" and not str(card.get("bridge", "")).strip():
            raise ValueError(f"Missing bridge in {filename}")
        if card["layout"] == "focus":
            details = card.get("details")
            if not str(card.get("detail_title", "")).strip() or not isinstance(details, list) \
                    or not 1 <= len(details) <= 3 or any(not str(item).strip() for item in details):
                raise ValueError(f"Focus card needs detail_title and 1-3 details: {filename}")
        for item in card["panels"]:
            if not str(item.get("label", "")).strip():
                raise ValueError(f"Missing panel label in {filename}")
            source = source_path(base, item["file"])
            if not source.is_file():
                raise FileNotFoundError(source)
            with Image.open(source) as image:
                image.verify()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output = args.output.resolve()
    validate(config, config_path.parent, output)
    rendered = [render(card, config, config_path.parent) for card in config["cards"]]
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for (image, record), card in zip(rendered, config["cards"], strict=True):
        target = output / card["file"]
        image.save(target, optimize=True)
        record["sha256"] = digest(target)
        manifest.append(record)
    (output / "render-manifest.json").write_text(
        json.dumps({"cards": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "cards": len(manifest), "output": str(output)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
