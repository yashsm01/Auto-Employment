# Hands-off job hunting: design

Date: 27 November 2026. Status: approved by the user on 27 November 2026 ("make proper", then "do"). Decisions marked "(my call)" are the designer's.

## Intent

The user wants it simple: set the resume and the areas once, and the app does everything else, with no clicks:

1. Find jobs in the chosen areas that fit the resume.
2. Find the employer's contact details.
3. Tailor the resume and send the application.
4. Follow up.

The same should happen for employers found on Google Maps that aren't advertising. They use company contacts only ("not individual"). The user gets WhatsApp updates and can see everything in the Outbox.

Research basis: [reports/NZ employer contact sources and limits.md](../../../reports/NZ%20employer%20contact%20sources%20and%20limits.md).
- Contacts an employer publishes for recruitment, and the contact named in an advert, are the lawful ones to find automatically.
- Named staff, owners and coworkers are not. Neither are email-finder tools or WhatsApp to employers.
- One application email and one or two polite follow-ups are accepted practice.
- Unrequested bulk messages start to fall under the Unsolicited Electronic Messages Act 2007.

## What exists today

- The daily search finds jobs from the resume's search terms, already drops jobs outside the chosen areas, scores them and shortlists them.
- **Auto mode** (Settings › Auto mode) does three things:
  - approves shortlisted jobs at or above the minimum score, up to its daily limit
  - approves the tailored resume
  - emails the suggested address (advert, then hiring email or recruiter, then general email)
- When there's no address, Auto mode sends one "apply on the job site yourself" WhatsApp update and stops.
- Follow-ups go out automatically 5 working days apart, two at most, then the job closes. Replies and bounces stop them.
- Employer contacts (website and Google Maps) are looked up only in three cases:
  - when the user saves an employer
  - when the user presses **Get contact details**
  - for up to 10 shortlisted employers in the daily research
- **Nearby employers** (Google Maps) is manual: the user searches, saves, and does nothing more.

## Goals

1. **Contacts found automatically for approved jobs.** When a job is approved, by the user or by Auto mode, the employer's website is checked in the background unless it was checked in the last 30 days.
   - Auto mode waits for that check before deciding there's no address.
   - Only then does it send the "apply on the job site" update.
2. **The contact named in the advert is used.** A name, role, email or phone written in the advert ("contact Jane Smith, Talent Partner, on 021…") is extracted by plain code. An email there already comes first in the suggested address; the name and phone are shown too.
3. **Jobs outside the chosen areas are removed.**
   - When the user changes their areas, found and shortlisted jobs outside the new areas are closed, with an event note "Outside your areas".
   - New searches already drop them.
4. **Google Maps employers are approached automatically, within strict limits:**
   - Business types to approach are kept as a list on Settings › Auto mode. With an AI key, it is filled once from the resume; otherwise the user types it. An empty list means no Google Maps outreach.
   - Each day, for each chosen area and business type, the app runs the Places search, within the existing daily limit on Nearby searches.
   - It picks **at most 5 new employers a day**: ones it has never applied to or emailed before, that publish a hiring or general email (found by the contact lookup), and that aren't already tied to a job.
   - Each gets **one speculative application email**, with the master CV attached in the chosen design, and **one follow-up** 5 working days later. Then the record closes.
   - Every speculative email ends with: "If you'd rather I didn't contact you again, just reply and I won't."
   - Any reply or bounce stops it for good: that employer is never emailed again.
   - These emails count toward the overall daily send limit.
5. **An evening WhatsApp summary.** At 18:00 NZ time, if anything happened that day: applications sent, follow-ups sent, replies, bounces, Google Maps employers emailed, and jobs left to apply for on a job site.
6. **The Outbox shows every contact.** A read-only list with one row per job or Google Maps employer in the Outbox, showing:
   - employer
   - source (advert or Google Maps)
   - hiring email and general email
   - advert contact (name and role)
   - business phone
   - each detail's source label
   - the address used
   - **why it's missing** when nothing was found: "Website not checked yet", "Checked {date}: no email on the site", "No website known", "Could not read the website", or "Advert asks you to apply on the job site"
   - a **Find contacts** button that forces a fresh check
7. **Carried over from the resume builder** (must land first):
   - the one-line fix so a fresh AI section read with no jobs never reaches a tailored PDF
   - the three out-of-date doc sentences

## Non-goals and anti-goals

- No WhatsApp, text or calls to employers from this feature. The existing AI calls feature stays as it is.
- No named staff, owners or coworkers found automatically. No email-finder services, no guessed addresses, no LinkedIn.
- No submitting applications on job sites (SEEK, Trade Me, government portals). Those jobs are listed for the user, with one WhatsApp update.
- No unlimited cold outreach: the limits above are fixed defaults, editable within caps.
  - Up to 10 Google Maps employers a day (my call).
  - Never more than one follow-up for speculative emails.
