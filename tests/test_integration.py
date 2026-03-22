"""
tests/test_integration.py
──────────────────────────
Full end-to-end integration test for the FinClose AI pipeline.

Requires Ollama to be running with the mistral model pulled:
  ollama serve
  ollama pull mistral

Skip gracefully when Ollama is not available.
"""
import sys
import os
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _ollama_available() -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


OLLAMA_SKIP_REASON = "Ollama not running — skipping integration tests (run `ollama serve` to enable)"
requires_ollama = unittest.skipUnless(_ollama_available(), OLLAMA_SKIP_REASON)


class TestFullPipelineIntegration(unittest.TestCase):

    @requires_ollama
    def test_anomaly_scan_pipeline(self):
        """Full pipeline run on anomaly detection query produces valid output."""
        from pipeline import run_pipeline
        from core.state import SoxFlag

        result = run_pipeline(
            query="Scan all December 2024 journal entries for SOX control violations",
            period="2024-12",
            requested_by="integration_test",
        )

        # Audit trail must have exactly 4 entries (one per agent)
        self.assertEqual(len(result.audit_log), 4,
                         f"Expected 4 audit entries, got {len(result.audit_log)}")

        # Agents must be in the correct order
        agent_names = [e.agent for e in result.audit_log]
        self.assertEqual(agent_names, ["planner", "retriever", "executor", "critic"])

        # SOX flags should be present — 11 anomalies injected in DB
        self.assertGreater(len(result.sox_flags), 0,
                           "Expected at least 1 SOX flag for anomaly detection query")

        # All flags must be valid SoxFlag enum values
        for flag in result.sox_flags:
            self.assertIsInstance(flag, SoxFlag)

        # Verdict must be one of the 3 valid values
        self.assertIn(result.critic_verdict, ["APPROVED", "FLAGGED", "REJECTED"])

        # Confidence must be in valid range
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)

        # Processing time must be > 0
        self.assertGreater(result.processing_ms, 0.0)

        # Final response must be non-empty
        self.assertIsNotNone(result.final_response)
        self.assertGreater(len(result.final_response), 100)

        # Session ID must be present
        self.assertIsNotNone(result.session_id)
        self.assertGreater(len(result.session_id), 0)

    @requires_ollama
    def test_variance_analysis_pipeline(self):
        """Variance analysis query routes correctly and returns threshold breach info."""
        from pipeline import run_pipeline
        from core.state import TaskType, SoxFlag

        result = run_pipeline(
            query="Analyze December 2024 budget vs actual variances",
            period="2024-12",
            requested_by="integration_test",
        )

        self.assertEqual(len(result.audit_log), 4)
        self.assertEqual(result.task_type, TaskType.VARIANCE_ANALYSIS)
        self.assertIn(result.critic_verdict, ["APPROVED", "FLAGGED", "REJECTED"])

        # Variance analysis with 4 threshold breaches should flag THRESHOLD_BREACH
        flag_values = [f.value for f in result.sox_flags]
        self.assertIn("THRESHOLD_BREACH", flag_values,
                      "Expected THRESHOLD_BREACH flag for variance analysis with 4 breaches")

    @requires_ollama
    def test_metrics_recorded_after_run(self):
        """Pipeline run is recorded in monitoring metrics."""
        from pipeline import run_pipeline
        from monitoring.metrics import load_records

        records_before = len(load_records())

        run_pipeline(
            query="Quick reconciliation check",
            period="2024-12",
            requested_by="integration_test",
        )

        records_after = len(load_records())
        self.assertGreater(records_after, records_before,
                           "Expected a new metrics record after pipeline run")

    @requires_ollama
    def test_audit_log_entries_have_required_fields(self):
        """All audit entries have timestamps, hashes, and non-empty reasoning."""
        from pipeline import run_pipeline

        result = run_pipeline(
            query="Review accrual schedule",
            period="2024-12",
            requested_by="integration_test",
        )

        for entry in result.audit_log:
            self.assertIsNotNone(entry.timestamp, f"Missing timestamp in {entry.agent} entry")
            self.assertIsNotNone(entry.input_hash, f"Missing hash in {entry.agent} entry")
            self.assertGreater(len(entry.reasoning), 0, f"Empty reasoning in {entry.agent} entry")
            self.assertGreaterEqual(entry.confidence, 0.0)
            self.assertLessEqual(entry.confidence, 1.0)


class TestPipelineWithoutOllama(unittest.TestCase):
    """These tests verify pipeline structure without needing Ollama."""

    def test_pipeline_imports_without_error(self):
        """Pipeline module imports cleanly."""
        try:
            from pipeline import run_pipeline, export_audit_log
        except ImportError as e:
            self.fail(f"Pipeline import failed: {e}")

    def test_state_schema_is_complete(self):
        """AgentState has all required fields."""
        from core.state import AgentState, TaskType, SoxFlag, AuditEntry
        import dataclasses

        state = AgentState(user_query="test", period="2024-12", session_id="abc")
        fields = {f.name for f in dataclasses.fields(state)}

        required = {
            "user_query", "period", "session_id", "requested_by",
            "task_type", "task_plan", "relevant_tables",
            "retrieved_data", "policy_context", "data_summary",
            "analysis_result", "journal_entries",
            "sox_flags", "sox_flag_details", "critic_verdict", "confidence_score",
            "audit_log", "errors", "final_response", "processing_ms",
        }
        missing = required - fields
        self.assertEqual(len(missing), 0, f"Missing AgentState fields: {missing}")

    def test_sox_flag_enum_values(self):
        """All expected SoxFlag enum values exist."""
        from core.state import SoxFlag
        expected = {
            "SELF_APPROVAL", "MISSING_APPROVER", "UNBALANCED_ENTRY",
            "WEEKEND_POSTING", "PRIOR_PERIOD_POSTING", "ROUND_NUMBER_MANUAL",
            "THRESHOLD_BREACH", "UNUSUAL_ACCOUNT_COMBO",
        }
        actual = {f.value for f in SoxFlag}
        self.assertEqual(expected, actual)

    def test_db_tools_accessible(self):
        """DB tools can connect and return data from finclose.db."""
        from core.db_tools import get_chart_of_accounts
        result = get_chart_of_accounts()
        self.assertIn("records", result)
        self.assertGreater(len(result["records"]), 0)

    def test_monitoring_module_imports(self):
        """Monitoring module imports and basic functions work."""
        from monitoring.metrics import load_records, get_summary
        records = load_records()
        self.assertIsInstance(records, list)

    def test_api_module_imports(self):
        """FastAPI server module imports without error."""
        try:
            import api.server  # noqa: F401
        except ImportError as e:
            self.fail(f"API server import failed: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
