"""Beta support paths: Help > Report a Problem and File > Recover."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.ui import menus


def _op_exists(path):
    module, name = path.split(".", 1)
    return hasattr(getattr(bpy.ops, module), name) and getattr(getattr(bpy.ops, module), name).idname() != ""


def _ops(entries):
    for entry in entries:
        if entry[0] == "SUB":
            yield from _ops(entry[2])
        elif entry[0] == "OP":
            yield entry[1], entry[2]


class TestReportProblemHeadless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        landfall_studio.register()

    @classmethod
    def tearDownClass(cls):
        try:
            landfall_studio.unregister()
        except Exception:
            pass

    def test_menus_offer_report_and_recover(self):
        help_ops = dict(_ops(menus.HELP_MENU))
        file_ops = dict(_ops(menus.FILE_MENU))
        self.assertEqual(help_ops.get("Report a Problem…"), "landfall_studio.report_problem")
        self.assertEqual(file_ops.get("Last Session"), "wm.recover_last_session")
        self.assertEqual(file_ops.get("Auto Save…"), "wm.recover_auto_save")
        for label, op in list(help_ops.items()) + list(file_ops.items()):
            self.assertTrue(_op_exists(op), f"{label}: {op}")

    def test_report_without_launcher_zips_sysinfo_and_diagnostics(self):
        profile = tempfile.mkdtemp(prefix="lf_report_")
        saved = {k: os.environ.get(k) for k in ("LANDFALL_STUDIO_PROFILE", "LANDFALL_STUDIO_LAUNCHER")}
        os.environ["LANDFALL_STUDIO_PROFILE"] = profile
        os.environ.pop("LANDFALL_STUDIO_LAUNCHER", None)
        try:
            self.assertIn("FINISHED", bpy.ops.landfall_studio.report_problem())
            logs = Path(profile) / "logs"
            self.assertGreater((logs / "sysinfo.txt").stat().st_size, 500)
            self.assertIn("Landfall", (logs / "diagnostics.txt").read_text(encoding="utf-8"))
            zips = list(logs.glob("Landfall Studio report *.zip"))
            self.assertEqual(len(zips), 1)
            with zipfile.ZipFile(zips[0]) as zf:
                self.assertEqual(sorted(zf.namelist()), ["diagnostics.txt", "sysinfo.txt"])
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    result = unittest.main(argv=[sys.argv[0]], exit=False).result
    sys.exit(0 if result.wasSuccessful() else 1)
