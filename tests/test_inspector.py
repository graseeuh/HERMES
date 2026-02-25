import pytest
import json
from core_logic.orchestrator import ExecutionResult, ExecutionStatus
from inspector.inspector_general import InspectorGeneral, InspectorVerdict
from inspector.behavioral_monitor import BehavioralMonitor


class TestInspectorGeneral:
    def test_clean_result_passes(self, hermes_base, clean_result):
        ig = InspectorGeneral(base_path=str(hermes_base))
        verdict = ig.inspect(clean_result, raw_input="analyze the codebase")
        assert isinstance(verdict, InspectorVerdict)
        assert verdict.passed is True
        assert verdict.degraded is False
        assert verdict.confidence == 1.0

    def test_missing_gate_fails(self, hermes_base):
        ig = InspectorGeneral(base_path=str(hermes_base))
        result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            original_input="test",
            results={"task_1": {"output": "done"}},
            errors={},
            execution_time=5.0,
            agents_used=["a1"],
            agents_buffed=[],
            summary="Execution Summary for: test...",
        )
        verdict = ig.inspect(result, raw_input="test")
        assert verdict.passed is False
        assert "SECURITY_GATE_ABSENT" in verdict.flags

    def test_never_raises(self, hermes_base):
        """inspect() must never raise regardless of what it receives."""
        ig = InspectorGeneral(base_path=str(hermes_base))
        # Pass completely wrong types — should return degraded verdict, not raise
        verdict = ig.inspect(None, raw_input="test")  # type: ignore
        assert isinstance(verdict, InspectorVerdict)
        assert verdict.degraded is True

    def test_degraded_verdict_has_zero_confidence(self, hermes_base):
        ig = InspectorGeneral(base_path=str(hermes_base))
        verdict = ig.inspect(None, raw_input="test")  # type: ignore
        assert verdict.confidence == 0.0
        assert verdict.passed is False

    def test_verdict_contains_behavioral_summary(self, hermes_base, clean_result):
        ig = InspectorGeneral(base_path=str(hermes_base))
        verdict = ig.inspect(clean_result, raw_input="analyze codebase")
        assert "total_invocations" in verdict.behavioral_summary
        assert "success_rate" in verdict.behavioral_summary

    def test_log_file_created(self, hermes_base, clean_result):
        ig = InspectorGeneral(base_path=str(hermes_base))
        ig.inspect(clean_result, raw_input="analyze codebase")
        log_files = list((hermes_base / "inspector" / "logs").glob("*.jsonl"))
        assert len(log_files) == 1

    def test_session_id_unique_per_call(self, hermes_base, clean_result):
        ig = InspectorGeneral(base_path=str(hermes_base))
        v1 = ig.inspect(clean_result, raw_input="task one")
        v2 = ig.inspect(clean_result, raw_input="task two")
        assert v1.session_id != v2.session_id

    def test_task_hash_deterministic(self, hermes_base, clean_result):
        ig = InspectorGeneral(base_path=str(hermes_base))
        v1 = ig.inspect(clean_result, raw_input="same input")
        v2 = ig.inspect(clean_result, raw_input="same input")
        assert v1.task_hash == v2.task_hash


class TestBehavioralMonitor:
    def test_initial_state_is_zero(self, hermes_base):
        state_path = hermes_base / "inspector" / "state" / "behavioral_state.json"
        monitor = BehavioralMonitor(state_path=state_path)
        report = monitor.get_report()
        assert report.total_invocations == 0

    def test_record_increments_invocations(self, hermes_base, clean_result):
        state_path = hermes_base / "inspector" / "state" / "behavioral_state.json"
        monitor = BehavioralMonitor(state_path=state_path)
        monitor.record(clean_result, flags=[], raw_input="test")
        report = monitor.get_report()
        assert report.total_invocations == 1

    def test_state_persists_across_instances(self, hermes_base, clean_result):
        state_path = hermes_base / "inspector" / "state" / "behavioral_state.json"
        m1 = BehavioralMonitor(state_path=state_path)
        m1.record(clean_result, flags=[], raw_input="test")
        m1.record(clean_result, flags=[], raw_input="test")

        m2 = BehavioralMonitor(state_path=state_path)
        report = m2.get_report()
        assert report.total_invocations == 2

    def test_baseline_set_after_min_samples(self, hermes_base, clean_result):
        state_path = hermes_base / "inspector" / "state" / "behavioral_state.json"
        monitor = BehavioralMonitor(state_path=state_path)
        for _ in range(10):
            monitor.record(clean_result, flags=[], raw_input="test")
        report = monitor.get_report()
        assert report.baseline_success_rate is not None

    def test_flag_rate_tracked(self, hermes_base, clean_result):
        state_path = hermes_base / "inspector" / "state" / "behavioral_state.json"
        monitor = BehavioralMonitor(state_path=state_path)
        monitor.record(clean_result, flags=["SECURITY_GATE_ABSENT"], raw_input="test")
        report = monitor.get_report()
        assert report.flag_rate == 1.0
