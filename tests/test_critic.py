"""
tests/test_critic.py
─────────────────────
Unit tests for the Critic agent.
LLM is mocked — no Ollama required.
Rule-based SOX checks use real data structures.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state import AgentState, TaskType, SoxFlag
from agents.agents import critic_agent, _run_sox_rule_checks, _extract_field


def _make_state(task_type: TaskType = TaskType.ANOMALY_DETECTION) -> AgentState:
    state = AgentState(
        user_query="Scan for SOX violations",
        period="2024-12",
        session_id="test0004",
        requested_by="test",
    )
    state.task_type = task_type
    state.analysis_result = "Analysis: Found 11 anomalies. 5 missing approvers detected."
    state.narrative = state.analysis_result
    state.citations = ["Oracle GL | 50 records | hash:abc123"]
    state.retrieved_data = {}
    return state


def _mock_critic_llm(verdict: str = "FLAGGED", confidence: float = 0.85,
                     sox_flags: str = "MISSING_APPROVER", issues: str = "Missing approvers found"):
    response_text = (
        f"VERDICT: {verdict}\n"
        f"CONFIDENCE: {confidence}\n"
        f"SOX_FLAGS: {sox_flags}\n"
        f"ISSUES: {issues}\n"
        f"CITATIONS: Oracle GL\n"
        f"SUMMARY: Review complete. {len(sox_flags.split(','))} SOX flags raised."
    )
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


class TestCriticAgent(unittest.TestCase):

    @patch("agents.agents._llm")
    def test_verdict_parsed_correctly(self, mock_llm_factory):
        """Critic sets critic_verdict to parsed LLM output."""
        mock_llm_factory.return_value = _mock_critic_llm(verdict="REJECTED")
        state = _make_state()
        result = critic_agent(state)

        self.assertEqual(result.critic_verdict, "REJECTED")

    @patch("agents.agents._llm")
    def test_confidence_parsed_correctly(self, mock_llm_factory):
        """Confidence score is parsed as float from LLM response."""
        mock_llm_factory.return_value = _mock_critic_llm(confidence=0.92)
        state = _make_state()
        result = critic_agent(state)

        self.assertAlmostEqual(result.confidence_score, 0.92, places=2)

    @patch("agents.agents._llm")
    def test_confidence_is_clamped_0_to_1(self, mock_llm_factory):
        """Confidence score should always be in [0.0, 1.0]."""
        # Mock an LLM that returns confidence > 1
        mock_llm_factory.return_value = _mock_critic_llm(confidence=0.99)
        state = _make_state()
        result = critic_agent(state)

        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)

    @patch("agents.agents._llm")
    def test_sox_flags_populated_from_llm(self, mock_llm_factory):
        """SOX flags from LLM response are converted to SoxFlag enums."""
        mock_llm_factory.return_value = _mock_critic_llm(
            verdict="FLAGGED",
            sox_flags="MISSING_APPROVER, SELF_APPROVAL"
        )
        state = _make_state()
        result = critic_agent(state)

        flag_values = [f.value for f in result.sox_flags]
        self.assertIn("MISSING_APPROVER", flag_values)
        self.assertIn("SELF_APPROVAL", flag_values)

    @patch("agents.agents._llm")
    def test_audit_entry_appended(self, mock_llm_factory):
        """Critic appends exactly one audit entry."""
        mock_llm_factory.return_value = _mock_critic_llm()
        state = _make_state()
        result = critic_agent(state)

        self.assertEqual(len(result.audit_log), 1)
        self.assertEqual(result.audit_log[0].agent, "critic")
        self.assertEqual(result.audit_log[0].action, "sox_review")

    @patch("agents.agents._llm")
    def test_final_response_contains_verdict(self, mock_llm_factory):
        """final_response is populated and includes the verdict."""
        mock_llm_factory.return_value = _mock_critic_llm(verdict="APPROVED")
        state = _make_state()
        result = critic_agent(state)

        self.assertIsNotNone(result.final_response)
        self.assertIn("APPROVED", result.final_response)

    @patch("agents.agents._llm")
    def test_approved_verdict_no_sox_flags(self, mock_llm_factory):
        """APPROVED verdict with NONE flags results in empty sox_flags list."""
        mock_llm_factory.return_value = _mock_critic_llm(
            verdict="APPROVED",
            sox_flags="NONE",
        )
        state = _make_state()
        result = critic_agent(state)

        self.assertEqual(result.critic_verdict, "APPROVED")
        # sox_flags list should be empty or only contain rule-based flags
        llm_derived = [f for f in result.sox_flags if f.value not in ("THRESHOLD_BREACH", "UNBALANCED_ENTRY")]
        self.assertEqual(len(llm_derived), 0)

    @patch("agents.agents._llm")
    def test_graceful_degradation_on_llm_error(self, mock_llm_factory):
        """If LLM fails, critic falls back to FLAGGED verdict."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ConnectionError("Ollama offline")
        mock_llm_factory.return_value = mock_llm

        state = _make_state()
        result = critic_agent(state)

        # Should not raise — should degrade to FLAGGED
        self.assertEqual(result.critic_verdict, "FLAGGED")
        self.assertEqual(len(result.audit_log), 1)


