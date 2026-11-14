"""
Utility script to purge temporary test users and test admins created during unit test executions.
Preserves genuine accounts:
- Users:
  - panda (prasadpanda7989@gmail.com)
  - Prasad (24a51a4281@adityatekkali.edu.in)
  - ippili_lakshmi_lahari_31 (ippililakshmilahari@gmail.com)
- Admin:
  - admin (pjaykrishnaprasad@gmail.com)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from src.database.cleanup_test_data import purge_test_accounts


def cleanup():
    purge_test_accounts()


if __name__ == "__main__":
    cleanup()
