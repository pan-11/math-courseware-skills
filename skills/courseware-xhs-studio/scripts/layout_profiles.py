"""Native parameters and page mappings for the four unchanged local templates."""
import re

TEMPLATES = {
    "watermark": "watermark-layout-v6.html",
    "product": "product-layout-v7.html",
    "direct-133-33": "direct-layout-133-33-v1.html",
    "direct-1222-3-3": "direct-layout-1222-3-3.html",
}


def layout_config(template, supplied):
    if not isinstance(template, str) or template not in TEMPLATES:
        raise ValueError("Unsupported template: " + str(template))
    if template == "watermark":
        config = {"bgColor": "#ffffff", "fitMode": "contain", "watermarkText": "", "watermarkEnabled": False}
    elif template == "product":
        config = {"bgColor": "#f6f3ed", "barColor": "#ffffff", "accentColor": "#56766a",
                  "fitMode": "contain", "title": "", "subtitle": "课件内容展示"}
    else:
        config = {"width": 1242, "gap": 18 if template == "direct-133-33" else 10,
                  "bgColor": "#f3f3f3", "fitMode": "contain", "watermarkText": ""}
    if not isinstance(supplied, dict) or set(supplied) - set(config):
        raise ValueError("Unknown layout config fields for " + template)
    config.update(supplied)
    if config["fitMode"] != "contain":
        raise ValueError("Courseware images require fitMode=contain")
    for key in ("bgColor", "barColor", "accentColor"):
        if key in config and (not isinstance(config[key], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", config[key])):
            raise ValueError(f"config.{key} must be a six-digit hex color")
    for key in ("watermarkText", "title", "subtitle"):
        if key in config:
            if not isinstance(config[key], str):
                raise ValueError(f"config.{key} must be text")
            config[key] = config[key].strip()
    if template == "watermark":
        if type(config["watermarkEnabled"]) is not bool:
            raise ValueError("config.watermarkEnabled must be a boolean")
        if config["watermarkEnabled"] and not config["watermarkText"]:
            raise ValueError("Enabled watermark needs actual watermarkText")
        native = {key: value for key, value in config.items() if key != "fitMode"}
        # An empty array is ignored by the original HTML; one invisible box clears its example.
        native["textBoxes"] = [{"id": "adapter-no-text", "text": "", "visible": False}]
    elif template == "product":
        if not config["title"]:
            raise ValueError("config.title must contain the actual note/course title")
        if not config["subtitle"]:
            raise ValueError("config.subtitle must not be empty")
        native = {"settings": {"bg": config["bgColor"], "bar": config["barColor"],
                  "accent": config["accentColor"], "t1": config["title"], "t2": config["subtitle"],
                  "w": 960, "h": 140, "fit": "contain"}, "coverCardPosition": {"x": 120, "y": 730}}
    else:
        if type(config["width"]) is not int or config["width"] < 720:
            raise ValueError("config.width must be an integer of at least 720")
        if type(config["gap"]) is not int or not 0 < config["gap"] < config["width"] / 4:
            raise ValueError("config.gap must be a positive integer smaller than width/4")
        native = dict(config)
    return config, native


def layout_outputs(template, images):
    outputs = []

    def add(role, group, **details):
        pages = [item["slide"] for item in group]
        label = "overview" if role == "overview" else "pages-" + "-".join(f"{page:03d}" for page in pages)
        output = {"file": f"{len(outputs) + 1:02d}-{label}.jpg", "role": role, "slides": pages}
        output.update(details)
        outputs.append(output)
        return output

    if template == "watermark":
        if len(images) > 36:
            raise ValueError("Layout1 supports at most 36 selected images; choose a smaller actual selection")
        for start in range(0, len(images), 3):
            group = images[start:start + 3]
            if start + 10 <= len(images):
                thumbs = images[start:start + 10]
            elif len(images) >= 10:
                thumbs = images[-10:]
            else:
                thumbs = [images[index % len(images)] for index in range(10)]
            height = sum(item["height"] * (1200 / item["width"]) for item in group)
            height += 40 * (len(group) - 1) + 80
            thumb_height = (height - 80 - 40 * 9) / 10
            thumb_width = max(item["width"] * (thumb_height / item["height"]) for item in thumbs)
            width = (40 + thumb_width if thumb_width > 0 else 0) + 40 + 1200 + 40
            if thumb_height <= 0:
                raise ValueError("Layout1 image aspect ratio produces invalid thumbnail geometry")
            output = add("detail", group, detail_slides=[item["slide"] for item in group],
                         thumbnail_slides=[item["slide"] for item in thumbs], expected_size=[int(width), int(height)])
            output["slides"] = list(dict.fromkeys(output["detail_slides"] + output["thumbnail_slides"]))
    elif template == "product":
        lead = images[:2]
        add("lead", lead, panel_slides=[item["slide"] for item in lead] if len(lead) == 2 else [lead[0]["slide"]] * 2,
            expected_size=[1200, 1600], empty_slots=0)
        for start in range(2, len(images), 5):
            group = images[start:start + 5]
            add("detail", group, expected_size=[1200, 1600], empty_slots=5 - len(group))
    else:
        if len(images) >= 7:
            add("overview", images[:7])
        start = 7 if template == "direct-133-33" and len(images) >= 7 else 0
        for index in range(start, len(images), 3):
            add("detail", images[index:index + 3])
    return outputs
