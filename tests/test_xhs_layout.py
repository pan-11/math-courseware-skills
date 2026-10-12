"""Retained synthetic fixtures for local layout4 jobs and delivery integrity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/courseware-xhs-studio/scripts"
QA = ROOT / "tests/runs/xhs-layout-adapter-20261012"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


class LayoutFixture(unittest.TestCase):
    def setUp(self):
        self.root = QA / ("unit-" + uuid.uuid4().hex[:12])
        self.root.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text(
            "# Retained synthetic fixtures\nAll files and tool/ output/ subtrees are synthetic. "
            "Declare output/runtime rules before use. No deletion or real lesson acceptance.\n",
            encoding="utf-8")

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def image(self, name, size=(960, 540), color="#d8e8ee", fmt=None):
        file = self.root / name
        Image.new("RGB", size, color).save(file, format=fmt)
        return file


class DeliveryTests(LayoutFixture):
    def setUp(self):
        super().setUp()
        self.checker = load_script("check_delivery")
        self.image("cover.png", (720, 960))
        (self.root / "copy.md").write_text("# Synthetic title\n" + "A real explanatory sentence. " * 5, encoding="utf-8")
        self.note = {"id": "01", "topic": "synthetic", "format": "image",
                     "cover": "cover.png", "copy": "copy.md", "cards": ["cover.png"]}

    def result(self):
        return self.checker.check({"notes": [self.note]}, self.root, None)

    def layout_card(self):
        image = self.image("content.jpg", (1242, 2106))
        manifest = {"kind": "courseware-layout", "status": "PASS",
                    "template": "direct-1222-3-3", "config": {"fitMode": "contain"},
                    "outputs": [{"file": "01-pages-001.jpg", "sha256": digest(image),
                                 "width": 1242, "height": 2106, "format": "JPEG"}]}
        self.write_json("render-manifest.json", manifest)
        self.note["cards"] = [{"file": "content.jpg", "kind": "courseware-layout",
                               "render_manifest": "render-manifest.json",
                               "render_output": "01-pages-001.jpg"}]
        return manifest

    def test_existing_png_cards_still_pass(self):
        self.assertEqual(self.result()["status"], "PASS")

    def test_unmarked_jpg_long_card_is_rejected(self):
        self.image("content.jpg", (1242, 2106))
        self.note["cards"] = ["content.jpg"]
        self.assertEqual(self.result()["status"], "FAIL")

    def test_manifest_backed_layout_content_passes(self):
        self.layout_card()
        self.assertEqual(self.result()["status"], "PASS", self.result())

    def test_layout_content_does_not_relax_cover(self):
        self.layout_card()
        self.note["cover"] = "content.jpg"
        self.assertEqual(self.result()["status"], "FAIL")

    def test_missing_render_manifest_is_rejected(self):
        self.layout_card()
        self.note["cards"][0]["render_manifest"] = "absent.json"
        self.assertEqual(self.result()["status"], "FAIL")

    def test_modified_layout_output_is_rejected(self):
        self.layout_card()
        self.image("content.jpg", (1242, 2106), "#eeaa88")
        self.assertEqual(self.result()["status"], "FAIL")

    def test_recorded_dimensions_must_match(self):
        manifest = self.layout_card()
        manifest["outputs"][0]["height"] = 1600
        self.write_json("render-manifest.json", manifest)
        self.assertEqual(self.result()["status"], "FAIL")

    def test_failed_render_is_rejected(self):
        manifest = self.layout_card()
        manifest["status"] = "FAIL"
        self.write_json("render-manifest.json", manifest)
        self.assertEqual(self.result()["status"], "FAIL")

    def test_cropped_layout_profile_is_rejected(self):
        manifest = self.layout_card()
        manifest["config"]["fitMode"] = "cover"
        self.write_json("render-manifest.json", manifest)
        self.assertEqual(self.result()["status"], "FAIL")

    def test_unknown_output_or_card_type_is_rejected(self):
        self.layout_card()
        self.note["cards"][0]["render_output"] = "absent.jpg"
        self.assertEqual(self.result()["status"], "FAIL")
        self.note["cards"][0]["kind"] = "skip-check"
        self.assertEqual(self.result()["status"], "FAIL")

    def test_real_encoding_is_checked(self):
        self.image("disguised.png", (720, 960), fmt="JPEG")
        self.note["cards"] = ["disguised.png"]
        self.assertEqual(self.result()["status"], "FAIL")

    def test_malformed_manifest_returns_a_failure(self):
        self.layout_card()
        self.write_json("render-manifest.json", ["not an object"])
        self.assertEqual(self.result()["status"], "FAIL")


class AdapterContractTests(LayoutFixture):
    def setUp(self):
        super().setUp()
        self.adapter = load_script("render_layout_tool")
        self.tool = self.root / "tool"
        self.tool.mkdir()
        (self.tool / "AGENTS.md").write_text("# Fake tool fixture\nlegacy-tools contains inert HTML; desktop contains an inert executable. Never launch it.\n", encoding="utf-8")
        (self.tool / "legacy-tools").mkdir()
        (self.tool / "legacy-tools/direct-layout-1222-3-3.html").write_text("<html>synthetic contract fixture</html>", encoding="utf-8")
        executable = self.tool / "desktop/node_modules/electron/dist/electron.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"synthetic executable placeholder; never launch")
        self.job = {"template": "direct-1222-3-3", "output_dir": "output", "images": []}
        for index in range(1, 9):
            image = self.image(f"page {index}.png")
            self.job["images"].append({"path": image.name, "slide": index})
        self.path = self.write_json("job.json", self.job)

    def prepare(self):
        self.write_json("job.json", self.job)
        return self.adapter.prepare_job(self.path, tool_root=self.tool)

    def test_explicit_image_order_and_hash_are_preserved(self):
        self.job["images"] = [self.job["images"][5], self.job["images"][0]]
        prepared = self.prepare()
        self.assertEqual([i["slide"] for i in prepared["images"]], [6, 1])
        self.assertEqual(prepared["images"][0]["sha256"], digest(self.root / "page 6.png"))
        self.assertEqual(prepared["outputs"][0]["slides"], [6, 1])
        self.assertFalse((self.root / "output").exists())

    def test_one_seven_and_eight_pages_have_complete_detail_coverage(self):
        all_images = self.job["images"][:]
        for count, expected in [(1, 1), (7, 4), (8, 4)]:
            with self.subTest(count=count):
                self.job["images"] = all_images[:count]
                prepared = self.prepare()
                self.assertEqual(len(prepared["outputs"]), expected)
                details = [o for o in prepared["outputs"] if o["role"] == "detail"]
                self.assertEqual([s for o in details for s in o["slides"]], list(range(1, count + 1)))

    def test_settings_resolve_relative_to_settings_file(self):
        settings = self.write_json("local-settings.json", {"tool_root": "tool"})
        prepared = self.adapter.prepare_job(self.path, settings=settings)
        self.assertEqual(Path(prepared["tool_root"]), self.tool)

    def test_existing_output_directory_is_never_reused(self):
        output = self.root / "output"
        output.mkdir()
        sentinel = output / "AGENTS.md"
        sentinel.write_text("keep these exact bytes", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exist"):
            self.prepare()
        self.assertEqual(sentinel.read_text(), "keep these exact bytes")

    def test_unsupported_template_and_crop_mode_are_rejected(self):
        self.job["template"] = "other"
        with self.assertRaisesRegex(ValueError, "template"):
            self.prepare()
        self.job["template"] = "direct-1222-3-3"
        self.job["config"] = {"fitMode": "cover"}
        with self.assertRaisesRegex(ValueError, "contain"):
            self.prepare()

    def test_invalid_or_misleading_config_is_rejected(self):
        for config in [{"width": 600}, {"gap": 0}, {"width": True}, {"bogus": 1}]:
            with self.subTest(config=config):
                self.job["config"] = config
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_missing_and_corrupt_images_are_rejected(self):
        self.job["images"][0]["path"] = "missing.png"
        with self.assertRaisesRegex(ValueError, "image"):
            self.prepare()
        (self.root / "corrupt.png").write_bytes(b"not an image")
        self.job["images"][0]["path"] = "corrupt.png"
        with self.assertRaisesRegex(ValueError, "image"):
            self.prepare()

    def test_duplicate_and_invalid_slide_numbers_are_rejected(self):
        for slide in [1, 0, True]:
            self.job["images"][1]["slide"] = slide
            with self.subTest(slide=slide), self.assertRaisesRegex(ValueError, "slide"):
                self.prepare()

    def test_missing_tool_does_not_create_output(self):
        with self.assertRaisesRegex(ValueError, "tool|template"):
            self.adapter.prepare_job(self.path, tool_root=self.root / "absent")
        self.assertFalse((self.root / "output").exists())

    def test_output_cannot_modify_external_tool_tree(self):
        self.job["output_dir"] = str(self.tool / "output")
        with self.assertRaisesRegex(ValueError, "tool"):
            self.prepare()

    def test_failed_runtime_keeps_evidence_without_success_manifest(self):
        with patch.object(self.adapter.subprocess, "run", side_effect=OSError("synthetic startup failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic startup failure"):
                self.adapter.render(self.path, tool_root=self.tool)
        output = self.root / "output"
        self.assertTrue((output / "AGENTS.md").is_file())
        self.assertTrue((output / "failure.json").is_file())
        self.assertFalse((output / "render-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
