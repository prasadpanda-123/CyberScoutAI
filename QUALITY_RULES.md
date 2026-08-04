# Quality Intelligence Rules Specification

This document details the exact rule definitions, keyword dictionaries, blacklists, and topic taxonomies used by the Quality Intelligence Engine (`src/intelligence/`).

---

## 1. Blacklist Term Rules (Stage 5 — Immediate Hard Rejection)

Any opportunity whose title, description, or payload contains any of the following terms is **immediately rejected** with `rejection_reason = "BLACKLIST_KEYWORD"` or `"PLAYLIST_DETECTED"`:

- **Streaming / IPTV**: `iptv`, `m3u`, `#extm3u`, `playlist`, `movie`, `tv channels`, `streaming channels`, `radio playlist`, `free movies`
- **Entertainment / Gaming**: `anime`, `music`, `spotify`, `netflix`
- **P2P / Piracy**: `torrent`, `warez`, `keygen`, `crack`, `serial`, `telegram dump`, `proxy list`, `ebook collection`
- **Commercial / Spam**: `coupon`, `promo code`, `discount`
- **Adult**: `adult`, `porn`

---

## 2. Approved Cybersecurity Topic Taxonomy (Stage 2)

GitHub repository topics are checked against:
`security`, `cybersecurity`, `ctf`, `owasp`, `pentesting`, `osint`, `forensics`, `malware`, `reverse-engineering`, `bug-bounty`, `red-team`, `blue-team`, `dfir`, `cloud-security`, `web-security`, `network-security`.

Repositories having topic metadata but **none** of these approved cybersecurity topics are flagged with `NO_SECURITY_TOPICS` and rejected under `INVALID_TOPIC`.

---

## 3. Approved Programming Languages & Markup Penalties (Stage 3)

- **Approved Languages**: `Python`, `Go`, `Rust`, `C`, `C++`, `Java`, `JavaScript`, `PowerShell`, `Bash`, `TypeScript`, `Shell`, `Lua`.
- **Markup / Non-Code Only**: `HTML`, `CSS`, `Markdown`. Repositories containing only markup or documentation files receive a confidence score penalty and flag `MARKUP_ONLY_LANG`.

---

## 4. Cybersecurity Keyword Taxonomy (Stage 4)

Positive keyword weighting matches domain terminology:
- **Foundational**: `OWASP`, `CVE`, `Exploit`, `Authentication`, `Authorization`, `SQL Injection`, `XSS`, `CSRF`
- **Operations & Platforms**: `SOC`, `SIEM`, `IDS`, `IPS`, `Threat Intelligence`, `Malware`, `Forensics`, `Incident Response`
- **Practice & Training**: `CTF`, `HackTheBox`, `TryHackMe`, `PortSwigger`, `Burp Suite`, `Nmap`, `Metasploit`, `Wireshark`
- **Detection & Defensive**: `YARA`, `Sigma`, `IOC`, `Detection`, `Blue Team`, `Red Team`, `DFIR`
