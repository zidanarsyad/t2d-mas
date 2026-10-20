"""The analysis program a Scout-Log mobile agent carries to a data node.

The orchestrator signs this file's source code and ships it inside an agent bundle.
The node runs it next to its own logs and sends back only the aggregate fields
below; the raw log rows never leave the node. It uses the standard library only,
because nothing else is available in the node's sandbox.
"""
import hashlib
import json
import sys


def summarize(state):
    """Turn raw request logs into a handful of numbers (the only data allowed to leave)."""
    service = state.get("service", "unknown")
    logs = state.get("local_logs", [])
    latencies = sorted(row["latency_ms"] for row in logs)
    errors = sum(1 for row in logs if row["status"] >= 500)
    fingerprint = f"{service}:{len(logs)}:{sum(latencies):.1f}:{errors}"
    return {
        "service": service,
        "request_count": len(logs),
        "error_rate": round(errors / max(1, len(logs)), 4),
        "latency_p50_ms": latencies[len(latencies) // 2] if latencies else 0.0,
        "latency_p95_ms": latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0,
        # A hash lets an investigator prove which evidence was used without moving it.
        "evidence_hash": "sha256:" + hashlib.sha256(fingerprint.encode()).hexdigest()[:16],
    }


if __name__ == "__main__":
    print(json.dumps(summarize(json.load(sys.stdin))))
