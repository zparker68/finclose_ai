"""
tests/test_planner.py
──────────────────────
Unit tests for the Planner agent.
LLM is mocked — no Ollama required.
"""
import json
import sys
import os
import unittest
from typing import List, Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state import AgentState, TaskType
from agents.agents import planner_agent


def _make_state(query: str, period: str = "2024-12") -> AgentState:
    return AgentState(
        user_query=query,
        period=period,
        session_id="test0001",
        requested_by="test",
    )


def _mock_llm_response(task_type: str, tables: Optional[List[str]] = None):
    """Build a mock ChatOllama that returns a structured JSON plan."""
    plan_json = json.dumps({
        "task_type": task_type,
        "routing_reason": f"Query is clearly about {task_type}",
        "task_plan": ["Step 1", "Step 2", "Step 3"],
        "relevant_tables": tables or ["gl_transactions"],
        "policy_category": "Financial Close",
    })
    mock_response = MagicMock()
    mock_response.content = plan_json
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


class TestPlannerAgent(unittest.TestCase):

    @patch("agents.agents._llm")
    def test_anomaly_detection_routing(self, mock_llm_factory):
        """Anomaly detection query routes to ANOMALY_DETECTION task type."""
        mock_llm_factory.return_value = _mock_llm_response(
            "anomaly_detection", ["gl_transactions"]
        )
        state = _make_state("Scan all GL entries for SOX violations")
        result = planner_agent(state)

        self.assertEqual(result.task_type, TaskType.ANOMALY_DETECTION)
        self.assertIn("gl_transactions", result.relevant_tables)

    @patch("agents.agents._llm")
    def test_variance_analysis_routing(self, mock_llm_factory):
        """Variance analysis query selects variance_analysis table."""
        mock_llm_factory.return_value = _mock_llm_response(
            "variance_analysis", ["variance_analysis", "trial_balance"]
        )
        state = _make_state("Analyze budget vs actual variances for December")
        result = planner_agent(state)

        self.assertEqual(result.task_type, TaskType.VARIANCE_ANALYSIS)
        self.assertIn("variance_analysis", result.relevant_tables)

    @patch("agents.agents._llm")
    def test_reconciliation_routing(self, mock_llm_factory):
        """Reconciliation query routes correctly."""
        mock_llm_factory.return_value = _mock_llm_response(
            "reconciliation", ["reconciliations", "trial_balance"]
        )
        state = _make_state("Review all open reconciliations for December")
        result = planner_agent(state)

        self.assertEqual(result.task_type, TaskType.RECONCILIATION)

    @patch("agents.agents._llm")
    def test_plan_has_3_to_5_steps(self, mock_llm_factory):
        """Execution plan always has between 3 and 5 steps."""
        mock_llm_factory.return_value = _mock_llm_response("anomaly_detection")
        state = _make_state("Find anomalies")
        result = planner_agent(state)

        self.assertGreaterEqual(len(result.task_plan), 3)
        self.assertLessEqual(len(result.task_plan), 5)

    @patch("agents.agents._llm")
    def test_audit_entry_appended(self, mock_llm_factory):
        """Planner always appends exactly one audit entry."""
        mock_llm_factory.return_value = _mock_llm_response("anomaly_detection")
        state = _make_state("Find anomalies")
        result = planner_agent(state)

        self.assertEqual(len(result.audit_log), 1)
        self.assertEqual(result.audit_log[0].agent, "planner")
        self.assertEqual(result.audit_log[0].action, "classify_and_plan")

    @patch("agents.agents._llm")
    def test_routing_reason_set(self, mock_llm_factory):
        """routing_reason is populated after planner runs."""
        mock_llm_factory.return_value = _mock_llm_response("variance_analysis")
        state = _make_state("Budget vs actual analysis")
        result = planner_agent(state)

        self.assertIsNotNone(result.routing_reason)
        self.assertGreater(len(result.routing_reason), 0)

    @patch("agents.agents._llm")
    def test_graceful_degradation_on_bad_llm_response(self, mock_llm_factory):
        """If LLM returns invalid JSON, planner falls back gracefully without crashing."""
        bad_response = MagicMock()
        bad_response.content = "THIS IS NOT JSON {{{broken"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = bad_response
        mock_llm_factory.return_value = mock_llm

        state = _make_state("Do something")
        result = planner_agent(state)

        # Should fall back to GENERAL_QUERY with a fallback plan
        self.assertEqual(result.task_type, TaskType.GENERAL_QUERY)
        self.assertGreater(len(result.task_plan), 0)
        self.assertEqual(len(result.audit_log), 1)

    @patch("agents.agents._llm")
    def test_processing_ms_incremented(self, mock_llm_factory):
        """processing_ms increases after planner runs."""
        mock_llm_factory.return_value = _mock_llm_response("anomaly_detection")
        state = _make_state("Scan for anomalies")
        result = planner_agent(state)

        self.assertGreater(result.processing_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
