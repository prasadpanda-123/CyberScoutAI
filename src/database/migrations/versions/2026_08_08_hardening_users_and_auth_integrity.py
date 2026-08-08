"""hardening_users_and_auth_integrity

Revision ID: 20260808_001
Revises: 
Create Date: 2026-08-08 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260808_001'
down_revision = None
branch_labels = None
depends_on = None


PRESERVED_EMAILS = (
    'admin@cyberscout.ai',
    'adminuser@cyberscout.ai',
    'prasadpanda7989@gmail.com',
    'hi@gamil.com',
    'sateeshwarareddy@adityatekkali.edu.in'
)


def upgrade() -> None:
    # 1. Clean up orphaned user_id in AuditLogs before creating FK
    op.execute("""
        UPDATE "AuditLogs" 
        SET user_id = NULL 
        WHERE user_id IS NOT NULL 
          AND user_id NOT IN (SELECT id FROM "Users");
    """)

    # 2. Safely clean confirmed automated test users from Users table
    op.execute("""
        DELETE FROM "Users" 
        WHERE LOWER(email) NOT IN ('admin@cyberscout.ai', 'adminuser@cyberscout.ai', 'prasadpanda7989@gmail.com', 'hi@gamil.com', 'sateeshwarareddy@adityatekkali.edu.in')
          AND (
            LOWER(email) IN ('testuser@cyberscout.ai', 'regular@cyberscout.ai')
            OR (
                LOWER(email) LIKE '%@cyberscout.ai' 
                AND (
                    username LIKE 'viewer_%' 
                    OR username LIKE 'secops_%' 
                    OR username LIKE 'hacker_%' 
                    OR username LIKE 'user_%'
                )
            )
          );
    """)

    # 3. Create Case-Insensitive Unique Index on Users.email
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_users_lower_email ON "Users" (LOWER(email));')

    # 4. Add CHECK constraint for canonical roles on Users table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_role'
            ) THEN
                ALTER TABLE "Users" 
                ADD CONSTRAINT chk_users_role 
                CHECK (role IN ('Admin', 'admin', 'Super Admin', 'Administrator', 'Operator', 'Viewer', 'User', 'user'));
            END IF;
        END $$;
    """)

    # 5. Add CHECK constraint for non-empty email
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_email_not_empty'
            ) THEN
                ALTER TABLE "Users" 
                ADD CONSTRAINT chk_users_email_not_empty 
                CHECK (TRIM(email) <> '');
            END IF;
        END $$;
    """)

    # 6. Set is_active NOT NULL DEFAULT 1
    op.execute('ALTER TABLE "Users" ALTER COLUMN is_active SET DEFAULT 1;')
    op.execute('ALTER TABLE "Users" ALTER COLUMN is_active SET NOT NULL;')

    # 7. Add Foreign Key on AuditLogs(user_id) -> Users(id) ON DELETE SET NULL
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_auditlogs_user_id'
            ) THEN
                ALTER TABLE "AuditLogs" 
                ADD CONSTRAINT fk_auditlogs_user_id 
                FOREIGN KEY (user_id) 
                REFERENCES "Users"(id) 
                ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # 8. Indexes for performance
    op.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON "Users" (role);')
    op.execute('CREATE INDEX IF NOT EXISTS idx_users_is_active ON "Users" (is_active);')
    op.execute('CREATE INDEX IF NOT EXISTS idx_auditlogs_user_id ON "AuditLogs" (user_id);')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_auditlogs_user_id;')
    op.execute('DROP INDEX IF EXISTS idx_users_is_active;')
    op.execute('DROP INDEX IF EXISTS idx_users_role;')
    op.execute('ALTER TABLE "AuditLogs" DROP CONSTRAINT IF EXISTS fk_auditlogs_user_id;')
    op.execute('ALTER TABLE "Users" DROP CONSTRAINT IF EXISTS chk_users_email_not_empty;')
    op.execute('ALTER TABLE "Users" DROP CONSTRAINT IF EXISTS chk_users_role;')
    op.execute('DROP INDEX IF EXISTS uq_users_lower_email;')
