# Source Registry

Each source below is documented with: **category, login requirement, RSS availability, recommended collection method, difficulty, and priority.**

Legend —
Difficulty: 🟢 Easy 🟡 Medium 🔴 Hard
Priority: P0 (build first) → P3 (nice to have, later)

---

## 1. Internships & Jobs

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| Internshala (internshala.com) | Internship | No (browse public) | No | Playwright (JS-rendered listings) | 🟡 Medium | P0 |
| LinkedIn Jobs | Internship/Job | Yes for full details | No | Public search results page scraping is fragile & ToS-sensitive; prefer RSS-to-job aggregators or manual saved-search email digests | 🔴 Hard | P2 |
| AngelList / Wellfound | Internship/Startup jobs | Partial | No | Playwright | 🟡 Medium | P2 |
| Indeed (India) | Internship/Job | No for search | Some regions have RSS | Requests + BeautifulSoup on public search | 🟡 Medium | P1 |
| Cisco Networking Academy Careers Board | Internship | No | No | Requests + BeautifulSoup | 🟢 Easy | P1 |
| Government internship portals (e.g., NIC, MyGov India) | Internship | No | No | Requests + BeautifulSoup | 🟢 Easy | P2 |

## 2. Free Courses & Certifications

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| TryHackMe (free rooms) | Course/Cert | No for public pages | No official RSS | Requests + BeautifulSoup on public room listing | 🟢 Easy | P0 |
| HackTheBox Academy (free modules) | Course/Cert | No for listing | No | Requests + BeautifulSoup | 🟢 Easy | P0 |
| PortSwigger Web Security Academy | Course/Cert | No | No | Requests + BeautifulSoup (fully free content, stable structure) | 🟢 Easy | P0 |
| Cisco Networking Academy (free courses) | Course/Cert | No for catalog | No | Requests + BeautifulSoup | 🟢 Easy | P1 |
| Coursera (filter: free/audit) | Course | No for catalog | No | Requests + BeautifulSoup (catalog pages are mostly static) | 🟡 Medium | P1 |
| edX | Course | No for catalog | No | Requests + BeautifulSoup | 🟡 Medium | P1 |
| Google Cybersecurity Certificate (Coursera-hosted) | Certification | No for info page | No | Requests + BeautifulSoup | 🟢 Easy | P1 |
| ISC2 free training / Certified in Cybersecurity (CC) promos | Certification | No for announcements | No | Requests + BeautifulSoup on news page | 🟢 Easy | P1 |
| freeCodeCamp | Course | No | Yes (blog RSS) | RSS | 🟢 Easy | P1 |
| Great Learning / Simplilearn free courses | Course | No for catalog | No | Requests + BeautifulSoup | 🟡 Medium | P2 |
| YouTube (structured playlists as "courses") | Course | No | Yes (channel RSS via `https://www.youtube.com/feeds/videos.xml?channel_id=`) | RSS | 🟢 Easy | P1 |

## 3. Hackathons & CTFs

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| CTFtime.org | CTF | No | Yes (iCal + JSON API, unofficial but public) | Public API (`https://ctftime.org/api/v1/events/`) | 🟢 Easy | P0 |
| picoCTF | CTF | No for announcements | No | Requests + BeautifulSoup | 🟢 Easy | P1 |
| Devpost (hackathons, filter security) | Hackathon | No for listing | No | Requests + BeautifulSoup | 🟡 Medium | P1 |
| MLH (Major League Hacking) | Hackathon | No | No | Requests + BeautifulSoup | 🟡 Medium | P2 |
| Unstop (formerly Dare2Compete) | Hackathon/Competition (India-focused) | No for listing | No | Requests + BeautifulSoup | 🟡 Medium | P1 |

## 4. Scholarships

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| WiCyS (Women in CyberSecurity) scholarships | Scholarship | No | No | Requests + BeautifulSoup | 🟢 Easy | P2 |
| (ISC)2 scholarship programs | Scholarship | No | No | Requests + BeautifulSoup | 🟢 Easy | P2 |
| SANS Cyber FastTrack / scholarship academies | Scholarship | No | No | Requests + BeautifulSoup | 🟡 Medium | P2 |

## 5. Webinars, Workshops, Conferences

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| OWASP local chapter event pages (Meetup-based) | Webinar/Workshop | No for listing | Meetup has RSS-like feeds via API | Meetup public API | 🟡 Medium | P2 |
| Cisco/Microsoft Learn Live Events | Webinar | No | No | Requests + BeautifulSoup | 🟡 Medium | P2 |
| DEFCON/Black Hat news pages (for conference dates) | Conference | No | No | Requests + BeautifulSoup, low frequency | 🟢 Easy | P3 |

## 6. News & Blogs

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| The Hacker News | News | No | **Yes** | RSS | 🟢 Easy | P0 |
| BleepingComputer | News | No | **Yes** | RSS | 🟢 Easy | P0 |
| KrebsOnSecurity | News | No | **Yes** | RSS | 🟢 Easy | P1 |
| Dark Reading | News | No | **Yes** | RSS | 🟢 Easy | P1 |
| Schneier on Security | News/Blog | No | **Yes** | RSS | 🟢 Easy | P2 |
| Google Project Zero blog | Research/News | No | **Yes** | RSS | 🟢 Easy | P2 |

## 7. GitHub (Repos & Tools)

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| GitHub Search API (topics: `pentesting`, `security-tools`, `ctf`) | Repository/Tool | Token recommended (free, higher rate limit) | No | GitHub REST API (free, 5000 req/hr authenticated) | 🟢 Easy | P0 |
| GitHub Trending (security category, unofficial page) | Repository | No | No official RSS, but static HTML | Requests + BeautifulSoup | 🟢 Easy | P1 |
| Awesome-lists (`awesome-security`, `awesome-pentest`) | Repository/Curated list | No | No | Requests + BeautifulSoup / raw README parse | 🟢 Easy | P1 |

## 8. YouTube Tutorials

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| John Hammond | Tutorial | No | Yes (channel RSS) | RSS | 🟢 Easy | P1 |
| NetworkChuck | Tutorial | No | Yes (channel RSS) | RSS | 🟢 Easy | P1 |
| David Bombal | Tutorial | No | Yes (channel RSS) | RSS | 🟢 Easy | P1 |
| IppSec (HTB walkthroughs) | Tutorial | No | Yes (channel RSS) | RSS | 🟢 Easy | P1 |
| The Cyber Mentor (TCM Security) | Tutorial | No | Yes (channel RSS) | RSS | 🟢 Easy | P2 |

## 9. Research Papers (Phase 10, future)

| Source | Category | Login? | RSS? | Method | Difficulty | Priority |
|---|---|---|---|---|---|---|
| arXiv (cs.CR category) | Research Paper | No | **Yes** | RSS (`http://export.arxiv.org/rss/cs.CR`) | 🟢 Easy | P3 |
| USENIX Security proceedings | Research Paper | No | No | Requests + BeautifulSoup, low frequency | 🟡 Medium | P3 |

---

## Notes on Legality & Ethics
- Prefer official RSS/APIs over scraping wherever they exist (marked above).
- Respect `robots.txt` and each site's Terms of Service; some sites (notably LinkedIn) actively prohibit scraping — for those, prefer manual saved-search alerts or RSS bridges rather than direct automation.
- Rate-limit all collectors; add a `User-Agent` identifying the bot and a contact method if the project goes public.
- GitHub API and CTFtime API are the most robust, ToS-friendly, free data sources — good anchors for Phase 3.
