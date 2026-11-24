# NZ employer and job research sources: access, cost, and terms (as of Nov 2026)

Scope: sources a personal job-prep agent (about 30 jobs/day, NZ$5-10/month total) may call for a NZ employer and a job. Prices are from vendor pages fetched during this run. Items marked UNVERIFIED were not confirmed from a fetched source.

## Summary for the builder

| Source | Use? | Cost at ~900 jobs/month | Main constraint |
|---|---|---|---|
| Google Places API (New) | Yes, with field-mask discipline | Likely $0 if each job uses 1 Text Search + 1 Details call on Pro fields (under free caps) | Field-to-SKU mapping; caching/display terms (UNVERIFIED) |
| Companies Office / NZBN (MBIE API portal) | Yes, if a subscription is obtained | Unknown (not published on the pages fetched) | Response schema and terms not retrieved |
| Brave Search API | Yes | $5 monthly credit covers about 1,000 queries | Web-wide index, weaker on small NZ firms |
| Exa | Optional | About $3.60 USD for 900 "lite" searches | Paid after $10 starter credit |
| Tavily | Optional | 1,000 free credits/month; paid rate per credit $0.008 (PAYG) | Credit cost per search not confirmed on the page |
| Jina Reader | Yes, for page text of company's own site | Free basic use, no key; key gives 10M free tokens | Token pricing table not retrieved |
| Claude web search tool | Only for small volume | $10 USD per 1,000 searches plus tokens; about $9 USD for 900 searches (about NZ$15+) | Exceeds NZ$10 cap at 1 search/job |
| SEEK, LinkedIn, Indeed, Glassdoor | Never scrape or automate | n/a | Terms prohibit automated access (LinkedIn confirmed; others not retrieved) |

Budget implication: a 900-job month at 5-20 web lookups per job is 4,500-18,000 search calls. That is beyond the NZ$5-10 budget on any paid search API. The agent should cap general web search to about 1 call per job, use Google Places and direct company-website fetches for the rest, and cache per employer (one lookup per company, not per job).

## 1. NZ Companies Office and NZBN (MBIE API portal)

Key question: what do the APIs return?

### Takeaway
The portal lists Companies Office and NZBN API groups, but the pages fetched name no endpoints, response fields, rate limits or terms. Field-level claims (directors, shareholders, addresses, ANZSIC codes, contacts) cannot be sourced from this run.

