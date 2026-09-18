"""
Step 8: Table Row Counts & Isolation Audit
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

def check_table_counts():
    db = DatabaseManager()
    counts = {}
    with db.get_session() as s:
        tables = [r[0] for r in s.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)).fetchall()]

        for t in tables:
            cnt = s.execute(text(f'SELECT COUNT(*) FROM "{t}";')).scalar()
            counts[t] = cnt
            print(f"  {t}: {cnt}")

    out_file = os.path.join(project_root, "docs", "audits", "step8_table_counts.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(counts, f, indent=2)
    print(f"\nSaved table row counts to {out_file}")

if __name__ == "__main__":
    check_table_counts()
