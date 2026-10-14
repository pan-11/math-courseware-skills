"""Four original layout contracts and the user-confirmed five-post distribution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import uuid

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/courseware-xhs-studio/scripts"
QA = ROOT / "tests/runs/xhs-layout-series-20261012"
TEMPLATES = {
    "watermark": "watermark-layout-v6.html",
    "product": "product-layout-v7.html",
    "direct-133-33": "direct-layout-133-33-v1.html",
    "direct-1222-3-3": "direct-layout-1222-3-3.html",
}


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = QA / ("unit-" + uuid.uuid4().hex[:12])
        self.root.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text(
            "# Retained synthetic layout tests\nOnly synthetic images, manifests, fake non-executable "
            "tool files and new output paths. Never launch the fake runtime or delete files.\n", encoding="utf-8")

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path


class ProfileTests(Fixture):
    def setUp(self):
        super().setUp()
        self.adapter = load("render_layout_tool")
        self.tool = self.root / "tool"
        for folder in (self.tool, self.tool / "legacy-tools", self.tool / "desktop",
                       self.tool / "desktop/node_modules", self.tool / "desktop/node_modules/electron",
                       self.tool / "desktop/node_modules/electron/dist"):
            folder.mkdir()
            (folder / "AGENTS.md").write_text("# Inert synthetic tool fixture\nNever execute.\n", encoding="utf-8")
        for name in TEMPLATES.values():
            (self.tool / "legacy-tools" / name).write_text("Synthetic template", encoding="utf-8")
        (self.tool / "desktop/node_modules/electron/dist/electron.exe").write_bytes(b"INERT TEST FIXTURE")
        Image.new("RGB", (960, 540), "#e8e8e8").save(self.root / "page.png")

    def job(self, template, count=8, config=None):
        return {"template": template, "output_dir": "out-" + uuid.uuid4().hex[:8],
                "images": [{"path": "page.png", "slide": n} for n in range(1, count + 1)],
                "config": config if config is not None else ({"title": "本课内容"} if template == "product" else {})}

    def prepare(self, job):
        try:
            return self.adapter.prepare_job(self.write("job.json", job), tool_root=self.tool)
        except ValueError as exc:
            self.fail(f"Expected supported original layout; got {exc}")

    def test_all_four_templates_resolve_to_the_actual_html(self):
        for template, filename in TEMPLATES.items():
            with self.subTest(template=template):
                prepared = self.prepare(self.job(template))
                self.assertEqual(Path(prepared["template_file"]).name, filename)
                self.assertEqual(prepared["template"], template)
                self.assertEqual(prepared["config"]["fitMode"], "contain")

    def test_malformed_template_id_returns_a_validation_error(self):
        job = self.job("watermark")
        job["template"] = []
        try:
            self.adapter.prepare_job(self.write("job.json", job), tool_root=self.tool)
        except Exception as exc:
            self.assertIsInstance(exc, ValueError)
        else:
            self.fail("Malformed template ID must be rejected")

    def test_layout1_records_large_and_repeated_thumbnail_slots(self):
        prepared = self.prepare(self.job("watermark", 8))
        self.assertEqual([item["detail_slides"] for item in prepared["outputs"]], [[1, 2, 3], [4, 5, 6], [7, 8]])
        self.assertEqual(prepared["outputs"][0]["thumbnail_slides"], [1, 2, 3, 4, 5, 6, 7, 8, 1, 2])
        self.assertEqual(set(prepared["outputs"][0]["slides"]), set(range(1, 9)))

    def test_layout1_uses_last_ten_thumbnails_at_the_tail(self):
        prepared = self.prepare(self.job("watermark", 12))
        self.assertEqual(prepared["outputs"][0]["thumbnail_slides"], list(range(1, 11)))
        self.assertEqual(prepared["outputs"][-1]["thumbnail_slides"], list(range(3, 13)))
        self.assertEqual(prepared["outputs"][-1]["detail_slides"], [10, 11, 12])

    def test_layout1_disables_original_example_text(self):
        prepared = self.prepare(self.job("watermark", 1))
        native = prepared["render_config"]
        self.assertEqual(native["watermarkText"], "")
        self.assertFalse(native["watermarkEnabled"])
        self.assertEqual(len(native["textBoxes"]), 1)
        self.assertFalse(native["textBoxes"][0]["visible"])
        self.assertEqual(native["textBoxes"][0]["text"], "")

    def test_layout1_36_pages_have_complete_detail_coverage(self):
        prepared = self.prepare(self.job("watermark", 36))
        self.assertEqual(len(prepared["outputs"]), 12)
        self.assertEqual([page for item in prepared["outputs"] for page in item["detail_slides"]], list(range(1, 37)))

    def test_layout1_rejects_silent_truncation_and_unsupported_width(self):
        for job in (self.job("watermark", 37), self.job("watermark", 8, {"width": 1242})):
            with self.subTest(job=job):
                with self.assertRaisesRegex(ValueError, "36|config"):
                    self.adapter.prepare_job(self.write("job.json", job), tool_root=self.tool)

    def test_layout2_has_first_pair_then_five_page_groups(self):
        prepared = self.prepare(self.job("product", 8))
        self.assertEqual([item["slides"] for item in prepared["outputs"]], [[1, 2], [3, 4, 5, 6, 7], [8]])
        self.assertEqual(prepared["outputs"][0]["role"], "lead")
        self.assertTrue(all(item["expected_size"] == [1200, 1600] for item in prepared["outputs"]))
        self.assertEqual(prepared["outputs"][-1]["empty_slots"], 4)

    def test_layout2_single_image_duplicate_is_recorded(self):
        prepared = self.prepare(self.job("product", 1))
        self.assertEqual(prepared["outputs"][0]["panel_slides"], [1, 1])

    def test_layout2_maps_title_and_forces_native_contain(self):
        prepared = self.prepare(self.job("product", 7, {"title": "图形怎么分", "subtitle": "教学片段"}))
        self.assertEqual(prepared["render_config"]["settings"]["t1"], "图形怎么分")
        self.assertEqual(prepared["render_config"]["settings"]["t2"], "教学片段")
        self.assertEqual(prepared["render_config"]["settings"]["fit"], "contain")

    def test_layout2_requires_real_title_and_rejects_crop(self):
        for config in ({}, {"title": " "}, {"title": "Test", "fitMode": "cover"}):
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, "title|contain"):
                    self.adapter.prepare_job(self.write("job.json", self.job("product", 7, config)), tool_root=self.tool)

    def test_layout3_starts_detail_after_its_seven_page_overview(self):
        prepared = self.prepare(self.job("direct-133-33", 8))
        self.assertEqual([item["slides"] for item in prepared["outputs"]], [list(range(1, 8)), [8]])
        prepared = self.prepare(self.job("direct-133-33", 7))
        self.assertEqual(len(prepared["outputs"]), 1)
        prepared = self.prepare(self.job("direct-133-33", 4))
        self.assertEqual([item["slides"] for item in prepared["outputs"]], [[1, 2, 3], [4]])


class SeriesDeliveryTests(Fixture):
    def setUp(self):
        super().setUp()
        self.checker = load("check_delivery")
        Image.new("RGB", (720, 960), "white").save(self.root / "cover.png")
        Image.new("RGB", (1200, 1600), "#ddeeff").save(self.root / "layout.jpg")
        (self.root / "copy.md").write_text("# Synthetic title\n" + "Synthetic explanatory sentence. " * 5
                                           + "\n\n#数学 #教学设计\n", encoding="utf-8")

    def card(self, template):
        file = self.root / "layout.jpg"
        manifest = {"status": "PASS", "kind": "courseware-layout", "template": template,
                    "config": {"fitMode": "contain"}, "outputs": [{"file": "01.jpg", "width": 1200,
                    "height": 1600, "format": "JPEG", "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}]}
        self.write(template + ".json", manifest)
        return {"file": "layout.jpg", "kind": "courseware-layout", "render_manifest": template + ".json", "render_output": "01.jpg"}

    def series(self, second="product"):
        notes = [{"id": str(n), "topic": f"distinct synthetic topic {n}", "cover": "cover.png", "copy": "copy.md"} for n in range(1, 6)]
        for note, cards in zip(notes[:3], ([self.card("watermark")], [self.card(second)], ["cover.png"])):
            note.update(format="image", cards=cards)
        for note in notes[3:]:
            note.update(format="video-cover-copy")
        return {"series_profile": "three-image-two-video", "notes": notes}

    def result(self, manifest):
        return self.checker.check(manifest, self.root, None)

    def test_cover_copy_needs_no_video_sources_or_editing_files(self):
        value = self.series()
        result = self.result(value)
        self.assertEqual(result["status"], "PASS", result)
        for note in value["notes"][3:]:
            self.assertEqual(set(note), {"id", "topic", "format", "cover", "copy"})

    def test_cover_copy_is_also_valid_as_a_single_post(self):
        result = self.result({"notes": [self.series()["notes"][3]]})
        self.assertEqual(result["status"], "PASS", result)

    def test_cover_copy_requires_title_body_and_hashtags(self):
        valid = (self.root / "copy.md").read_text(encoding="utf-8")
        for text in (valid.split("#数学")[0], valid.replace("# Synthetic title", "Synthetic title"),
                     valid.replace("# Synthetic title", "# "),
                     "# Synthetic title\n\n" + "#SyntheticTag " * 20,
                     valid.replace("#数学 #教学设计", "## 话题")):
            with self.subTest(text=text):
                (self.root / "video-copy.md").write_text(text, encoding="utf-8")
                note = self.series()["notes"][3]
                note["copy"] = "video-copy.md"
                self.assertEqual(self.result({"notes": [note]})["status"], "FAIL")

    def test_cover_copy_rejects_accidental_editing_deliverables(self):
        for field, value in (("edit_list", "copy.md"), ("asset_list", "copy.md"),
                             ("narration", "copy.md"), ("clips", [{"source": "cover.png", "hold_seconds": 3}]),
                             ("cards", ["cover.png"]), ("planned_seconds", 55),
                             ("timeline", "timeline.json"), ("captions", "captions.srt")):
            with self.subTest(field=field):
                note = self.series()["notes"][3]
                note[field] = value
                self.assertEqual(self.result({"notes": [note]})["status"], "FAIL")

    def test_cover_copy_still_requires_real_readable_cover_and_copy(self):
        Image.new("RGB", (360, 480), "white").save(self.root / "small.png")
        for field, value in (("cover", "absent.png"), ("cover", "small.png"), ("copy", "absent.md")):
            with self.subTest(field=field, value=value):
                note = self.series()["notes"][3]
                note[field] = value
                self.assertEqual(self.result({"notes": [note]})["status"], "FAIL")

    def test_legacy_and_explicit_video_kits_remain_compatible(self):
        for count in (1, 2):
            with self.subTest(kits=count):
                value = self.series()
                for note in value["notes"][3:3 + count]:
                    note.update(format="video-edit-kit", edit_list="copy.md", asset_list="copy.md",
                                clips=[{"source": "cover.png", "hold_seconds": 3}])
                result = self.result(value)
                self.assertEqual(result["status"], "PASS", result)
                value["notes"][3]["clips"][0]["hold_seconds"] = 0
                self.assertEqual(self.result(value)["status"], "FAIL")
                value["notes"][3]["clips"][0] = {"source": "absent.mp4", "in_seconds": 0, "out_seconds": 2}
                self.assertEqual(self.result(value)["status"], "FAIL")

    def test_invalid_video_format_reports_failure(self):
        for fmt in ([], {}, None, "video"):
            with self.subTest(format=fmt):
                value = self.series()
                value["notes"][3]["format"] = fmt
                self.assertEqual(self.result(value)["status"], "FAIL")

    def test_all_three_second_post_choices_pass(self):
        for template in ("product", "direct-133-33", "direct-1222-3-3"):
            with self.subTest(template=template):
                result = self.result(self.series(template))
                self.assertEqual(result["status"], "PASS", result)

    def test_each_new_layout_is_also_valid_as_an_independent_post(self):
        for template in TEMPLATES:
            note = self.series()["notes"][0]
            note["cards"] = [self.card(template)]
            result = self.result({"notes": [note]})
            self.assertEqual(result["status"], "PASS", result)

    def test_series_rejects_missing_video_and_wrong_order(self):
        missing = self.series()
        missing["notes"].pop()
        reordered = self.series()
        reordered["notes"] = reordered["notes"][::-1]
        for value in (missing, reordered):
            self.assertEqual(self.result(value)["status"], "FAIL")

    def test_series_rejects_reusing_one_template_for_all_posts(self):
        value = self.series()
        for note in value["notes"][:3]:
            note["cards"] = [self.card("direct-1222-3-3")]
        self.assertEqual(self.result(value)["status"], "FAIL")

    def test_first_post_must_use_layout1(self):
        value = self.series()
        value["notes"][0]["cards"] = [self.card("product")]
        self.assertEqual(self.result(value)["status"], "FAIL")

    def test_second_post_uses_exactly_one_of_layout234(self):
        for templates in (("watermark",), ("product", "direct-133-33")):
            value = self.series()
            value["notes"][1]["cards"] = [self.card(template) for template in templates]
            self.assertEqual(self.result(value)["status"], "FAIL")

    def test_third_post_must_keep_original_explanatory_cards(self):
        value = self.series()
        value["notes"][2]["cards"] = [self.card("direct-1222-3-3")]
        self.assertEqual(self.result(value)["status"], "FAIL")

    def test_unknown_series_profile_is_rejected(self):
        value = self.series()
        value["series_profile"] = "invented"
        self.assertEqual(self.result(value)["status"], "FAIL")

    def test_changed_native_output_is_rejected(self):
        value = self.series()
        Image.new("RGB", (1200, 1600), "red").save(self.root / "layout.jpg")
        self.assertEqual(self.result(value)["status"], "FAIL")

    def test_malformed_record_template_is_reported_without_a_crash(self):
        value = self.series()
        path = self.root / "watermark.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["template"] = []
        path.write_text(json.dumps(record), encoding="utf-8")
        try:
            result = self.result(value)
        except TypeError as exc:
            self.fail(f"Invalid manifest must report FAIL, not crash: {exc}")
        self.assertEqual(result["status"], "FAIL")

    def companion(self, material_type="teaching-design"):
        return {"file": "cover.png", "kind": "teaching-companion", "material_type": material_type,
                "sources": [{"file": "copy.md", "ref": "Synthetic section 2; courseware P03"}]}

    def test_series_accepts_one_sourced_companion_per_post_for_each_second_layout(self):
        for template in ("product", "direct-133-33", "direct-1222-3-3"):
            with self.subTest(template=template):
                value = self.series(template)
                for note, material in zip(value["notes"], ("teaching-design", "verbatim-script", "blackboard-stickers")):
                    note["cards"].append(self.companion(material))
                result = self.result(value)
                self.assertEqual(result["status"], "PASS", result)

    def test_companion_types_can_follow_topic_instead_of_fixed_post_number(self):
        value = self.series()
        for note, material in zip(value["notes"], ("blackboard-stickers", "teaching-design", "verbatim-script")):
            note["cards"].append(self.companion(material))
        result = self.result(value)
        self.assertEqual(result["status"], "PASS", result)

    def test_third_post_can_use_one_original_companion_card(self):
        value = self.series()
        value["notes"][2]["cards"] = [self.companion("blackboard-stickers")]
        result = self.result(value)
        self.assertEqual(result["status"], "PASS", result)

    def test_single_image_post_accepts_a_companion_without_series_profile(self):
        note = self.series()["notes"][2]
        note["cards"] = [self.companion("verbatim-script")]
        result = self.result({"notes": [note]})
        self.assertEqual(result["status"], "PASS", result)

    def test_custom_nonseries_can_request_multiple_companion_cards(self):
        note = self.series()["notes"][2]
        note["cards"] = [self.companion(), self.companion("verbatim-script")]
        result = self.result({"notes": [note]})
        self.assertEqual(result["status"], "PASS", result)

    def test_companion_cannot_replace_required_courseware_layout(self):
        for index in (0, 1):
            value = self.series()
            value["notes"][index]["cards"] = [self.companion()]
            self.assertEqual(self.result(value)["status"], "FAIL")

    def test_companion_does_not_allow_unmarked_pngs_in_tool_posts(self):
        for index in (0, 1):
            value = self.series()
            value["notes"][index]["cards"].extend([self.companion(), "cover.png"])
            self.assertEqual(self.result(value)["status"], "FAIL")

    def test_companion_does_not_allow_a_second_courseware_template(self):
        for index in (0, 1):
            value = self.series()
            value["notes"][index]["cards"].extend([self.companion(), self.card("direct-133-33")])
            self.assertEqual(self.result(value)["status"], "FAIL")

    def test_default_series_accepts_multiple_sourced_companions(self):
        for template in ("product", "direct-133-33", "direct-1222-3-3"):
            with self.subTest(template=template):
                value = self.series(template)
                for note in value["notes"][:3]:
                    note["cards"].extend([self.companion(), self.companion("verbatim-script")])
                result = self.result(value)
                self.assertEqual(result["status"], "PASS", result)

    def test_presentation_worksheet_and_board_layout_are_supported(self):
        for material in ("lesson-presentation", "worksheet", "blackboard-layout"):
            with self.subTest(material=material):
                value = self.series()
                for note in value["notes"][:3]:
                    note["cards"].append(self.companion(material))
                result = self.result(value)
                self.assertEqual(result["status"], "PASS", result)

    def test_same_finished_companion_image_can_be_reused_across_posts(self):
        Image.new("RGB", (720, 960), "#f3efe2").save(self.root / "shared-content.png")
        shared = self.companion("verbatim-script")
        shared["file"] = "shared-content.png"
        value = self.series()
        for note in value["notes"][:3]:
            note["cards"].append(dict(shared))
        result = self.result(value)
        self.assertEqual(result["status"], "PASS", result)

    def test_expanded_series_checks_sources_on_every_companion(self):
        value = self.series()
        value["notes"][0]["cards"].extend([
            self.companion("teaching-design"), self.companion("verbatim-script"),
            self.companion("lesson-presentation"), self.companion("worksheet"),
        ])
        result = self.result(value)
        self.assertEqual(result["status"], "PASS", result)
        value["notes"][0]["cards"][-1]["sources"] = [
            {"file": "missing-worksheet.docx", "ref": "task 2; courseware P03"}
        ]
        result = self.result(value)
        self.assertEqual(result["status"], "FAIL", result)
        self.assertTrue(any("missing-worksheet.docx" in error for error in result["errors"]), result)

    def test_companion_requires_material_type_and_readable_source_references(self):
        for change in (
            {"material_type": None}, {"material_type": []}, {"material_type": "invented"},
            {"sources": None}, {"sources": []}, {"sources": "copy.md"}, {"sources": [None]},
            {"sources": [{"file": "absent.md", "ref": "section 1; P03"}]},
            {"sources": [{"file": "copy.md", "ref": " "}]},
            {"sources": [{"file": "copy.md", "ref": []}]},
            {"sources": [{"ref": "section 1; P03"}]},
        ):
            with self.subTest(change=change):
                value = self.series()
                card = self.companion()
                card.update(change)
                value["notes"][0]["cards"].append(card)
                self.assertEqual(self.result(value)["status"], "FAIL")

    def test_companion_png_checks_are_not_relaxed(self):
        for name, size, fmt in (("wrong.jpg", (720, 960), "JPEG"),
                                ("disguised.png", (720, 960), "JPEG"),
                                ("small.png", (360, 480), "PNG"),
                                ("wide.png", (960, 540), "PNG")):
            with self.subTest(name=name):
                Image.new("RGB", size, "white").save(self.root / name, format=fmt)
                value = self.series()
                card = self.companion()
                card["file"] = name
                value["notes"][0]["cards"].append(card)
                self.assertEqual(self.result(value)["status"], "FAIL")

    def test_companion_preserves_courseware_output_hash_checks(self):
        value = self.series()
        value["notes"][0]["cards"].append(self.companion())
        Image.new("RGB", (1200, 1600), "red").save(self.root / "layout.jpg")
        self.assertEqual(self.result(value)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
