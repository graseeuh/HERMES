import pytest
from core_logic.orchestrator import ExecutionResult, ExecutionStatus
from inspector.claim_verifier import ClaimVerifier


@pytest.fixture
def verifier():
    return ClaimVerifier()


def make_result(**kwargs):
    defaults = dict(
        status=ExecutionStatus.COMPLETED,
        original_input="test",
        results={"security_gate": {"status": "completed", "output": "ok"}},
        errors={},
        execution_time=5.0,
        agents_used=["a1"],
        agents_buffed=[],
        summary="Execution Summary for: test...",
    )
    defaults.update(kwargs)
    return ExecutionResult(**defaults)


class TestSecurityGatePresent:
    def test_passes_when_gate_in_results(self, verifier):
        r = make_result(results={"security_gate": {"output": "ok"}})
        result = verifier.verify(r, "test")
        assert "SECURITY_GATE_ABSENT" not in result.flags

    def test_flags_when_gate_absent(self, verifier):
        r = make_result(results={"task_1": {"output": "done"}})
        result = verifier.verify(r, "test")
        assert "SECURITY_GATE_ABSENT" in result.flags

    def test_warns_when_gate_errored(self, verifier):
        r = make_result(
            results={"task_1": {"output": "done"}},
            errors={"security_gate": "scan failed"},
        )
        result = verifier.verify(r, "test")
        assert "SECURITY_GATE_ERRORED" in result.warnings
        assert "SECURITY_GATE_ABSENT" not in result.flags


class TestExecutionTimePlausibility:
    def test_passes_normal_time(self, verifier):
        r = make_result(execution_time=5.0)
        result = verifier.verify(r, "test")
        assert "IMPLAUSIBLE_EXECUTION_TIME" not in result.flags

    def test_flags_sub_100ms(self, verifier):
        r = make_result(execution_time=0.05)
        result = verifier.verify(r, "test")
        assert "IMPLAUSIBLE_EXECUTION_TIME" in result.flags

    def test_warns_sub_500ms(self, verifier):
        r = make_result(execution_time=0.3)
        result = verifier.verify(r, "test")
        assert "VERY_FAST_EXECUTION" in result.warnings
        assert "IMPLAUSIBLE_EXECUTION_TIME" not in result.flags

    def test_does_not_apply_to_failed_status(self, verifier):
        r = make_result(status=ExecutionStatus.FAILED, execution_time=0.05)
        result = verifier.verify(r, "test")
        assert "IMPLAUSIBLE_EXECUTION_TIME" not in result.flags


class TestStatusContentConsistency:
    def test_passes_completed_with_results(self, verifier):
        r = make_result(results={"security_gate": {"output": "ok"}, "t1": {"output": "done"}})
        result = verifier.verify(r, "test")
        assert "COMPLETED_WITH_NO_RESULTS" not in result.flags

    def test_flags_completed_with_empty_results(self, verifier):
        r = make_result(results={})
        result = verifier.verify(r, "test")
        assert "COMPLETED_WITH_NO_RESULTS" in result.flags

    def test_warns_all_none_values(self, verifier):
        r = make_result(results={"security_gate": None, "task_1": None})
        result = verifier.verify(r, "test")
        assert "COMPLETED_WITH_ALL_NONE_RESULTS" in result.warnings


class TestErrorSuppression:
    def test_passes_clean_completed(self, verifier):
        r = make_result(errors={}, summary="Execution Summary for: test...")
        result = verifier.verify(r, "test")
        assert "ERROR_SUPPRESSION_DETECTED" not in result.flags

    def test_flags_errors_with_success_summary(self, verifier):
        r = make_result(
            errors={"task_1": "failed"},
            summary="completed successfully",
        )
        result = verifier.verify(r, "test")
        assert "ERROR_SUPPRESSION_DETECTED" in result.flags

    def test_warns_errors_present_in_completed(self, verifier):
        r = make_result(
            errors={"task_1": "minor issue"},
            summary="Execution Summary for: test...",
        )
        result = verifier.verify(r, "test")
        assert "ERRORS_PRESENT_IN_COMPLETED" in result.warnings


class TestAgentCountConsistency:
    def test_passes_normal(self, verifier):
        r = make_result(
            results={"task_1": {"output": "ok"}, "security_gate": {"output": "ok"}},
            agents_used=["a1"],
        )
        result = verifier.verify(r, "test")
        assert "NO_AGENTS_CLAIMED_BUT_RESULTS_EXIST" not in result.flags

    def test_flags_no_agents_but_results(self, verifier):
        r = make_result(
            results={"task_1": {"output": "ok"}, "security_gate": {"output": "ok"}},
            agents_used=[],
        )
        result = verifier.verify(r, "test")
        assert "NO_AGENTS_CLAIMED_BUT_RESULTS_EXIST" in result.flags

    def test_passes_only_security_gate_with_no_agents(self, verifier):
        """Security gate result alone with no agents is acceptable."""
        r = make_result(
            results={"security_gate": {"output": "ok"}},
            agents_used=[],
        )
        result = verifier.verify(r, "test")
        assert "NO_AGENTS_CLAIMED_BUT_RESULTS_EXIST" not in result.flags


class TestChecksRunTracking:
    def test_all_checks_run_on_clean_result(self, verifier, clean_result):
        result = verifier.verify(clean_result, "test")
        assert len(result.checks_run) == 7

    def test_checks_run_list_contains_expected_names(self, verifier, clean_result):
        result = verifier.verify(clean_result, "test")
        expected = {
            "security_gate_present", "execution_time_plausibility",
            "status_content_consistency", "error_suppression",
            "agent_count_consistency", "file_path_claims", "result_dict_structure",
        }
        assert set(result.checks_run) == expected
