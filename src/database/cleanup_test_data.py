"""
Database Purge Utility for CyberScout AI.

Safely purges ephemeral test accounts generated during test suites,
preserving all genuine accounts:
- Users:
  - 'panda' (prasadpanda7989@gmail.com)
  - 'Prasad' (24a51a4281@adityatekkali.edu.in)
  - 'ippili_lakshmi_lahari_31' (ippililakshmilahari@gmail.com)
- Admin:
  - 'admin' (pjaykrishnaprasad@gmail.com)
"""

import sys
import os
from typing import List, Tuple

sys.path.insert(0, os.path.abspath('CyberScoutAI'))
from dotenv import load_dotenv
load_dotenv('CyberScoutAI/.env')

from src.database.connection import DatabaseManager
from src.core.logging import get_logger

logger = get_logger(__name__)

GENUINE_USERS = ('panda', 'Prasad', 'ippili_lakshmi_lahari_31')
GENUINE_ADMINS = ('admin',)


def purge_test_accounts() -> Tuple[int, int]:
    """
    Deletes all test users and test admins from the PostgreSQL database,
    preserving genuine user and admin accounts.
    Returns (users_deleted_count, admins_deleted_count).
    """
    db = DatabaseManager()
    
    with db.transaction() as cursor:
        # 1. Fetch test users
        cursor.execute(
            """
            SELECT id, username, email FROM Users 
            WHERE email LIKE %s AND username NOT IN (%s, %s, %s);
            """,
            ('%@cyberscout.ai', *GENUINE_USERS)
        )
        test_users = cursor.fetchall()
        test_user_ids = [str(r.get('id')) for r in test_users]
        
        # 2. Fetch test admins
        cursor.execute(
            """
            SELECT id, username, email FROM Admins 
            WHERE email LIKE %s AND username NOT IN (%s);
            """,
            ('%@cyberscout.ai', *GENUINE_ADMINS)
        )
        test_admins = cursor.fetchall()
        test_admin_ids = [str(r.get('id')) for r in test_admins]

        print(f"Identified {len(test_users)} test users to purge.")
        print(f"Identified {len(test_admins)} test admins to purge.")

        all_test_account_ids = test_user_ids + test_admin_ids

        # 3. Clean up PendingMfa entries for test accounts
        if all_test_account_ids:
            cursor.execute(
                'DELETE FROM PendingMfa WHERE account_id = ANY(%s) OR email LIKE %s;',
                (all_test_account_ids, '%@cyberscout.ai')
            )
            print(f"Purged test entries from PendingMfa: {cursor.rowcount}")

        # 4. Clean up ServerSessions entries for test accounts
        if all_test_account_ids:
            cursor.execute(
                'DELETE FROM ServerSessions WHERE account_id = ANY(%s);',
                (all_test_account_ids,)
            )
            print(f"Purged test sessions from ServerSessions: {cursor.rowcount}")

        # 5. Delete test users (cascades to SavedOpportunities, UserPreferences, UserSearchHistory, etc.)
        if test_user_ids:
            cursor.execute(
                'DELETE FROM Users WHERE id = ANY(%s::uuid[]);',
                (test_user_ids,)
            )
            print(f"Purged {cursor.rowcount} test users from Users table.")

        # 6. Delete test admins
        if test_admin_ids:
            admin_int_ids = [int(i) for i in test_admin_ids]
            cursor.execute(
                'DELETE FROM Admins WHERE id = ANY(%s);',
                (admin_int_ids,)
            )
            print(f"Purged {cursor.rowcount} test admins from Admins table.")

        # 7. Verify remaining accounts
        cursor.execute('SELECT id, username, email, role FROM Users ORDER BY created_at ASC;')
        remaining_users = cursor.fetchall()
        cursor.execute('SELECT id, username, email, role FROM Admins ORDER BY created_at ASC;')
        remaining_admins = cursor.fetchall()

    print("\n=== PURGE COMPLETED SUCCESSFULLY ===")
    print(f"Remaining Users ({len(remaining_users)}):")
    for u in remaining_users:
        print(f"  ID: {u.get('id')} | Username: {u.get('username')} | Email: {u.get('email')} | Role: {u.get('role')}")
        
    print(f"\nRemaining Admins ({len(remaining_admins)}):")
    for a in remaining_admins:
        print(f"  ID: {a.get('id')} | Username: {a.get('username')} | Email: {a.get('email')} | Role: {a.get('role')}")

    return len(test_users), len(test_admins)


if __name__ == "__main__":
    purge_test_accounts()
