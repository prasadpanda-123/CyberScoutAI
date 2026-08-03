# Search Query Templates

Reusable, parameterized templates the Search Intelligence Layer (Phase 2) will fill in using `keywords.yaml`. Placeholders use `{curly_braces}`.

---

## 1. GitHub Search API Templates

Base endpoint: `https://api.github.com/search/repositories`

```
q=topic:{keyword}+pushed:>{date_30_days_ago}&sort=updated&order=desc
q={keyword}+in:name,description+topic:security&sort=stars&order=desc
q=topic:ctf+topic:writeups&sort=updated&order=desc
q=topic:pentesting+topic:tools&sort=stars&order=desc
```

Examples with real keywords:
- `topic:osint pushed:>2026-07-01`
- `owasp+in:name,description+topic:security`
- `topic:red-team+topic:active-directory`

## 2. Google-style Dork Templates (for Requests+BeautifulSoup against Google/Bing result pages — use sparingly, respect ToS; prefer as a fallback discovery layer, not a daily collector)

```
site:{domain} "{keyword}" "free" ("internship" OR "course" OR "certification")
"{keyword}" "apply now" "deadline" site:{domain}
"{keyword}" "scholarship" 2026 site:{domain}
"{keyword}" ctf 2026 register
```

## 3. RSS-based Sources — No query needed, just feed URLs
```
https://feeds.feedburner.com/TheHackersNews
https://www.bleepingcomputer.com/feed/
https://krebsonsecurity.com/feed/
https://www.darkreading.com/rss.xml
https://www.schneier.com/feed/atom/
https://googleprojectzero.blogspot.com/feeds/posts/default
https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}
http://export.arxiv.org/rss/cs.CR
```

## 4. CTFtime API Template
```
GET https://ctftime.org/api/v1/events/?limit=30&start={unix_start}&finish={unix_finish}
```

## 5. Site-Search Templates (internal search boxes)

**TryHackMe** (public room listing, filter client-side after fetch):
```
https://tryhackme.com/hacktivities?tab=all&difficulty=&type=free
```

**HackTheBox Academy** (public module catalog):
```
https://academy.hackthebox.com/catalogue
```

**PortSwigger Academy** (topic index, fully static):
```
https://portswigger.net/web-security/all-topics
```

**Cisco Networking Academy** (course catalog):
```
https://www.netacad.com/courses/all-courses?free=true
```

**Coursera** (search with free/audit filter param):
```
https://www.coursera.org/search?query={keyword}&productDifficultyLevel=Beginner&price=Free
```

**Unstop** (competitions, category=cybersecurity):
```
https://unstop.com/hackathons?category=cybersecurity
```

**Devpost** (challenges, filter by tag):
```
https://devpost.com/hackathons?challenge_type[]=online&search={keyword}
```

## 6. Query Construction Rule (used by `search.build_queries` in Phase 2)
For every `(source, keyword)` pair where the source is a **search-driven** source (not a fixed catalog/RSS page), the builder should:
1. Pull the source's `query_template` from `sources.yaml`
2. Substitute keywords from `keywords.yaml`
3. Apply date-window substitution where relevant
4. Emit a deduplicated list of concrete URLs/API calls for the Collector layer to fetch

## 7. Rate-Limiting Defaults
- GitHub API: max 30 requests/run (well under the 5000/hr authenticated limit)
- RSS feeds: 1 fetch per feed per run, no query needed
- HTML catalog pages: 1 fetch per source per run unless paginated (max 3 pages)
- Google/Bing dork fallback: disabled by default; only enabled manually, max 5 queries/run, with delay ≥10s between requests
