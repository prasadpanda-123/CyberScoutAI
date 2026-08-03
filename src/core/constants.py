"""
Centralized constants for the CyberScout AI application.
"""

from pathlib import Path

# Project Application Metadata
APP_NAME = "CyberScout AI"
APP_VERSION = "0.1.0"
APP_TAGLINE = "Never Miss a Cybersecurity Opportunity Again."

# Directory Structure
CURRENT_FILE = Path(__file__).resolve()
SRC_ROOT = CURRENT_FILE.parent.parent
PROJECT_ROOT = SRC_ROOT.parent

# Config, Data, Logs, and Reports Directories
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
TESTS_DIR = PROJECT_ROOT / "tests"

# Config Files
DEFAULT_CONFIG_FILE = CONFIG_DIR / "settings.yaml"
SOURCES_CONFIG_FILE = CONFIG_DIR / "sources.yaml"
KEYWORDS_CONFIG_FILE = CONFIG_DIR / "keywords.yaml"
SCHEDULE_CONFIG_FILE = CONFIG_DIR / "schedule.yaml"
WEIGHTS_CONFIG_FILE = CONFIG_DIR / "weights.yaml"

# Database Constants
DEFAULT_DB_NAME = "cyberscout.db"
DB_PATH = DATA_DIR / DEFAULT_DB_NAME

# Technical Defaults
ENCODING = "utf-8"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_DESCRIPTION_LENGTH = 2000
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
