# Goal

NZ Job Autopilot is a personal tool that takes one person from job search to sent application.
The resume drives everything: what to search for, how jobs are scored, and what goes into each tailored resume.

## Build phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Repo, database, resume profile, lead search, employer records, Pipeline and Shortlist screens | In progress |
| 2 | One week of shortlist review, then resume tailoring and the Resume review screen | Not started |
| 3 | Email sending, follow-ups, Outbox screen | Not started |
| 4 | WhatsApp and OmniDimension AI calls, as tests only | Not started |
| 5 | Auto mode, switched on by the user | Not started |

## Budget

NZ$5–10 a month, at about 30 jobs a day.

## Rules that must not be broken

- **Never invent experience.** Tailored resumes may only reword and reorder facts from the base resume.
- **The user approves before anything is sent**, until they switch on auto mode themselves.
- **Do not scrape SEEK, LinkedIn or Indeed.** Their terms ban it. Use official APIs and the user's own job alert emails.
- **Public business contact details only** (NZ Privacy Act 2020). Do not harvest email addresses (Unsolicited Electronic Messages Act 2007).
- **Keep send limits low** so the user's email is not flagged as spam.
- **Say when data is an example.** Example jobs are labelled in the UI.
