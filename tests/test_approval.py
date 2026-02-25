import pytest
import time
from approval.approval_gate import ApprovalGate, APPROVAL_TIMEOUT_SECONDS


@pytest.fixture
def gate(hermes_base):
    return ApprovalGate(base_path=str(hermes_base))


class TestRequiresApproval:
    def test_safe_task_returns_empty(self, gate):
        assert gate.requires_approval("analyze the codebase for unused imports") == []

    def test_delete_flagged(self, gate):
        matched = gate.requires_approval("delete all log files older than 30 days")
        assert len(matched) > 0
        assert any("deletion" in m.lower() for m in matched)

    def test_git_push_flagged(self, gate):
        matched = gate.requires_approval("git push origin main")
        assert any("git remote" in m.lower() for m in matched)

    def test_deploy_flagged(self, gate):
        matched = gate.requires_approval("deploy the latest build to production")
        assert len(matched) > 0

    def test_pip_install_flagged(self, gate):
        matched = gate.requires_approval("pip install numpy in the venv")
        assert any("package installation" in m.lower() for m in matched)

    def test_rm_flagged(self, gate):
        matched = gate.requires_approval("rm -rf the temp directory")
        assert len(matched) > 0

    def test_case_insensitive(self, gate):
        assert gate.requires_approval("DELETE all files") != []
        assert gate.requires_approval("Git Push origin main") != []

    def test_multiple_patterns_returned(self, gate):
        matched = gate.requires_approval("delete files and git push the changes")
        assert len(matched) >= 2


class TestRequestLifecycle:
    def test_create_returns_pending(self, gate):
        patterns = ["File/data deletion"]
        req = gate.create_request("delete logs", patterns)
        assert req.status == "pending"
        assert req.request_id.startswith("req_")
        assert req.task == "delete logs"
        assert req.matched_patterns == patterns

    def test_get_request_returns_created(self, gate):
        req = gate.create_request("delete logs", ["deletion"])
        fetched = gate.get_request(req.request_id)
        assert fetched is not None
        assert fetched.request_id == req.request_id
        assert fetched.status == "pending"

    def test_get_nonexistent_returns_none(self, gate):
        assert gate.get_request("req_doesnotexist") is None

    def test_approve(self, gate):
        req = gate.create_request("delete logs", ["deletion"])
        resolved = gate.resolve(req.request_id, approved=True, reason="confirmed")
        assert resolved.status == "approved"
        assert resolved.reason == "confirmed"
        assert resolved.resolved_at is not None

    def test_deny(self, gate):
        req = gate.create_request("delete logs", ["deletion"])
        resolved = gate.resolve(req.request_id, approved=False, reason="not now")
        assert resolved.status == "denied"

    def test_double_resolve_raises(self, gate):
        req = gate.create_request("delete logs", ["deletion"])
        gate.resolve(req.request_id, approved=True, reason="ok")
        with pytest.raises(ValueError):
            gate.resolve(req.request_id, approved=False, reason="should fail")

    def test_resolve_unknown_raises(self, gate):
        with pytest.raises(KeyError):
            gate.resolve("req_doesnotexist", approved=True, reason="")

    def test_list_pending_only_shows_pending(self, gate):
        r1 = gate.create_request("delete logs", ["deletion"])
        r2 = gate.create_request("git push", ["git"])
        gate.resolve(r1.request_id, approved=True, reason="ok")
        pending = gate.list_pending()
        ids = [p.request_id for p in pending]
        assert r1.request_id not in ids
        assert r2.request_id in ids

    def test_state_persists_across_instances(self, hermes_base):
        g1 = ApprovalGate(base_path=str(hermes_base))
        req = g1.create_request("delete logs", ["deletion"])

        g2 = ApprovalGate(base_path=str(hermes_base))
        fetched = g2.get_request(req.request_id)
        assert fetched is not None
        assert fetched.status == "pending"


class TestExpiry:
    def test_cleanup_expired_marks_timed_out(self, hermes_base):
        gate = ApprovalGate(base_path=str(hermes_base))
        req = gate.create_request("delete logs", ["deletion"])

        # Manually backdating expires_at in the state file
        from pathlib import Path
        import json
        state_file = hermes_base / "approval" / "state" / "pending_approvals.json"
        state = json.loads(state_file.read_text())
        state[req.request_id]["expires_at"] = "2000-01-01T00:00:00+00:00"
        state_file.write_text(json.dumps(state))

        count = gate.cleanup_expired()
        assert count == 1
        fetched = gate.get_request(req.request_id)
        assert fetched.status == "expired"

    def test_cleanup_does_not_affect_resolved(self, hermes_base):
        gate = ApprovalGate(base_path=str(hermes_base))
        req = gate.create_request("delete logs", ["deletion"])
        gate.resolve(req.request_id, approved=True, reason="ok")
        count = gate.cleanup_expired()
        assert count == 0
