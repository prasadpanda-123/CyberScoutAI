"""
SMTP Configuration Diagnostics & Validation Module for CyberScout AI.
"""

import os
from pathlib import Path
import socket
import smtplib
from typing import Any, Dict, Optional, Tuple
import yaml

from src.core.constants import CONFIG_DIR
from src.core.exceptions import ConfigurationError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SMTPValidator:
    """
    Validates SMTP environment configurations, performs DNS lookup,
    tests TCP connectivity, and verifies SMTP authentication credentials.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (CONFIG_DIR / "email.yaml")

    def get_smtp_config(self) -> Dict[str, Any]:
        """
        Reads SMTP configuration from environment variables with fallback to email.yaml.

        Returns:
            Dictionary containing normalized SMTP parameters.
        """
        yaml_data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Could not parse email.yaml: {e}")

        # Resolve parameters from .env first, fallback to email.yaml
        host = os.getenv("SMTP_HOST") or yaml_data.get("smtp_host") or ""
        port_raw = os.getenv("SMTP_PORT") or str(yaml_data.get("smtp_port", 587))
        username = (
            os.getenv("SMTP_USERNAME")
            or os.getenv("SMTP_USER")
            or yaml_data.get("smtp_user")
            or ""
        )
        password = (
            os.getenv("SMTP_PASSWORD")
            or os.getenv("SMTP_PASS")
            or yaml_data.get("smtp_password")
            or ""
        )
        email_from = (
            os.getenv("EMAIL_FROM")
            or os.getenv("SMTP_USER")
            or os.getenv("SMTP_USERNAME")
            or yaml_data.get("sender")
            or ""
        )
        email_to = (
            os.getenv("EMAIL_TO")
            or os.getenv("RECIPIENT_EMAIL")
            or yaml_data.get("recipient")
            or ""
        )

        tls_val = os.getenv("SMTP_TLS")
        if tls_val is not None:
            tls = tls_val.lower() in ("true", "1", "yes")
        else:
            tls = bool(yaml_data.get("tls", True))

        ssl_val = os.getenv("SMTP_SSL")
        if ssl_val is not None:
            ssl_enabled = ssl_val.lower() in ("true", "1", "yes")
        else:
            ssl_enabled = str(port_raw) == "465"

        return {
            "smtp_host": host.strip(),
            "smtp_port_raw": str(port_raw).strip(),
            "smtp_username": username.strip(),
            "smtp_password": password.strip(),
            "email_from": email_from.strip(),
            "email_to": email_to.strip(),
            "tls_enabled": tls,
            "ssl_enabled": ssl_enabled,
            "env_loaded": bool(os.getenv("SMTP_HOST") or os.getenv("SMTP_USER")),
        }

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validates presence and syntax of all required SMTP configuration fields.
        Raises ConfigurationError if any required value is missing or invalid.

        Returns:
            Dict containing validated config parameters.
        """
        cfg = self.get_smtp_config()

        if not cfg["smtp_host"]:
            raise ConfigurationError("Missing SMTP_HOST in .env")

        try:
            port = int(cfg["smtp_port_raw"])
            if not (1 <= port <= 65535):
                raise ValueError("Out of port range 1-65535")
            cfg["smtp_port"] = port
        except (ValueError, TypeError):
            raise ConfigurationError(f"Invalid SMTP_PORT: '{cfg['smtp_port_raw']}'. Must be an integer.")

        if not cfg["smtp_username"]:
            raise ConfigurationError("Missing SMTP_USERNAME in .env")

        if not cfg["smtp_password"]:
            raise ConfigurationError("Missing SMTP_PASSWORD in .env")

        if not cfg["email_from"]:
            raise ConfigurationError("Missing EMAIL_FROM in .env")

        if not cfg["email_to"]:
            raise ConfigurationError("Missing EMAIL_TO in .env")

        return cfg

    def verify_dns(self, host: str) -> Tuple[bool, str]:
        """
        Verifies DNS resolution for target SMTP host.

        Returns:
            Tuple of (success_bool, message_or_ip)
        """
        if not host:
            return False, "Invalid SMTP hostname: empty host"
        try:
            addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not addr_info:
                return False, f"Invalid SMTP hostname: {host}"
            resolved_ip = addr_info[0][4][0]
            return True, f"SUCCESS (Resolved to {resolved_ip})"
        except (socket.gaierror, socket.herror, OverflowError, Exception) as e:
            logger.error(f"DNS resolution failed for hostname '{host}': {e}")
            return False, f"Invalid SMTP hostname: {host}"

    def verify_tcp_connection(self, host: str, port: int, timeout: float = 10.0) -> Tuple[bool, str]:
        """
        Attempts a TCP socket connection to the target SMTP host and port.

        Returns:
            Tuple of (success_bool, message)
        """
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True, "SUCCESS"
        except (socket.timeout, ConnectionRefusedError, OSError, Exception) as e:
            logger.error(f"TCP connection failed to {host}:{port}: {e}")
            return False, f"FAILED (Reason: {e})"

    def verify_authentication(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: float = 10.0,
    ) -> Tuple[bool, str]:
        """
        Attempts SMTP connection and login authentication.

        Returns:
            Tuple of (success_bool, message)
        """
        server = None
        try:
            if port == 465 or use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=timeout)
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)
                if use_tls:
                    server.starttls()

            if username and password:
                server.login(username, password)
            
            server.quit()
            return True, "Authenticated"
        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error(f"SMTP authentication failed for user '{username}': {auth_err}")
            return False, f"Authentication failed: {auth_err.smtp_error.decode('utf-8', errors='ignore') if isinstance(auth_err.smtp_error, bytes) else auth_err.smtp_error}"
        except (smtplib.SMTPException, Exception) as err:
            logger.error(f"SMTP connection/login failed: {err}")
            return False, f"Authentication failed: {err}"
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Executes end-to-end SMTP configuration, DNS, TCP, and authentication checks.
        NEVER prints passwords.

        Returns:
            Structured dictionary of diagnostic results.
        """
        results: Dict[str, Any] = {
            "smtp_host": "N/A",
            "smtp_port": "N/A",
            "tls_enabled": False,
            "ssl_enabled": False,
            "username": "N/A",
            "environment_loaded": False,
            "dns_resolution": "FAILED",
            "tcp_connection": "FAILED",
            "authentication_result": "FAILED",
            "is_healthy": False,
            "errors": [],
        }

        try:
            cfg = self.validate_configuration()
        except ConfigurationError as err:
            results["errors"].append(str(err))
            return results

        host = cfg["smtp_host"]
        port = cfg["smtp_port"]
        username = cfg["smtp_username"]
        password = cfg["smtp_password"]

        results["smtp_host"] = host
        results["smtp_port"] = port
        results["tls_enabled"] = cfg["tls_enabled"]
        results["ssl_enabled"] = cfg["ssl_enabled"]
        results["username"] = username
        results["environment_loaded"] = cfg["env_loaded"]

        # 1. DNS Resolution Check
        dns_ok, dns_msg = self.verify_dns(host)
        results["dns_resolution"] = dns_msg
        if not dns_ok:
            results["errors"].append(dns_msg)
            return results

        # 2. TCP Connection Check
        tcp_ok, tcp_msg = self.verify_tcp_connection(host, port)
        results["tcp_connection"] = tcp_msg
        if not tcp_ok:
            results["errors"].append(f"TCP connection failed to {host}:{port}")
            return results

        # 3. Authentication Check
        auth_ok, auth_msg = self.verify_authentication(
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=cfg["tls_enabled"],
            use_ssl=cfg["ssl_enabled"],
        )
        results["authentication_result"] = auth_msg
        if not auth_ok:
            results["errors"].append(auth_msg)
            return results

        results["is_healthy"] = True
        return results
