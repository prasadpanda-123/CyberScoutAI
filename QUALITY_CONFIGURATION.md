# Quality Engine Configuration (`config/quality.yaml`)

This document explains the YAML configuration options available in `config/quality.yaml`.

---

## Configuration Schema

```yaml
minimum_confidence: 50.0
minimum_keyword_score: 10.0
minimum_topic_score: 0.0
spam_threshold: 40.0
duplicate_threshold: 0.85

approved_languages:
  - Python
  - Go
  - Rust
  - C
  - C++
  - Java
  - JavaScript
  - PowerShell
  - Bash
  - TypeScript
  - Shell
  - Lua

approved_topics:
  - security
  - cybersecurity
  - ctf
  - owasp
  - pentesting
  - osint
  - forensics
  - malware
  - reverse-engineering
  - bug-bounty
  - red-team
  - blue-team
  - dfir
  - cloud-security
  - web-security
  - network-security

blacklist_keywords:
  - iptv
  - m3u
  - playlist
  - movie
  - anime
  - music
  - spotify
  - netflix
  - telegram dump
  - proxy list
  - adult
  - porn
  - warez
  - keygen
  - crack
  - serial
  - coupon
  - ebook collection
  - torrent
  - free movies
  - streaming channels
  - radio playlist
  - TV channels
  - "#EXTM3U"

quality_weights:
  source_trust: 0.25
  keyword_relevance: 0.35
  topic_match: 0.20
  structural_completeness: 0.20
```

All parameters can be modified dynamically without code changes.
