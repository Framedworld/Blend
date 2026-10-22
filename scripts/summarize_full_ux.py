"""Collect the final full-Studio UX evidence; never promote older diagnostics."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
OUT = ROOT / "output"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def runs(name):
    data = read_json(OUT / name)
    return data if isinstance(data, list) else [data]


def summarize(path, run=None):
    data = read_json(path)
    failed = data.get("failed", [])
    ok = data.get("ok", not failed) and not failed
    fresh = True
    if run:
        fresh = path.stat().st_mtime >= datetime.fromisoformat(run["started"]).timestamp()
        ok = ok and fresh and run["exit"] == 0
    result = {
        "path": str(path.relative_to(WORKSPACE)),
        "ok": bool(ok),
        "fresh_for_final_run": fresh,
        "passed": len(data.get("passed", [])),
        "failed": failed,
    }
    for key in ("dpr", "triangles", "input_method", "boundary", "responsive"):
        if key in data:
            result[key] = data[key]
    if "buttons" in data:
        result["buttons_inventoried"] = len(data["buttons"])
    return result


gui_runs = runs("full_accept_gui_runs.json")
gui_diagnostics = [r for r in runs("full_accept_gui_runs_before_layoutfix.json") if r["name"] == "sculpt_ux2"]
gui_diagnostics += runs("full_accept_focus_crash_run.json")
data_runs = runs("full_accept_data_runs.json") + runs("full_accept_extra_runs.json")
diagnostic_runs = gui_diagnostics + [r for r in data_runs if r["name"] == "full_ux_handoff_data"]
# This suite is deliberately ordinary-Python unittest code. The initial batch
# supplied Blender's process arguments to unittest; preserve that diagnostic.
data_runs = [r for r in data_runs if r["name"] != "full_ux_handoff_data"]
data_runs += runs("full_accept_handoff_python_run.json")
for replacement in runs("full_accept_focus_data_runs.json"):
    data_runs = [r for r in data_runs if r["name"] != replacement["name"]]
    data_runs.append(replacement)
file_runs = runs("full_accept_file_runs.json")
gui_files = {
    "scale100": "full_ux_gui_scale100.json",
    "scale125": "full_ux_gui_scale125.json",
    "scale150": "full_ux_gui_scale150.json",
    "controls": "controls_gui_results.json",
    "zbrush_sculpt": "zbrush_sculpt_gui_results.json",
    "sculpt_ux2": "sculpt_ux2_gui_results_full.json",
    "sculpt_ux2_scale100": "sculpt_ux2_gui_results_full_scale100.json",
    "sculpt_ux2_scale150": "sculpt_ux2_gui_results_full_scale150.json",
    "sculpt_pen": "sculpt_pen_gui_full.json",
    "channel_stability": "channel_stability_gui_results.json",
    "sculpt_feedback": "sculpt_feedback_gui_results.json",
    "sculpt_reference": "sculpt_reference_gui_full.json",
    "sculpt_density": "zbrush_density_results.json",
}
assert {r["name"] for r in gui_runs} == set(gui_files), "Incomplete GUI batch"
assert len(data_runs) == 18, "Incomplete data batch"
assert len(file_runs) == 1 and file_runs[0]["name"] == "file_lifecycle"
assert all(r["exit"] == 0 for r in gui_runs + data_runs + file_runs), "A final process failed"

gui = {r["name"]: summarize(OUT / gui_files[r["name"]], r) for r in gui_runs}
gui["file_lifecycle"] = summarize(OUT / "full_ux_file_gui.json", file_runs[0])
minimum_checks = {"scale100":180,"scale125":180,"scale150":180,
                  "sculpt_ux2":63,"sculpt_ux2_scale100":63,"sculpt_ux2_scale150":63,
                  "controls":71,"zbrush_sculpt":93,"sculpt_pen":47,
                  "channel_stability":13,"sculpt_feedback":13,"sculpt_reference":56,
                  "file_lifecycle":16}
assert all(gui[name]["passed"] >= count for name,count in minimum_checks.items()), "A behavior run is incomplete"
data_files = {
    "controls_data": "controls_data_results.json",
    "full_ux_panels_data": "full_ux_panels_data_results.json",
    "sculpt_ux2_data": "sculpt_ux2_data_results.json",
    "sculpt_reference_data": "sculpt_reference_data_results.json",
    "zbrush_sculpt_studio": "zbrush_sculpt_results.json",
}
data = {}
for run in data_runs:
    log_path = Path(run["log"])
    log = log_path.read_text(encoding="utf-8-sig", errors="replace")
    assert log_path.stat().st_mtime >= datetime.fromisoformat(run["started"]).timestamp()
    item = {"exit": run["exit"], "log": str(log_path.relative_to(WORKSPACE))}
    if run["name"] in data_files:
        item.update(summarize(OUT / data_files[run["name"]], run))
    else:
        counts = re.findall(r"Ran (\d+) tests?", log)
        if counts:
            item["unittest_tests"] = int(counts[-1])
            assert re.search(r"^OK(?:\s|$)", log, re.M), "Unittest report is not OK"
        if run["name"] == "audit_26_fixes":
            assert "ALL 26 CODE AUDIT FINDINGS VERIFIED & PASSED" in log
            item["audit_checks"] = 26
        item["ok"] = True
    data[run["name"]] = item

assert all(g["ok"] for g in gui.values()), "A GUI behavior result failed"
assert all(d["ok"] for d in data.values()), "A data behavior result failed"
gui_log_review = {}
for run in gui_runs + file_runs:
    log = Path(run["log"]).read_text(encoding="utf-8-sig", errors="replace")
    assert "Traceback (most recent call last)" not in log, "A native GUI timer or callback raised"
    assert "EXCEPTION_ACCESS_VIOLATION" not in log, "A native GUI process crashed"
    gui_log_review[run["name"]] = {
        "no_python_traceback_or_access_violation": True,
        "shutdown_diagnostics": [line for line in log.splitlines() if "Not freed memory blocks" in line],
    }
startup = read_json(OUT / "full_ux_demo_startup.json")
assert startup["ok"] and startup["qt_binding"] == "PySide6", "Interactive launcher verification failed"

paths = list((ROOT / "landfall_studio").rglob("*.py"))
paths += [ROOT / "scripts/launch_studio.ps1", ROOT / "scripts/open_studio.py", Path(__file__)]
paths += [WORKSPACE / "upstream/blendertk/blendertk/ui_utils/qt_dock.py"]
paths += [WORKSPACE / "Open Landfall Studio.cmd", WORKSPACE / "Open Landfall Sculpt Studio.cmd"]
paths += list((ROOT / "tests").glob("test_*.py"))
manifest = {str(p.relative_to(WORKSPACE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
result = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Full Studio UX fixes and scoped native acceptance; not full feature parity or physical device certification",
    "automated_ux_acceptance": "PASS",
    "full_product_certification": "NOT CLAIMED",
    "environment": "Windows; Blender 5.2.2 LTS; Python 3.13; PySide6; isolated factory scenes",
    "gui": gui,
    "gui_log_review": gui_log_review,
    "data": data,
    "runs": gui_runs + file_runs + data_runs,
    "diagnostic_runs": diagnostic_runs,
    "diagnostic_artifacts": ["sculpt_ux2_gui_full_layout_failure.json", "full_ux_focus_native_crash.txt", "sculpt_ux2_gui_full_focus_crash.json", "sculpt_ux2_gui_screen_binding_experiment.json", "full_ux_deferred_focus_probe.log", "sculpt_ux2_gui_results_deferred_probe.json"],
    "diagnostic_note": "Initial workspace run exited 0 with one failed GoZ pane-size assertion (43/44); original JSON preserved as sculpt_ux2_gui_full_layout_failure.json. A later baseline crashed in ED_screen_areas_iter_next after 27 checks (full_ux_focus_native_crash.txt). Final repair defers native focus screen changes outside area handling, cancels stale focus requests, validates queued live areas, recovers stopped retry timers and coalesces newest sizes. Strengthened 63-check matrix repeated. Intermediate Screen-keymap (41/60) and stale-timer (62/63) probes remain diagnostic only. The handoff unittest initially received Blender arguments (exit 2); rerun with its documented ordinary Python runner, 18/18 passed. Original logs retained.",
    "launcher_preflight": read_json(OUT / "full_ux_launcher.json"),
    "interactive_launch": startup,
    "boundaries": {
        "maya_runtime": "BLOCKED: Maya 2024 standalone initialization rc=3221225477 (0xC0000005); full_review_phase07_headless.log",
        "physical_devices": "UNVERIFIED: actual tablet/driver feel, mixed physical input, monitor-to-monitor use",
        "full_window_visuals": "BLOCKED: existing blank/stale GPU presentation also reproduces before Studio; native QWidget captures inspected",
        "exhaustiveness": "Menu poll and 91-button inventory do not mean every command, topology and scene combination was executed",
        "distribution": "Clean-machine installation and redistributable packaging/license review not performed",
    },
    "source_sha256": manifest,
}
(OUT / "full_ux_acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"automated_ux_acceptance": result["automated_ux_acceptance"], "gui": {k:v["passed"] for k,v in gui.items()}, "data_suites": len(data), "source_files_hashed": len(manifest)}, indent=2))
