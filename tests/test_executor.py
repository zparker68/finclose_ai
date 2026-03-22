"""
tests/test_executor.py
───────────────────────
Unit tests for the Executor agent.
LLM is mocked — no Ollama required.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state import AgentState, TaskType
from agents.agents import executor_agent


def _make_state(task_type: TaskType = TaskType.ANOMALY_DETECTION) -> AgentState:
    state = AgentState(
        user_query="Scan for SOX violations",
        period="2024-12",
        session_id="test0003",
        requested_by="test",
    )
    state.task_type = task_type
    state.task_plan = ["Step 1: Retrieve GL data", "Step 2: Analyze", "Step 3: Report"]
    state.data_summary = "Oracle GL: 50 records retrieved. 11 anomalies flagged."
    state.policy_context = ["Policy 1: All JEs require dual approval."]
    state.retrieved_data = {
        "gl_transactions": {"record_count": 50, "records": []},
        "anomalous_entries": {"record_count": 11, "records": []},
    }
    return state


def _mock_llm(content: str):
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


class TestExecutorAgent(unittest.TestCase):

    @patch("agents.agents._llm")
    def test_analysis_result_populated(self, mock_llm_factory):
        """Executor sets analysis_result from LLM response."""
        mock_llm_factory.return_value = _mock_llm(
            "Analysis complete. Found 11 anomalies in December GL transactions."
        )
        state = _make_state()
        result = executor_agent(state)

        self.assertIsNotNone(result.analysis_result)
        self.assertGreater(len(result.analysis_result), 0)

    @patch("agents.agents._llm")
    def test_audit_entry_appended(self, mock_llm_factory):
        """Executor appends exactly one audit entry with correct agent name."""
        mock_llm_factory.return_value = _mock_llm("Some analysis result.")
        state = _make_state()
        result = executor_agent(state)

        self.assertEqual(len(result.audit_log), 1)
        self.assertEqual(result.audit_log[0].agent, "executor")

    @patch("agents.agents._llm")
    def test_journal_entry_extraction_dr_cr(self, mock_llm_factory):
        """Journal entry lines with DR/CR pattern are extracted."""
        je_text = """
        Here is the journal entry:
        Debit  Salaries Expense (6100)      285,000
        Credit Salaries Payable (2200)      285,000
        This accrues December payroll.
        """
        mock_llm_factory.return_value = _mock_llm(je_text)
        state = _make_state(TaskType.JOURNAL_ENTRY)
        state.user_query = "Generate salary accrual JE for $285,000"
        result = executor_agent(state)

        self.assertIsInstance(result.journal_entries, list)
        # Should have extracted at least 1 JE line
        self.assertGreater(len(result.journal_entries), 0)

    @patch("agents.agents._llm")
    def test_narrative_set(self, mock_llm_factory):
        """narrative field is set from executor output."""
        mock_llm_factory.return_value = _mock_llm(
            "Variance analysis shows Professional Services exceeded budget by 19%."
        )
        state = _make_state(TaskType.VARIANCE_ANALYSIS)
        result = executor_agent(state)

        self.assertIsNotNone(result.narrative)
        self.assertGreater(len(result.narrative), 0)

    @patch("agents.agents._llm")
    def test_processing_ms_incremented(self, mock_llm_factory):
        """processing_ms increases after executor runs."""
        mock_llm_factory.return_value = _mock_llm("Analysis done.")
        state = _make_state()
        result = executor_agent(state)

        self.assertGreater(result.processing_ms, 0.0)

    @patch("agents.agents._llm")
    def test_graceful_degradation_on_llm_error(self, mock_llm_factory):
        """If LLM call fails, executor handles the exception without crashing."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ConnectionError("Ollama not running")
        mock_llm_factory.return_value = mock_llm

        state = _make_state()
        # Should not raise — should degrade gracefully
        try:
            result = executor_agent(state)
            # audit log should still be appended
            self.assertEqual(len(result.audit_log), 1)
        except Exception as e:
            self.fail(f"executor_agent raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
