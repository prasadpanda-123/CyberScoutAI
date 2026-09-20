"""
Utility script to purge temporary test users and test admins created during unit test executions.
Preserves genuine accounts:
- User: panda (prasadpanda7989@gmail.com)
- Admin: admin (pjaykrishnaprasad@gmail.com)
"""

from src.database.connection import DatabaseManager

def cleanup():
    db = DatabaseManager()
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM "Users" WHERE username != %s;', ('panda',))
        deleted_users = cur.rowcount
        cur.execute('DELETE FROM "Admins" WHERE username != %s;', ('admin',))
        deleted_admins = cur.rowcount
        conn.commit()
        print(f"Purged {deleted_users} test users and {deleted_admins} test admins.")
    finally:
        cur.close()

if __name__ == "__main__":
    cleanup()