- No emailing employers whose advert says to apply only through the site, or "no agencies or direct contact" (detected by plain phrases, my call). No emailing jobs on jobs.govt.nz.
- Logins for more than one user stay a later project.

## Approaches considered

| | How | Trade-off | Outcome |
|---|---|---|---|
| A | Google Maps employers become a "speculative application" record in the existing pipeline: a job with source `nearby` and title "Speculative application", tied to the company | Reuses applications, the Outbox, sending, follow-ups, replies, bounces, notifications and limits. Needs a new job source value and a follow-up cap per kind. | **Chosen (my call)** |
| B | A separate prospects table with its own sending and follow-up loop | Clean separation, but it duplicates the whole Outbox lifecycle and its tests | Not chosen |
| C | Only the job-advert side automatic; Google Maps stays manual | Simplest and lowest risk, but not what the user asked for | Rejected |

## Design details

- **Storage.**
  - Migration `0011`:
    - adds `'nearby'` to `jobs.source`
    - adds `applications.kind` (`'advert'` default, or `'speculative'`)
    - adds `profiles.business_types text[]`
    - adds `profiles.prospects_per_day int default 5`
    - adds `outreach_blocks (profile_id, company_id, reason, created_at)`, so any reply or bounce on a speculative email blocks that employer forever
  - A speculative job has title "Speculative application", the company's name, and its location from Google Maps.
  - The dedupe key is the company, so an employer gets at most one speculative record.
- **Speculative emails.**
  - Subject: "Enquiry about opportunities at {company} – {name}".
  - The body is a short note:
    - with an AI key, written from the employer's stored facts and the master CV, passed through the existing fact check and declined-skill rules
    - without one, a standard note
  - Signature as today. Then the stop line.
  - The attachment is the master CV PDF in the chosen design. It isn't tailored: there's no advert to tailor to.
- **Follow-ups.**
  - Advert applications keep two follow-ups.
  - Speculative ones get one, with a short body, then close.
  - Ask mode works the same for both.
- **Order each day:**
  1. The daily search at the usual hour.
  2. Research, including contact lookups.
  3. Auto mode approvals.
  4. Google Maps prospecting (search, contact lookup, speculative records).
  5. Sending, every 15 minutes within the daily limit.
  6. The 18:00 summary.
- **Settings › Auto mode** gains:
  - a "Google Maps employers" section: business types (an editable chip list) and new employers a day (1–10, default 5)
  - an on/off switch for Google Maps outreach, off by default and needing Auto mode on
- **UI.**
  - The Outbox gets a "Contacts" list, plus a "Speculative" label on Google Maps rows.
  - Nearby employers shows "Emailed {date}", "Replied" or "Do not contact" on saved employers that went through outreach.

## Answers to the builder check

1. **Approval.** Speculative records skip every approval step when both Auto mode and the Google Maps outreach switch are on. The user asked for "all no my interaction", and the switch is the opt-in, off by default. With the switch off, no Google Maps outreach happens at all. Ask mode still applies to follow-ups.
2. **Matching replies and bounces.** Speculative records are applications with outbox rows, so the existing checks apply unchanged. A reply is found by the Gmail search `from:{emailed address} after:{date sent}`, and a bounce by the bounce search for that address. On a speculative record, either one also writes an `outreach_blocks` row for the company.
   - A block stops future speculative outreach only. It does not stop applying to that employer's adverts (my call: an advert invites applications).
   - A company already tied to an advert application is never picked for speculative outreach.
3. **When limits run out** (my calls):
   - Advert applications send first. Speculative emails use whatever is left of the daily send limit.
   - Unsent emails stay queued and go on the next working day.
   - The "new employers a day" cap counts speculative records created, not emails sent.
   - Google Maps searches go round each area and business type in turn, continuing the next day from where the daily search limit stopped them.
4. **"No unsolicited applications" on employer websites** (my call). The contact lookup already reads the home, contact and careers pages. If their text contains phrases like "no unsolicited", "do not accept unsolicited", "no recruitment agencies" or "no cold calls", the employer is blocked from speculative outreach with that reason.
5. **Prerequisites.** The resume-builder work is uncommitted in the working tree, including migrations 0009 and 0010. This feature's migration is `0011`. Goal 7's fix comes first.

## Left to the builder

- Exact phrases for detecting "apply only on the site" and "no direct contact" (a short list, matched case-insensitively).
- The wording of the speculative note template.
- The layout of the Contacts list.

## Not verified

- No New Zealand source rules on job-seeker cold emails specifically. The limits follow the research's caution, not a ruling.
- Get legal advice before raising the limits.
