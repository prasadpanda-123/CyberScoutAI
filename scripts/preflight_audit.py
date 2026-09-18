import os
import sys
import json
from pathlib import Path
from sqlalchemy import text
from src.database.connection import DatabaseManager
from src.database.engine import get_masked_db_host

def run_audit():
    db = DatabaseManager()
    with db.get_session() as s:
        # 1. Identity
        identity = s.execute(text("""
            SELECT current_database(), current_user, session_user, version(),
                   (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),
                   (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user),
                   inet_server_port();
        """)).fetchone()

        db_name, cur_user, sess_user, pg_ver, rolsuper, rolbypassrls, srv_port = identity
        masked_host = get_masked_db_host()
        app_env = os.getenv("APP_ENV", "unknown")

        print("=== DATABASE IDENTITY ===")
        print(f"Masked Host: {masked_host}")
        print(f"Database Name: {db_name}")
        print(f"Connected User: {cur_user} (Session: {sess_user})")
        print(f"PostgreSQL Version: {pg_ver}")
        print(f"rolsuper: {rolsuper}")
        print(f"rolbypassrls: {rolbypassrls}")
        print(f"Server Port: {srv_port}")
        print(f"APP_ENV: {app_env}")

        # Check application role cyberscout_app
        app_role = s.execute(text("""
            SELECT rolname, rolsuper, rolbypassrls, rolcanlogin 
            FROM pg_roles 
            WHERE rolname IN ('cyberscout_app', 'postgres', 'authenticated', 'anon');
        """)).fetchall()
        print("\n=== RELEVANT ROLES ===")
        for r in app_role:
            print(f"Role: {r[0]}, Superuser: {r[1]}, BypassRLS: {r[2]}, CanLogin: {r[3]}")

        # 2. Schema version
        print("\n=== SCHEMA VERSIONS ===")
        try:
            versions = s.execute(text("SELECT version, description, applied_at FROM schema_version ORDER BY version ASC;")).fetchall()
            for v in versions:
                print(f"v{v[0]}: {v[1]} (applied: {v[2]})")
        except Exception as e:
            print(f"Error fetching schema_version: {e}")

        # 3. Tables in public schema
        tables = s.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)).fetchall()
        table_names = [t[0] for t in tables]
        print(f"\n=== PUBLIC TABLES ({len(table_names)}) ===")
        print(", ".join(table_names))

        # 4. Row counts
        print("\n=== ROW COUNTS ===")
        row_counts = {}
        for t in table_names:
            cnt = s.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
            row_counts[t] = cnt
            print(f"  {t}: {cnt}")

        # 5. Primary Keys
        print("\n=== PRIMARY KEYS ===")
        pk_query = s.execute(text("""
            SELECT tc.table_name, c.column_name, c.data_type, c.udt_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu 
              ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
            JOIN information_schema.columns c
              ON c.table_name = tc.table_name AND c.column_name = ccu.column_name AND c.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
            ORDER BY tc.table_name, c.column_name;
        """)).fetchall()
        for pk in pk_query:
            print(f"  {pk[0]}.{pk[1]} ({pk[2]} / {pk[3]})")

        # 6. Foreign Keys referencing Users or any other table
        print("\n=== FOREIGN KEY CONSTRAINTS ===")
        fk_query = s.execute(text("""
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.update_rule,
                rc.delete_rule,
                c.data_type,
                c.udt_name
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
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.column_name;
        """)).fetchall()
        for fk in fk_query:
            print(f"  {fk[0]}.{fk[1]} ({fk[6]}/{fk[7]}) -> {fk[2]}.{fk[3]} [ON UPDATE {fk[4]}, ON DELETE {fk[5]}]")

        # 7. RLS Status and Policies
        print("\n=== RLS STATUS PER TABLE ===")
        rls_query = s.execute(text("""
            SELECT 
                c.relname AS table_name,
                c.relrowsecurity AS rls_enabled,
                c.relforcerowsecurity AS rls_forced,
                pg_get_userbyid(c.relowner) AS table_owner
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY c.relname;
        """)).fetchall()
        for r in rls_query:
            print(f"  {r[0]}: RLS={r[1]}, FORCE_RLS={r[2]}, Owner={r[3]}")

        print("\n=== POLICIES PER TABLE ===")
        policies = s.execute(text("""
            SELECT 
                schemaname,
                tablename,
                policyname,
                permissive,
                roles,
                cmd,
                qual,
                with_check
            FROM pg_policies
            WHERE schemaname = 'public'
            ORDER BY tablename, policyname;
        """)).fetchall()
        print(f"Total Policies in public: {len(policies)}")
        for p in policies:
            print(f"  [{p[1]}] {p[2]} (CMD: {p[5]}, Roles: {p[4]}, Permissive: {p[3]})")
            if p[6]:
                print(f"     USING: {p[6]}")
            if p[7]:
                print(f"     WITH CHECK: {p[7]}")

if __name__ == "__main__":
    run_audit()
