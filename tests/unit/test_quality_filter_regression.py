"""
Regression & Acceptance tests for CyberScout AI Quality Intelligence Engine (Tasks 9, 10, 11).
"""

import unittest
from src.intelligence.quality_engine import QualityEngine
from src.models.opportunity import Opportunity


class TestQualityFilterRegression(unittest.TestCase):
    def setUp(self):
        self.engine = QualityEngine()

    def test_negative_cases_100_percent_rejected(self):
        """Task 9: Negative regression cases must all be 100% rejected."""
        negative_samples = [
            # 1. IPTV Playlist
            Opportunity(
                title="#EXTM3U IPTV Playlist 2026",
                description="Live TV channels stream m3u8 playlist Indonesian channels sports movies.",
                url="https://example.com/playlist.m3u",
                source_id="generic_rss",
            ),
            # 2. Movie Repository
            Opportunity(
                title="Free 4K Movies HD Download Collection",
                description="Latest Hollywood movies dual audio 1080p full free download.",
                url="https://example.com/movies-hd",
                source_id="generic_rss",
            ),
            # 3. Anime Repository
            Opportunity(
                title="Watch Naruto Anime Series 1080p Episodes",
                description="Free anime streams subbed and dubbed download list.",
                url="https://example.com/anime-stream",
                source_id="generic_rss",
            ),
            # 4. Torrent Index
            Opportunity(
                title="The Pirate Bay Torrent Index Magnet Links",
                description="Full torrent list search engine for games and movies.",
                url="https://example.com/torrent-index",
                source_id="generic_rss",
            ),
            # 5. Proxy List
            Opportunity(
                title="Free HTTP SOCKS5 Proxy List 2026",
                description="Daily updated free proxy IP addresses list for scraping.",
                url="https://example.com/proxy-list",
                source_id="generic_rss",
            ),
            # 6. Spotify Downloader
            Opportunity(
                title="Spotify MP3 Music Downloader Script",
                description="Download high quality mp3 tracks directly from Spotify for free.",
                url="https://example.com/spotify-downloader",
                source_id="generic_rss",
            ),
            # 7. Netflix Downloader
            Opportunity(
                title="Free Netflix Account Generator and Stream Ripper",
                description="Get free premium Netflix accounts and download movies.",
                url="https://example.com/netflix-ripper",
                source_id="generic_rss",
            ),
            # 8. Crack Repository
            Opportunity(
                title="Windows 11 Activator Keygen Crack Repository",
                description="Full crack and serial key generator for software registration.",
                url="https://example.com/crack-repo",
                source_id="generic_rss",
            ),
            # 9. Keygen Repository
            Opportunity(
                title="Photoshop CC Keygen Serial Generator Software",
                description="Free software license keys and keygens.",
                url="https://example.com/keygen-download",
                source_id="generic_rss",
            ),
            # 10. Pirated Software
            Opportunity(
                title="Pirated Adobe Premiere Pro Warez Full Version",
                description="Cracked software collection warez release.",
                url="https://example.com/pirated-software",
                source_id="generic_rss",
            ),
        ]

        for sample in negative_samples:
            eval_opp = self.engine.evaluate_opportunity(sample)
            self.assertTrue(
                eval_opp.is_rejected,
                f"Negative test failed: '{sample.title}' was NOT rejected! Rejection reason: {eval_opp.rejection_reason}",
            )

    def test_positive_cases_100_percent_accepted(self):
        """Task 10: Genuine cybersecurity opportunities must all be accepted."""
        positive_samples = [
            # 1. OWASP
            Opportunity(
                title="OWASP Top 10 Web Application Security Vulnerabilities Guide",
                description="Comprehensive documentation of OWASP Top 10 web application security flaws including SQL Injection and XSS.",
                url="https://owasp.org/top10",
                source_id="owasp_official",
            ),
            # 2. PortSwigger
            Opportunity(
                title="PortSwigger Web Security Academy Authentication Labs",
                description="Hands-on labs learning OAuth authentication vulnerabilities and CSRF mitigation.",
                url="https://portswigger.net/web-security",
                source_id="portswigger_feed",
            ),
            # 3. HackTheBox
            Opportunity(
                title="HackTheBox Penetration Testing Challenge Writeups",
                description="Detailed penetration testing walkthroughs covering privilege escalation and Metasploit exploitation.",
                url="https://hackthebox.com/challenges",
                source_id="hackthebox_rss",
            ),
            # 4. TryHackMe
            Opportunity(
                title="TryHackMe SOC Analyst Learning Path",
                description="Interactive cybersecurity labs on SIEM log analysis, Wireshark packet analysis, and Incident Response.",
                url="https://tryhackme.com/path/soc",
                source_id="tryhackme_rss",
            ),
            # 5. GSoC Security
            Opportunity(
                title="Google Summer of Code Cybersecurity Internship 2026",
                description="Open source cybersecurity internship developing YARA rules and vulnerability scanning tools.",
                url="https://summerofcode.withgoogle.com/security",
                source_id="gsoc_official",
            ),
            # 6. Microsoft Security Internship
            Opportunity(
                title="Microsoft Security Engineering Internship 2026",
                description="Summer internship in cloud security architecture, threat intelligence, and DevSecOps.",
                url="https://careers.microsoft.com/security-intern",
                source_id="microsoft_jobs",
            ),
            # 7. PicoCTF
            Opportunity(
                title="PicoCTF Cybersecurity Competition 2026",
                description="Free high school and college CTF competition covering reverse engineering, cryptography, and forensics.",
                url="https://picoctf.org/competition",
                source_id="picoctf_official",
            ),
            # 8. CVE Advisory
            Opportunity(
                title="CVE-2026-1234 Critical Remote Code Execution Vulnerability",
                description="Critical vulnerability advisory in Linux kernel network stack allowing RCE.",
                url="https://cve.mitre.org/cve-2026-1234",
                source_id="cve_mitre",
            ),
            # 9. MITRE ATT&CK
            Opportunity(
                title="MITRE ATT&CK Framework Enterprise Technique Mapping",
                description="Updated threat intelligence matrix for adversary tactics, techniques, and procedures (TTPs).",
                url="https://attack.mitre.org/matrices/enterprise",
                source_id="mitre_attack",
            ),
            # 10. DFIR
            Opportunity(
                title="Digital Forensics and Incident Response (DFIR) Memory Analysis Tool",
                description="Python forensic tool for Volatility memory dump analysis and malware artifact extraction.",
                url="https://github.com/dfir-labs/volatility-analyzer",
                source_id="github_sec",
            ),
            # 11. YARA
            Opportunity(
                title="YARA Malware Signatures & Threat Hunting Rules",
                description="Open-source repository of YARA detection rules for ransomware and trojan malware families.",
                url="https://github.com/yara-rules/rules",
                source_id="github_sec",
            ),
            # 12. Sigma Rules
            Opportunity(
                title="Sigma Rules for SOC Log Analysis & Threat Detection",
                description="Generic log signature rules for detecting PowerShell empire and credential dumping.",
                url="https://github.com/SigmaHQ/sigma",
                source_id="github_sec",
            ),
            # 13. Detection Engineering
            Opportunity(
                title="Detection Engineering & SIEM Rule Repository",
                description="Advanced detection engineering repository for Splunk and Elastic SIEM detection rules.",
                url="https://github.com/detection-engineering/siem-rules",
                source_id="github_sec",
            ),
        ]

        for sample in positive_samples:
            eval_opp = self.engine.evaluate_opportunity(sample)
            self.assertFalse(
                eval_opp.is_rejected,
                f"Positive test failed: '{sample.title}' was unexpectedly rejected! Reason: {eval_opp.rejection_reason}",
            )


if __name__ == "__main__":
    unittest.main()
