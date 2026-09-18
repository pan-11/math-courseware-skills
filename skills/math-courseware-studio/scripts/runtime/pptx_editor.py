"""Conservative OfficeCLI text edits on retained copies of layered PPTX files.

Only selected text bodies/transforms are copied back from OfficeCLI's work file.
All other package parts retain their original bytes, including unknown parts.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import uuid
import zipfile

from lxml import etree as ET

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
EMU = 12700
SHAPES = {"sp", "pic", "grpSp", "graphicFrame", "cxnSp"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def plan_digest(plan):
    return _digest({k: v for k, v in plan.items() if k not in {"review", "authorization"}})


def _local(node):
    return ET.QName(node).localname


def _xml_value(node):
    if node is None:
        return None
    return [node.tag, sorted(node.attrib.items()), node.text if node.text and node.text.strip() else None,
            [_xml_value(child) for child in node]]


def _parse(data):
    return ET.fromstring(data, ET.XMLParser(resolve_entities=False, no_network=True))


def _parts(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP part names")
        return {name: archive.read(name) for name in names}


def _slides(parts):
    pres = _parse(parts["ppt/presentation.xml"])
    rels = _parse(parts["ppt/_rels/presentation.xml.rels"])
    targets = {r.get("Id"): posixpath.normpath(posixpath.join("/ppt", r.get("Target"))).lstrip("/")
               for r in rels if r.get("TargetMode") != "External"}
    return [targets[n.get("{" + NS["r"] + "}id")] for n in pres.findall("p:sldIdLst/p:sldId", NS)]


def _shape_nodes(root):
    tree = root.find("p:cSld/p:spTree", NS)
    return [node for node in tree.iter() if _local(node) in SHAPES]


def _identity(node):
    for child in node:
        if _local(child).startswith("nv"):
            return child.find("p:cNvPr", NS)
    return None


def _transform(node):
    for query in ("p:spPr/a:xfrm", "p:grpSpPr/a:xfrm", "p:xfrm"):
        value = node.find(query, NS)
        if value is not None:
            return value
    return None


def _text(node):
    body = node.find("p:txBody", NS)
    if body is None:
        return None
    lines = []
    for paragraph in body.findall("a:p", NS):
        lines.append("".join("\n" if _local(n) == "br" else (n.text or "")
                             for n in paragraph.iter() if _local(n) in {"t", "br"}))
    return "\n".join(lines)


def _shape_info(node):
    identity, transform = _identity(node), _transform(node)
    geometry = {}
    if transform is not None:
        for name in ("off", "ext", "chOff", "chExt"):
            child = transform.find("a:" + name, NS)
            if child is not None:
                geometry[name] = dict(child.attrib)
        geometry["attributes"] = dict(transform.attrib)
    fonts = []
    for prop in node.findall("p:txBody//a:rPr", NS):
        color = prop.find("a:solidFill/a:srgbClr", NS)
        fonts.append({"size_pt": int(prop.get("sz")) / 100 if prop.get("sz") else None,
                      "color": color.get("val") if color is not None else None,
                      "bold": prop.get("b") in {"1", "true"},
                      **{slot: prop.find("a:" + slot, NS).get("typeface")
                         for slot in ("latin", "ea", "cs") if prop.find("a:" + slot, NS) is not None}})
    parent = node.getparent()
    return {"shape_id": int(identity.get("id")), "name": identity.get("name"),
            "type": _local(node), "text": _text(node), "fonts": fonts,
            "geometry": geometry, "geometry_sha256": _digest(_xml_value(transform)),
            "object_sha256": _digest(_xml_value(node)),
            "parent_shape_id": int(_identity(parent).get("id")) if _local(parent) == "grpSp" else None,
            "crop": [dict(n.attrib) for n in node.findall(".//a:srcRect", NS)]}


def inspect_deck(path):
    path = Path(path)
    parts = _parts(path)
    size = _parse(parts["ppt/presentation.xml"]).find("p:sldSz", NS)
    return {"source_sha256": sha256(path), "width_pt": int(size.get("cx")) / EMU,
            "height_pt": int(size.get("cy")) / EMU,
            "slides": [{"slide_index": i + 1, "part": part,
                        "shapes": [_shape_info(n) for n in _shape_nodes(_parse(parts[part]))]}
                       for i, part in enumerate(_slides(parts))],
            "media": {n: hashlib.sha256(data).hexdigest() for n, data in parts.items() if n.startswith("ppt/media/")},
            "parts": {n: hashlib.sha256(data).hexdigest() for n, data in parts.items()}}


def _inside(project, value):
    relative = Path(value)
    root = Path(project).resolve()
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root) or target == root:
        raise ValueError("Path must stay inside project: " + str(value))
    return target


def _mapping(mapping, count):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Explicit page mapping required")
    for page_id, index in mapping.items():
        if not isinstance(page_id, str) or not page_id or type(index) is not int or not 1 <= index <= count:
            raise ValueError("Invalid page mapping")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Two page IDs cannot map to the same slide")


def import_deck(project, deck, mapping):
    source = Path(deck).resolve()
    inventory = inspect_deck(source)
    _mapping(mapping, len(inventory["slides"]))
    target = _inside(project, "editable/returned/" + inventory["source_sha256"][:12] + "-" + source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) != inventory["source_sha256"]:
        raise ValueError("Imported copy has manual changes")
    if not target.exists():
        shutil.copy2(source, target)
    inventory.update(source_deck=target.relative_to(Path(project).resolve()).as_posix(), mapping=mapping)
    report = target.with_suffix(".inventory.json")
    report.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory


def _box(unit, width, height):
    if "box" in unit and "box_px" in unit:
        raise ValueError("Choose pt box or pixel box")
    keys = ("x", "y", "width", "height")
    value = unit.get("box", unit.get("box_px"))
    if not isinstance(value, dict) or set(value) != set(keys) or any(type(value.get(k)) not in (int, float) or not math.isfinite(value[k]) for k in keys):
        raise ValueError("A finite box is required")
    value = dict(value)
    if "box_px" in unit:
        rect = unit.get("source_content_rect", {})
        if not isinstance(rect, dict) or set(rect) != set(keys) or any(type(rect.get(k)) not in (int, float) or not math.isfinite(rect[k]) for k in keys) or rect["width"] <= 0 or rect["height"] <= 0:
            raise ValueError("Actual source content rectangle in target slide pt is required")
        image = unit.get("source_image_size", {})
        if not isinstance(image, dict) or set(image) != {"width", "height"} or any(type(image.get(k)) not in (int, float) or not math.isfinite(image[k]) or image[k] <= 0 for k in ("width", "height")):
            raise ValueError("Actual source_image_size in pixels is required")
        if rect["x"] < 0 or rect["y"] < 0 or rect["x"] + rect["width"] > width + .001 or rect["y"] + rect["height"] > height + .001:
            raise ValueError("Target content rectangle exceeds slide")
        if value["x"] < 0 or value["y"] < 0 or value["width"] <= 0 or value["height"] <= 0 or value["x"] + value["width"] > image["width"] or value["y"] + value["height"] > image["height"]:
            raise ValueError("Pixel box exceeds source image")
        value = {"x": rect["x"] + value["x"] * rect["width"] / image["width"],
                 "y": rect["y"] + value["y"] * rect["height"] / image["height"],
                 "width": value["width"] * rect["width"] / image["width"],
                 "height": value["height"] * rect["height"] / image["height"]}
    elif "source_image_size" in unit or "source_content_rect" in unit:
        raise ValueError("Source coordinate fields require box_px")
    if value["x"] < 0 or value["y"] < 0 or value["width"] <= 0 or value["height"] <= 0 or value["x"] + value["width"] > width + .001 or value["y"] + value["height"] > height + .001:
        raise ValueError("Text box exceeds slide")
    return value


def _known_fields(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError("Unsupported " + label + " fields: " + ", ".join(sorted(unknown)))


def _format(unit):
    _known_fields(unit, {"page_id", "unit_id", "text", "display_text", "target_shape_id", "expected_text",
                        "expected_geometry_sha256", "box", "box_px", "source_image_size", "source_content_rect",
                        "font", "font_size", "paragraph", "auto_shrink", "vertical_anchor"}, "text unit")
    if unit.get("vertical_anchor", "top") not in {"top", "center", "bottom"}:
        raise ValueError("Unsupported vertical_anchor")
    raw = unit.get("font", "KaiTi")
    if isinstance(raw, str):
        font = {"family": raw, "east_asian": raw, "size_pt": unit.get("font_size", 32)}
    else:
        _known_fields(raw, {"family", "east_asian", "size_pt", "color", "bold"}, "font")
        if "font_size" in unit:
            raise ValueError("font_size cannot accompany canonical font object")
        font = {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 32, **raw}
    font = {"color": "000000", "bold": False, **font}
    if any(not isinstance(font[k], str) or not font[k].strip() for k in ("family", "east_asian")):
        raise ValueError("Font family and east_asian must be nonempty strings")
    if type(font["size_pt"]) not in (int, float) or not math.isfinite(font["size_pt"]) or font["size_pt"] <= 0:
        raise ValueError("Invalid font size")
    if not isinstance(font["color"], str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", font["color"]):
        raise ValueError("Font color must be six-digit RGB")
    font["color"] = font["color"].lstrip("#").upper()
    if type(font["bold"]) is not bool:
        raise ValueError("Font bold must be boolean")
    raw_paragraph = unit.get("paragraph", {})
    _known_fields(raw_paragraph, {"align", "line_spacing", "margin_pt"}, "paragraph")
    paragraph = {"align": "left", "line_spacing": 1.0, "margin_pt": {"left": 0, "right": 0, "top": 0, "bottom": 0}, **raw_paragraph}
    if paragraph["align"] not in {"left", "center", "right", "justify"}:
        raise ValueError("Unsupported paragraph alignment")
    spacing = paragraph["line_spacing"]
    if type(spacing) not in (int, float) or not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("line_spacing must be a positive multiplier")
    margin = paragraph["margin_pt"]
    _known_fields(margin, {"left", "right", "top", "bottom"}, "margin_pt")
    if set(margin) != {"left", "right", "top", "bottom"} or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in margin.values()):
        raise ValueError("margin_pt requires four finite nonnegative values")
    return font, paragraph


def _verify_format(node, operation):
    font, paragraph = operation["font"], operation["paragraph"]
    body = node.find("p:txBody/a:bodyPr", NS)
    if body is None or body.find("a:noAutofit", NS) is None or body.find("a:normAutofit", NS) is not None:
        raise ValueError("OfficeCLI autofit round-trip mismatch")
    if "vertical_anchor" in operation and body.get("anchor", "t") != {"top": "t", "center": "ctr", "bottom": "b"}[operation["vertical_anchor"]]:
        raise ValueError("OfficeCLI vertical anchor round-trip mismatch")
    for side, attr in {"left": "lIns", "top": "tIns", "right": "rIns", "bottom": "bIns"}.items():
        if abs(int(body.get(attr, "-1")) - round(paragraph["margin_pt"][side] * EMU)) > 1:
            raise ValueError("OfficeCLI margin round-trip mismatch")
    for p in node.findall("p:txBody/a:p", NS):
        prop = p.find("a:pPr", NS)
        alignment = {"left": "l", "center": "ctr", "right": "r", "justify": "just"}[paragraph["align"]]
        spacing = prop.find("a:lnSpc/a:spcPct", NS) if prop is not None else None
        if prop is None or prop.get("algn") != alignment or spacing is None or abs(int(spacing.get("val")) - round(paragraph["line_spacing"] * 100000)) > 1:
            raise ValueError("OfficeCLI paragraph round-trip mismatch")
    runs = _shape_info(node)["fonts"]
    if not runs or any(f.get("latin") != font["family"] or f.get("ea") != font["east_asian"] or f["size_pt"] != font["size_pt"] or f["color"] != font["color"] or f["bold"] != font["bold"] for f in runs):
        raise ValueError("OfficeCLI font round-trip mismatch")


def _office(args):
    executable = shutil.which("officecli")
    if executable is None:
        raise RuntimeError("OfficeCLI is required; do not install automatically")
    result = subprocess.run([executable, *map(str, args)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120, shell=False)
    if result.returncode:
        raise RuntimeError("OfficeCLI failed: " + result.stdout + result.stderr)
    return result.stdout


def _review(project, plan):
    if "authorization" in plan:
        if "review" in plan:
            raise ValueError("Choose authorization or historical review, not both")
        authorization = plan["authorization"]
        _known_fields(authorization, {"evidence", "sha256"}, "authorization")
        evidence = _inside(project, authorization.get("evidence", ""))
        if not evidence.is_file() or sha256(evidence) != authorization.get("sha256"):
            raise ValueError("Direct authorization evidence missing or changed")
        data = json.loads(evidence.read_text(encoding="utf-8"))
        pages = [page for page, index in sorted(plan.get("mapping", {}).items(), key=lambda item: item[1])]
        if (data.get("authorized") is not True or data.get("scope") != "editable-build"
                or data.get("source_sha256") != plan.get("source_sha256")
                or not pages or data.get("page_ids") != pages
                or any(not isinstance(data.get(key), str) or not data[key].strip()
                       for key in ("requested_by", "user_instruction", "evidence_ref"))):
            raise ValueError("Direct authorization does not cover this source and page range")
        return
    review = plan.get("review", {})
    if review.get("confirmed") is not True:
        raise ValueError("Explicit editable review confirmation required")
    evidence = _inside(project, review.get("evidence", ""))
    if not evidence.is_file() or sha256(evidence) != review.get("sha256"):
        raise ValueError("Review evidence missing or changed")
    data = json.loads(evidence.read_text(encoding="utf-8"))
    if data.get("confirmed") is not True or data.get("scope") != "editable-build" or data.get("plan_sha256") != plan_digest(plan) or not data.get("reviewer") or not data.get("evidence_ref"):
        raise ValueError("Review evidence does not confirm this exact plan")


def expand_text_units(units):
    expanded, logical_ids = [], set()
    for unit in units:
        key = (unit["page_id"], unit["unit_id"])
        if key in logical_ids:
            raise ValueError("Duplicate logical text unit")
        logical_ids.add(key)
        mode = "segments" if "segments" in unit else "instances" if "instances" in unit else None
        if mode is None:
            expanded.append((unit, unit["unit_id"]))
            continue
        _known_fields(unit, {"page_id", "unit_id", "text", mode}, "segmented or repeated text unit")
        segments = unit[mode]
        if (not isinstance(segments, list) or not segments
                or any(not isinstance(s, dict) or not isinstance(s.get("text"), str) for s in segments)
                or (mode == "segments" and "".join(s["text"] for s in segments) != unit["text"])
                or (mode == "instances" and any(s["text"] != unit["text"] for s in segments))):
            raise ValueError("Text " + mode + " must preserve the authoritative unit exactly")
        for segment in segments:
            if not isinstance(segment.get("object_id"), str) or not segment["object_id"]:
                raise ValueError("Text segments need nonempty object_id")
            if "page_id" in segment or "unit_id" in segment:
                raise ValueError("Text segments inherit page and logical unit")
            value = {k: v for k, v in segment.items() if k != "object_id"}
            value.update(page_id=unit["page_id"], unit_id=segment["object_id"])
            expanded.append((value, unit["unit_id"]))
    return expanded


def build_editable(project, plan):
    _review(project, plan)
    _known_fields(plan, {"source_deck", "source_sha256", "output", "mapping", "review", "authorization", "text_units",
                         "required_native_objects", "build_scope", "remaining_native_objects"}, "plan")
    scope = plan.get("build_scope", "complete")
    if scope not in {"complete", "text-refill"}:
        raise ValueError("Unsupported build_scope")
    remaining = plan.get("remaining_native_objects", [])
    if not isinstance(remaining, list) or (remaining and scope != "text-refill"):
        raise ValueError("Only text-refill can report remaining native objects")
    for item in remaining:
        _known_fields(item, {"page_id", "object_id", "reason"}, "remaining native object")
        if item.get("page_id") not in plan["mapping"] or any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("object_id", "reason")):
            raise ValueError("Invalid remaining native object")
    source = _inside(project, plan["source_deck"])
    output = _inside(project, plan["output"])
    if source == output or output.suffix.lower() != ".pptx":
        raise ValueError("Output must be a new PPTX path")
    before = inspect_deck(source)
    if before["source_sha256"] != plan["source_sha256"]:
        raise ValueError("Source changed since review")
    mapping = plan["mapping"]
    _mapping(mapping, len(before["slides"]))
    report_path = output.with_suffix(".report.json")
    digest = plan_digest(plan)
    if output.exists():
        if not report_path.exists():
            raise ValueError("Output exists without provenance; do not overwrite")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("plan_sha256") != digest or report.get("output_sha256") != sha256(output):
            raise ValueError("Output was manually modified or belongs to another plan")
        return {**report, "idempotent": True}
    operations, names, targets = [], set(), set()
    for slide in before["slides"]:
        existing_names = [shape["name"] for shape in slide["shapes"]]
        if len(existing_names) != len(set(existing_names)):
            raise ValueError("Duplicate source shape names require review")
    for unit, source_unit_id in expand_text_units(plan.get("text_units", [])):
        font, paragraph = _format(unit)
        page_id, unit_id = unit["page_id"], unit["unit_id"]
        if page_id not in mapping or not isinstance(unit_id, str) or not unit_id:
            raise ValueError("Invalid unit/page ID")
        name = "mcw:" + page_id + ":" + unit_id
        if name in names:
            raise ValueError("Duplicate text unit name")
        names.add(name)
        text = unit["text"]
        display = unit.get("display_text", text)
        if not isinstance(text, str) or not isinstance(display, str) or re.sub(r"\s", "", text) != re.sub(r"\s", "", display):
            raise ValueError("display_text differs from authoritative text")
        if unit.get("auto_shrink", False) is not False:
            raise ValueError("Automatic text shrinking is prohibited")
        box = _box(unit, before["width_pt"], before["height_pt"])
        index = mapping[page_id]
        shapes = before["slides"][index - 1]["shapes"]
        target_id = unit.get("target_shape_id")
        if any(s["name"] == name and s["shape_id"] != target_id for s in shapes):
            raise ValueError("Text unit name already exists on another shape")
        if target_id is not None:
            target = next((s for s in shapes if s["shape_id"] == target_id), None)
            if not target or target["type"] != "sp" or target["parent_shape_id"] is not None:
                raise ValueError("Target must be an existing top-level native text shape")
            if target["text"] != unit.get("expected_text") or target["geometry_sha256"] != unit.get("expected_geometry_sha256"):
                raise ValueError("Target text or geometry conflict")
            if (index, target_id) in targets:
                raise ValueError("Two units cannot target the same shape")
            targets.add((index, target_id))
        margins = paragraph["margin_pt"]
        if margins["left"] + margins["right"] >= box["width"] or margins["top"] + margins["bottom"] >= box["height"]:
            raise ValueError("Paragraph margins leave no text area")
        operations.append({"index": index, "target_id": target_id, "name": name, "text": display,
                           "source_unit_id": source_unit_id, "box": box, "font": font, "paragraph": paragraph,
                           "vertical_anchor": unit.get("vertical_anchor", "top")})
    native = plan.get("required_native_objects", [])
    for item in native:
        index = mapping.get(item["page_id"])
        shape = next((s for s in before["slides"][index - 1]["shapes"] if s["shape_id"] == item["shape_id"]), None) if index else None
        if not shape or shape["type"] not in {"sp", "cxnSp", "graphicFrame"}:
            raise ValueError("Required native/math object is absent or raster")
    if not operations:
        raise ValueError("At least one reviewed text unit required")
    output.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output.parent / ("work-" + uuid.uuid4().hex)
    work_dir.mkdir()
    work = work_dir / "officecli-working.pptx"
    shutil.copy2(source, work)
    command_log = []
    for operation in operations:
        font, paragraph = operation["font"], operation["paragraph"]
        props = {"text": operation["text"], "name": operation["name"], "font": font["family"],
                 "font.ea": font["east_asian"], "size": str(font["size_pt"]), "color": font["color"],
                 "bold": str(font["bold"]).lower(), "autoFit": "none", "align": paragraph["align"],
                 "valign": {"top": "top", "center": "middle", "bottom": "bottom"}[operation["vertical_anchor"]],
                 "lineSpacing": str(paragraph["line_spacing"]) + "x",
                 "margin": ",".join(str(paragraph["margin_pt"][k]) + "pt" for k in ("left", "top", "right", "bottom")),
                 **{k: str(v) + "pt" for k, v in operation["box"].items()}}
        if operation["target_id"] is None:
            args = ["add", work, f'/slide[{operation["index"]}]', "--type", "shape",
                    "--prop", "fill=none", "--prop", "line=none"]
        else:
            args = ["set", work, f'/slide[{operation["index"]}]/shape[@id={operation["target_id"]}]']
        for key, value in props.items():
            args.extend(["--prop", key + "=" + value])
        command_log.append(_office(args))
    command_log.append(_office(["close", work]))
    edited = _parts(work)
    original = _parts(source)
    slide_parts = _slides(original)
    patched = {}
    for index in sorted({op["index"] for op in operations}):
        part = slide_parts[index - 1]
        root = _parse(original[part])
        modified = _parse(edited[part])
        for operation in (op for op in operations if op["index"] == index):
            matches = [n for n in _shape_nodes(modified) if _identity(n).get("name") == operation["name"]]
            if len(matches) != 1:
                raise ValueError("OfficeCLI did not create exactly one named unit")
            changed = matches[0]
            if _text(changed) != operation["text"]:
                raise ValueError("OfficeCLI text round-trip mismatch")
            _verify_format(changed, operation)
            if operation["target_id"] is None:
                root.find("p:cSld/p:spTree", NS).append(deepcopy(changed))
            else:
                target = next(n for n in _shape_nodes(root) if int(_identity(n).get("id")) == operation["target_id"])
                _identity(target).set("name", operation["name"])
                body = target.find("p:txBody", NS)
                if body is not None:
                    target.replace(body, deepcopy(changed.find("p:txBody", NS)))
                else:
                    target.append(deepcopy(changed.find("p:txBody", NS)))
                transform = _transform(target)
                if transform is not None:
                    transform.getparent().replace(transform, deepcopy(_transform(changed)))
                else:
                    raise ValueError("Mapped target has no explicit geometry")
        patched[part] = ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    candidate = work_dir / "candidate.pptx"
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(candidate, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, patched.get(info.filename, original[info.filename]))
    after = inspect_deck(candidate)
    for slide in before["slides"]:
        resulting_shapes = after["slides"][slide["slide_index"] - 1]["shapes"]
        after_shapes = {s["shape_id"]: s for s in resulting_shapes}
        if len(after_shapes) != len(resulting_shapes) or len({s["name"] for s in resulting_shapes}) != len(resulting_shapes):
            raise ValueError("Output contains duplicate shape IDs or names")
        prior_ids = [s["shape_id"] for s in slide["shapes"]]
        if [s["shape_id"] for s in resulting_shapes if s["shape_id"] in prior_ids] != prior_ids:
            raise ValueError("Original stacking/group order changed")
        for shape in slide["shapes"]:
            if (slide["slide_index"], shape["shape_id"]) not in targets and shape["object_sha256"] != after_shapes.get(shape["shape_id"], {}).get("object_sha256"):
                raise ValueError("Non-target shape changed")
    for part, data in original.items():
        if part not in patched and after["parts"].get(part) != hashlib.sha256(data).hexdigest():
            raise ValueError("Non-target ZIP part changed")
    if sha256(source) != before["source_sha256"]:
        raise ValueError("Source changed during build")
    validation = _office(["validate", candidate])
    with output.open("xb") as handle:
        handle.write(candidate.read_bytes())
    report = {"plan_sha256": digest, "source_sha256": before["source_sha256"], "output": plan["output"],
              "output_sha256": sha256(output), "units": operations, "native_objects": native,
              "non_target_parts_preserved": True, "media_preserved": before["media"] == after["media"],
              "source_unchanged": True, "wps_render": "unverified", "idempotent": False,
              "officecli_validation": validation, "work_directory": work_dir.relative_to(Path(project).resolve()).as_posix()}
    report.update(build_scope=scope, remaining_native_objects=remaining,
                  full_editability_verified=scope == "complete" and not remaining)
    (work_dir / "officecli-log.json").write_text(json.dumps(command_log, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, value in (("reviewed-plan.json", plan), ("source-inventory.json", before), ("output-inventory.json", after)):
        (work_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