### Cited Findings
- The MBIE API portal home page describes "a diverse range of APIs for connecting directly to various government services and information sources" and links to "Explore APIs", "Getting started", "Copyright" and "Privacy" pages — [MBIE API portal](https://portal.api.business.govt.nz)
- The Explore APIs page has tiles for "Companies" (tag CompaniesOffice) and "NZBN" (tag NZBN). Access is "Explore the API documentation and subscribe to gain access." — [Explore APIs](https://portal.api.business.govt.nz/explore-apis)
- Insolvency and PPSR registers are also listed; the page does not say whether they cover businesses — [Explore APIs](https://portal.api.business.govt.nz/explore-apis)

### Inferences
- Access is by subscription (a developer account on the portal), so an API key is likely needed. This is an inference from "subscribe to gain access".
- The NZBN and Companies Office data are public registers. Directors and shareholder details are public register data, but whether the API exposes them, and under what terms, is not confirmed.

### Gaps
- Endpoint list, response format and field names, rate limits, and the portal's terms of use were not retrieved. Next step: create a free portal account, read the Companies Office and NZBN API docs, and record exact fields and limits before the builder designs against them.
- The public NZBN/Companies Office web search pages (not the API) are a possible fallback but were not checked for terms.

## 2. Google Places API (New)

Key question: which fields help, and what do they cost?

### Takeaway
Places API (New) gives a free monthly cap per SKU, then per-1,000 pricing by volume tier. At 900 jobs a month, one Text Search and one Place Details call per job (Pro-level fields) should stay under the free caps. Field-to-SKU mapping and storage terms still need checking.

### Cited Findings
- Text Search (New) SKUs: Essentials (IDs Only), Pro, Enterprise, Enterprise + Atmosphere. Place Details (New) SKUs: Essentials (IDs Only), Essentials, Pro, Enterprise, Enterprise + Atmosphere, Photos — [Places usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)
- Billing rule: "You are then billed at the highest SKU applicable to your request." Requesting one Pro field bills the whole request at Pro — [Places usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)
- Per-1,000 prices and monthly free caps (tier 1, up to 100k calls/month; from the Google Maps Platform pricing list):
  - Text Search Pro: free cap 5,000/month; $32.00 per 1,000 up to 100k
  - Text Search Enterprise: free cap 1,000; $35.00
  - Place Details Essentials: free cap 10,000; $5.00
  - Place Details Pro: free cap 5,000; $17.00
  - Place Details Enterprise: free cap 1,000; $20.00
  - Place Details Enterprise + Atmosphere: free cap 1,000; $25.00
  - Place Details Photos: free cap 1,000; $7.00
  — [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing.md.txt). The fetched copy shows no date. The older "$200 monthly credit" model is not on this page; free usage is per-SKU caps. Confirm on the live page before building.
- Volume tiers are summed across all projects on the billing account — [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing.md.txt)

### Inferences
- At about 900 Place Details calls a month on Pro, usage is within the 5,000 Pro free cap. Using Enterprise fields (for example reviews, if Enterprise-tier) would be 900 calls within a 1,000 cap, so it is still free at this volume but has little headroom. Keep the total under the cap with a counter.
- Estimated cost for 900 jobs with one Text Search (Pro) and one Details (Pro): $0 under free caps. Going over 5,000 Pro calls in a month costs about $32 and $17 per 1,000 respectively.

### Gaps
- Which fields map to which SKU (reviews, rating, editorialSummary, regularOpeningHours, websiteUri, photos) was not retrieved from the SKU detail page. My recollection is that reviews and editorialSummary sit in Enterprise and rating/hours/website in Pro, but this is UNVERIFIED. Check the Places SKU details page before writing the field mask.
- Google Maps Platform terms on storing or displaying Places content (caching limits, attribution, display requirements) were not retrieved. My recollection is that place IDs may be stored longer than other content, and other fields may need refreshing and attribution. UNVERIFIED. Build the agent to cache only place IDs and to show results to the user without redistributing them.

## 3. Web search and reader APIs

### Takeaway
Brave's $5 monthly credit is the cheapest general search at this volume. Exa and Tavily are workable options. Jina Reader is free for page text and needs no key. None of them is a reliable source for small NZ firms on its own; the company's own website and the Places listing are better first sources.

### Cited Findings
- Brave Search API: $5 in free credits every month; Search plan at $5 per 1,000 requests; 50 queries per second — [Brave Search API](https://brave.com/search/api/). Note the page header also says "up to $20 in free calls", which conflicts with the $5 credit shown; confirm.
- Exa: Starter plan includes $10 credit (up to 2,500 Lite searches) with no card; then Search lite $4 per 1,000, auto/fast $7 per 1,000; contents $1 per 1,000 pages — [Exa pricing](https://exa.ai/pricing)
- Tavily: Free plan "1,000 API credits / month", no card. Pay As You Go $0.008 per credit. Project plan $30/month for 4,000 credits. Credit cost per search/extract was not stated on the page — [Tavily pricing](https://tavily.com/pricing)
- Jina Reader: each new API key includes 10M free tokens; Reader works without a key for basic use by prefixing `https://r.jina.ai/`. Rate limits: 20 RPM without key; 500 RPM with free key (a FAQ elsewhere on the page says 100 RPM free, which conflicts). Search (`s.jina.ai`) needs a key — [Jina Reader](https://jina.ai/reader/). Reader token pricing per million was not retrieved.

### Inferences
- At 900 searches a month: Brave is about $4.50 USD after the $5 credit (roughly covered); Exa lite is about $3.60 USD; Tavily uses about 900 credits, inside the free 1,000 if one credit per search. All fit within NZ$10 if kept to one search per job.
- Jina Reader is the cheapest way to pull text from a company's own website, since it costs tokens only and the free 10M tokens cover many pages.

### Gaps
- Tavily credit cost per basic search and per extract was not confirmed; check the docs before budgeting.
- Jina token price per million and the Reader token count per page were not retrieved.
- Quality for small NZ employers was not tested. Expect company-website and Places results to be more reliable than general search.

## 4. Claude server-side web search and web fetch

### Takeaway
Claude's web search costs $10 USD per 1,000 searches, plus tokens for results. At 900 searches a month that is about $9 USD (roughly NZ$15-16), which is over the NZ$10 cap. It is only sensible for a handful of searches a week. Web fetch pricing was not confirmed.

### Cited Findings
- Claude API web search: "$10 USD per 1,000 searches, plus standard token costs for search-generated content." Each search counts as one use regardless of results; failed searches are not billed. Search results count as input tokens in later turns — [Claude web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- `max_uses` caps searches per turn; `allowed_domains` / `blocked_domains` limit sources — [Claude web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- Web search is available on Claude Haiku 5.5 and other current models — [Claude web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

### Inferences
- Token costs for result content can be significant. Searching 5-20 times per job would cost $0.05-$0.20 per job in search fees alone, plus tokens. That is far above the budget. Use Claude search only if the other sources fail.

### Gaps
- Web fetch tool price and the token cost per fetched page were not retrieved (the fetch docs page was not fetched). Check `platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool` before comparing.
- A direct cost comparison with Tavily plus Jina for 5-20 lookups per job is approximate: Tavily and Jina together run about $0 at this volume under free tiers, while Claude search costs about $0.01 per search before tokens.

## 5. Sources the agent must avoid or treat carefully

### Takeaway
Do not automate SEEK, LinkedIn, Indeed or Glassdoor. LinkedIn's terms explicitly prohibit scraping, bots, and third-party collection of its data, so the agent must not call LinkedIn, even via a search API, for profile data. SEEK, Indeed and Glassdoor terms were not retrieved in this run (fetches failed), so the restriction rests on the builder's own rule.

### Cited Findings
- LinkedIn User Agreement (effective 3 Nov 2025), section 8.2: prohibits developing or using "software, devices, scripts, robots or any other means or processes" to scrape or copy the Services; prohibits "bots or other unauthorized automated methods to access the Services"; prohibits scraping "profiles and other data from the Services"; prohibits bypassing "access controls or use limits"; prohibits copying or using content "whether directly or through third parties (such as search tools or data aggregators or brokers)" without consent — [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement)
- LinkedIn section 2.2: users may not sell or transfer others' personal data — [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement)
- SEEK NZ terms: the `seek.co.nz/terms-and-conditions` URL redirects to `nz.seek.com/terms-and-conditions`; the redirected page was not fetched — NOT VERIFIED.
- Indeed user agreement: fetch returned HTTP 404 — NOT VERIFIED.
- Glassdoor terms: fetch returned HTTP 403 — NOT VERIFIED.
- Privacy Act 2020, IPP 2: "If an agency collects personal information, the information must be collected from the individual concerned." Exceptions include (d) "that the information is publicly available information" — [OPC IPP 2](https://www.privacy.org.nz/privacy-act-2020/privacy-principles/2/). The OPC guidance notes that a public source does not automatically count as a "publicly available publication" (case note on district council records).

### Inferences
- Even a single user-supplied LinkedIn or SEEK link should not be fetched by the agent. The user can read it. The agent should not fetch it on the user's behalf, since the terms restrict automated access and the "through third parties" clause covers search tools.
- Under IPP 2(2)(d), collecting a hiring manager's details from public sources may be allowed where the information is "publicly available", but this is a judgment and the OPC notes public availability is not automatic. A conservative reading for the tool:
  - Use only the hiring manager's business role and business contact details that the employer publishes (company website, official listing).
  - Do not collect home addresses, personal social media, family details, or anything beyond what the job application needs.
  - Do not build profiles or store them beyond the application.
  - Do not use LinkedIn-derived details, since their collection is prohibited by LinkedIn's terms regardless of privacy law.
  - Keep a note of the source and date for any personal detail, and delete it when the application closes.
- This is not legal advice. The builder should treat the rule as "business-role information from employer-published sources only".

### Gaps
- SEEK NZ, Indeed and Glassdoor terms were not retrieved. Fetch them before relying on a stance other than "do not automate".
- IPP 1 and IPP 3 full text was not retrieved (only titles). IPP 3 requires telling the person what is collected and why when collecting directly; indirect collection is covered by IPP 2 exceptions.
- No OPC guidance specifically on hiring managers was found in this run.

## 6. NZ salary data for pay ranges

### Takeaway
Stats NZ publishes an occupation-level earnings table from the Household Labour Force Survey (ANZSCO 2006, by sex, age and ethnicity). It is a national, annual-ish median/mean at occupation level, not by region. An industry-level hourly earnings series from the Quarterly Employment Survey covers employer-reported data. Region-level pay for a role is not available from these; agency salary guides and job-posting data are the next step, but were not checked.

### Cited Findings
- Stats NZ dataset: "Earnings from main wage and salary job by occupation (ANZSCO 2006), sex, age group, and ethnic group", from the Household Labour Force Survey; latest version listed is June 2025 (released 27 Aug 2025), with a 2009–2026 version also listed — [figure.nz mirror of Stats NZ table](https://figure.nz/table/tANdfeZpRDSl8UII). Figure.nz is a mirror; the official download is Stats NZ InfoShare (infoshare.stats.govt.nz) — not confirmed by table code.
- Average hourly earnings are total hourly earnings from main job divided by the number of wage and salary earners — same source.
- Quarterly Employment Survey: "Employment - Average hourly earnings by industry and sex 1989 Q1–2026 Q2" — [figure.nz mirror](https://figure.nz/table/DqnS5qj2ILILPoWj). Employer-reported, by industry, not occupation.

### Inferences
- The occupation table is a credible national baseline for a role family (for example "professionals" or "labourers"), not a precise pay range for one job in one city. Use it as a sanity check, not a figure to quote.
- Region-level pay would need a different source (for example Seek salary insights, recruiter salary guides, or the employer's own published range). Seek salary insights were not checked; do not scrape them.

### Gaps
- Stats NZ official table codes and InfoShare paths were not confirmed.
- Seek salary insights, recruiter guides (for example Hays, Robert Walters NZ) and their terms were not researched.
- Regional breakdown by occupation: not confirmed available.

## Recommended allowed-source list for the agent (draft)

1. Google Places API (New): Text Search + Place Details, Pro-tier fields only, with a monthly counter under the free caps. Cache place IDs.
2. Companies Office / NZBN API, once the subscription and schema are confirmed. Business-level fields only.
3. The employer's own website, fetched through Jina Reader or direct HTTP with robots.txt respected.
4. One general web search per job via Brave (or Exa or Tavily if Brave is unsuitable), capped at about 900 calls a month.
5. Stats NZ occupation earnings table for national pay baselines.

Blocked: SEEK, LinkedIn, Indeed, Glassdoor (and any URL the user pastes from them); scraping of any page behind login; personal details beyond business role and employer-published contact info.

## Open items before building
- Read the Companies Office and NZBN API docs on the MBIE portal (requires a free account).
- Confirm Google Places SKU field mapping and storage/display terms.
- Fetch the Tavily credit docs, the Jina Reader token price, and the Claude web fetch pricing.
- Fetch SEEK NZ (nz.seek.com/terms-and-conditions), Indeed and Glassdoor terms to record them directly.
- Check the IPP 3 text on privacy.org.nz.
