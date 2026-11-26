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

With a Maps key, each search finds up to 60 employers for your job titles and towns (3 Maps searches) and checks 8 saved employers' websites for open jobs. Change this with `MAX_DISCOVERY_SEARCHES_PER_RUN`, `MAX_EMPLOYER_SITES_PER_RUN` and `MAX_NEARBY_SEARCHES_PER_DAY` in `.env`. Many small employers have no careers page, so expect a few jobs per search from this source.

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
3. Edit the cover note if you like, then **Approve**, **Reject** or **Regenerate**. **Download PDF** gives the file that will be attached.

Tailoring only rewords and reorders what your resume already says. Titles, employers and dates are copied from your resume, never from the AI. Every result is checked twice: by code (no new numbers or skills) and by a second AI check against your resume and the job post. Anything unsupported goes back to your original wording, and the Fact check box lists what changed back.

Your name, email and phone at the top of the PDF come from **My resume profile** under "Your details for resumes". Your email and phone number are removed from your resume before it is sent to AI. The greeting and sign-off are added by the app.

If tailoring fails, the job shows the error and a **Try again** button. Failed jobs are not retried on their own, so a broken key does not keep using calls. A queue every 15 minutes picks up approved jobs that have not been tried yet, for example after a restart. Approved resumes wait for Phase 3, which adds email sending.

Models are set in `.env`: `RESUME_MODEL` reads your resume into sections, `TAILOR_MODEL` writes the tailored version, and `SCORING_MODEL` runs the fact check.

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

- **Queue email** sends the cover note with the tailored PDF attached, from your own Gmail. The address box is filled in when the advert gives one ("send your CV to …") or the employer's contact details have one (see [Employer contact details](#employer-contact-details)), and you can change it.
- **I applied on the job site** is for SEEK, LinkedIn and other jobs you apply for on the site. The app tracks the job and reminds you to follow up.

The rules:
- At most 15 emails a day (change it on the Outbox page). A failed send is retried twice, 15 minutes apart, then shown under **Failed** with **Try again**.
- With no reply after 5 working days (weekends and NZ public holidays skipped; regional anniversary days are not), a short follow-up is sent in the same email thread. A second follows 5 working days later, and the job closes 5 working days after that.
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
3. queues the application email when the advert or the employer's public record gives an address. Jobs without an address wait in the Outbox under "Ready to apply", and you get a WhatsApp update.

Everything after that follows the normal rules:
- emails still need `EMAIL_SEND_ENABLED=true` and stay within the daily send limit
- follow-ups, reply checks and AI calls work as usual

Auto mode needs your own uploaded resume, and it ignores example jobs. Switching it off stops new approvals, but emails already queued still go out; cancel them on the Outbox. Each auto-approved job says "Approved by auto mode" in its Contact history. Without a Claude key, it sends your resume as it is with a short standard cover note.

After updating the code, run `.venv\Scripts\python -m app.db.migrate` once in `backend`.

## Project docs

- [GOAL.md](GOAL.md): what this is, the phases, and the rules
- [ARCHITECTURE.md](ARCHITECTURE.md): layers and debugging
- [AGENT.md](AGENT.md): commands and rules for AI coding agents
- [docs/DATABASE.md](docs/DATABASE.md), [docs/PROCESS_FLOW.md](docs/PROCESS_FLOW.md), [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md)
