"""
Step 4 UUID Verification Script for CyberScout AI.
Verifies Users table UUID schema, default generator, nullability,
all dependent tables, foreign key constraints, indexes, and orphan counts.
"""

import uuid
from sqlalchemy import text
from src.database.connection import DatabaseManager

def verify_uuid_integrity():
    db = DatabaseManager()
    with db.get_session() as session:
        print("=== 1. USERS TABLE SCHEMA VERIFICATION ===")
        user_col = session.execute(text("""
            SELECT column_name, data_type, udt_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'Users' AND column_name = 'id';
        """)).fetchone()
        print(f"Users.id: name={user_col[0]}, type={user_col[1]}, udt={user_col[2]}, nullable={user_col[3]}, default={user_col[4]}")
        assert user_col[2] == 'uuid', f"Expected udt_name 'uuid', got {user_col[2]}"
        assert user_col[3] == 'NO', f"Expected is_nullable 'NO', got {user_col[3]}"
        assert 'gen_random_uuid()' in str(user_col[4]), f"Expected gen_random_uuid() default, got {user_col[4]}"

        user_pk = session.execute(text("""
            SELECT tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = 'Users' AND tc.constraint_type = 'PRIMARY KEY';
        """)).fetchone()
        print(f"Users PK: constraint={user_pk[0]}, column={user_pk[1]}")
        assert user_pk[1] == 'id', f"Expected PK column 'id', got {user_pk[1]}"

        print("\n=== 2. CATALOG DISCOVERY: ALL FKs TO Users(id) ===")
        fks = session.execute(text("""
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.update_rule,
                rc.delete_rule,
                c.data_type,
                c.udt_name,
                c.is_nullable
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON rc.constraint_name = tc.constraint_name
            JOIN information_schema.columns c
              ON c.table_name = tc.table_name AND c.column_name = kcu.column_name AND c.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
              AND tc.table_schema = 'public'
              AND ccu.table_name = 'Users'
              AND ccu.column_name = 'id'
            ORDER BY tc.table_name, kcu.column_name;
        """)).fetchall()

        for fk in fks:
            tbl, col, f_tbl, f_col, upd, dele, dtype, udt, nullable = fk
            print(f"FK: {tbl}.{col} ({udt}, nullable={nullable}) -> {f_tbl}.{f_col} [ON UPDATE {upd}, ON DELETE {dele}]")
            assert udt == 'uuid', f"Expected FK column {tbl}.{col} to be uuid, got {udt}"

        print("\n=== 3. AUDIT OF OTHER USER-REFERENCING / IDENTITY TABLES ===")
        # Check ServerSessions.account_id
        sess_col = session.execute(text("""
            SELECT column_name, data_type, udt_name, is_nullable, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'ServerSessions' AND column_name = 'account_id';
        """)).fetchone()
        print(f"ServerSessions.account_id: type={sess_col[1]}, udt={sess_col[2]}, max_len={sess_col[4]}")
        assert sess_col[4] >= 36, "ServerSessions.account_id must accommodate 36-char UUID strings"

        # Check PendingMfa.account_id
        mfa_col = session.execute(text("""
            SELECT column_name, data_type, udt_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'PendingMfa' AND column_name = 'account_id';
        """)).fetchone()
        print(f"PendingMfa.account_id: type={mfa_col[1]}, udt={mfa_col[2]}")

        # Check ScanJobs.created_by_admin_id
        scan_col = session.execute(text("""
            SELECT column_name, data_type, udt_name, is_nullable, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'ScanJobs' AND column_name = 'created_by_admin_id';
        """)).fetchone()
        print(f"ScanJobs.created_by_admin_id: type={scan_col[1]}, max_len={scan_col[4]}")

        print("\n=== 4. INDEXES ON FK COLUMNS ===")
        indexes = session.execute(text("""
            SELECT
                t.relname AS table_name,
                i.relname AS index_name,
                a.attname AS column_name
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND a.attname IN ('user_id', 'account_id', 'id')
              AND t.relname IN ('SavedOpportunities', 'UserPreferences', 'UserSearchHistory', 'NotificationOutbox', 'AuditLogs', 'Users', 'ServerSessions')
            ORDER BY t.relname, i.relname;
        """)).fetchall()
        for idx in indexes:
            print(f"Index: {idx[0]}.{idx[2]} via {idx[1]}")

        print("\n=== 5. ORPHAN RECORD CHECK ===")
        # Count any orphans (should all be 0)
        dependent_tables = [
            ("SavedOpportunities", "user_id"),
            ("UserPreferences", "user_id"),
            ("UserSearchHistory", "user_id"),
            ("NotificationOutbox", "user_id"),
            ("AuditLogs", "user_id"),
        ]
        for tbl, col in dependent_tables:
            orphan_cnt = session.execute(text(f"""
                SELECT COUNT(*) FROM "{tbl}"
                WHERE "{col}" IS NOT NULL 
                  AND "{col}" NOT IN (SELECT id FROM "Users");
            """)).scalar()
            print(f"Orphans in {tbl}.{col}: {orphan_cnt}")
            assert orphan_cnt == 0, f"Found {orphan_cnt} orphans in {tbl}!"

        print("\n=== 6. USER CREATION UUID GENERATION TEST ===")
        # Insert a user letting PostgreSQL generate the UUID default
        u_res = session.execute(text("""
            INSERT INTO "Users" (username, email, password_hash, role, created_at)
            VALUES ('test_uuid_user', 'uuid_test@example.com', 'dummy_hash', 'Viewer', CURRENT_TIMESTAMP)
            RETURNING id;
        """)).fetchone()
        gen_id = u_res[0]
        print(f"PostgreSQL generated default UUID: {gen_id} (type: {type(gen_id)})")
        assert isinstance(gen_id, uuid.UUID) or uuid.UUID(str(gen_id))

        # Insert a dependent record referencing this UUID
        session.execute(text(f"""
            INSERT INTO "UserPreferences" (id, user_id, preferred_categories)
            VALUES (gen_random_uuid()::text, '{gen_id}', '[\"testing\"]');
        """))
        pref_user_id = session.execute(text(f'SELECT user_id FROM "UserPreferences" WHERE user_id = \'{gen_id}\'')).scalar()
        print(f"Dependent UserPreferences.user_id: {pref_user_id}")
        assert str(pref_user_id) == str(gen_id)

        # Test CASCADE delete
        session.execute(text(f"DELETE FROM \"Users\" WHERE id = '{gen_id}';"))
        remaining_pref = session.execute(text(f'SELECT COUNT(*) FROM "UserPreferences" WHERE user_id = \'{gen_id}\'')).scalar()
        print(f"UserPreferences count after CASCADE delete: {remaining_pref}")
        assert remaining_pref == 0, "CASCADE delete failed on UserPreferences!"

        session.commit()
        print("\nALL STEP 4 CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    verify_uuid_integrity()
