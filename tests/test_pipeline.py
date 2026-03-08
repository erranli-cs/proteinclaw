from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from proteinclaw.campaign import build_campaign_spec, required_clarifications, resolve_clarifications
from proteinclaw.dossier import _filter_literature_hits, build_target_dossier, write_fixture_pdb
from proteinclaw.env import load_env
from proteinclaw.learning import export_learning_dataset
from proteinclaw.pipeline import run_campaign
from proteinclaw.scouting import run_heartbeat
from proteinclaw.tamarind import TamarindError, request_text
from proteinclaw.tooling import TOOL_REGISTRY, load_tool_registry, run_tool_adapter, select_route


class CampaignTests(unittest.TestCase):
    def test_campaign_spec_defaults(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
        self.assertEqual(spec["target"]["identifier"], "P04626")
        self.assertEqual(spec["task_type"], "protein_binder_design")
        self.assertTrue(spec["constraints"]["glycan_avoidance"])

    def test_second_supported_target_defaults(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits EGFR")
        self.assertEqual(spec["target"]["identifier"], "P00533")

    def test_trka_target_defaults(self) -> None:
        spec = build_campaign_spec("Please design a protein minibinder to tropomyosin receptor kinase A (TrkA; also known as NTRK1)")
        self.assertEqual(spec["target"]["identifier"], "P04629")
        self.assertEqual(spec["design_space"]["modality"], "mini-binder")

    def test_clarifications_are_high_value_only(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
        questions = required_clarifications(spec)
        self.assertEqual([item.key for item in questions], ["epitope", "modality"])

    def test_resolve_clarifications_applies_defaults(self) -> None:
        spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
        answers, records = resolve_clarifications(spec, interactive=False, answers={"epitope": "known therapeutic epitope"})
        self.assertEqual(answers["epitope"], "known therapeutic epitope")
        self.assertEqual(answers["modality"], "open modality")
        self.assertEqual(len(records), 2)

    def test_commercial_safe_route_excludes_restricted_tools(self) -> None:
        route = select_route("commercial_safe", {"name": "domain-ii-blockade"})
        self.assertEqual(route, ["rfd3", "ligandmpnn"])

    def test_end_to_end_campaign_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_campaign(
                prompt="Design me a protein binder that inhibits HER2",
                root=Path(tmpdir),
                execution_mode="academic",
                use_fixture=True,
            )
            manifest_path = Path(result["manifest"]["artifact_paths"]["candidates"])
            self.assertTrue(manifest_path.exists())
            candidates = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(candidates), 3)
            self.assertGreater(candidates[0]["final_score"], candidates[-1]["final_score"])
            self.assertGreaterEqual(len(result["target_dossier"]["literature"]), 2)
            self.assertIn("literature references", result["target_dossier"]["summary"])
            self.assertTrue(any(event["type"] == "tool_invoked" for event in result["trace_events"]))
            run_log_path = Path(result["manifest"]["artifact_paths"]["run_log"])
            self.assertTrue(run_log_path.exists())
            self.assertIn("## Planning", run_log_path.read_text(encoding="utf-8"))
            rfd3_invocation = next(item for item in result["tool_invocations"] if item["tool"] == "rfd3")
            self.assertEqual(rfd3_invocation["inputs"]["settings"]["numDesigns"], 10)

    def test_stale_dossier_cache_is_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / ".cache" / "dossiers"
            cache_dir.mkdir(parents=True, exist_ok=True)
            stale_payload = {
                "schema_version": "2026-03-08",
                "campaign_id": "old-campaign",
                "target": {"name": "HER2", "species": "human", "identifier": "P04626"},
                "summary": "stale",
                "sources": [],
                "annotations": {},
                "structures": [],
                "warnings": [],
            }
            (cache_dir / "P04626.json").write_text(json.dumps(stale_payload), encoding="utf-8")
            spec = build_campaign_spec("Design me a protein binder that inhibits HER2")
            dossier = build_target_dossier(spec, cache_dir, use_fixture=True)
            self.assertIn("literature", dossier)
            self.assertGreaterEqual(len(dossier["literature"]), 2)

    def test_literature_filter_prefers_target_relevant_hits(self) -> None:
        results = [
            {"title": "HER2-targeted nanobody binder synergizes with trastuzumab"},
            {"title": "Protein labeling efficiency improves in DNA-PAINT"},
        ]
        filtered = _filter_literature_hits(results, ["HER2", "ERBB2"])
        self.assertEqual(len(filtered), 1)
        self.assertIn("HER2", filtered[0]["title"])

    def test_tool_registry_loads_from_config(self) -> None:
        registry = load_tool_registry()
        self.assertIn("rfd3", registry)
        self.assertEqual(registry["rfd3"].remote_type, "rfdiffusion")

    def test_env_loader_ignores_env_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".env.example").write_text("TAMARIND=placeholder\n", encoding="utf-8")
            self.assertEqual(load_env(root), {})

    def test_run_tool_adapter_marks_unconfigured_tools_as_mock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invocation = run_tool_adapter(
                "campaign-x",
                "rfd3",
                "generation",
                "academic",
                {"hypothesis_id": "h1", "output_dir": str(Path(tmpdir) / "out"), "settings": {}},
                Path(tmpdir),
            )
            self.assertEqual(invocation["status"], "mock")
            self.assertIn("missing_tamarind_api_key", invocation["failure_codes"])

    def test_run_tool_adapter_blocks_restricted_tool_in_commercial_safe_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invocation = run_tool_adapter(
                "campaign-x",
                "alphafold3",
                "validation",
                "commercial_safe",
                {"hypothesis_id": "h1", "output_dir": str(Path(tmpdir) / "out"), "settings": {"sequence": "ACDE"}},
                Path(tmpdir),
            )
            self.assertEqual(invocation["status"], "skipped")
            self.assertEqual(invocation["failure_codes"], ["license_blocked"])
            self.assertEqual(invocation["outputs"]["reason"], "license_blocked")

    def test_tamarind_request_text_preserves_http_error_body(self) -> None:
        http_error = HTTPError(
            url="https://app.tamarind.bio/api/submit-job",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None,
        )
        http_error.read = lambda: b"Monthly job limit exceeded."
        with mock.patch("proteinclaw.tamarind._request", side_effect=http_error):
            with self.assertRaises(TamarindError) as exc:
                request_text(Path("."), "POST", "/submit-job", {"jobName": "debug"})
        self.assertEqual(str(exc.exception), "HTTP 400: Monthly job limit exceeded.")

    def test_run_tool_adapter_surfaces_tamarind_submission_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_summary_path = Path(tmpdir) / "out" / "mock-response.json"
            with (
                mock.patch("proteinclaw.tooling.has_tamarind_key", return_value=True),
                mock.patch("proteinclaw.tooling.submit_job", side_effect=TamarindError("HTTP 400: Monthly job limit exceeded.")),
            ):
                invocation = run_tool_adapter(
                    "campaign-x",
                    "rfd3",
                    "generation",
                    "academic",
                    {
                        "hypothesis_id": "h1",
                        "output_dir": str(Path(tmpdir) / "out"),
                        "settings": {"task": "Binder Design"},
                    },
                    Path(tmpdir),
                )
            self.assertEqual(invocation["status"], "mock")
            self.assertEqual(invocation["failure_codes"], ["tamarind_quota_exceeded_mocked"])
            self.assertEqual(invocation["outputs"]["reason"], "HTTP 400: Monthly job limit exceeded.")
            self.assertTrue(invocation["outputs"]["mocked"])
            self.assertTrue(mock_summary_path.exists())

    def test_quota_mock_writes_placeholder_ligandmpnn_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_fasta_path = Path(tmpdir) / "out" / "mock_sequences.fa"
            with (
                mock.patch("proteinclaw.tooling.has_tamarind_key", return_value=True),
                mock.patch("proteinclaw.tooling.submit_job", side_effect=TamarindError("HTTP 400: Monthly job limit exceeded.")),
            ):
                invocation = run_tool_adapter(
                    "campaign-x",
                    "ligandmpnn",
                    "sequence_design",
                    "academic",
                    {
                        "hypothesis_id": "h1",
                        "output_dir": str(Path(tmpdir) / "out"),
                        "settings": {"numSequences": 2},
                    },
                    Path(tmpdir),
                )
            self.assertEqual(invocation["status"], "mock")
            self.assertTrue(mock_fasta_path.exists())

    def test_fixture_pdb_writer_creates_local_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_fixture_pdb(Path(tmpdir) / "target.pdb", chain_id="A")
            self.assertTrue(path.exists())
            self.assertIn("ATOM", path.read_text(encoding="utf-8"))

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

    def test_cli_plan_with_clarification_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "proteinclaw",
                    "plan",
                    "--prompt",
                    "Design me a protein binder that inhibits EGFR",
                    "--epitope",
                    "known therapeutic epitope",
                    "--modality",
                    "mini-binder",
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
            self.assertTrue(all("retrieved_at" in item for item in payload["items"]))

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
            self.assertIn("score_components", payload["rows"][0])


if __name__ == "__main__":
    unittest.main()
