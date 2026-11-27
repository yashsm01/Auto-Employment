# Auto-Employment: NZ Job Autopilot

A personal tool that finds New Zealand jobs, scores them against your resume, researches employers, and tracks each job from shortlist to reply.

**Current state: Phase 3.** It reads your resume, searches, scores, shortlists and researches employers. When you approve a job, it writes a tailored resume and cover note for you to review. Approved applications go to the Outbox, which can email them from your Gmail and follow up, once you switch sending on. Until you add your resume or a job source, it uses clearly labelled example jobs.

## Run it locally

You need Python 3.12, Node 20 or newer, and a Postgres database.

```powershell
# 1. Create a database (or use a Supabase project)
createdb -U postgres job_autopilot

# 2. Backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env      # then set DATABASE_URL in .env
.venv\Scripts\python -m app.db.migrate --seed
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, go to **My resume profile**, and upload your resume.

The backend has no login yet, so run it only on your own computer.

## Connect job sources and AI

Everything below is optional. Add keys to `backend/.env`, then restart the backend.

| Feature | What you need | Without it |
|---|---|---|
| Company careers pages | Nothing. Add Greenhouse, Lever or Ashby boards on your profile | No jobs from those companies |
| Local employers from Google Maps | `GOOGLE_MAPS_API_KEY`, plus `ANTHROPIC_API_KEY` to read careers pages | No employer websites checked |
| AI resume reading and scoring | `ANTHROPIC_API_KEY` | Free keyword matching |
| Tailored resumes and cover notes | `ANTHROPIC_API_KEY` | Your resume as it is, with a short standard cover note |
| Deep search preparation packs | `ANTHROPIC_API_KEY`, plus `TAVILY_API_KEY` and `GOOGLE_MAPS_API_KEY` for more sources | Not available |
| Job ranking | `GOOGLE_API_KEY` | Skill matching only |
| Trade Me jobs | `TRADEME_CONSUMER_KEY` and `TRADEME_CONSUMER_SECRET` | No Trade Me jobs |
| SEEK, LinkedIn and Indeed alerts | `EMAIL_ENABLED`, `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD` and `ANTHROPIC_API_KEY` | No alert jobs |
| Employer address and phone | `GOOGLE_MAPS_API_KEY` | Details from the job post only |
| Employer news | `TAVILY_API_KEY` | No news |

Each search lists where it looked on the Pipeline page, and every job shows its source.

With a Maps key, each search finds up to 60 employers for your job titles and towns (3 Maps searches) and checks 8 saved employers' websites for open jobs. If you set business types under **Settings › Auto mode › Google Maps employers**, the searches use "{business type} in {town}" instead of your job titles, and the next run picks up where this one stopped. The business types are used even with Auto mode off. Change this with `MAX_DISCOVERY_SEARCHES_PER_RUN`, `MAX_EMPLOYER_SITES_PER_RUN` and `MAX_NEARBY_SEARCHES_PER_DAY` in `.env`. Many small employers have no careers page, so expect a few jobs per search from this source.

To connect Gmail, turn on 2-Step Verification for your Google account, create an app password at https://myaccount.google.com/apppasswords, then set these in `.env`:

```env
EMAIL_ENABLED=true
EMAIL_ADDRESS=you@gmail.com
EMAIL_APP_PASSWORD=your-16-letter-app-password
```

The app reads your mailbox read-only. It never sends, deletes or marks email, and it never opens links from alerts. Set your job alerts for NZ, for example on nz.indeed.com.

The search runs daily at 7 am NZ time **while the backend is running**. If the computer was off, it catches up the next time the backend starts.

## Tailored resumes

1. On **Shortlist**, approve a job. Tailoring starts straight away and usually takes under a minute.
2. Open **Resume review**. Each job shows your original resume next to the tailored one, with reworded lines highlighted.
3. Edit the cover note if you like, then **Approve**, **Reject** or **Regenerate**. **Download PDF** gives the file that will be attached, and **Download Word** gives an editable copy of the same resume.

Tailoring only rewords and reorders what your resume already says. Titles, employers and dates are copied from your resume, never from the AI. Every result is checked twice: by code (no new numbers or skills) and by a second AI check against your resume and the job post. Anything unsupported goes back to your original wording, and the Fact check box lists what changed back.

Your name, email and phone at the top of the PDF come from **My resume profile** under "Your details for resumes". Before your resume goes to AI (sections, profile, tailoring, the fact check and the deep-search pack), email addresses and phone numbers are removed. Your name, LinkedIn and WhatsApp number are removed too, using the stored details with any blank filled from the resume text (the name only when it has four or more characters). Referees and role locations are not sent. The greeting and sign-off are added by the app.

Tailored resumes use the design you chose on the [Resume builder](#resume-builder). Tailoring uses your master CV only when it has at least one role. Otherwise, or without an AI key, the PDF and Word file use your uploaded resume as it is with a short standard cover note, and the checks do not run (see [Skill coverage](#skill-coverage)). Tailoring never adds a skill you marked **Not me**, and never claims one in the cover note, unless your master CV itself shows it. The uploaded resume text alone does not count. A declined skill is also left off the tailored Key skills list unless your master CV lists it.

If tailoring fails, the job shows the error and a **Try again** button. Failed jobs are not retried on their own, so a broken key does not keep using calls. A queue every 15 minutes picks up approved jobs that have not been tried yet, for example after a restart. Approved resumes wait for Phase 3, which adds email sending.

Models are set in `.env`: `RESUME_MODEL` reads your resume into sections, `TAILOR_MODEL` writes the tailored version, and `SCORING_MODEL` runs the fact check.

## Resume builder

Open **Resume builder** in the menu, after **Shortlist**. It holds your **master CV**: the one version of your resume that the app edits, searches with, scores with and tailors from.

- **Contact:** name, email, phone, city, LinkedIn, WhatsApp and a work-rights line (for example "NZ citizen", or your visa and its expiry date).
- **Sections:** headline, profile, key skills, work history (title, employer, location, dates and bullets), education and certifications, interests and referees.

The builder starts from your uploaded resume. With an `ANTHROPIC_API_KEY`, the AI splits it into sections, after your contact details are removed. Without a key, the form's Key skills start from your resume profile's skills, for display only: nothing is saved until you press Save CV. When you save, new key skills and your headline are added to your resume profile, so the daily search and scoring use them. Nothing is removed from your profile this way. Your name also becomes your profile name.

### Four designs

Choose one of four looks: **Classic**, **Modern**, **Compact** or **Executive**. Each prints the same content in the same order, on A4 in a single column. They differ in accent colour, heading style, name alignment and spacing. Compact also uses smaller type: a 15 pt name and 8.5 pt text and headings, against a 20 pt name and 9.5 pt text elsewhere. Your choice applies to every file, including tailored resumes.

- The PDF uses DejaVu Sans for all four, so macrons such as "ā" print correctly.
- The Word file uses Georgia (Classic), Calibri (Modern), Arial (Compact), and Cambria headings with Calibri text (Executive).
- Nothing is in a table, text box, image, or header or footer, because applicant tracking software often misreads those.

Download the **PDF** or **Word** file from the builder. Each tailored resume has both as well.

### ATS check

Below the builder, the **ATS check** lists nine items, each marked ok or not. It has no score and no pass mark. It runs when the page opens and after each save. Each run renders fresh PDF and Word previews from your saved CV and checks those files.

1. **One column, no tables, text boxes or images.** Every design is built this way, so this always passes.
2. **Name and contact details at the top of the page body.** Your name must be the first line of the PDF, with an email or phone number.
3. **Standard section names in the NZ order.** Profile, Key skills, Work history, Education and certifications, Interests (only when filled in) and Referees.
4. **Dates as month and year,** such as "Mar 2021 – Present".
5. **Two pages or fewer.**
6. **A profile of 50 to 150 words.**
7. **No photo, date of birth, gender, marital status, nationality or religion.** The check looks for these as field labels in the text, such as "Gender:". It cannot see a photo.
8. **Work rights stated.**
9. **Files under 2.5 MB,** for the PDF and the Word file.

Press **Show what ATS software reads** to see the plain text taken from the PDF. If the check itself fails, the panel says **ATS check could not run**, and saving still works.

Applicant tracking software reads the text inside the file. It works best with plain single-column text, standard headings and your name on the first line. It cannot read text inside images, text boxes or headers, and it can jumble words in columns. The research behind these rules is in [reports/ATS resume parsing and scoring NZ.md](reports/ATS%20resume%20parsing%20and%20scoring%20NZ.md). The research found no published data on how SEEK, Trade Me, JobAdder or PageUp parse resumes, so the check is a sound guide, not proof for those sites.

### New Zealand CV conventions

The layout follows the New Zealand advice in that report, including Tahatu's CV guidance.

- Two pages if you can, with the sections in the order above.
- Your name, then the headline, then one contact line: city, phone, email and LinkedIn. WhatsApp is added only when it is a different number. The work-rights line comes after that.
- Month and year for every date. The builder keeps the order of jobs you enter, so put the most recent first.
- Plain text, with the accent colour only on headings and rules. There are no fields for personal details such as a photo, date of birth or marital status.
- "Available on request." under Referees, unless you change it.

### Email signature and WhatsApp

Emails and follow-ups end with your name, then your phone and WhatsApp numbers from the builder's contact details. If the two numbers are the same, the line reads "Phone and WhatsApp". Otherwise there are separate Phone and WhatsApp lines. The PDF is unchanged.

The app never messages employers on WhatsApp. WhatsApp is only for your own updates, as described under [AI phone calls and WhatsApp updates](#ai-phone-calls-and-whatsapp-updates-phase-4).

After updating the code, run `.venv\Scripts\python -m app.db.migrate` once in `backend` to add the resume builder columns and the skill decisions table.

## Skill coverage

On the **Resume review** page, **Skill coverage for this job** lists the skills the ad asks for and where your CV shows them. The **Shortlist** shows a shorter count for each job. If the AI cannot read your CV sections at that moment, the Shortlist still loads and counts, using your profile's skills.

- When the AI scores a job, it also reads the ad's **required** and **nice to have** skills. Only skills the ad names are kept. Jobs scored before this update, and jobs whose scoring found no required or nice-to-have skills and whose skills were not split into required and nice to have, show the skills the earlier scoring listed as matched or missing, as one group. Those were not checked against the ad. Without an AI key, the keyword scorer lists the skills it finds under **Skills the ad mentions**.
- The two groups are counted separately, for example "3 of 4" required.
- Each skill shows where your CV mentions it, looking in this order: a role (title, then bullets), your profile, key skills, then education.
- Synonyms count. The app knows pairs such as AWS and Amazon Web Services, Postgres and PostgreSQL, K8s and Kubernetes, and JS and JavaScript. When a synonym matched, the panel says "Matched as AWS". Matching ignores capitals and allows a plural. Skills of two letters or fewer, such as Go, match only in the capitals you typed, so "Go" does not match "we go live".
- Coverage is a guide, not a score. There is no pass mark, and it does not change the match score. The panel says: "How many of the ad's skills your CV shows, and where. Employers' systems differ, so this is a guide, not a prediction of an interview."
- On the **Shortlist**, a chip shows the required count. It reads "Skills: 3 of 4 required" when the ad's skills are split into required and nice to have, and "Skills: 3 of 4 in the ad" when they are not.

### Your decisions

For a skill your CV does not show, choose one of these:

- **I have this** adds the skill to your resume profile, and to your Key skills on the master CV when the CV has content. The skill then shows as "Added by you to Key skills", and it counts as covered. With no CV content and no AI, the master CV is not saved from this.
- **Not me** records that you don't have it. The skill counts as declined. Tailored resumes never add it, as described under Tailored resumes.
- **Undo** is offered while a skill is marked added or declined. Undoing **I have this** removes the skill from your Key skills and resume profile only when the app added it. A skill you already had stays. Undoing **Not me** only clears the answer. Once a skill marked **Not me** appears in your CV, it shows as covered and no Undo is offered.

## Deep search

Deep search researches one job and its employer and writes a **preparation pack**. It shows on the job's **Preparation** tab:

- how each requirement in the advert matches a line from your resume, or a gap
- the likely interview stages, to confirm with the recruiter
- a pay range when a source gives one
- what the employer does and recent news
- questions to ask
- things to brush up on
- practical details
- application tips
- what's still unknown

Every employer fact links to the page it came from.

Switch it on under **Deep search** on **My resume profile**. When it's on, it runs each time you approve a job. You can also press **Run deep search** on any job's Preparation tab. In the **Extra details** box you can paste a company or news link, or text from the advert.

What it reads:
- the job post
- your extra details
- the advert page
- the employer's website and careers page
- Google Maps, with `GOOGLE_MAPS_API_KEY`
- web search results, with `TAVILY_API_KEY`

It never opens SEEK, LinkedIn, Indeed, Glassdoor, Trade Me, Facebook or Instagram pages, including links you paste.

Limits:
- **Per run:** 4 searches, 6 pages, 3 extra steps chosen by the AI when sections are still empty, 14 AI calls, and an estimated US$0.12 ceiling.
- **Per month:** 30 runs by default, which you can change. A test run cost about NZ$0.04, and each pack shows what it cost.
- **Google Maps:** at most `MAX_PREP_PLACES_CALLS_PER_MONTH` calls (default 1000).

It checks its own work:
- Each note the AI takes must quote the page it came from, word for word, in 25 words or fewer, and can't add a number the quote doesn't have. Notes that fail are left out and listed under **Could not verify**.
- The employer, pay and practical lines are built from those checked notes, each with its quote, so the AI writing the pack can't add claims of its own.
- A resume line that isn't word for word in your resume is marked **Check this**.
- Notes that mention roles such as CEO, founder, director or recruiter are discarded, so people's names aren't kept.
- A link on a blocked site is refused before a run starts.

Employer facts are reused for 30 days for other jobs at the same company. About and news facts are also given to resume tailoring.

Runs wait in a queue and go one at a time. A queue job every 15 minutes picks up any that are waiting. A failed run shows its error and a **Try again** button; it isn't retried on its own. A run cut off by a restart is marked failed after 10 minutes.

Deep search needs `ANTHROPIC_API_KEY`. The models are `PREP_MODEL` (default Haiku), which plans, reads and explores, and `PREP_WRITE_MODEL` (default Sonnet), which writes the pack. `USD_TO_NZD` sets the rate used to show costs.

After updating the code, run `.venv\Scripts\python -m app.db.migrate` once in `backend` to add the deep search table.

## Sending applications (Outbox)

After you approve a tailored resume on **Resume review**, it waits under **Ready to apply** on **Outbox and follow-ups**.

- **Queue email** sends the cover note with the tailored PDF attached, from your own Gmail. The address box is filled in when the advert gives one ("send your CV to …") or the employer's contact details have one (see [Employer contact details](#employer-contact-details)), and you can change it. It refuses an advert that asks you to apply on the job site ("This advert asks you to apply on the job site.").
- **I applied on the job site** is for SEEK, LinkedIn and other jobs you apply for on the site. The app tracks the job and reminds you to follow up.

The rules:
- At most 15 emails a day (change it on the Outbox page). A failed send is retried twice, 15 minutes apart, then shown under **Failed** with **Try again**.
- With no reply after 5 working days (weekends and NZ public holidays skipped; regional anniversary days are not), a short follow-up is sent in the same email thread. A second follows 5 working days later, and the job closes 5 working days after that.
- **Follow-up mode** is set under **Settings › Auto mode › Follow-ups**. The default, **Send follow-ups automatically**, is what is described above. With **Ask me before each follow-up**, a due follow-up waits in the Outbox under **Follow-ups waiting for you**. **Send** queues it, and it goes out on the next run. **Skip** stops follow-ups for that job. You get a notification when one is waiting. A draft waits until you press **Send** or **Skip**. Skip stops follow-ups for the job, and the job is then not closed automatically. A job closes automatically only after two follow-ups have been sent, in both modes.
- Each email ends with your name and your phone and WhatsApp numbers, from the [Resume builder](#resume-builder) contact details.
- With `EMAIL_ENABLED` set, replies are noticed automatically: any email from that address after you applied marks the job **Replied** and stops follow-ups. You can also press **They replied**, **Stop follow-ups** or **Close**.
- The Outbox is checked every 15 minutes while the backend is running.
- Automatic replies such as "out of office" are ignored, so follow-ups continue.
- A bounced email returns the job to "Ready to apply", so you can choose another address, and you get a WhatsApp update.

**Nothing is sent until you switch it on.** Sending uses the same Gmail app password as reading alerts. Add this to `backend/.env` and restart the backend:

```env
EMAIL_SEND_ENABLED=true
```

Sending signs in to `smtp.gmail.com` over TLS, and refuses to sign in to any other server without encryption. `EMAIL_SMTP_HOST` and `EMAIL_SMTP_PORT` change the server.

After updating the code, run `.venv\Scripts\python -m app.db.migrate` once in `backend` to add the Outbox columns.

## Employer contact details

For each employer you save, the app shows its contact details: phone, email, website, contact and careers pages, a LinkedIn company link, address, map link, opening hours and rating. Each line says where it came from.

**Where you see them**
- **Employers page:** saved employer cards show the contact details, with a **Get contact details** button. Nearby search results show what Google Maps returns (phone, address, business type, rating, hours). Save an employer to see its contact details.
- **Job, Employer tab:** the same details for that job's employer. The button is on the Employers page.

**Where they come from**
- **Google Maps** (`GOOGLE_MAPS_API_KEY`): phone, rating and opening hours. Business type is shown on search results only. A saved employer's map link is built from its saved address.
- **The employer's own website:** email addresses, hiring addresses (careers@, jobs@, hr@ and similar), a phone number, links to the contact and careers pages, a LinkedIn company link, and sometimes a named person who handles hiring.

**When lookups run**
- When you save an employer, in the background.
- When you approve a job, in the background.
- In Auto mode, when an approved advert gives no address (see Auto mode below).
- During the daily search, for employers of shortlisted jobs that have not been researched yet. At most 10 a run (`MAX_EMPLOYER_PROFILES_PER_RUN`).
- When you press **Get contact details**. This reads the website again, even if it was checked recently.
- Automatic lookups skip an employer checked in the last 30 days. If its website could not be read because of a timeout, a dropped connection, rate limiting or a server error, the lookup does not count as checked and the next automatic lookup reads it again. If the site refused access (for example a 403), the lookup still counts as checked, so use **Get contact details** to try again sooner.

**Limits**
- At most 3 pages per employer: the home page, then the contact and careers pages it links to. Pages are read through the same reader as the rest of the app, which respects robots.txt. Only pages on the employer's own site are read. A careers page on a hiring system such as Workday, or on a separate careers subdomain, is shown as a link, not read.
- LinkedIn is never read. The app shows only the company page link found on the employer's site, for you to open.
- Addresses are never guessed, such as firstname@company.
- Only the text of the careers and contact pages goes to AI, and only when `ANTHROPIC_API_KEY` is set. The AI looks for people the page names for hiring. Without a Claude key that check is skipped and the other details still work.
- A named person is kept only when the page shows their name, a hiring job title and a short quote (25 words or fewer) that appears on the page. Their email or phone is shown only when the page gives it.

**The Outbox address.** When an application has no address in its advert, the Outbox suggests the first of these it finds: a hiring address from the employer's site, the email of a named hiring contact, then the general email.

**Outbox contacts list.** Under **Contacts** on the Outbox, each approved or sent application shows the employer's address when the app has found one. When it has none, the list shows why:
- "Advert asks you to apply on the job site"
- "No website known"
- "Website not checked yet"
- "Could not read the website"
- "Checked {d Mon yyyy}: no email on the site", for example "Checked 3 Nov 2026: no email on the site"

**Find contacts** reads the employer's website again at once. On the Employers page, a saved employer shows "Emailed {date}", "Replied" or "Do not contact" when it is blocked from enquiries.

## AI phone calls and WhatsApp updates (Phase 4)

Both are off until you switch them on in `backend/.env`. The **Settings** page shows their status, has test buttons, and lists recent calls.

**AI phone calls (OmniDimension).** When an emailed application gets no reply after two follow-ups, the app calls the employer instead of closing the job. The call goes to the employer's published business number from Google Maps or their website.

- The AI assistant says it is calling for you, and asks where to send your resume.
- Calls go out Monday to Friday, 9:30 to 4:30 NZ time, with at most `MAX_CALLS_PER_MONTH` calls a month (default 5).
- Afterwards, the app fetches the result: the transcript, how long the call took, and any email address given. The Outbox then shows **Email my resume to …**.
- Jobs with no published number close as before.

To set it up:

1. In the OmniDimension dashboard, create an **outgoing** agent.
   - Set its maximum call length to 180 seconds.
   - Make its welcome message say it is an AI assistant calling on behalf of `{{candidate_name}}`.
   - Its instructions can use these values, which the app sends with each call: `candidate_name`, `candidate_email`, `job_title`, `company`, `applied_on`, `candidate_summary` and `purpose` (`follow_up` or `test`).
2. Add to `backend/.env`:

```env
CALLS_ENABLED=true
OMNIDIM_API_KEY=your-key
OMNIDIM_AGENT_ID=your-agent-id
```

3. Restart the backend and press **Test call to my phone** on Settings. This rings the phone number under "Your details for resumes".

When `EMAIL_ADDRESS` is set, OmniDimension also emails you a summary of each call. Each call costs about NZ$0.15–0.30 a minute.

**WhatsApp updates.** These go only to you, through WhatsApp Web, which you link with a QR code on **Settings › WhatsApp**. Nothing is sent to employers on WhatsApp, because Meta's rules don't allow messaging people who haven't opted in.

You get an update for:
- new shortlisted jobs
- resumes ready for review
- employer replies
- follow-ups due
- finished calls
- emails that failed to send or bounced
- Auto mode emails sent, and jobs it could not email because the advert or employer gives no address
- the evening summary, at 18:00 (see Auto mode)

To set it up:

1. Start the WhatsApp service in a second terminal. It needs Node 20 or newer, and it listens only on this computer, at `127.0.0.1:3010`:

```powershell
cd whatsapp-service
npm install     # first time only
npm start
```

2. In `backend/.env`, set:

```env
WHATSAPP_ENABLED=true
WHATSAPP_TO=+6422XXXXXXX
```

   Leave `WHATSAPP_SERVICE_URL` empty to use this service.
3. Restart the backend, open **Settings › WhatsApp**, and scan the QR code: WhatsApp › Settings › Linked devices › Link a device.
4. Press **Send me a test WhatsApp**.

Some details:
- The login is kept in `whatsapp-service/auth/`, which git ignores and which gives access to your WhatsApp, so never share it. **Unlink WhatsApp** removes it.
- The service only messages the linked number. To send to another number of yours, start it with `WA_ALLOWED_TO=64XXXXXXXXX`.
- To require a token, start it with `WA_TOKEN=...` and put the same value in `WHATSAPP_SERVICE_TOKEN`.
- Messages to your own number arrive in "Message yourself" and may not ring. For alerts with sound, link a second WhatsApp number to the service and set `WHATSAPP_TO` (and `WA_ALLOWED_TO`) to your main number.
- WhatsApp Web through Baileys isn't an official WhatsApp product, so keep it to these low-volume updates.

After updating the code, run `.venv\Scripts\python -m app.db.migrate` once in `backend` to add the calls and notifications tables.

## Auto mode (Phase 5)

Auto mode acts for you, so it's off until you switch it on under **Auto mode** on the Settings page. Every 15 minutes, while the backend is running, it:

1. approves shortlisted jobs that score at least your **Minimum score** (default 80), up to **Jobs a day** (default 5), best first. This starts tailoring, and deep search if that's on.
2. approves the tailored resume, but only for jobs auto mode approved itself, never for jobs you approved by hand.
3. queues the application email when the advert or the employer's public record gives an address. Auto mode looks up the employer's website first when the advert gives none (see below). Adverts that say to apply on the job site only are never queued by auto mode. Jobs still without an address stay in the Outbox under "Ready to apply", and you get a WhatsApp update.

Everything after that follows the normal rules:
- emails still need `EMAIL_SEND_ENABLED=true` and stay within the daily send limit
- follow-ups, reply checks and AI calls work as usual

**Waiting for contact details.** As soon as auto mode approves a job, it looks up the employer's website. If the advert gives no address, auto mode waits for that lookup for up to 24 hours after the approval. A website that could not be read is tried again at most once an hour. After 24 hours, or straight away when the employer has no website or its site was already checked, the job waits under "Ready to apply" and you are told to apply on the job site.

**Adverts to apply for on the job site.** An advert that says to apply on the job site only, for example "apply online only", "please do not contact" or a jobs.govt.nz link, is never emailed by auto mode. You get a WhatsApp update to apply on the site yourself. **Queue email** on the Outbox refuses them too.

**Changing your areas** closes the jobs you have found or shortlisted that are outside the new areas. Each one shows the note "Outside your areas".

**Google Maps employers.** Under **Settings › Auto mode › Google Maps employers**, switch on **Email Google Maps employers automatically**. It needs Auto mode on. After each daily search, the app emails up to **New employers a day** (1 to 10, default 5) of the employers it saved from Google Maps that have no advert with you:
- Only employers in your areas that have an address. The app looks up their website, and emails only when it publishes an email address. Employers without one are skipped, and looked at again the next day.
- Never an employer you have applied to, one that has replied or bounced, or one whose site says it takes no unsolicited applications (for example "no unsolicited applications", "no cold calls" or "no recruitment agencies").
- Each email is an enquiry, with the subject "Enquiry about opportunities at {company} – {your name}", your cover note with your signature, your master CV attached, and the line "If you'd rather I didn't contact you again, just reply and I won't." An enquiry gets one follow-up and then closes. It never leads to a phone call.
- A reply or a bounce stops enquiries to that employer. Cancelling a queued enquiry closes it.
- Switching **Email Google Maps employers automatically** off, or Auto mode off, stops enquiries at once: enquiries not sent yet are cancelled, approved ones that were never sent are closed, and sent ones get no follow-up. Replies and bounces are still noticed.
- Adverts are sent before enquiries, within the daily send limit.
- Your master CV needs at least one role. Without one, nothing is sent and the app says: "Add your work history in the Resume builder to start Google Maps outreach."

**Evening summary.** At 18:00 New Zealand time the app sends one WhatsApp line about the day, for example "Today: 1 application sent, 1 reply, 2 Google Maps employers emailed." It is sent only on days with activity, and only when WhatsApp is set up. It never includes an employer's email address or phone number.

**Still needs you:**
- **Adverts that ask you to apply on the job site.** Neither auto mode nor **Queue email** emails them. Apply on the site, then press **I applied on the job site** on the Outbox.
- **Jobs whose employer publishes no email.** They wait under "Ready to apply". The **Contacts** list on the Outbox gives the reason. Add an address, or apply another way.
- **Running the migrations** (below) and restarting the backend before using these features.

Auto mode needs your own uploaded resume, and it ignores example jobs. Switching it off stops new approvals, but emails already queued for adverts still go out; cancel them on the Outbox. Google Maps enquiries stop at once (see Google Maps employers above). The daily search and Google Maps outreach run for the first profile only. Each auto-approved job says "Approved by auto mode" in its Contact history. Without a Claude key, it sends your resume as it is with a short standard cover note.

After updating the code, stop the backend, run `.venv\Scripts\python -m app.db.migrate` once in `backend`, then start the backend again. This adds migrations `0011_outreach.sql` (Google Maps outreach) and `0012_contacts_attempted.sql` (contact checks). Google Maps outreach and Auto mode's wait for contact details need them.

## Project docs

- [GOAL.md](GOAL.md): what this is, the phases, and the rules
- [ARCHITECTURE.md](ARCHITECTURE.md): layers and debugging
- [AGENT.md](AGENT.md): commands and rules for AI coding agents
- [docs/DATABASE.md](docs/DATABASE.md), [docs/PROCESS_FLOW.md](docs/PROCESS_FLOW.md), [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md)