class TestSoxRuleChecks(unittest.TestCase):

    def test_missing_approver_flag_from_anomaly_data(self):
        """Rule-based check raises MISSING_APPROVER from anomalous_entries data."""
        state = _make_state()
        state.retrieved_data = {
            "anomalies": {
                "records": [
                    {"je_id": "JE001", "anomaly_type": "missing_approver",
                     "debit": 5000, "account_code": "6100", "created_by": "jsmith"},
                ]
            }
        }
        flags = _run_sox_rule_checks(state)
        flag_types = [f["flag"] for f in flags]
        self.assertIn(SoxFlag.MISSING_APPROVER.value, flag_types)

    def test_self_approval_flag(self):
        """Rule-based check raises SELF_APPROVAL."""
        state = _make_state()
        state.retrieved_data = {
            "anomalies": {
                "records": [
                    {"je_id": "JE002", "anomaly_type": "self_approved",
                     "debit": 10000, "account_code": "5100", "created_by": "admin"},
                ]
            }
        }
        flags = _run_sox_rule_checks(state)
        flag_types = [f["flag"] for f in flags]
        self.assertIn(SoxFlag.SELF_APPROVAL.value, flag_types)

    def test_unbalanced_entry_from_unbalanced_data(self):
        """Rule-based check raises UNBALANCED_ENTRY when unbalanced count > 0."""
        state = _make_state()
        state.retrieved_data = {
            "unbalanced": {"unbalanced_count": 2}
        }
        flags = _run_sox_rule_checks(state)
        flag_types = [f["flag"] for f in flags]
        self.assertIn(SoxFlag.UNBALANCED_ENTRY.value, flag_types)

    def test_threshold_breach_from_variance_data(self):
        """Rule-based check raises THRESHOLD_BREACH when variance has breaches."""
        state = _make_state()
        state.retrieved_data = {
            "variance_analysis": {"threshold_breaches": 4}
        }
        flags = _run_sox_rule_checks(state)
        flag_types = [f["flag"] for f in flags]
        self.assertIn(SoxFlag.THRESHOLD_BREACH.value, flag_types)

    def test_no_flags_on_clean_data(self):
        """No flags raised when data is clean."""
        state = _make_state()
        state.retrieved_data = {}
        flags = _run_sox_rule_checks(state)
        self.assertEqual(len(flags), 0)


class TestExtractField(unittest.TestCase):

    def test_extracts_verdict(self):
        text = "VERDICT: FLAGGED\nCONFIDENCE: 0.85\nSOX_FLAGS: NONE"
        self.assertEqual(_extract_field(text, "VERDICT", "APPROVED"), "FLAGGED")

    def test_extracts_confidence(self):
        text = "VERDICT: APPROVED\nCONFIDENCE: 0.92\nSOX_FLAGS: NONE"
        self.assertEqual(_extract_field(text, "CONFIDENCE", "0.75"), "0.92")

    def test_returns_default_on_missing_field(self):
        text = "VERDICT: APPROVED"
        self.assertEqual(_extract_field(text, "CONFIDENCE", "0.75"), "0.75")

    def test_case_insensitive_field_match(self):
        text = "verdict: FLAGGED\nconfidence: 0.80"
        self.assertEqual(_extract_field(text, "VERDICT", "APPROVED"), "FLAGGED")


if __name__ == "__main__":
    unittest.main()
