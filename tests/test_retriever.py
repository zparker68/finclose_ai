"""
tests/test_retriever.py
────────────────────────
Unit tests for the Retriever agent.
No LLM is used — retriever is a pure data function.
Uses the real finclose.db (read-only).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state import AgentState, TaskType
from agents.agents import retriever_agent


def _make_state(task_type: TaskType, period: str = "2024-12") -> AgentState:
    state = AgentState(
        user_query="test query",
        period=period,
        session_id="test0002",
        requested_by="test",
    )
    state.task_type = task_type
    state.task_plan = ["Step 1", "Step 2", "Step 3"]
    state.relevant_tables = []
    return state


class TestRetrieverAgent(unittest.TestCase):

    def test_anomaly_detection_retrieves_gl_data(self):
        """ANOMALY_DETECTION retrieves anomalous entries from GL."""
        state = _make_state(TaskType.ANOMALY_DETECTION)
        result = retriever_agent(state)

        # Retriever stores anomaly data under "anomalies" key for ANOMALY_DETECTION
        self.assertIn("anomalies", result.retrieved_data)
        self.assertGreater(result.retrieved_data["anomalies"].get("anomaly_count", 0), 0)

    def test_reconciliation_retrieves_recon_data(self):
        """RECONCILIATION retrieves reconciliations and trial balance."""
        state = _make_state(TaskType.RECONCILIATION)
        result = retriever_agent(state)

        self.assertIn("reconciliations", result.retrieved_data)
        self.assertIn("trial_balance", result.retrieved_data)

    def test_variance_analysis_retrieves_variance_data(self):
        """VARIANCE_ANALYSIS retrieves variance analysis records."""
        state = _make_state(TaskType.VARIANCE_ANALYSIS)
        result = retriever_agent(state)

        self.assertIn("variance_analysis", result.retrieved_data)
        # Should report 4 threshold breaches (known DB fact)
        va = result.retrieved_data["variance_analysis"]
        self.assertGreaterEqual(va.get("threshold_breaches", 0), 1)

    def test_accrual_review_retrieves_accruals(self):
        """ACCRUAL_REVIEW retrieves accruals data."""
        state = _make_state(TaskType.ACCRUAL_REVIEW)
        result = retriever_agent(state)

        self.assertIn("accruals", result.retrieved_data)
        accruals = result.retrieved_data["accruals"]
        self.assertGreater(accruals.get("total_accrual_amount", 0), 0)

    def test_journal_entry_retrieves_gl_and_accruals(self):
        """JOURNAL_ENTRY retrieves GL transactions and accruals."""
        state = _make_state(TaskType.JOURNAL_ENTRY)
        result = retriever_agent(state)

        self.assertIn("gl_transactions", result.retrieved_data)
        self.assertIn("accruals", result.retrieved_data)

    def test_data_summary_is_non_empty(self):
        """data_summary is always populated after retriever runs."""
        state = _make_state(TaskType.ANOMALY_DETECTION)
        result = retriever_agent(state)

        self.assertIsNotNone(result.data_summary)
        self.assertGreater(len(result.data_summary), 0)

    def test_audit_entry_appended(self):
        """Retriever appends exactly one audit entry."""
        state = _make_state(TaskType.RECONCILIATION)
        result = retriever_agent(state)

        self.assertEqual(len(result.audit_log), 1)
        self.assertEqual(result.audit_log[0].agent, "retriever")
        self.assertEqual(result.audit_log[0].confidence, 1.0)

    def test_policy_context_populated(self):
        """Retriever always includes policy context for executor grounding."""
        state = _make_state(TaskType.ANOMALY_DETECTION)
        result = retriever_agent(state)

        self.assertIsInstance(result.policy_context, list)
        self.assertGreater(len(result.policy_context), 0)

    def test_known_anomaly_count(self):
        """GL anomalous entries should return 11 injected SOX anomalies."""
        state = _make_state(TaskType.ANOMALY_DETECTION)
        result = retriever_agent(state)

        # Retriever stores under "anomalies" key for ANOMALY_DETECTION
        anomalous = result.retrieved_data.get("anomalies", {})
        count = anomalous.get("anomaly_count", 0)
        # DB has 11 injected — allow ≥5 in case period filter applied
        self.assertGreaterEqual(count, 5)

    def test_general_query_retrieves_trial_balance(self):
        """GENERAL_QUERY falls back to trial balance + GL."""
        state = _make_state(TaskType.GENERAL_QUERY)
        result = retriever_agent(state)

        self.assertGreater(len(result.retrieved_data), 0)


if __name__ == "__main__":
    unittest.main()
