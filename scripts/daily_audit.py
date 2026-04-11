"""HERMES Daily Audit — analyzes Inspector General data and suggests improvements.

Standalone script, stdlib only, no HERMES imports.
Run: venv/Scripts/python.exe scripts/daily_audit.py
"""

import json
import os
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Data Readers
# ---------------------------------------------------------------------------

class InspectorLogReader:
    """Reads inspector JSONL logs from inspector/logs/."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir

    def read_entries(self, days: int = 7, limit: int = 2000) -> list:
        entries = []
        today = datetime.now(timezone.utc).date()
        for offset in range(days - 1, -1, -1):
            day = today - timedelta(days=offset)
            path = self.log_dir / f"inspector_{day.strftime('%Y%m%d')}.jsonl"
            if not path.exists():
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue
        if len(entries) > limit:
            entries = entries[-limit:]
        return entries


class BehavioralStateReader:
    """Reads behavioral_state.json."""

    def __init__(self, state_path: Path):
        self.state_path = state_path

    def read(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}


class ApprovalStateReader:
    """Reads pending_approvals.json."""

    def __init__(self, state_path: Path):
        self.state_path = state_path

    def read(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class AuditAnalyzer:
    """Analyzes inspector data and produces findings."""

    def __init__(self, entries: list, behavioral: dict, approvals: dict):
        self.entries = entries
        self.behavioral = behavioral
        self.approvals = approvals

        self.total = len(entries)
        self.completed_count = sum(
            1 for e in entries if e.get("orchestrator_status") == "completed"
        )
        self.failed_count = sum(
            1 for e in entries if e.get("orchestrator_status") == "failed"
        )
        self.flagged_count = sum(
            1 for e in entries if not e.get("inspector_passed", True)
        )
        self.gate_skip_count = sum(
            1 for e in entries
            if "SECURITY_GATE_ABSENT" in e.get("flags", [])
        )

    def _rate(self, numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator > 0 else 0.0

    def compute_health_score(self) -> dict:
        if self.total == 0:
            return {
                "score": 0, "grade": "CRITICAL",
                "components": {
                    "success_rate_points": 0.0, "flag_rate_points": 0.0,
                    "gate_compliance_points": 0.0, "confidence_points": 0.0,
                },
            }

        success_pts = 40 * self._rate(self.completed_count, self.total)
        flag_pts = 25 * (1 - self._rate(self.flagged_count, self.total))
        gate_pts = 20 * (1 - self._rate(self.gate_skip_count, self.total))

        confidences = [e.get("confidence", 0.0) for e in self.entries]
        conf_pts = 15 * (sum(confidences) / len(confidences))

        score = round(success_pts + flag_pts + gate_pts + conf_pts)
        score = max(0, min(100, score))

        if score >= 90:
            grade = "EXCELLENT"
        elif score >= 70:
            grade = "GOOD"
        elif score >= 50:
            grade = "FAIR"
        elif score >= 30:
            grade = "POOR"
        else:
            grade = "CRITICAL"

        return {
            "score": score,
            "grade": grade,
            "components": {
                "success_rate_points": round(success_pts, 1),
                "flag_rate_points": round(flag_pts, 1),
                "gate_compliance_points": round(gate_pts, 1),
                "confidence_points": round(conf_pts, 1),
            },
        }

    def analyze_recurring_flags(self) -> list:
        all_flags = [f for e in self.entries for f in e.get("flags", [])]
        if not all_flags:
            return []

        counts = Counter(all_flags)
        mid = self.total // 2
        first_half = self.entries[:mid] if mid > 0 else []
        second_half = self.entries[mid:] if mid > 0 else self.entries

        results = []
        for flag, count in counts.most_common():
            first_count = sum(
                1 for e in first_half if flag in e.get("flags", [])
            )
            second_count = sum(
                1 for e in second_half if flag in e.get("flags", [])
            )

            if first_count == 0 and second_count > 0:
                trend = "new"
            elif second_count > first_count:
                trend = "increasing"
            elif second_count < first_count:
                trend = "decreasing"
            else:
                trend = "stable"

            results.append({
                "flag": flag, "count": count, "trend": trend,
                "first_half": first_count, "second_half": second_count,
            })
        return results

    def analyze_execution_times(self) -> dict:
        times = [
            e.get("execution_time_reported")
            for e in self.entries
            if e.get("execution_time_reported") is not None
        ]
        if not times:
            return {
                "count": 0, "mean": 0.0, "median": 0.0, "stdev": 0.0,
                "outliers": [], "suspicious_fast": [],
            }

        mean = statistics.mean(times)
        median = statistics.median(times)
        stdev = statistics.stdev(times) if len(times) >= 2 else 0.0

        outliers = [t for t in times if abs(t - mean) > 2 * stdev] if stdev > 0 else []

        suspicious = [
            {"time": e.get("execution_time_reported"), "session_id": e.get("session_id")}
            for e in self.entries
            if e.get("execution_time_reported") is not None
            and e["execution_time_reported"] < 0.5
            and e.get("orchestrator_status") in ("completed", "partial")
        ]

        return {
            "count": len(times),
            "mean": round(mean, 3),
            "median": round(median, 3),
            "stdev": round(stdev, 3),
            "outliers": outliers,
            "suspicious_fast": suspicious,
        }

    def analyze_security_gate_compliance(self) -> dict:
        skip_rate = self._rate(self.gate_skip_count, self.total)

        mid = self.total // 2
        if mid > 0:
            first_skips = sum(
                1 for e in self.entries[:mid]
                if "SECURITY_GATE_ABSENT" in e.get("flags", [])
            )
            second_skips = sum(
                1 for e in self.entries[mid:]
                if "SECURITY_GATE_ABSENT" in e.get("flags", [])
            )
            first_rate = self._rate(first_skips, mid)
            second_rate = self._rate(second_skips, self.total - mid)

            if second_rate > first_rate:
                trend = "worsening"
            elif second_rate < first_rate:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "skip_count": self.gate_skip_count,
            "skip_rate": round(skip_rate, 4),
            "threshold": 0.10,
            "compliant": skip_rate <= 0.10,
            "trend": trend,
        }

    def analyze_approval_gate(self) -> dict:
        if not self.approvals:
            return {
                "total": 0, "approved": 0, "denied": 0, "expired": 0,
                "pending": 0, "common_patterns": [], "avg_resolution_seconds": None,
            }

        status_counts = Counter(
            v.get("status", "unknown") for v in self.approvals.values()
        )
        pattern_counter = Counter()
        resolution_times = []

        for v in self.approvals.values():
            for p in v.get("matched_patterns", []):
                pattern_counter[p] += 1

            if v.get("status") in ("approved", "denied") and v.get("resolved_at") and v.get("created_at"):
                try:
                    created = datetime.fromisoformat(v["created_at"])
                    resolved = datetime.fromisoformat(v["resolved_at"])
                    resolution_times.append((resolved - created).total_seconds())
                except (ValueError, TypeError):
                    pass

        avg_resolution = (
            round(statistics.mean(resolution_times), 1)
            if resolution_times else None
        )

        return {
            "total": len(self.approvals),
            "approved": status_counts.get("approved", 0),
            "denied": status_counts.get("denied", 0),
            "expired": status_counts.get("expired", 0),
            "pending": status_counts.get("pending", 0),
            "common_patterns": [
                {"pattern": p, "count": c}
                for p, c in pattern_counter.most_common(10)
            ],
            "avg_resolution_seconds": avg_resolution,
        }

    def rank_weak_points(self) -> list:
        weak_points = []
        flag_rate = self._rate(self.flagged_count, self.total)
        skip_rate = self._rate(self.gate_skip_count, self.total)
        success_rate = self._rate(self.completed_count, self.total)
        baseline = self.behavioral.get("baseline_success_rate")

        if self.total > 0 and flag_rate > 0.30:
            weak_points.append({
                "id": "high_flag_rate",
                "description": f"Flag rate is {flag_rate:.0%} (threshold: 30%)",
                "severity": min(1.0, flag_rate / 0.50),
                "category": "reliability",
            })

        if self.total > 0 and skip_rate > 0.10:
            weak_points.append({
                "id": "security_gate_noncompliant",
                "description": f"Security gate skip rate is {skip_rate:.0%} (threshold: 10%)",
                "severity": min(1.0, skip_rate / 0.25),
                "category": "security",
            })

        if baseline is not None and (baseline - success_rate) > 0.20:
            drop = baseline - success_rate
            weak_points.append({
                "id": "success_rate_drop",
                "description": f"Success rate dropped {drop:.0%} from baseline ({baseline:.0%} -> {success_rate:.0%})",
                "severity": min(1.0, drop / 0.40),
                "category": "reliability",
            })

        exec_analysis = self.analyze_execution_times()
        if exec_analysis["suspicious_fast"]:
            count = len(exec_analysis["suspicious_fast"])
            weak_points.append({
                "id": "execution_time_anomalies",
                "description": f"{count} task(s) completed suspiciously fast (<0.5s)",
                "severity": 0.5,
                "category": "integrity",
            })

        error_suppression_count = sum(
            1 for e in self.entries
            if "ERROR_SUPPRESSION_DETECTED" in e.get("flags", [])
        )
        if error_suppression_count > 0:
            weak_points.append({
                "id": "error_suppression",
                "description": f"Error suppression detected in {error_suppression_count} task(s)",
                "severity": min(1.0, error_suppression_count / 3.0),
                "category": "integrity",
            })

        approval = self.analyze_approval_gate()
        if approval["total"] > 0:
            expiry_rate = self._rate(approval["expired"], approval["total"])
            if expiry_rate > 0.20:
                weak_points.append({
                    "id": "high_approval_expiry",
                    "description": f"{approval['expired']} approval(s) expired without resolution",
                    "severity": 0.4,
                    "category": "operations",
                })

        if self.total < 10:
            weak_points.append({
                "id": "low_sample_size",
                "description": f"Only {self.total} entries analyzed — results may not be representative",
                "severity": 0.2,
                "category": "data_quality",
            })

        flag_counts = Counter(f for e in self.entries for f in e.get("flags", []))
        for flag, count in flag_counts.items():
            if count > 5:
                weak_points.append({
                    "id": f"recurring_flag_{flag.lower()}",
                    "description": f"Flag '{flag}' appeared {count} times",
                    "severity": min(1.0, count / 10.0),
                    "category": "reliability",
                })

        weak_points.sort(key=lambda w: w["severity"], reverse=True)
        return weak_points

    def generate_suggestions(self) -> list:
        suggestion_map = {
            "high_flag_rate": {
                "suggestion": "High flag rate indicates recurring execution issues",
                "action": "Review the most common flags in this report and address root causes one by one",
                "priority": "high",
            },
            "security_gate_noncompliant": {
                "suggestion": "Security gate is being skipped too often",
                "action": "Check orchestrator._run_security_gate() — ensure it runs on every execution path and adds 'security_gate' key to results",
                "priority": "critical",
            },
            "success_rate_drop": {
                "suggestion": "Success rate has dropped significantly from baseline",
                "action": "Review recent failed tasks in inspector logs to identify common failure patterns",
                "priority": "high",
            },
            "execution_time_anomalies": {
                "suggestion": "Some tasks are completing too fast, which may indicate they didn't actually execute",
                "action": "Cross-reference fast tasks with their results — verify they produced real output",
                "priority": "medium",
            },
            "error_suppression": {
                "suggestion": "Execution summaries are claiming success despite errors being present",
                "action": "Fix summary generation in orchestrator to acknowledge errors instead of masking them",
                "priority": "high",
            },
            "high_approval_expiry": {
                "suggestion": "Approval requests are timing out before being resolved",
                "action": "Consider increasing the 5-minute timeout or improving approval notification visibility",
                "priority": "medium",
            },
            "low_sample_size": {
                "suggestion": "Not enough execution data for reliable analysis",
                "action": "Run more tasks through the HERMES pipeline to build a meaningful baseline",
                "priority": "low",
            },
        }

        weak_points = self.rank_weak_points()
        suggestions = []
        seen_ids = set()
        for wp in weak_points:
            wp_id = wp["id"]
            # Handle recurring_flag_* IDs
            base_id = wp_id if wp_id in suggestion_map else None
            if base_id is None and wp_id.startswith("recurring_flag_"):
                flag_name = wp["description"].split("'")[1] if "'" in wp["description"] else wp_id
                suggestions.append({
                    "for_weak_point": wp_id,
                    "suggestion": f"Recurring flag '{flag_name}' needs investigation",
                    "action": f"Review what triggers '{flag_name}' and fix the underlying cause in the orchestrator or agents",
                    "priority": "medium",
                })
                continue

            if base_id and base_id not in seen_ids:
                seen_ids.add(base_id)
                entry = suggestion_map[base_id].copy()
                entry["for_weak_point"] = wp_id
                suggestions.append(entry)

        return suggestions


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class AuditReporter:
    """Builds and saves the audit report."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def build_report(self, analyzer: AuditAnalyzer, days: int = 7) -> dict:
        return {
            "report_version": "1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "entries_analyzed": analyzer.total,
            "health": analyzer.compute_health_score(),
            "recurring_flags": analyzer.analyze_recurring_flags(),
            "execution_times": analyzer.analyze_execution_times(),
            "security_gate_compliance": analyzer.analyze_security_gate_compliance(),
            "approval_gate": analyzer.analyze_approval_gate(),
            "weak_points": analyzer.rank_weak_points(),
            "suggestions": analyzer.generate_suggestions(),
            "data_sources": {
                "behavioral_state": {
                    "total_invocations": analyzer.behavioral.get("total_invocations", 0),
                    "baseline_success_rate": analyzer.behavioral.get("baseline_success_rate"),
                    "last_updated": analyzer.behavioral.get("last_updated", "unknown"),
                },
            },
        }

    def save_report(self, report: dict) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().strftime("%Y%m%d")
        target = self.output_dir / f"audit_report_{today}.json"
        tmp = self.output_dir / f"audit_report_{today}.json.tmp"

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        os.replace(tmp, target)
        return target

    def print_summary(self, report: dict) -> None:
        health = report["health"]
        score = health["score"]
        grade = health["grade"]
        c = health["components"]

        print("=" * 64)
        print(f"  HERMES Daily Audit Report -- {date.today().isoformat()}")
        print("=" * 64)
        print()
        print(f"  Health Score: {score}/100 ({grade})")
        print(f"  |-- Success Rate:      {c['success_rate_points']}/40 pts")
        print(f"  |-- Flag Rate:         {c['flag_rate_points']}/25 pts")
        print(f"  |-- Gate Compliance:   {c['gate_compliance_points']}/20 pts")
        print(f"  +-- Check Confidence:  {c['confidence_points']}/15 pts")
        print()
        print(f"  Period: {report['period_days']} days | Entries analyzed: {report['entries_analyzed']}")

        weak_points = report.get("weak_points", [])
        if weak_points:
            print()
            print("  -- Weak Points (ranked by severity) ----------")
            for i, wp in enumerate(weak_points[:5], 1):
                sev = wp["severity"]
                level = "CRITICAL" if sev >= 0.8 else "HIGH" if sev >= 0.5 else "MEDIUM" if sev >= 0.3 else "LOW"
                print(f"  {i}. [{level}] {wp['description']}")

        suggestions = report.get("suggestions", [])
        if suggestions:
            print()
            print("  -- Suggestions --------------------------------")
            for i, s in enumerate(suggestions[:5], 1):
                print(f"  {i}. [{s['priority'].upper()}] {s['action']}")

        gate = report.get("security_gate_compliance", {})
        if gate:
            skip_pct = gate.get("skip_rate", 0) * 100
            status = "COMPLIANT" if gate.get("compliant") else "NON-COMPLIANT"
            print()
            print(f"  -- Security Gate ------------------------------")
            print(f"  Skip rate: {skip_pct:.1f}% (threshold: 10%) -- {status}")
            print(f"  Trend: {gate.get('trend', 'unknown')}")

        approval = report.get("approval_gate", {})
        if approval.get("total", 0) > 0:
            print()
            print(f"  -- Approval Gate ------------------------------")
            print(f"  Total: {approval['total']} | Approved: {approval['approved']} | Denied: {approval['denied']} | Expired: {approval['expired']}")

        flags = report.get("recurring_flags", [])
        if flags:
            print()
            print(f"  -- Recurring Flags ----------------------------")
            for f in flags[:5]:
                print(f"  {f['flag']}: {f['count']}x ({f['trend']})")

        print()
        print("=" * 64)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    project_root = Path(__file__).resolve().parent.parent
    log_dir = project_root / "inspector" / "logs"
    behavioral_path = project_root / "inspector" / "state" / "behavioral_state.json"
    approval_path = project_root / "approval" / "state" / "pending_approvals.json"

    days = 7
    if len(sys.argv) > 1:
        try:
            days = max(1, min(30, int(sys.argv[1])))
        except ValueError:
            pass

    log_reader = InspectorLogReader(log_dir)
    behavioral_reader = BehavioralStateReader(behavioral_path)
    approval_reader = ApprovalStateReader(approval_path)

    entries = log_reader.read_entries(days=days)
    behavioral = behavioral_reader.read()
    approvals = approval_reader.read()

    analyzer = AuditAnalyzer(entries, behavioral, approvals)
    reporter = AuditReporter(log_dir)

    report = reporter.build_report(analyzer, days=days)
    saved_path = reporter.save_report(report)
    reporter.print_summary(report)

    print(f"  Report saved: {saved_path}")
    print()

    grade = report["health"]["grade"]
    if grade in ("EXCELLENT", "GOOD"):
        sys.exit(0)
    elif grade in ("FAIR", "POOR"):
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
