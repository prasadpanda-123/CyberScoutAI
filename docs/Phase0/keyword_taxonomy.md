# Keyword Taxonomy

Organized hierarchically: **Domain → Subdomain → Keywords/Synonyms**. This taxonomy backs `config/keywords.yaml` and drives both search-query generation (Phase 2) and categorization/tagging (Phase 5).

---

## 1. Core Cybersecurity

### Offensive Security
- Penetration testing, pentest, pentesting
- Red team, red teaming
- Ethical hacking
- Exploit development
- Vulnerability research
- Social engineering
- Physical security testing

### Defensive Security
- Blue team
- SOC (Security Operations Center)
- SIEM (Splunk, QRadar, Sentinel, Elastic Security)
- Threat hunting
- Incident response, DFIR
- Digital forensics
- Malware analysis, reverse engineering
- Threat intelligence

### Purple Team & GRC
- Purple team
- Governance, Risk, Compliance (GRC)
- Risk assessment
- Security auditing
- Compliance frameworks (ISO 27001, NIST, PCI-DSS, SOC 2)

### Application & Web Security
- OWASP, OWASP Top 10
- Web application security
- Burp Suite
- API security
- Secure code review
- DevSecOps
- CI/CD security

### Network Security
- Nmap
- Wireshark
- Firewalls, IDS/IPS
- VPN
- Network segmentation
- Active Directory security
- Zero Trust

### Offensive Tooling
- Metasploit
- Cobalt Strike (awareness only — not for illegal use)
- Nessus, OpenVAS
- OSINT (Open Source Intelligence)
- Recon tools (theHarvester, Shodan, Maltego)

### Cloud Security
- Cloud Security, CSPM
- AWS Security, Azure Security, GCP Security
- Container security, Kubernetes security
- IAM (Identity & Access Management)
- Cloud misconfigurations

---

## 2. Supporting / Related Technical Domains

### Programming
- Python, C, C++, Java, Go, Rust
- Bash scripting, PowerShell
- Scripting for automation

### Networking
- TCP/IP, DNS, HTTP/HTTPS
- Linux, Windows Server
- CCNA, routing, switching
- Subnetting, VLANs

### Cloud & Infrastructure
- AWS, Azure, Google Cloud
- Docker, Kubernetes
- Infrastructure as Code (Terraform)

### Data & AI (adjacent, for cross-disciplinary opportunities)
- AI security / adversarial ML
- Data privacy engineering

---

## 3. Opportunity-Type Keywords (used to classify, not just search)
- internship, summer internship, winter internship, remote internship, paid internship
- fellowship, apprenticeship
- scholarship, grant
- free course, free certification, certification voucher, exam voucher
- hackathon, CTF, capture the flag, wargame
- webinar, workshop, bootcamp, training program
- conference, summit, meetup
- open source, GitHub repository, security tool release
- research paper, whitepaper, technical report

## 4. Qualifier Keywords (used by Processing/Ranking, not search)
- free, 100% free, no cost
- beginner-friendly, beginner, entry-level
- remote, work from home, virtual
- deadline, apply by, closing date
- certificate of completion, certification included
- limited seats, limited time, early bird

## 5. Provider / Brand Keywords (used for "recognized provider" ranking bonus)
- TryHackMe, HackTheBox, PortSwigger, Cisco, Microsoft, Google, AWS, CompTIA, EC-Council, Offensive Security (OffSec), SANS, GIAC, ISC2, CNCF

## 6. Synonym Mapping (normalize during Processing phase)
| Canonical | Synonyms |
|---|---|
| internship | intern program, internship opportunity, summer intern |
| certification | cert, certificate program, credentialing |
| free | no-cost, complimentary, zero-cost |
| CTF | capture the flag, wargame, hacking challenge |
| hackathon | hack event, coding challenge (security-flavored only) |
| red team | offensive security team, attacker simulation |
| blue team | defensive security team, SOC team |

---

## Usage Note
This taxonomy is intentionally broader than "pure cybersecurity" per the original project scope — programming, networking, and cloud keywords exist because many internships/courses are labeled under those umbrella terms even when security-relevant. The **Ranking Engine** (Phase 5/7) is what filters signal from noise, not the taxonomy itself — the taxonomy should stay broad and inclusive; over-filtering here would cause false negatives (missed opportunities).
