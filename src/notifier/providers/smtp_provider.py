"""
SMTP / Gmail Email Provider for CyberScout AI.

Supports host cleaning, dual-stack IPv4/IPv6 socket connectivity fallback,
explicit EHLO/STARTTLS handshake, structured error stage classification,
and pre-flight health diagnostics.
"""

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
import os
from pathlib import Path
import re
import smtplib
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider

logger = get_logger(__name__)


def clean_host_and_port(raw_host: str, raw_port: Any = None) -> Tuple[str, int]:
    """
    Cleans raw hostname string by stripping schemes (http://, https://) and
    extracting embedded port numbers if passed as 'smtp.gmail.com:587'.
    """
    host = (raw_host or "").strip()
    host = re.sub(r"^https?://", "", host, flags=re.IGNORECASE).rstrip("/")

    port = 587
    if raw_port is not None:
        try:
            port = int(str(raw_port).strip())
        except (ValueError, TypeError):
            port = 587

    # If host contains host:port syntax e.g. smtp.gmail.com:587
    if ":" in host and not host.startswith("["):
        parts = host.split(":")
        if len(parts) == 2 and parts[1].isdigit():
            host = parts[0].strip()
            port = int(parts[1])

    return host or "smtp.gmail.com", port


class SMTPEmailProvider(BaseEmailProvider):
    """
    SMTP Email Provider implementing robust dual-stack IPv4/IPv6 socket fallback
    and structured error stage diagnostics.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path

    @property
    def provider_name(self) -> str:
        return "smtp"

    def get_smtp_config(self) -> Dict[str, Any]:
        """
        Reads and normalizes SMTP settings from environment variables.
        """
        raw_host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
        raw_port = os.getenv("SMTP_PORT") or "587"
        host, port = clean_host_and_port(raw_host, raw_port)

        username = (
            os.getenv("SMTP_USERNAME")
            or os.getenv("SMTP_USER")
            or os.getenv("SMTP_EMAIL")
            or ""
        ).strip()

        password = (
            os.getenv("SMTP_PASSWORD")
            or os.getenv("SMTP_PASS")
            or ""
        ).strip()

        email_from = (
            os.getenv("EMAIL_FROM")
            or username
            or "cyberscout-alerts@example.com"
        ).strip()

        email_to = (
            os.getenv("EMAIL_TO")
            or os.getenv("RECIPIENT_EMAIL")
            or username
            or "user@example.com"
        ).strip()

        tls_val = os.getenv("SMTP_USE_TLS") or os.getenv("SMTP_TLS")
        if tls_val is not None:
            tls_enabled = tls_val.lower() in ("true", "1", "yes", "on")
        else:
            tls_enabled = port == 587

        ssl_val = os.getenv("SMTP_USE_SSL") or os.getenv("SMTP_SSL")
        if ssl_val is not None:
            ssl_enabled = ssl_val.lower() in ("true", "1", "yes", "on")
        else:
            ssl_enabled = port == 465

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "email_from": email_from,
            "email_to": email_to,
            "tls_enabled": tls_enabled,
            "ssl_enabled": ssl_enabled,
        }

    def _dual_stack_connect(self, host: str, port: int, timeout: float = 15.0) -> Tuple[socket.socket, str]:
        """
        Attempts socket connection iterating over resolved IPv4 and IPv6 addresses.
        Ensures IPv6 unreachability on cloud platforms (like Render) falls back to IPv4.

        Returns:
            Tuple of (connected_socket, connected_ip_str)
        """
        addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            raise socket.gaierror(f"Could not resolve host '{host}'")

        # Sort so IPv4 (AF_INET) is tried first if available
        addr_info_sorted = sorted(addr_info, key=lambda x: 0 if x[0] == socket.AF_INET else 1)

        last_err = None
        for family, socktype, proto, canonname, sa in addr_info_sorted:
            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(timeout)
                sock.connect(sa)
                ip_str = sa[0]
                return sock, ip_str
            except Exception as err:
                last_err = err
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

        raise OSError(f"Failed to connect to {host}:{port} across all resolved IP addresses: {last_err}") from last_err

    def check_health(self) -> Dict[str, Any]:
        """
        Executes diagnostic pre-flight checks: CONFIG -> DNS -> TCP -> SMTP Handshake -> Auth.
        """
        cfg = self.get_smtp_config()
        host = cfg["host"]
        port = cfg["port"]
        username = cfg["username"]

        diagnostics: Dict[str, Any] = {
            "provider": self.provider_name,
            "host": host,
            "port": port,
            "tls_enabled": cfg["tls_enabled"],
            "ssl_enabled": cfg["ssl_enabled"],
            "username": username or "N/A",
            "dns": "FAILED",
            "tcp": "FAILED",
            "smtp": "FAILED",
            "is_healthy": False,
            "errors": [],
        }

        # 1. Config Stage
        if not host:
            diagnostics["errors"].append("Missing SMTP_HOST configuration")
            diagnostics["stage"] = "CONFIG"
            return diagnostics
        if not cfg["username"]:
            diagnostics["errors"].append("Missing SMTP_USERNAME / SMTP_USER configuration")
            diagnostics["stage"] = "CONFIG"
            return diagnostics
        if not cfg["password"]:
            diagnostics["errors"].append("Missing SMTP_PASSWORD / SMTP_PASS configuration")
            diagnostics["stage"] = "CONFIG"
            return diagnostics

        # 2. DNS Resolution Stage
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            resolved_ips = [a[4][0] for a in addr_info]
            diagnostics["dns"] = "OK"
            diagnostics["resolved_ips"] = resolved_ips[:4]
        except Exception as dns_err:
            diagnostics["stage"] = "DNS_LOOKUP"
            diagnostics["reason"] = f"DNS resolution failed for '{host}': {dns_err}"
            diagnostics["errors"].append(diagnostics["reason"])
            return diagnostics

        # 3. TCP Connectivity Stage with Dual-Stack Fallback
        connected_sock = None
        target_ip = host
        try:
            connected_sock, target_ip = self._dual_stack_connect(host, port, timeout=10.0)
            diagnostics["tcp"] = "OK"
            diagnostics["connected_ip"] = target_ip
        except Exception as tcp_err:
            diagnostics["stage"] = "TCP_CONNECT"
            diagnostics["reason"] = f"Network connection failed to {host}:{port} ({target_ip}): {tcp_err}"
            diagnostics["errors"].append(diagnostics["reason"])
            return diagnostics

        # 4. SMTP Handshake & Login Stage
        server = None
        try:
            if cfg["ssl_enabled"] or port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)

            server.ehlo()
            if cfg["tls_enabled"] and not cfg["ssl_enabled"]:
                server.starttls()
                server.ehlo()

            diagnostics["smtp"] = "OK"

            if cfg["username"] and cfg["password"]:
                server.login(cfg["username"], cfg["password"])
                diagnostics["auth"] = "OK"

            server.quit()
            diagnostics["is_healthy"] = True
            return diagnostics
        except smtplib.SMTPAuthenticationError as auth_err:
            diagnostics["stage"] = "SMTP_AUTH"
            diagnostics["reason"] = f"SMTP Authentication Failed for user '{username}': {auth_err.smtp_error.decode('utf-8', errors='ignore') if isinstance(auth_err.smtp_error, bytes) else auth_err.smtp_error}"
            diagnostics["errors"].append(diagnostics["reason"])
            return diagnostics
        except Exception as smtp_err:
            diagnostics["stage"] = "SMTP_HANDSHAKE"
            diagnostics["reason"] = f"SMTP Handshake error on {host}:{port}: {smtp_err}"
            diagnostics["errors"].append(diagnostics["reason"])
            return diagnostics
        finally:
            if connected_sock:
                try:
                    connected_sock.close()
                except Exception:
                    pass
            if server:
                try:
                    server.close()
                except Exception:
                    pass

    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Transmits email payload via SMTP with dual-stack socket fallback and stage classification.
        """
        cfg = self.get_smtp_config()
        host = cfg["host"]
        port = cfg["port"]
        user = cfg["username"]
        password = cfg["password"]
        sender = cfg["email_from"]
        recipient = cfg["email_to"]

        # Stage 1: Config Validation
        if not host:
            return {"status": "failed", "stage": "CONFIG", "reason": "Missing SMTP_HOST configuration", "host": host, "port": port}
        if not user:
            return {"status": "failed", "stage": "CONFIG", "reason": "Missing SMTP_USER / SMTP_USERNAME configuration", "host": host, "port": port}
        if not password:
            return {"status": "failed", "stage": "CONFIG", "reason": "Missing SMTP_PASSWORD / SMTP_PASS configuration", "host": host, "port": port}

        # Stage 2: Pre-flight Socket Diagnostics
        connected_sock = None
        target_ip = host
        try:
            connected_sock, target_ip = self._dual_stack_connect(host, port, timeout=12.0)
            logger.info(f"SMTPEmailProvider: Pre-flight TCP connection established to {host}:{port} ({target_ip}).")
            connected_sock.close()
            connected_sock = None
        except Exception as tcp_err:
            logger.error(f"SMTPEmailProvider: TCP connection failed to {host}:{port}: {tcp_err}")
            return {
                "status": "failed",
                "stage": "TCP_CONNECT",
                "reason": f"Network is unreachable to {host}:{port} ({tcp_err})",
                "host": host,
                "port": port,
            }

        # Stage 3: Construct MIME Payload
        try:
            msg = MIMEMultipart("mixed") if attachments else MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            msg_id = f"<{uuid.uuid4()}@cyberscout.ai>"
            msg["Message-ID"] = msg_id

            if attachments:
                body_part = MIMEMultipart("alternative")
                body_part.attach(MIMEText(plain_content, "plain"))
                body_part.attach(MIMEText(html_content, "html"))
                msg.attach(body_part)

                for att in attachments:
                    path = Path(att)
                    if not path.exists():
                        continue
                    suffix = path.suffix.lower()
                    if suffix == ".docx":
                        maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif suffix == ".csv":
                        maintype, subtype = "text", "csv"
                    else:
                        mime_type, _ = mimetypes.guess_type(str(path))
                        maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))

                    try:
                        with open(path, "rb") as f:
                            part = MIMEBase(maintype, subtype)
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
                            msg.attach(part)
                    except Exception as att_err:
                        logger.warning(f"Could not attach '{path.name}': {att_err}")
            else:
                msg.attach(MIMEText(plain_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))
        except Exception as payload_err:
            return {"status": "failed", "stage": "MAIL_SEND", "reason": f"MIME construction failed: {payload_err}", "host": host, "port": port}

        # Stage 4: SMTP Handshake & Login
        server = None
        try:
            if cfg["ssl_enabled"] or port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                if cfg["tls_enabled"]:
                    server.starttls()
                    server.ehlo()

            if user and password:
                server.login(user, password)

            server.sendmail(sender, [recipient], msg.as_string())
            server.quit()
            logger.info(f"SMTPEmailProvider: Email successfully delivered to {recipient}. Message-ID: {msg_id}")

            return {
                "status": "success",
                "message_id": msg_id,
                "provider": self.provider_name,
                "host": host,
                "port": port,
                "recipient": recipient,
            }
        except smtplib.SMTPAuthenticationError as auth_err:
            reason_clean = auth_err.smtp_error.decode("utf-8", errors="ignore") if isinstance(auth_err.smtp_error, bytes) else str(auth_err.smtp_error)
            logger.error(f"SMTPEmailProvider: SMTP Authentication failed: {reason_clean}")
            return {"status": "failed", "stage": "SMTP_AUTH", "reason": f"SMTP Authentication failed: {reason_clean}", "host": host, "port": port}
        except Exception as send_err:
            logger.error(f"SMTPEmailProvider: Delivery failed on {host}:{port}: {send_err}")
            return {"status": "failed", "stage": "MAIL_SEND", "reason": f"SMTP transmission error: {send_err}", "host": host, "port": port}
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass
