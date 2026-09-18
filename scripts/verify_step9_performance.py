"""
Phase 12.2 Step 9: Query Performance Inspection
Executes EXPLAIN (ANALYZE, BUFFERS) on critical query paths and records metrics.
"""
import os
import sys
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from sqlalchemy import text
from src.database.connection import DatabaseManager

def run_performance_audit():
    db = DatabaseManager()
    results = {}

    queries = {
        "user_lookup_by_username": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "Users" WHERE username = :uname',
            {"uname": "admin_test"}
        ),
        "user_lookup_by_uuid": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "Users" WHERE id = :uid',
            {"uid": "00000000-0000-0000-0000-000000000000"}
        ),
        "opportunity_search_vector": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id, title, company FROM "Opportunities" WHERE search_vector @@ to_tsquery(\'english\', \'security\') LIMIT 20',
            {}
        ),
        "saved_opportunities_join": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT so.id, so.opportunity_id, o.title FROM "SavedOpportunities" so JOIN "Opportunities" o ON so.opportunity_id = o.id WHERE so.user_id = :uid',
            {"uid": "00000000-0000-0000-0000-000000000000"}
        ),
        "notification_outbox_lookup": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "NotificationOutbox" WHERE user_id = :uid AND is_read = false',
            {"uid": "00000000-0000-0000-0000-000000000000"}
        ),
        "audit_logs_recent": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "AuditLogs" ORDER BY timestamp DESC LIMIT 50',
            {}
        ),
        "server_sessions_lookup": (
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "ServerSessions" WHERE session_hash = :sid AND expires_at > CURRENT_TIMESTAMP',
            {"sid": "sample_session_hash"}
        )
    }

    with db.get_session() as s:
        for name, (sql, params) in queries.items():
            res = s.execute(text(sql), params).scalar()
            # res is parsed JSON list from PostgreSQL
            plan_data = res[0] if isinstance(res, list) else res
            results[name] = {
                "planning_time_ms": plan_data.get("Planning Time"),
                "execution_time_ms": plan_data.get("Execution Time"),
                "node_type": plan_data.get("Plan", {}).get("Node Type"),
                "total_cost": plan_data.get("Plan", {}).get("Total Cost"),
                "actual_rows": plan_data.get("Plan", {}).get("Actual Rows"),
                "buffers": {
                    "shared_hit": plan_data.get("Plan", {}).get("Shared Hit Blocks", 0),
                    "shared_read": plan_data.get("Plan", {}).get("Shared Read Blocks", 0)
                }
            }
            print(f"[{name}] Exec: {plan_data.get('Execution Time')}ms | Plan: {plan_data.get('Planning Time')}ms | Node: {plan_data.get('Plan', {}).get('Node Type')}")

    out_file = os.path.join(project_root, "docs", "audits", "step9_query_performance.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved performance audit results to {out_file}")

if __name__ == "__main__":
    run_performance_audit()
