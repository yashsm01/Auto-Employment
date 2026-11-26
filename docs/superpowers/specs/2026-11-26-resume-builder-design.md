# Resume builder and skill coverage: design

Date: 26 November 2026. Status: draft for the user's review. The user moved straight to planning, so the decisions marked "(my call)" have not been confirmed yet.

## Intent

The user wants a resume builder that gives their resume a proper structure and shows an ATS score for each job they pick. It should come with ready-made professional designs, and it should be part of the whole flow:

1. The pipeline finds jobs that fit the resume.
2. The app checks each job's requirements.
3. The app updates the resume for that job.
4. The app sends the email, with the user's WhatsApp number.
5. Follow-ups run automatically, or manually if the user prefers.

Steps 1, 3, 4 and 5 already exist ([README](../../../README.md)). This design adds:
- a master CV that the user edits, which feeds the search, the scoring and the tailoring
- four designs
- an ATS check
- each job's requirements, with skill coverage
- the WhatsApp number in emails
- a way to approve follow-ups by hand

Research basis: [reports/ATS resume parsing and scoring NZ.md](../../../reports/ATS%20resume%20parsing%20and%20scoring%20NZ.md).
- Keep one plain layout that ATS software reads well, and change only the content for each job.
- Show coverage counts, not a pass mark.
- Follow New Zealand CV conventions.

Mockups:
- designs: https://claude.ai/artifact/1PYGFyigCNBq9td3rnkmhE (page "CV templates")
- app flow: the same link, page "In the app"

## Goals

1. **Master CV.** Editable sections:
   - contact: name, email, phone, city, LinkedIn, WhatsApp and a work-rights line
   - headline
   - profile
   - key skills
   - work history: title, employer, location, dates, bullets
   - education and certifications
   - interests
   - referees

   It starts from the uploaded resume, using the existing AI section reader when a key is set, and otherwise an empty form. Saving it adds new skills and the headline to the resume profile, so the daily search and the scoring use them. Nothing in the profile is removed this way.
2. **Four designs:** Classic, Modern, Compact and Executive. One choice applies to every file. Each design is available as a PDF and a Word download. All are A4, a single column, with no tables, text boxes, images, or page header or footer content.
3. **ATS check.**
   - Rules: contact details at the top of the page body, standard headings in the New Zealand order, month-and-year dates, 2 pages or fewer, a profile of 50 to 150 words, no personal details (photo, date of birth, gender, marital status, nationality, religion), files under 2.5 MB, and a stated work right.
   - A plain-text preview pulled from the generated PDF.
4. **Requirements for each job.** The existing AI scoring call also returns required skills and nice-to-have skills. A skill is kept only if it appears in the ad text. Without AI, the keyword scorer lists the skills it finds as one group, "Skills the ad mentions".
5. **Skill coverage for each job:**
   - Required and nice-to-have counts are shown separately, for example "4 of 6".
   - Each skill shows where it appears, in this order of preference: a role, then the profile, then key skills, then education.
   - Synonyms count, for example AWS and Amazon Web Services.
   - **I have this** adds the skill to the master CV's key skills and to the resume profile.
   - **Not me** records the skill for the profile. Tailored resumes and cover notes never claim it.
   - **Undo** reverses either one.
   - A chip on the Shortlist shows the required count.
6. **Tailored resumes** use the chosen design, as a PDF (still the attachment) and a Word file, and show the coverage of the tailored version.
7. **Email signature:**
   - It adds "Phone and WhatsApp: …" when the two numbers are the same, or separate "Phone: …" and "WhatsApp: …" lines when they differ.
   - It applies to applications and follow-ups. The PDF stays as it is.
   - (My call) The app never messages employers on WhatsApp. This keeps the user's earlier choice of "updates to me only" and Meta's opt-in rule.
8. **Follow-up mode,** a setting: "Send follow-ups automatically" (the default, and today's behaviour) or "Ask me before each follow-up". In ask mode, a due follow-up waits in the Outbox under "Follow-ups waiting for you", with **Send** and **Skip**. Closing a job after two follow-ups stays automatic.

## Non-goals and anti-goals

- No separate file for each ATS or job site, and no single "ATS score" with a pass mark.
- No hidden keywords, no repeated keywords, and no skill the user hasn't confirmed.
- Tailoring never changes titles, employers or dates.
- Contact details are never sent to AI.
- No photos, and no template editor.
- Logins for more than one user are a separate, later project.
- Old jobs keep their match score. Coverage is worked out live from the master CV.

## Approaches considered

| | How | Trade-off | Outcome |
|---|---|---|---|
| A | Master CV stored in the base resume's content: extend `BaseSections` and `ContactDetails`, and get requirements from the existing scoring call | No new AI calls. Tailoring already reads these sections. | **Chosen (my call)** |
| B | A separate `master_cv` table, plus a separate requirements chain for each job | Cleaner separation, but it duplicates the sections and adds one AI call per job | Not chosen |
| C | A builder in the browser only | Can't feed the search, scoring or tailoring | Rejected |

## Design details

- **Storage.**
  - The base resume's `content` holds `sections` (`BaseSections` plus `headline`, `interests`, and `referees`, defaulting to "Available on request."), `contact` (`ContactDetails` plus `location`, `linkedin`, `whatsapp`, `work_rights`) and `template`.
  - Migration `0009_resume_builder.sql` adds to `applications`: `required_skills`, `preferred_skills` and `requirements_split`.
  - It adds a `skill_decisions` table: profile, skill key, skill, `have`/`no`.
  - It adds the outbox status `draft`.
- **Fonts (my call).**
  - The PDF uses the bundled DejaVu Sans for every design, because it covers macrons and no serif version is available offline. The designs differ by accent colour, heading style, name alignment and spacing.
  - The Word files use Word fonts: Classic Georgia, Modern Calibri, Compact Arial, and Executive Cambria headings with Calibri body text.
  - Cost if wrong: the serif look shows only in Word until a DejaVu Serif font file is added.
- **Headings,** exactly: Profile, Key skills, Work history, Education and certifications, Interests (only when filled in) and Referees.
  - Order: name, headline, contact line, work-rights line, then the sections in that order.
  - The contact line is the city · phone · email · LinkedIn, plus "WhatsApp …" when it differs from the phone.
- **Coverage copy.**
  - Heading: "Skill coverage for this job".
  - Text under it: "How many of the ad's skills your CV shows, and where. Employers' systems differ, so this is a guide, not a prediction of an interview."
  - When no skills were found: "No skills found in this ad."
- **UI** as in the mockup:
  - a new menu item **Resume builder** at `/builder`, after Shortlist
  - the coverage panel on the tailored resume page
  - the Shortlist chip
  - the follow-up switch on Settings › Auto mode
  - drafts on the Outbox

## Left to the builder

- Exact spacing and sizes within each design's look.
- The full synonym list, beyond the seed list in the plan.
- The editor layout on the Resume builder page.

## Not verified

From the research: how SEEK, Trade Me, JobAdder and PageUp parse resumes. The ATS check is a sound guide, not proof for those platforms.
