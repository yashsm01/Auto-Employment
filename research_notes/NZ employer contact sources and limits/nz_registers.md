# NZ Employer Contact Sources: NZBN, Companies Register, Job Adverts

Research date: as of late November 2026. Sources are primary (government and legislation pages) unless marked as secondary commentary. Items marked UNCONFIRMED could not be verified from a fetched primary source.

## NZBN primary business data: which fields are public, and how often they are filled

### Takeaway
The NZBN register holds 21 primary business data (PBD) fields, including phone, email, websites, directors and owners. The official NZBN page does not say which of these are public by default, and it says optional fields may be absent. Email and phone are optional and businesses choose whether to make them public, so coverage will be patchy. No NZ statistic on the share of SMEs publishing an email on NZBN was found.

### Cited Findings
- The NZBN page lists 21 PBD fields: legal name, trading names, trading areas, NZBN, entity type, registration status, industry classification (BIC), directors, websites, owners, phone numbers, email addresses, registered address, postal address, address for service, office address, delivery address, invoice address, GST number, ABN, Maori Business Identifier. — [NZBN, Primary business data](https://nzbn.govt.nz/whats-an-nzbn/primary-business-data)
- Some PBD is mandatory and automatically public under NZBN legislation, varying by business structure. Other data is optional and businesses choose whether to provide and publish it, so some records will be incomplete. — [NZBN, Primary business data](https://nzbn.govt.nz/whats-an-nzbn/primary-business-data)
- Phone numbers and email addresses can each be recorded with a stated purpose, and more than one of each can be added. The page does not state their default visibility. — [NZBN, Primary business data](https://nzbn.govt.nz/whats-an-nzbn/primary-business-data)
- Incorporated businesses (companies, limited partnerships) always have a publicly available registered address, which may be an accountant's or lawyer's address. — [NZBN, Primary business data](https://nzbn.govt.nz/whats-an-nzbn/primary-business-data)
- The 2018 Order sets public PBD for companies, with phone, email, postal, address for service, office, delivery, invoice, GST and bank account fields in the "other" category for corporate entities. Secondary summary only; the Order itself should be checked. — [New Zealand Business Number (Primary Business Data) Order 2018](https://legislation.govt.nz/secondary-legislation/pco-drafted/2018/273/en/latest/) (not fetched; cited via search result)
- NZBN terms: "We will not disclose your email address to third parties." The email supplied may be used to update the business on NZBN services. The terms do not address direct marketing or reuse. — [NZBN Terms of use](https://nzbn.govt.nz/about-us/terms-of-use)
- NZBN register has no charges "at this time." — [NZBN Terms of use](https://nzbn.govt.nz/about-us/terms-of-use)
- Bulk data files are refreshed monthly. — [NZBN bulk data search summary](https://www.nzbn.govt.nz/using-the-nzbn/nzbn-services/bulk-data/) (search result only, not fetched)

### Inferences
- A business email or phone on NZBN is plausible for a minority of records. It is an optional, self-declared field whose stated purpose may be "general" or "accounts" rather than HR. Each record's purpose label should be checked before use.
- The NZBN terms say the register will not disclose email addresses to third parties. A bulk harvest of NZBN emails for outreach would sit awkwardly with that statement, and with the Unsolicited Electronic Messages Act (see below).

### Gaps
- Which PBD fields are default-public and which are private for each entity type: not stated on the fetched page. Check a live record (nzbn.govt.nz) or the NZBN Fact sheet on PBD (https://www.nzbn.govt.nz/assets/fact-sheets/NZBN-Fact-sheet-Primary-Business-Data.pdf, not fetched).
- Share of NZ SMEs that publish an email or phone on NZBN: no statistic found. Stats NZ/MBIE business demography gives about 612,417 businesses in 2024, about 97% small (fewer than 20 employees) (secondary search summary of Stats NZ; not verified). No NZBN-specific publication rate located.

## NZBN API: access, keys, cost, limits, terms

### Takeaway
The NZBN API has no fee for use. Access is by subscribing to the NZBN API product in the MBIE API portal, with a sandbox for development and production keys afterwards. Public-data searches need only a subscription key. Rate limits, tiers and pricing are not published on the fetched pages; they must be requested from API support. Terms on reuse and direct marketing are not stated.

### Cited Findings
- "There is no fee for using this API." Fees may apply in some cases, such as creating more than two organisation parts for an NZBN entity. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)
- Access steps: read the technical details in the developer portal; subscribe to the NZBN API Product (API support may ask for more information before approval); generate a subscription key. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)
- Sandbox is for development; production keys are used at go-live. Sandbox data is not a mirror of production, contains test cases and old Companies Register data from before 2010, and NZBNs may collide with unrelated production businesses. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)
- Authentication: subscription key only is sufficient for searching and retrieving public information. Two-legged OAuth2 is suggested where the key might be exposed to end users. Three-legged OAuth2 is needed to update entities, and updating PBD also requires end-user business authority. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)
- Private data, including email and phone for business owners with authority, is accessible via a three-legged token. — [NZBN API search summary](https://portal.api.business.govt.nz/api/nzbn) (search result, consistent with the page)
- The page states no rate limits or quotas and names no subscription tiers. It refers to a comparison table not in the fetched content. Disclaimer: MBIE is not liable for accuracy of returned information. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)
- Weekly maintenance window, usually 9pm to 11pm Wednesdays. — [NZBN API page](https://portal.api.business.govt.nz/api/nzbn)

### Inferences
- An app that searches NZBN for public contact fields is within the documented API use. The main unknowns are rate limits and any reuse restriction, which are only in the subscription terms or from API support.
- Because a business's own email on NZBN is "published" and no prohibition on contact is stated, using it is a matter of the Unsolicited Electronic Messages Act and Privacy Act (below), not NZBN terms alone.

### Gaps
- Rate limits, quotas, tier pricing: not published on fetched pages. Ask API support via the MBIE API portal contact page.
- Whether the subscription agreement restricts reuse or marketing: the Copyright and Privacy pages linked from the API page were not retrieved. Read the subscription terms before building.

## Companies Register: public data, residential addresses, API terms

### Takeaway
Companies Register entries are public for registered address, addresses for service and company details. Director details are public subject to the residential-address protections. Contact details (email, phone) are restricted, not public. The residential-address protection in NZ came via a new Act (Companies (Address Information) Amendment Act 2025), not a 2021–2023 change as the brief assumed. The Companies Register APIs are described as mostly free, with lower-cost transaction fees. Terms restricting use of director data are not stated.

### Cited Findings
- The Companies Office business entity data page marks contact details (address for communication, email, phone) as Restricted. It lists addresses as public for the Companies Register and notes businesses may choose to make some addresses private. It sets no marketing-use terms. — [Companies Office, Business entity data](https://www.companiesoffice.govt.nz/data-services/available-data/business-entity-data)
- The same page does not list directors or shareholders as data fields, and does not address residential addresses. — [Companies Office, Business entity data](https://www.companiesoffice.govt.nz/data-services/available-data/business-entity-data)
- The Companies Office API page says the APIs let users search by company name, director or shareholder, look up disqualified directors and prohibited managers, and maintain company details and file annual returns. — [Companies Office, Using our data through APIs](https://www.companiesoffice.govt.nz/about-us/using-our-data-through-apis/)
- Access is through the MBIE API Explorer (portal.api.business.govt.nz). Most APIs are free; some transactions (e.g., annual return filing) are charged at a lower API rate than the website, paid by monthly direct debit. Setup costs are likely. Terms, rate limits and officer-data restrictions are not covered; contact the Companies Office for these. — [Companies Office, Using our data through APIs](https://www.companiesoffice.govt.nz/about-us/using-our-data-through-apis/)
- Residential addresses: Family Court protection order holders could already have residential addresses suppressed on the Companies Register before the recent change. — [Companies Office PPSR news, New law related to directors' residential addresses](https://ppsr.companiesoffice.govt.nz/news/new-law-related-to-directors-residential-addresses/) (search summary; fetch returned no usable text for the help-centre suppression page, which returned an empty body or 404 on the attempt).
- Companies (Address Information) Amendment Act 2025: directors, including prospective directors, with serious safety concerns may apply to replace their residential address on the public register with an alternative address. The application needs a statutory declaration that public disclosure is likely to cause physical or mental harm to them or a person they live with, and pays any prescribed fee. The alternative address cannot be the registered office, address for service, a postal centre or document exchange. Once approved, the alternative address is the only publicly accessible address for that directorship, and approved residential addresses are redacted from the main record, historic filings and consent forms. — [Hesketh Henry, Director residential address protection bill passed into law](https://www.heskethhenry.co.nz/insights-opinion/director-residential-address-protection-bill-is-passed-into-law/) (secondary commentary)
- Commencement: set by Order in Council; if not in force by 18 November 2026, it commences on that date. Applications cannot be lodged before commencement. — [Hesketh Henry](https://www.heskethhenry.co.nz/insights-opinion/director-residential-address-protection-bill-is-passed-into-law/) (secondary); corroborated by [IoD commentary, 30 July 2026](https://www.iod.org.nz/news/articles/director-home-addresses-update) per a search summary (page itself returned 404 on fetch)
- The Companies (Address Information) Amendment Regulations 2026 are referenced in a Cabinet minute dated 24 September 2026; whether they have been made is not confirmed. — [MBIE proactive release, search summary](https://www.mbie.govt.nz/dmsdocument/32655-companies-act-1993-address-information-amendment-regulations-2026-minute-of-decision-proactiverelease-pdf) (search summary, not fetched)
- Residential addresses are still held by the Companies Office internally; the amendment affects the public register only. — [search summary of commentary](https://www.mbie.govt.nz/dmsdocument/32654-companies-act-1993-address-information-amendment-regulations-2026-proactiverelease-pdf) (secondary)
- Australia's ASIC stopped showing officeholders' residential addresses on purchased extracts from February 2026. This is not NZ and is listed only for comparison. — [AICD, director detail suppression](https://www.aicd.com.au/board-of-directors/duties/director-detail-suppression.html) (search summary)

### Inferences
- Director names remain public on the Companies Register under the existing scheme (general NZ practice); this was not confirmed by a fetched primary source, since the Companies Office data page omits directors. Treat director names as likely public but UNCONFIRMED until checked on a live company record.
- Director names and roles on the Companies Register are sufficient for owner/director lookup, but not for direct contact: the publicly displayed address is either the registered office, an address for service, or (where approved) an alternative address. Residential contact is not available by design.
- Using a director's name from the register to contact them personally about job applications is a different purpose from the register's purpose. Privacy Act IPP 10/11 limits on secondary use apply. Not verified (IPP 10/11 pages not retrieved).

### Gaps
- Companies Register API terms, cost schedule, rate limits, and any restriction on using director data for contact or marketing: not published on fetched pages. Ask the Companies Office.
- Whether the 2026 regulations are in force and whether existing residential addresses are redacted automatically: not confirmed.
- The brief's "2021–2023 changes" premise: no NZ change in that window was found. The residential-address changes are from the 2025 Act (commencing by 18 November 2026 at the latest).

## Sole traders and partnerships

### Takeaway
Sole traders, partnerships and trusts are not on the Companies Register. They appear on the NZBN register and in the Companies Office "other registers" search. Public data is limited, and contact details are restricted. An app must use NZBN for these entities.

### Cited Findings
- Sole traders and partnerships do not appear on the Companies Register; they are on the NZBN register, searchable at nzbn.govt.nz. — [Companies Office, Searching our other registers](https://lp-register.companiesoffice.govt.nz/help-centre/searching-the-registers/searching-our-other-registers) (search summary)
- Other-registers search results show name, NZBN, address, registration date, business type and status. — [Companies Office, Searching our other registers](https://lp-register.companiesoffice.govt.nz/help-centre/searching-the-registers/searching-our-other-registers) (search summary)
- The business address is public but may be kept private; contact details are restricted. — [Companies Office, Business entity data](https://www.companiesoffice.govt.nz/data-services/available-data/business-entity-data)
- A sole trader may hold only one NZBN and be registered once as a sole trader. — [NZBN and the Companies Register](https://companies-register.companiesoffice.govt.nz/help-centre/getting-support-to-use-the-companies-register/new-zealand-business-number-nzbn/) (search summary)

### Inferences
- For sole traders, the individual is the business owner and their identity is less protected than a director's; still, contact details are restricted, so contact would have to come from a published advert or the trader's own site.

### Gaps
- Exact display of sole trader and partnership owner names on the NZBN public view: not confirmed from a live record.

## Job adverts: named contacts and extraction

### Takeaway
Named contacts with phone or email in NZ job adverts were not quantified in any source found. Recruitment agencies often conceal the client's name, and Trade Me reports about 22% of its listings come from agencies. Using a contact a job advert publishes, for the purpose of applying for that advertised role, is the most defensible use. Bulk extraction from SEEK, Trade Me or LinkedIn is out of scope for this project and was not attempted.

### Cited Findings
- Agencies commonly keep client names private, partly so candidates cannot apply directly; Trade Me reported about 22% of its listings in one month came from agencies. One job seeker said up to five listings in a daily update had the advertiser concealed. SEEK declined to comment. — [RNZ, Why are some job ads so secretive, 14 Aug 2024](https://www.rnz.co.nz/news/top/525126/why-are-some-job-ads-so-secretive)
- A recruiter said agencies should name the employer before candidate applications, and that not all do. — [RNZ, 14 Aug 2024](https://www.rnz.co.nz/news/top/525126/why-are-some-job-ads-so-secretive)
- SEEK's Talent Acquisition team uses only @seek.co.nz addresses and does not contact people via social media. Trade Me warns of fake job ads and scammers posing as Trade Me Jobs recruiters by SMS. — [SEEK Employer Security Hub](https://nz.employer.seek.com/security-hub); [Trade Me Help Centre, job advertisement scams](https://help.trademe.co.nz/hc/en-us/articles/12434557275535-Job-advertisement-scams) (search summaries)
- Unsolicited Electronic Messages Act 2007: a commercial electronic message needs consent. Deemed consent applies where contact details are conspicuously published and the person has not asked not to receive messages. The sender bears the onus of proof of consent (s 9(3)). Harvesting addresses with software for unsolicited commercial messages is prohibited. Passing addresses to another organisation without permission may breach the Privacy Act. Commercially bought lists may not meet the deemed-consent test. — [DIA, Spam and electronic address harvesting](https://www.dia.govt.nz/Spam-Electronic-Address-Harvesting-Software); [UEMA 2007](https://www.legislation.govt.nz/act/public/2007/7/en/latest/) (search summaries; statutory text not fetched)
- Privacy Act IPP 3 requires collecting agencies to tell individuals why information is collected and who will receive it. IPP 10 and IPP 11 limit use and disclosure of information for other purposes; not retrieved in full. — [Privacy Commissioner, IPP 3](https://www.privacy.org.nz/privacy-act-2020/privacy-principles/3/)

### Inferences
- A contact named in a job advert, used to apply for that advertised role, is reasonable to use. A contact used for unrelated marketing or stored for later outreach is not covered by the advert's purpose and carries UEMA and Privacy Act risk.
- An app that extracts adverts at scale from SEEK or Trade Me would breach those sites' terms, so the app should take contacts only from the user's own applications or from employer-controlled pages it is permitted to read.
- Application emails should be transactional (a reply to an advert), identify the sender, and avoid bulk sending. Treat any sender-initiated follow-up as UEMA-regulated if it promotes services.

### Gaps
- Frequency with which NZ job ads name a contact person with phone or email: no statistic found.
- Whether the UEMA deemed-consent test applies to an unsolicited job application: not tested by case law found. Get legal advice before relying on it.
- The exact wording of SEEK and Trade Me terms on data extraction: not fetched (per instruction not to fetch SEEK). Check their terms before any use.

## Key limits for the app (summary)
- NZBN and Companies Register are usable for company name, NZBN, status, registered address, directors (names) and public NZBN fields. Contact fields are optional and often absent.
- Residential addresses of directors are not available by design, and new protections apply.
- API rate limits, tiers and reuse terms are not published; obtain them before building.
- Job-advert contacts are usable only for applying to the advertised role. No bulk harvesting.
- Sources of NZ-specific statistics on contact publication: none found.

Sources fetched directly: NZBN primary business data, NZBN terms, NZBN API page, Companies Office APIs page, Companies Office business entity data, Hesketh Henry on the 2025 Act, RNZ on job ads, Privacy Commissioner IPP 3. Failed or empty fetches: Companies Office suppression help-centre page (empty/404), IoD update (404). Search-only sources are marked.
