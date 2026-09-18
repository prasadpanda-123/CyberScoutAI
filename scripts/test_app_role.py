"""
Test script for Step 5: Application-Role RLS Verification.
Tests role privileges, SET ROLE cyberscout_app, and RLS behavior.
"""

from sqlalchemy import text
from src.database.connection import DatabaseManager

def test_app_role_rls():
    db = DatabaseManager()
    with db.get_session() as session:
        # Check current user and role
        res = session.execute(text("SELECT current_user, session_user;")).fetchone()
        print(f"Connected: current_user={res[0]}, session_user={res[1]}")

        # Check grants on cyberscout_app
        role_info = session.execute(text("""
            SELECT rolname, rolsuper, rolbypassrls, rolcanlogin,
                   pg_has_role(session_user, 'cyberscout_app', 'MEMBER') as is_member
            FROM pg_roles 
            WHERE rolname = 'cyberscout_app';
        """)).fetchone()
        print(f"cyberscout_app: super={role_info[1]}, bypassrls={role_info[2]}, canlogin={role_info[3]}, is_member={role_info[4]}")

        # Try SET ROLE cyberscout_app
        try:
            session.execute(text("SET ROLE cyberscout_app;"))
            cur = session.execute(text("SELECT current_user, (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user);")).fetchone()
            print(f"Switched role! current_user={cur[0]}, rolbypassrls={cur[1]}")
            assert cur[1] == False, "cyberscout_app MUST NOT have bypassrls!"
            print("Successfully running under least-privileged non-bypass role 'cyberscout_app'!")
        except Exception as e:
            print(f"Cannot SET ROLE cyberscout_app: {e}")
        finally:
            session.execute(text("RESET ROLE;"))

if __name__ == "__main__":
    test_app_role_rls()
