# Feasibility Matrix

Scoring each source on 4 dimensions (1–5, 5 = best) to produce a **Feasibility Score** used to sequence Phase 3 collector development.

**Dimensions:**
- **Stability** — how likely the HTML/API structure stays unchanged
- **Legality/ToS risk** — 5 = fully sanctioned (API/RSS), 1 = high scraping risk
- **Implementation effort** — 5 = trivial, 1 = very hard (JS-heavy, anti-bot)
- **Data richness** — how much of our shared schema the source naturally fills

`Feasibility Score = (Stability + Legality + Effort + Richness) / 4`

| Source | Stability | Legality | Effort | Richness | Score | Verdict |
|---|---|---|---|---|---|---|
| GitHub Search API | 5 | 5 | 5 | 4 | **4.75** | Build first |
| CTFtime API | 5 | 5 | 5 | 4 | **4.75** | Build first |
| The Hacker News RSS | 5 | 5 | 5 | 3 | **4.5** | Build first |
| BleepingComputer RSS | 5 | 5 | 5 | 3 | **4.5** | Build first |
| PortSwigger Academy | 4 | 4 | 4 | 4 | **4.0** | Build early |
| TryHackMe (free rooms page) | 3 | 4 | 4 | 4 | **3.75** | Build early |
| HackTheBox Academy (free modules) | 3 | 4 | 4 | 4 | **3.75** | Build early |
| YouTube channel RSS (per channel) | 5 | 5 | 5 | 2 | **4.25** | Build early |
| arXiv cs.CR RSS | 5 | 5 | 5 | 3 | **4.5** | Phase 10 |
| Awesome-lists (README parsing) | 4 | 5 | 4 | 3 | **4.0** | Build early |
| Cisco Networking Academy catalog | 3 | 4 | 3 | 4 | **3.5** | Medium |
| Coursera (audit/free filter) | 3 | 3 | 3 | 4 | **3.25** | Medium |
| edX | 3 | 3 | 3 | 4 | **3.25** | Medium |
| Unstop | 3 | 3 | 3 | 4 | **3.25** | Medium |
| Devpost | 3 | 3 | 3 | 4 | **3.25** | Medium |
| Internshala | 2 | 3 | 2 | 5 | **3.0** | Medium (needs Playwright) |
| Indeed | 2 | 3 | 2 | 4 | **2.75** | Medium |
| Meetup API (OWASP chapters) | 3 | 4 | 3 | 3 | **3.25** | Medium |
| WiCyS / (ISC)2 scholarships | 3 | 4 | 3 | 3 | **3.25** | Later |
| LinkedIn Jobs | 1 | 1 | 1 | 5 | **2.0** | Avoid direct scraping; use alerts/RSS bridges only |
| AngelList/Wellfound | 2 | 2 | 2 | 4 | **2.5** | Later |

## Reading the Table
- Everything scoring **≥4.0** should be a Phase 3 collector candidate for the first sprint.
- Sources scoring **≤2.5** (LinkedIn especially) should **not** be scraped directly — legal/ToS risk is too high relative to benefit for a personal open-source project. Use email digest subscriptions or RSS-bridge services instead, or skip.
- "Effort" scores assume Requests+BeautifulSoup as baseline; anything needing Playwright (JS rendering, infinite scroll, login walls) automatically loses 1–2 points here.
