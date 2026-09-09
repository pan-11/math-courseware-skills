import copy
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/math-courseware-studio/scripts/runtime"))
import pptx_editor as editor
from fixture_factory import retained_project, layered_deck


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.project = retained_project()
        source = layered_deck(self.project)
        self.inventory = editor.import_deck(self.project, source, {"P001": 1})
        self.source = self.project / self.inventory["source_deck"]
        self.target = next(s for s in self.inventory["slides"][0]["shapes"] if s["name"] == "existing-title")
        self.plan = {"source_deck": self.inventory["source_deck"], "source_sha256": editor.sha256(self.source),
                     "output": "editable/output/result.pptx", "mapping": {"P001": 1},
                     "text_units": [{"page_id": "P001", "unit_id": "title", "text": "一共有 5 个", "display_text": "一共有\n5 个",
                                     "target_shape_id": self.target["shape_id"], "expected_text": self.target["text"],
                                     "expected_geometry_sha256": self.target["geometry_sha256"],
                                     "box": {"x": 60, "y": 45, "width": 750, "height": 100}},
                                    {"page_id": "P001", "unit_id": "question", "text": "3 + 2 = 5", "box_px": {"x": 24, "y": 48, "width": 900, "height": 90},
                                     "source_image_size": {"width": 1920, "height": 1080},
                                     "source_content_rect": {"x": 50, "y": 60, "width": 800, "height": 450}}]}

    def review(self):
        # Test authority is explicitly synthetic; it is never course/user approval.
        evidence = self.project / "_state" / "synthetic-review.json"
        evidence.write_text(json.dumps({"confirmed": True, "scope": "editable-build", "plan_sha256": editor.plan_digest(self.plan),
                                       "reviewer": "synthetic-unittest", "evidence_ref": "synthetic test fixture only"}), encoding="utf-8")
        self.plan["review"] = {"confirmed": True, "evidence": "_state/synthetic-review.json", "sha256": editor.sha256(evidence)}

    def test_real_cli_updates_adds_and_preserves_source_layers(self):
        self.review()
        before = editor.sha256(self.source)
        report = editor.build_editable(self.project, self.plan)
        output = self.project / report["output"]
        inventory = editor.inspect_deck(output)
        self.assertEqual(before, editor.sha256(self.source))
        self.assertTrue(report["media_preserved"])
        self.assertTrue(report["non_target_parts_preserved"])
        self.assertEqual(len(inventory["slides"][0]["shapes"]), len(self.inventory["slides"][0]["shapes"]) + 1)
        units = [s for s in inventory["slides"][0]["shapes"] if s["name"].startswith("mcw:")]
        self.assertEqual({s["text"] for s in units}, {"一共有\n5 个", "3 + 2 = 5"})
        self.assertTrue(all(all(f.get("ea") == "KaiTi" for f in s["fonts"]) for s in units))
        added = next(s for s in units if s["name"].endswith("question"))
        self.assertEqual(int(added["geometry"]["off"]["x"]), 60 * editor.EMU)
        self.assertEqual(int(added["geometry"]["off"]["y"]), 80 * editor.EMU)
        self.assertEqual(int(added["geometry"]["ext"]["cx"]), 375 * editor.EMU)
        self.assertEqual(int(added["geometry"]["ext"]["cy"]), round(37.5 * editor.EMU))
        with zipfile.ZipFile(self.source) as zin, zipfile.ZipFile(output) as zout:
            for name in zin.namelist():
                if name != "ppt/slides/slide1.xml":
                    self.assertEqual(zin.read(name), zout.read(name), name)
            root = editor._parse(zout.read("ppt/slides/slide1.xml"))
            for node in editor._shape_nodes(root):
                if editor._identity(node).get("name").startswith("mcw:"):
                    self.assertIsNotNone(node.find("p:txBody/a:bodyPr/a:noAutofit", editor.NS))
        rerun = editor.build_editable(self.project, self.plan)
        self.assertTrue(rerun["idempotent"])
        self.assertEqual(report["output_sha256"], rerun["output_sha256"])

    def test_reject_manually_modified_output(self):
        self.review()
        report = editor.build_editable(self.project, self.plan)
        output = self.project / report["output"]
        with output.open("ab") as handle:
            handle.write(b"manual modification")
        with self.assertRaisesRegex(ValueError, "manually modified"):
            editor.build_editable(self.project, self.plan)

    def test_reject_source_change(self):
        self.review()
        with self.source.open("ab") as handle:
            handle.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            editor.build_editable(self.project, self.plan)

    def test_reject_text_mismatch_and_target_conflict(self):
        self.plan["text_units"][0]["display_text"] = "一共有6个"
        self.review()
        with self.assertRaisesRegex(ValueError, "authoritative text"):
            editor.build_editable(self.project, self.plan)
        self.plan["text_units"][0]["display_text"] = "一共有5个"
        self.plan["text_units"][0]["expected_text"] = "wrong prior text"
        self.review()
        with self.assertRaisesRegex(ValueError, "conflict"):
            editor.build_editable(self.project, self.plan)

    def test_reject_unreviewed_duplicate_out_of_range_and_missing_native(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            editor.build_editable(self.project, self.plan)
        self.plan["text_units"].append(copy.deepcopy(self.plan["text_units"][0]))
        self.review()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            editor.build_editable(self.project, self.plan)
        self.plan["text_units"].pop()
        self.plan["mapping"]["P001"] = 2
        self.review()
        with self.assertRaisesRegex(ValueError, "mapping"):
            editor.build_editable(self.project, self.plan)
        self.plan["mapping"]["P001"] = 1
        self.plan["required_native_objects"] = [{"page_id": "P001", "shape_id": 9999}]
        self.review()
        with self.assertRaisesRegex(ValueError, "native/math"):
            editor.build_editable(self.project, self.plan)

    def test_review_binds_plan_and_pixels_need_actual_rect(self):
        self.review()
        self.plan["text_units"][1]["box_px"]["x"] = 200
        with self.assertRaisesRegex(ValueError, "exact plan"):
            editor.build_editable(self.project, self.plan)
        self.plan["text_units"][1].pop("source_content_rect")
        self.review()
        with self.assertRaisesRegex(ValueError, "content rectangle"):
            editor.build_editable(self.project, self.plan)

    def test_canonical_font_and_paragraph_real_cli(self):
        for unit in self.plan["text_units"]:
            unit["font"] = {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 32, "color": "FFFFFF", "bold": True}
            unit["paragraph"] = {"align": "center", "line_spacing": 1.5,
                                 "margin_pt": {"left": 12, "right": 12, "top": 4, "bottom": 4}}
        self.review()
        report = editor.build_editable(self.project, self.plan)
        self.assertEqual(report["units"][0]["font"]["color"], "FFFFFF")
        inventory = editor.inspect_deck(self.project / report["output"])
        for shape in inventory["slides"][0]["shapes"]:
            if shape["name"].startswith("mcw:"):
                self.assertTrue(all(f["color"] == "FFFFFF" and f["bold"] and f["size_pt"] == 32 for f in shape["fonts"]))

    def test_unknown_format_fields_rejected_before_mutation(self):
        cases = [{"font": {"family": "KaiTi", "italic": True}},
                 {"paragraph": {"align": "center", "space_after": 10}},
                 {"bold": True}, {"paragraph": {"margin_pt": {"left": 12}}},
                 {"font": {"color": "white"}}, {"font": {"bold": "true"}}]
        original = copy.deepcopy(self.plan["text_units"][0])
        for extra in cases:
            with self.subTest(extra=extra):
                self.plan["text_units"][0] = {**original, **extra}
                self.review()
                with self.assertRaises(ValueError):
                    editor.build_editable(self.project, self.plan)
                self.assertFalse(list((self.project / "editable").rglob("work-*")))
                self.assertFalse((self.project / self.plan["output"]).exists())

    def test_absolute_package_slide_relationship(self):
        absolute = self.project / "inputs" / "absolute-rel.pptx"
        with zipfile.ZipFile(self.source) as zin, zipfile.ZipFile(absolute, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "ppt/_rels/presentation.xml.rels":
                    data = data.replace(b'Target="slides/slide1.xml"', b'Target="/ppt/slides/slide1.xml"')
                zout.writestr(info, data)
        inventory = editor.import_deck(self.project, absolute, self.plan["mapping"])
        self.assertEqual(inventory["slides"][0]["part"], "ppt/slides/slide1.xml")
        self.plan.update(source_deck=inventory["source_deck"], source_sha256=inventory["source_sha256"])
        self.review()
        report = editor.build_editable(self.project, self.plan)
        self.assertTrue(report["non_target_parts_preserved"])

    def test_pixels_reject_missing_size_outside_image_and_target(self):
        original = copy.deepcopy(self.plan["text_units"][1])
        cases = [{"source_image_size": {}}, {"box_px": {"x": 1900, "y": 48, "width": 900, "height": 90}},
                 {"source_content_rect": {"x": 500, "y": 60, "width": 800, "height": 450}}]
        for extra in cases:
            with self.subTest(extra=extra):
                self.plan["text_units"][1] = {**original, **extra}
                self.review()
                with self.assertRaises(ValueError):
                    editor.build_editable(self.project, self.plan)
                self.assertFalse(list((self.project / "editable").rglob("work-*")))


if __name__ == "__main__":
    unittest.main()
