# Employer contact details: design

Date: 26 November 2026. Status: approved by the user on 26 November 2026.

## Intent

For each employer the user finds on Google Maps, or meets through a job, the app shows its contact details: phone, email, website, and its HR or hiring contact. Google Maps doesn't give everything, so the app also reads the employer's own website, mainly its contact and careers pages, which the user pointed to.

The details are shown in the UI and used by the app:
- the hiring email becomes the Outbox's suggested address
- the phone number is used for AI calls

## Goals

- Show phone, email, website, contact page, careers page, LinkedIn company link, address, map link, opening hours and rating where available. Each line shows its source.
- Find the HR or hiring contact from the employer's own site:
  - hiring addresses (careers@, jobs@, hr@, recruitment@, talent@, people@)
  - a named recruiter, only when the employer lists them for hiring on its own pages
- Feed the hiring email into the Outbox suggestion. Order: the advert's address first, then the HR contact, then the general email.

## Non-goals and anti-goals

- No reading of LinkedIn. Its terms ban automated collection, and the plan's rules forbid scraping it. The app only shows the company page link found on the employer's site, for the user to open.
- No guessed addresses (firstname@company) and no third-party email finders.
- No people found outside the employer's own pages. No personal phone numbers or profiles.
- Collecting addresses must not turn into bulk harvesting: only employers the user saved or has a job with, and only a few pages each.

## Approaches considered

| | How | Trade-off | Outcome |
|---|---|---|---|
| A. Automatic plus a button | Look up when you save an employer, and for shortlisted jobs' employers during the daily search (up to 10 a run). A **Get contact details** button on each employer refreshes or fills in. | Bounded cost, and details are ready when you need them | **Chosen (designer's call)** |
| B. Button only | Nothing automatic | Cheapest, but the Outbox and calls often have nothing to use | Not chosen |
| C. Every Maps search result | Read 2–3 pages for each of up to 20 results per search | Slow searches, and bulk address collection | Rejected |

## Design

**Google Maps.** The Places search also returns:
- international phone number
- Google Maps link
- opening hours
- rating and number of ratings
- business type
- business status

These are in the same price tier as the phone and website fields it already requests.

**Website.** The Jina reader (already used, and it respects robots.txt) reads the home page, plus the contact page and careers page found from its links, at most 3 pages per employer. Plain code then extracts:
- email addresses from `mailto:` links and text, skipping no-reply addresses and job-board domains
- NZ phone numbers
- links to the contact page, the careers page and `linkedin.com/company/...`

Email addresses are sorted by the part before the @:
- **hiring:** careers, jobs, hr, recruit, talent, people, employment, vacancies
- **general:** info, hello, contact, admin, office

Addresses on another domain are kept only if the employer's own page shows them.

**Named recruiter (designer's call).** One small Haiku call reads only the careers and contact pages. It returns a name, role, email and a short quote. The contact is kept only when all of these hold:
- the quote appears word for word on that page
- the role is about hiring
- the email appears on that page

**Storage.**
- `companies.email` holds the general address.
- `company_facts` gets fields `email`, `hiring_email`, `phone`, `contact_page`, `careers_page`, `linkedin`, `opening_hours` and `rating`. Each has source `website` or `places`, a `source_url`, and confidence `high` (from the employer's own site or Google) or `check`.
- `contacts` gets role `recruiter` or `general` rows, with name, email, phone, source and confidence.
- Migration `0008` adds `contacts.source_url` and `contacts.checked_at`, and `companies.contacts_checked_at`.
- A lookup is skipped if it ran in the last 30 days.

**UI.**
- **Nearby employers**, results and saved list: phone, email, HR contact, and links to the website, contact page, careers page and LinkedIn, each with a source badge, plus a **Get contact details** button.
- **Job › Employer tab:** a **Contacts** section showing the same details.
- **Outbox:** the suggested address uses the HR contact when the advert has none.

**Rules.** Removing an employer deletes its contacts, because the database deletes them along with the employer. Contact details are never sent to AI, apart from the careers and contact page text used for the recruiter check.

## Left to the builder

- The exact link-matching patterns.
- Badge layout.

## Not verified yet

- The Places price tier for opening hours and rating. It is believed to be the same tier as phone and website.
