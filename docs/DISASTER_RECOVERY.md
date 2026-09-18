# CyberScout AI — Disaster Recovery & Backup Runbook (Phase 10)

## 1. Overview
This runbook details the backup, validation, and disaster recovery procedures for CyberScout AI's PostgreSQL database. Backups ensure zero data loss across opportunities, source health telemetry, outbox notifications, user bookmarks, and audit trails.

---

## 2. Backup Architecture & Engine
Database backups are orchestrated through `src/maintenance/backup_manager.py` and executable via `scripts/backup_database.py`.

### Dual-Engine Strategy:
1. **Primary (`pg_dump`)**: If PostgreSQL command-line tools are present in the system PATH, native binary/SQL dumping is executed.
2. **Fallback (Python-Native SQL Exporter)**: If `pg_dump` is absent (such as in minimalist container images or Windows environments without PostgreSQL tools in PATH), `BackupManager` executes an in-process, table-by-table SQL exporter.
   - Exports schema DDL and table rows in topological order.
   - Encloses statements within transaction framing (`BEGIN; ... COMMIT;`).
   - Automatically sanitizes sensitive secrets (passwords, auth tokens) from output.

---

## 3. CLI Management Utilities

### Create Backup
```powershell
python scripts/backup_database.py
```
Outputs:
`data/backups/cyberscout_backup_YYYYMMDD_HHMMSS.sql`

### List Available Backups
```powershell
python scripts/backup_database.py --list
```

### Validate Backup Integrity
```powershell
python scripts/backup_database.py --validate data/backups/cyberscout_backup_20260916_075922.sql
```
Validates:
- File existence and non-zero byte size.
- Presence of valid SQL statements (`CREATE TABLE`, `INSERT INTO`).
- Transaction closure (`BEGIN` and `COMMIT`).
- Total statements and row counts.

### Non-Destructive Restore Drill
```powershell
python scripts/backup_database.py --drill data/backups/cyberscout_backup_20260916_075922.sql
```
> [!IMPORTANT]
> Non-destructive restore drills **never overwrite production**. In PostgreSQL environments, the drill parses syntax, structure, and transaction integrity without issuing destructive drops or commits against active data.

---

## 4. Disaster Recovery Procedure (Step-by-Step)

In the event of total server loss or database corruption:

1. **Verify Target Database Provisioning**:
   Ensure a clean PostgreSQL 17 instance is available and `DATABASE_URL` is configured in `.env`.
2. **Select Most Recent Valid Backup**:
   Run `python scripts/backup_database.py --list` and validate the chosen archive with `--validate`.
3. **Restore Database**:
   - If using `psql`:
     ```bash
     psql "$DATABASE_URL" -f data/backups/cyberscout_backup_YYYYMMDD_HHMMSS.sql
     ```
   - If using Python restore runner:
     `BackupManager().restore_backup(filepath)`
4. **Run System Sanity Checks**:
   - Verify health probes: `curl http://localhost:5000/health/ready`
   - Run verification test: `python -m unittest tests/unit/test_phase10_reliability_observability.py`
