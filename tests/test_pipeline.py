from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from proteinclaw.campaign import build_campaign_spec, required_clarifications
from proteinclaw.learning import export_learning_dataset
from proteinclaw.pipeline import run_campaign
from proteinclaw.scouting import run_heartbeat
from proteinclaw.tooling import select_route


class CampaignTests(unittest.TestCase):
    def test_campaign_spec_defaults(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
        self.assertEqual(spec["target"]["identifier"], "P04626")
        self.assertEqual(spec["task_type"], "protein_binder_design")
        self.assertTrue(spec["constraints"]["glycan_avoidance"])

    def test_clarifications_are_high_value_only(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
        questions = required_clarifications(spec)
        self.assertEqual([item.key for item in questions], ["epitope", "modality"])

    def test_commercial_safe_route_excludes_restricted_tools(self) -> None:
        route = select_route(
            "commercial_safe",
            {"name": "domain-ii-blockade"},
        )
        self.assertNotIn("alphafold3", route)

    def test_end_to_end_campaign_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_campaign(
                prompt="Design me a protein binder that inhibits HER2",
                root=Path(tmpdir),
                execution_mode="commercial_safe",
                use_fixture=True,
            )
            manifest_path = Path(result["manifest"]["artifact_paths"]["candidates"])
            self.assertTrue(manifest_path.exists())
            candidates = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(candidates), 3)
            self.assertGreater(candidates[0]["final_score"], candidates[-1]["final_score"])

    def test_cli_plan_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "proteinclaw",
                    "plan",
                    "--prompt",
                    "Design me a protein binder that inhibits HER2",
                    "--execution-mode",
                    "academic",
                    "--use-fixture",
                    "--root",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("report.md", completed.stdout)

    def test_heartbeat_writes_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = run_heartbeat(Path(tmpdir))
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(payload["items"]), 5)

    def test_learning_export_writes_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_campaign(
                prompt="Design me a protein binder that inhibits HER2",
                root=root,
                execution_mode="academic",
                use_fixture=True,
            )
            output = export_learning_dataset(root)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreaterEqual(payload["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
