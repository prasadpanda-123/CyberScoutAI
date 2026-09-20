"""
Database Purge Utility for CyberScout AI.

Safely purges ephemeral test accounts generated during test suites,
preserving only genuine accounts:
- User: 'panda' (prasadpanda7989@gmail.com)
- Admin: 'admin' (pjaykrishnaprasad@gmail.com)
"""

import sys
from typing import List, Tuple
from src.database.connection import DatabaseManager
from src.core.logging import get_logger

logger = get_logger(__name__)


def purge_test_accounts() -> Tuple[int, int]:
    """
    Deletes all test users and test admins from the PostgreSQL database,
    preserving the primary genuine user and admin accounts.
    Returns (users_deleted_count, admins_deleted_count).
    """
    db = DatabaseManager()
    
    with db.transaction() as cursor:
        # 1. Fetch test users
        cursor.execute('SELECT id, username, email FROM "Users" WHERE username != %s', ('panda',))
        test_users = cursor.fetchall()
        test_user_ids = [str(r[0]) for r in test_users]
        
        # 2. Fetch test admins
        cursor.execute('SELECT id, username, email FROM "Admins" WHERE username != %s', ('admin',))
        test_admins = cursor.fetchall()
        test_admin_ids = [str(r[0]) for r in test_admins]

        print(f"Identified {len(test_users)} test users to purge.")
        print(f"Identified {len(test_admins)} test admins to purge.")

        # 3. Clean up PendingMfa entries for test accounts
        all_test_account_ids = test_user_ids + test_admin_ids
        if all_test_account_ids:
            cursor.execute(
                'DELETE FROM "PendingMfa" WHERE account_id = ANY(%s)',
                (all_test_account_ids,)
            )

        # 4. Delete test users (cascades to SavedOpportunities, UserPreferences, etc.)
        if test_user_ids:
            cursor.execute(
                'DELETE FROM "Users" WHERE id = ANY(%s::uuid[])',
                (test_user_ids,)
            )

        # 5. Delete test admins
        if test_admin_ids:
            admin_int_ids = [int(i) for i in test_admin_ids]
            cursor.execute(
                'DELETE FROM "Admins" WHERE id = ANY(%s)',
                (admin_int_ids,)
            )

        # 6. Verify remaining accounts
        cursor.execute('SELECT id, username, email, role FROM "Users"')
        remaining_users = cursor.fetchall()
        cursor.execute('SELECT id, username, email, role FROM "Admins"')
        remaining_admins = cursor.fetchall()

    print("\n=== PURGE COMPLETED SUCCESSFULLY ===")
    print(f"Remaining Users ({len(remaining_users)}):")
    for u in remaining_users:
        print(f"  ID: {u[0]} | Username: {u[1]} | Email: {u[2]} | Role: {u[3]}")
        
    print(f"Remaining Admins ({len(remaining_admins)}):")
    for a in remaining_admins:
        print(f"  ID: {a[0]} | Username: {a[1]} | Email: {a[2]} | Role: {a[3]}")

    return len(test_users), len(test_admins)


if __name__ == "__main__":
    purge_test_accounts()
