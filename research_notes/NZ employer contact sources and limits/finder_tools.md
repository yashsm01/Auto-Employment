# People-data and email-finder tools: sourcing, accuracy, terms, and NZ legal risk

Research date: 2026-11-27. Method: web search snippets and secondary coverage only. No vendor or LinkedIn pages were fetched directly, so vendor claims below are as relayed by search results and are flagged where unverified. Items marked "unverified" were not confirmed against a primary source.

## 1. How each tool gets its data, accuracy, pricing, and API

### Takeaway
Hunter.io is mainly a public-web crawler plus pattern guessing and SMTP verification. Apollo, RocketReach, Lusha, ZoomInfo and Snov.io mix public-web and third-party sourcing with, in some cases, LinkedIn-derived or user-contributed data. Independent accuracy evidence is thin and conflicting. Vendor "accuracy" claims (90-98%) are not supported by the independent tests found. Expect a large share of returned addresses to be wrong or to bounce.

### Cited Findings

**Hunter.io**
- Crawls public web pages (vendor claims 30M pages/day, 650M public sources) and detects per-domain email patterns such as {first}.{last}@company.com; Email Finder results are labelled "guesses" or "publicly sourced" — [Hunter help: how emails are found](https://help.hunter.io/en/articles/1922677-how-does-hunter-find-the-email-addresses-returned-in-the-domain-search); [Hunter help: publicly sourced](https://help.hunter.io/en/articles/2085802-are-the-emails-found-in-the-email-finder-publicly-sourced); [Hunter data platform](https://hunter.io/data-platform)
- Email Verifier runs SMTP and deliverability checks in bulk; some mail servers block verification, so results are probabilistic — [Hunter API docs](https://hunter.io/api-documentation/v1)
- Webmail domains are excluded; sources not reviewed for six months are removed — [Hunter help](https://help.hunter.io/en/articles/15921145-faqs-about-finding-emails-in-hunter)
- Accuracy: Anymail Finder's Sept 2025 benchmark (run by a competitor, 5,000 contacts) gave Hunter a 37.6% verified rate; a separate 200-profile test gave 85% valid; Hunter's "more than 95% of valid addresses will not bounce" is a vendor claim, not independent — [Anymail Finder benchmark](https://anymailfinder.com/email-finder-benchmark); [Instantly, May 2026](https://instantly.ai/blog/email-finder-accuracy-bounce-risk/); [ZoomInfo Pipeline review](https://pipeline.zoominfo.com/sales/hunter-io-review)
- Pricing: free plan currently 50 credits/month per a 2026 third-party snapshot; older sources say 25 searches/month (outdated, from the Feb 2021 update). Free plan described as "free forever" in Hunter help — [Hunter plans](https://hunter.io/pricing); [Hunter help: plans overview](https://help.hunter.io/en/articles/6001212-plans-overview); [Dupple 2026 guide](https://dupple.com/learn/hunter-io-pricing). Conflicting figures; verify on the official page.
- API: available (v1 documented) — [Hunter API docs](https://hunter.io/api-documentation/v1)

**Apollo.io**
- Sourcing: the 2018 incident (see section 2) showed a database of scraped/aggregated profiles. Current sourcing methodology was not confirmed in this research (gap).
- Accuracy: an r/coldemail test reported bounce rates of roughly 28-38% depending on tool, with Apollo near 32-38% (anecdotal, Reddit); Anymail's benchmark put Apollo's coverage at 29% vs 52% for Anymail — [Prospeo roundup](https://prospeo.io/s/email-finder-comparison) (secondary); [Anymail benchmark](https://anymailfinder.com/email-finder-benchmark)
- Pricing (2026, secondary sources): Free, then about $49, $79, $119 per user/month on annual billing (Basic, Professional, Organization); monthly billing about 15-25% higher. Free-plan credit allowance conflicts across sources (900 credits/year vs 10,000 email credits/month). Credits expire — [Docket/Apollo pricing](https://docket.io/resources/research/apollo-pricing); [Markaicode, Nov 2026](https://markaicode.com/pricing/apollo-io-pricing/); [Fullenrich](https://fullenrich.com/content/apollo-pricing). Verify on apollo.io/pricing.
- API: Not verified in this research (gap).

**RocketReach**
- Sourcing per secondary sources: public websites, professional profiles, company pages, social media, third-party data providers. Security.org says it continuously scrapes public sources such as LinkedIn and company websites (secondary, unverified against its own policy) — [Bitdefender](https://www.bitdefender.com/en-au/blog/hotforsecurity/control-your-privacy-series-what-is-rocketreach-and-what-are-your-opt-out-options); [Security.org opt-out page](https://www.security.org/data-removal/opt-out/rocketreach/)
- Accuracy: an independent audit reported a 29.8% hit rate, against published 90-98% accuracy claims; a separate benchmark (aiagenix) had it at 74% — as relayed in search results (the audit's identity and method were not confirmed).
- Pricing and API: not researched (gap).

**Lusha**
- The extension, per a G2 user discussion, reads limited information visible on the page the user is viewing (for example name and employer) and matches it against Lusha's backend — [G2 discussion](https://www.g2.com/discussions/privacy-edebedaf-da29-4e8d-84da-0b488c2d14e3); [Lusha extension overview](https://docs.lusha.com/user-guide/extension/extension-overview)
- A "contributor network" or address-book harvesting by Lusha was NOT confirmed by any search result. Treat as unverified; do not assume it.
- Compliance claims (per G2 listing): GDPR/CCPA compliant, ISO 27701, SOC 2 Type II — [G2 Lusha AI listing](https://ai.g2.com/marketplace/tools/lusha) (vendor-supplied claims)
- Pricing and API: not researched (gap).

**ZoomInfo (Community Edition, now "ZoomInfo Lite")**
- Free access to the database in exchange for users installing the ZoomInfo Contact Contributor or granting access to their business email. ZoomInfo says it collects name, email, job title and department, and phone numbers, extracted from email headers, signature blocks and contact books, and that the on-device parser does not send message bodies. The on-device claim is unaudited in the results found — [ZoomInfo CE page](https://www.zoominfo.com/ce); [ZoomInfo privacy policy](https://zoominfo.com/legal/privacy-policy); [ZoomInfo trust center](https://www.zoominfo.com/trust-center/misconceptions)
- An older InformationWeek report described an earlier Outlook plug-in as pulling address-book and signature data — [InformationWeek](https://www.informationweek.com:443/it-sectors/zoominfo-plug-in-siphons-contacts-from-outlook)
- Accuracy and pricing: not researched in detail (gap).

**Snov.io**
- Benchmark: 20.1% verified rate in a 5,000-contact test (as relayed by a secondary source; methodology caveats noted) — [Prospeo comparison](https://prospeo.io/s/email-finder-comparison) (secondary)
- Sourcing, pricing (free tier listed as 75 credits/seat/month in one table) and API: not verified (gap). Free-tier figure from [Snov.io pricing blog](https://snov.io/blog/?p=62273), secondary.

### Inferences
- Pattern-guessing plus SMTP verification (Hunter-style) has a structural accuracy ceiling: many mail servers accept all addresses (catch-all), and SMTP "accepted" does not prove a live mailbox.
- Any figure above from a vendor, or from a competitor's benchmark, should be treated as directional. The spread across benchmarks (Hunter 37.6% to 85%) shows the test design dominates the result.
- Contributor/extension-based tools (ZoomInfo CE, possibly others) carry a higher legal and reputational risk than crawl-based ones, because the data is obtained from third parties' inboxes.

### Gaps
- Apollo, RocketReach, Lusha, Snov.io and ZoomInfo: current privacy policies, GDPR/CCPA statements, opt-out procedures, and API terms were not fetched.
- Apollo's current sourcing method and API availability were not confirmed.
- No independent, methodologically sound benchmark covering all six tools was found.

---

## 2. Terms, privacy positions, regulatory actions and lawsuits

### Takeaway
Regulators and courts have acted against this sector, mainly on notice, lawful basis and consent. The Italian Garante fined Lusha EUR 2 million in July 2026 and ordered erasure of Italian data. ZoomInfo faced several privacy class actions, with most claims dismissed in 2024 and a $30M settlement in the Ramos case. Apollo's 2018 exposure was a publicly accessible unsecured database. RocketReach has reportedly drawn GDPR complaints (unverified).

### Cited Findings

**Lusha, Italy (Garante)**
- The Garante opened an investigation on 8 April 2025 and on 14 July 2026 fined Lusha Systems EUR 2 million for unlawful processing of contact data; it held that GDPR applies to a non-EU company because continuous collection and updating of professional profiles amounts to monitoring; it prohibited processing of data on people located in Italy and ordered erasure — [Digital Policy Alert](https://digitalpolicyalert.org/event/42272-data-protection-authority-fined-lusha-systems-eur-2-million-for-unauthorised-processing-of-contact-data); [CyberInsider](https://cyberinsider.com/italy-fines-us-data-broker-lusha-e2-million-over-unlawful-data-collection/); [GRC Report](https://www.grcreport.com/post/italy-fines-lusha-eu2-million-says-data-brokers-business-crossed-into-gdpr-monitoring)
- Sources differ on the basis: MLex describes unlawful collection of names and contact details via platforms such as LinkedIn; another ties it to unsolicited marketing calls — [MLex](https://www.mlex.com/mlex/articles/2322567/lusha-systems-faces-italian-gdpr-probe-for-selling-contact-data). The decision text was not reviewed.
- Contrary earlier outcome: the French CNIL dismissed a Lusha case on 20 December 2022, finding GDPR did not apply (no EU establishment, no offering to EU persons, no monitoring) — [DataGuidance](https://dataguidance.com/news/france-cnil-finds-case-against-lusha-outside-scope-gdpr). The Italian monitoring analysis is what differs.

**ZoomInfo, US class actions**
- Wysocki v. ZoomInfo (W.D. Wash., filed 2022, Contact Contributor / Community Edition): 13 of 14 claims dismissed in March 2024; the surviving claim is under the California Invasion of Privacy Act — [Columbian, March 2024](https://columbian.com/news/2024/mar/21/vancouver-based-tech-company-zoominfo-mostly-prevails-in-federal-suit); [complaint](https://www.classaction.org/media/wysocki-v-zoominfo-technologies-inc-et-al.pdf)
- Ramos v. ZoomInfo: $30 million settlement, preliminary approval June 2024, covering residents of CA, IL, IN, NV over use of personal data in promotional pages — [Bloomberg Law](https://news.bloomberglaw.com/litigation/zoominfo-privacy-class-action-gets-early-nod-for-30-million-deal)
- Martinez v. ZoomInfo (filed 2021): teaser-profile advertising claims — [Top Class Actions](https://topclassactions.com/lawsuit-settlements/privacy/woman-seriously-distressed-by-zoominfo-privacy-violations-claims-class-action)
- A later 2024 Washington suit alleged misuse of personal information under the Washington Personality Rights Act — [Bloomberg Law](https://news.bloomberglaw.com/litigation/zoominfo-sued-again-for-use-of-personal-info-to-promote-services). Current status not checked.

**Apollo 2018 exposure**
- An unsecured, publicly accessible database (described as an Amazon S3 bucket) was found by researcher Vinny Troia in July 2018. This was an exposure, not an intrusion. Have I Been Pwned lists about 125.9M unique email addresses; Security Affairs cites more than 200M contact records. Exposed fields included names, emails, phone numbers, employers, job titles, locations and social profiles. Apollo said no passwords, SSNs or financial data were exposed — [Have I Been Pwned](https://haveibeenpwned.com/breach/Apollo); [Security Affairs](https://securityaffairs.com/wordpress/76878/data-breach/apollo-data-breach.html); [Twingate](https://twingate.com/blog/tips/apollo-data-breach) (secondary). Regulatory outcome not researched.

**RocketReach**
- Reported GDPR complaints in several EU countries and a stated legitimate-interest basis; the same secondary assessment says it falls short of full GDPR compliance (no EU representative) — [Simple Analytics](https://www.simpleanalytics.com/is-gdpr-compliant/rocketreach) (secondary, unverified against complaint records).
- Registered as a data broker with the California AG — [CA AG data broker registry](https://oag.ca.gov/node/187542).
- Its FAQ says customer/user data is segregated from the main email database and that it is not responsible for individual usage of data found — [RocketReach knowledge base](https://knowledgebase.rocketreach.co/hc/en-us/articles/360004231574) (partial excerpt seen).

**Hunter, Apollo, Snov.io, Lusha (other), ZoomInfo (GDPR)**
- Vendor compliance claims (GDPR/CCPA statements, ISO/SOC certifications) were found for Lusha only (G2 listing). Opt-out processes and EU representative status were not verified for these tools (gap).

### Inferences
- The Lusha decision is the clearest recent signal that EU regulators will treat scraped or aggregated professional contact data as personal data requiring a lawful basis and notice, even for non-EU vendors. It is an Italian decision and is not binding elsewhere; a CNIL decision went the other way.
- The ZoomInfo cases suggest US state privacy and publicity statutes are the main US exposure for contributor-style data collection. Most claims were dismissed, so it is not clear how strong they are.

### Gaps
- Primary vendor privacy policies, DPA lists, and opt-out pages for Hunter, Apollo, Snov.io, Lusha and RocketReach were not fetched.
- Whether Hunter, Apollo, Snov.io or Lusha have faced regulatory action beyond the Lusha Italy case was not found.
- The Garante decision text was not reviewed.

---

## 3. LinkedIn: User Agreement, Sales Navigator, hiQ, enforcement

### Takeaway
LinkedIn prohibits scraping and third-party automation in its User Agreement and help pages. The hiQ case ended with a consent judgment and permanent injunction against scraping (December 2022), and the Ninth Circuit's 2022 ruling that scraping public pages is not a CFAA violation was a preliminary-injunction ruling, not a final merits decision. Contract breach is the more realistic route for LinkedIn. LinkedIn has since sued scrapers, including Proxycurl (2025) and ProAPIs (October 2025). Using scraping-based tools that touch LinkedIn carries account-restriction and legal risk.

### Cited Findings

**User Agreement and help pages**
- LinkedIn's help centre says third-party crawlers, bots, browser plug-ins or extensions that scrape or automate activity on LinkedIn are not permitted, and that violators risk account restriction, and that tools may stop working without notice — [LinkedIn help: prohibited software and extensions](https://www.linkedin.com/help/linkedin/answer/a1341387); [LinkedIn help: automated activity](https://www.linkedin.com/help/linkedin/answer/90586)
- The help page names Section 8.2 of the User Agreement, which covers copying, using or distributing information from the Services, including through third parties such as data aggregators, without consent. Secondary sources read it as applying regardless of whether data is public — [Conduct Atlas summary](https://conductatlas.com/platform/linkedin/linkedin-user-agreement/prohibition-on-scraping-and-automated-data-collection/) (secondary). The exact current wording was NOT retrieved; check the User Agreement directly.

**Sales Navigator**
- Native CSV export is capped at 2,500 leads per list and does not include email or phone numbers (per a sales-tool vendor's commentary) — [Cleanlist](https://www.cleanlist.ai/blog/2026-04-25-how-to-export-linkedin-sales-navigator-data) (secondary, vendor).
- Partner and API terms restrict exporting LinkedIn data beyond what is permitted — [Microsoft Learn: LinkedIn restricted uses](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2023-06); [Sales Navigator demo license](https://legal.linkedin.com/LSS-Demo-License-Agreement). No Sales Navigator clause specifically banning third-party extraction was confirmed in search results.

**hiQ Labs v. LinkedIn**
- Ninth Circuit, 18 April 2022 (41 F.4th 1180): after Van Buren, scraping publicly accessible profiles did not become "without authorization" under the CFAA; preliminary injunction for hiQ upheld. Interim ruling only — [Haynes Boone](https://www.haynesboone.com/news/publications/ninth-circuit-rejects-linkedin-attempt-to-prevent-web-scraping-of-publicly-member-profiles); [EFF](https://www.eff.org/deeplinks/2022/04/scraping-public-websites-still-isnt-crime-court-appeals-declares)
- November 2022: district court found hiQ breached LinkedIn's User Agreement, which clearly prohibits scraping; the no-unconscionability finding favoured LinkedIn; summary judgment mixed on other points — [Proskauer, Nov 2022](https://newmedialaw.proskauer.com/2022/11/11/court-finds-hiq-breached-linkedins-terms-prohibiting-scraping-but-in-mixed-ruling-declines-to-grant-summary-judgment-to-either-party-as-to-certain-key-issues/)
- Settlement, 6-8 December 2022: stipulated consent judgment and permanent injunction; hiQ must stop scraping LinkedIn and delete its scraped data, source code and algorithms; $500,000 judgment; hiQ stipulated to CFAA-level losses and to liability for trespass to chattels and misappropriation under California law. Commentators note the stipulation has no precedential value — [Proskauer, Dec 2022](https://newmedialaw.proskauer.com/2022/12/08/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case/); [NatLawReview](https://natlawreview.com/article/linkedin-s-data-scraping-battle-hiq-labs-ends-proposed-judgment); [Mealey's](https://mealeys.com/mealeys/articles/1673771)

**Enforcement after hiQ**
- Proxycurl: LinkedIn sued in January 2025; Proxycurl shut down in July 2025; the resolution was a permanent injunction requiring deletion of improperly obtained LinkedIn data and cessation of access. Reasoning reported by Bloomberg Law: scraping may be acceptable in some circumstances, but unauthorised scraping can support breach-of-contract claims — [LinkedIn news, 2025](https://news.linkedin.com/2025/LinkedInWinsLegalBattleToProtectMemberData); [Social Media Today](https://www.socialmediatoday.com/news/linkedin-wins-legal-case-data-scrapers-proxycurl/756101/). Court opinion not reviewed.
- ProAPIs: LinkedIn sued in October 2025; a December 2025 filing reportedly says the parties are exploring early resolution — [Bloomberg Law](https://news.bloomberglaw.com/artificial-intelligence/linkedin-battles-online-scrapers-in-perpetual-struggle-over-data) (snippet only).

### Inferences
- For a personal app, the most likely consequence of using a scraping-based tool that touches LinkedIn is account restriction and contract-based claims, rather than criminal exposure. The CFAA route is weaker after the Ninth Circuit ruling, but it is not a safe harbour: the hiQ settlement shows scraping can still end in an injunction and damages.
- Public-profile scraping is legally unsettled and depends on the contract (User Agreement) and on whether the data is logged-in or public. Relying on "it is public" is not a safe defence.

### Gaps
- LinkedIn's current User Agreement text (Section 8.2 wording and effective date) and the Sales Navigator-specific terms were not retrieved directly. LinkedIn pages were not fetched, per the research constraints.
- Proxycurl court opinion and ProAPIs docket not reviewed.

---

## 4. Legal risk for a New Zealand individual or small app, and practical risk

### Takeaway
Under the Privacy Act 2020, a NZ user or app that collects and uses personal information about employers, HR staff or team members must meet the information privacy principles. From 1 May 2026, new IPP 3A requires notice when personal information is collected indirectly (not from the individual). Sending unsolicited commercial email to NZ addresses is governed by the Unsolicited Electronic Messages Act 2007 (UEMA). Practically, bounces and spam complaints are a larger near-term risk than prosecution for a personal Gmail account.

### Cited Findings

**Privacy Act 2020 and IPP 3A**
- IPP 3 covers only direct collection from the individual. IPP 3A, added by the Privacy Amendment Act 2025 (royal assent 23 September 2025), covers indirect collection and took effect 1 May 2026. It has practicable exceptions similar to IPP 3 plus four new indirect-collection exceptions — [Privacy Commissioner, IPP 3A](https://www.privacy.org.nz/privacy-principles/3a/); [Privacy Commissioner IPP3A guidance (Oct 2025)](https://www.privacy.org.nz/assets/DOCUMENTS/251104-IPP3A-guidance-A1128460.pdf); [Bell Gully, effective 1 May 2026](https://www.bellgully.com/insights/preparing-for-ipp-3a-new-requirements-effective-1-may-2026/); [Justice NZ news](https://www.justice.govt.nz/about/news-and-media/news/new-privacy-information-principle-in/)
- Where a provider only processes data for the agency, the agency remains responsible (section 11 logic) — [search summary of Privacy Commissioner guidance]. The four new exceptions were not checked against the Act text.
- A contacted person's details scraped from a third-party site are an indirect collection, so IPP 3A notification would apply unless an exception does. Whether a job application app or an individual is an "agency" under the Act was not checked (gap).
- Penalty figures for Privacy Act breaches were not verified in this research (the $10,000 figure was not found in any source). Check legislation.govt.nz.

**UEMA 2007 (spam law)**
- Covers commercial electronic messages with a NZ link. Requires consent (express, implied or assumed); the sender bears the onus of proof (s 9(3)). Requires a functional unsubscribe facility and identification of the sender. Transactional messages that facilitate or confirm a previously agreed transaction are exempt — [DIA, NZ spam law](https://www.dia.govt.nz/SPAM-NZ-SPAM-Law); [DIA unsubscribe guidance](https://dia.govt.nz/Information-about-unsubscribing); [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions); [Act, legislation.govt.nz](https://www.legislation.govt.nz/act/public/2007/7/en/latest/)
- Penalty figures ($500,000 for businesses, $200,000 for individuals) come from one third-party legal site and were not verified against the Act.

**Practical risks**
- Bounce rates: one source suggests keeping total bounces under about 2% to protect sender reputation; verifying lists before sending is the main safeguard — [Instantly, May 2026](https://instantly.ai/blog/email-finder-accuracy-bounce-risk/) (secondary).
- Using a personal Gmail account to send bulk or templated outreach to finder-sourced addresses carries spam-flagging and account-suspension risk. Google's sending limits and bulk-sender rules were not verified in this research (gap).

### Inferences
- A one-off application to a named HR contact, drawn from a job advert, is probably not a "commercial electronic message" and has a low UEMA exposure. Repeated, templated cold outreach to finder-sourced addresses is closer to the line and should include an unsubscribe option and sender identification.
- The IPP 3A obligation is the more concrete change. Any app that stores contact details from third-party finders should give notice (or rely on an exception), limit retention to what is needed, and keep data secure (IPP 5). Purpose limits (IPP 1 and IPP 10) and disclosure limits (IPP 11) also apply, but were not checked in this research.
- Using contributor-based or extension-harvested data (ZoomInfo CE style) would be the highest-risk option under NZ law, given indirect collection and the Italian Lusha decision's reasoning on monitoring.

### Gaps
- IPP 1, IPP 5, IPP 10, IPP 11 wording and the four IPP 3A exceptions were not checked against primary text.
- Whether an individual-run app counts as an "agency" under the Act was not checked.
- Penalty amounts under the Privacy Act and UEMA were not verified.
- Google sending limits and any NZ-specific guidance on cold email were not researched.

---

## Overall summary for the decision

- Accuracy: independent evidence is weak. Expect 30-60% of finder-returned addresses to fail or be unverifiable in typical tests. Hunter's domain-pattern and public-source approach is the most transparent of the six. The others are less documented.
- Terms: LinkedIn prohibits scraping and automation, and enforces it. Avoid any tool that uses LinkedIn scraping or browser extensions on LinkedIn profiles.
- Regulatory: Lusha (Italy, EUR 2M, 2026) and ZoomInfo (US class actions) are the clearest warnings. Contributor-based data is the highest risk.
- NZ: IPP 3A (from 1 May 2026) requires notice for indirectly collected contact data. UEMA applies to bulk or commercial outreach. Bounce and spam risk on a personal Gmail account is the most immediate practical concern.
- Lower-risk options: use the employer's own published HR or careers contact, the company's careers page, or a verified job-advert contact. Limit finder use to a small verified set, honour unsubscribes, and give notice.
