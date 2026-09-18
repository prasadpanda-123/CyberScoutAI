"""
Database Backup CLI Utility for CyberScout AI (Phase 10).

Usage:
    python scripts/backup_database.py
    python scripts/backup_database.py --list
    python scripts/backup_database.py --validate data/backups/cyberscout_backup_latest.sql
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.logging import setup_logging, get_logger
from src.maintenance.backup_manager import BackupManager

setup_logging(level="INFO")
logger = get_logger("backup_cli")


def main():
    parser = argparse.ArgumentParser(description="CyberScout AI Database Backup Utility")
    parser.add_argument("--list", action="store_true", help="List available database backups")
    parser.add_argument("--validate", type=str, help="Validate an existing backup file path")
    parser.add_argument("--output", type=str, help="Custom output filepath for the backup")
    parser.add_argument("--drill", type=str, help="Run non-destructive restore drill on a backup file")
    args = parser.parse_args()

    manager = BackupManager()

    if args.list:
        backups = manager.list_backups()
        print(f"\nAvailable Database Backups ({len(backups)}):")
        for b in backups:
            print(f"  - {b['file_name']} ({b['size_bytes']} bytes, {b['created_at']})")
        sys.exit(0)

    if args.validate:
        res = manager.validate_backup(args.validate)
        if res.get("is_valid"):
            print(f"VALID: Backup '{args.validate}' passed validation ({res.get('size_bytes')} bytes).")
            sys.exit(0)
        else:
            print(f"INVALID: Backup validation failed: {res.get('error')}")
            sys.exit(1)

    if args.drill:
        res = manager.restore_drill(args.drill)
        if res.get("drill_success"):
            print(f"SUCCESS: Restore drill passed ({res.get('statements_verified')} SQL statements verified).")
            sys.exit(0)
        else:
            print(f"FAILED: Restore drill failed: {res.get('error')}")
            sys.exit(1)

    try:
        out_path = Path(args.output) if args.output else None
        res = manager.create_backup(custom_output_path=out_path)
        if res.get("is_valid"):
            print(f"SUCCESS: Backup created at '{res.get('file_path')}' ({res.get('file_size_bytes')} bytes, engine={res.get('engine')}).")
            sys.exit(0)
        else:
            print(f"FAILED: Backup created but validation failed: {res.get('validation', {}).get('error')}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Backup operation aborted with error: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
