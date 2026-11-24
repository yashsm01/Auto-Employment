# Deep search for job preparation: design

Date: 24 November 2026. Status: approved by the user on 24 November 2026.
Research behind it: [reports/Job preparation deep search.md](../../../reports/Job%20preparation%20deep%20search.md).

## Intent

The user wants the app to do the research they would otherwise do by hand before applying for a job or going to an interview. For one job, an agent looks at the job description, the user's resume, a link the user gives, and Google Maps. It then produces a **preparation pack**: how the user's experience matches the job, what the employer does and has done lately, the likely interview stages, a pay range, questions to ask, things to brush up on, and practical details such as location and work style.

The user asked for this to be an option they can switch on and off. It is new, not part of the original plan. It overlaps the plan's "Build employer profile" step (about their work, recent news), which is only partly built today.

## Goals

- An on/off switch for deep search.
- A preparation pack per job, with eight sections (listed under "The pack").
- Every employer fact in the pack links to the page it came from. Pay figures show their source and date.
- Each run shows what it cost, and a monthly cap stops runs before the budget is spent.
- It reuses the tools the project already has: Google Places, the Jina website reader, Tavily search and Claude.

## Non-goals

- Sending applications or finding who to email. That is Phase 3.
- Live help during an interview, mock interviews or practice question banks.
- Researching people beyond a business role and contact details the employer publishes.
- NZ Companies Office or NZBN data. Their API format is not confirmed yet.
- Calculating commute times. A Google Maps directions link is enough.

## Anti-goals (failure even if it technically works)

- The pack states something about the employer that no source supports.
- Any request to SEEK, LinkedIn, Indeed or Glassdoor, including links the user pastes.
- Runs that quietly use up the NZ$5–10 monthly budget.
- Instructions inside a fetched web page change what the agent does.

## Constraints

- Budget: NZ$5–10 a month for the whole app. Deep search should cost about NZ$0.07–0.15 per run.
- AI and search keys come only from `backend/.env`. The shell's Anthropic key must never be used.
- Text from web pages, job posts and the user's link is data. It never goes in a system prompt and is never followed as instructions.
- Privacy Act 2020: about people, keep only a business role and contact details the employer published, with source and date.
- Layering stays as it is: api → services/graphs → chains/repositories/providers.
- `graph_runs.graph` only allows `lead`, `resume` and `outreach`, and only one run per graph can be running at once.

## Approaches considered

| | How it works | Cost per run | Outcome |
|---|---|---|---|
| A. Fixed steps | AI plans searches, the code reads up to 6 pages, AI extracts quoted facts, the code checks for gaps once, AI writes the pack | about NZ$0.07 | Not chosen |
| B. Free agent | Claude picks tools in a loop (search, read, Maps) until it decides it is done | NZ$0.30–0.80 | Rejected: too costly, hard to test, most exposed to hostile pages |
| **C. Mixed** | A, plus a short agent step: when sections are still empty, Claude may make up to 3 tool calls of its own choosing | about NZ$0.10–0.15 | **Chosen by the user** |

Anthropic's Managed Agents (Anthropic hosts the agent loop) was also considered and not used. The user wants the agent inside their own LangGraph app, the tools use keys held locally, and Managed Agents bills session runtime on top of tokens.

## What the user decided

- Approach C.
- Keep the on/off switch.
- A monthly limit of 30 runs by default, changeable on the profile page.
- Inputs: the job description, the user's resume, a link the user gives, and Google Maps.

Everything else below is the designer's proposal. Items marked **(designer's call)** are the ones most worth a second look.

## The design

### The switch

- A "Deep search" switch on **My resume profile**, with a monthly run limit (default 30, chosen with the user; about NZ$2–4.50 a month). It is stored in `settings.ai` as `{"deep_search": {"enabled": bool, "monthly_limit": int}}`.
- **On:** deep search starts automatically when the user approves a job, alongside tailoring. **(designer's call)** Approved jobs are the ones the user will apply for, Once the monthly limit is used up, automatic runs pause and the button says the limit is reached.
- **Off:** nothing runs automatically.
- Either way, a **Run deep search** button on the job page runs it once for that job. Each run counts toward the monthly limit. **(designer's call)**

### Which jobs can have a pack

Every job in the app already has an `applications` row from the moment it is found, with status `found` and onward. A pack therefore always belongs to an application (`application_id` is required). The Preparation tab works on any job page, whether or not it has been approved.

### When several runs are requested

Only one `prep` run can be running at a time; this is the existing `graph_runs` rule. Runs therefore wait in a queue, the same way tailoring does:

- A request (approval with the switch on, or the button) creates a `prep_packs` row with status `queued` and starts the queue worker in the background.
- The worker takes queued rows oldest first, one at a time, until none are left.
- If another run holds the lock, it stops and leaves the rest queued.
- A 15-minute scheduler job picks up anything still queued, for example after a restart.
- A failed run sets the row to `failed` with the error. It is not retried until the user presses Try again.
- Asking again while a run for that job is already queued or running does nothing.

### Inputs for one run

- The job: title, company, location and description, from `jobs`.
- The employer: name, website, address and existing `company_facts`.
- The user's resume sections, already cached for tailoring.
- An optional **Extra details** box on the job page, for a link or pasted text. A link on a blocked site is refused, and the page asks the user to paste the text instead.
- The job's own URL, if it is not on a blocked site.

### The graph: `prep`

A new LangGraph graph in `backend/app/graphs/prep/`, the same shape as `lead` and `resume`: a graph file, a state, deps, and one file per node.

1. `load_job`: reads the inputs above. Stops with a clear error when there is no Claude key or the monthly limit is reached.
2. `plan` (Haiku 5.5, effort low): picks up to 4 search queries and which sections need web facts.
3. `gather` (code):
   - Google Places for the employer (address, website, rating), if a key is set and the monthly Places counter is under Google's free amount. Once the counter reaches it, the run skips Places, carries on, and says so in the pack.
   - The employer's site through Jina: home, About, Careers.
   - Tavily for the planned queries.
   - The user's link.
   - Every URL goes through one blocklist check. Up to 6 pages, each cut to about 6,000 tokens and stored with an id as untrusted text.
4. `extract` (Haiku 5.5, effort low, one call per page): returns facts, each with a source id and a verbatim quote of up to 25 words.
5. `check_gaps` (code): lists the required sections that still have no facts.
6. `explore` (Haiku 5.5, only when gaps remain and budget is left). This is approach C's agent step.
   - Claude gets three tools: `web_search(query)`, `read_page(url)` and `find_place(name, town)`, with `tool_choice` auto and `strict` schemas.
   - At most 3 tool calls in total.
   - Pages it reads go through the same blocklist, extract and quote check.
7. `write` (Sonnet 5.5): writes the pack as structured output, using `messages.parse` like the existing chains.
   - The code then checks every source id and quote against the stored page text.
   - A fact that fails is dropped from employer sections and listed as "could not verify". One retry if the output is invalid.
8. `save`: stores the pack and its sources, records the cost, and adds a `note` event to the job.

A failed run is rolled back and shown on the job page with a Try again button, the same as tailoring.

### The pack

Each item carries the ids of its sources. Sections, in order:

1. **Your evidence for each requirement.** Each must-have or nice-to-have from the advert, paired with a matching line from the resume or marked as a gap. Resume lines are quoted, never invented.
2. **Likely interview stages**, marked "unconfirmed, ask the recruiter".
3. **Pay range.** The posted range if the advert has one. Otherwise figures from sources, each with its date and how it was measured, or "unknown".
4. **About the employer.** What they do, recent news, products. Every line is linked.
5. **Questions to ask**, drawn from section 4.
6. **Things to brush up on.** The advertised stack compared with the resume.
7. **Practical details.** Address, a Google Maps directions link from the user's first region, and on-site, hybrid or remote status if the advert says.
8. **Application tips.** What to stress in the cover note. It must only use facts from the resume.

A final **Unknowns** list names what no source covered, such as culture, referee process or work-rights requirements, instead of guessing.

Employer facts that passed the quote check (`about`, `recent_news`) are also saved to `company_facts` with confidence `medium`, so resume tailoring can use them. **(designer's call)**

### Storage

Migration `0004`:

- Adds a `prep_packs` table: `id`, `profile_id`, `application_id` (required), `company_id`, `status` (`queued`, `running`, `done`, `failed`), `error`, `content jsonb`, `sources jsonb`, `cost_usd numeric`, `created_at`, `finished_at`, with row level security like the other tables.
- Lets `graph_runs.graph` be `prep`.

Running deep search again on the same job makes a new pack; the page shows the newest one.

If another pack for the same employer is under 30 days old, its employer facts from websites and search are reused instead of searched again. Places data is not cached beyond what Phase 1 already stores on `companies`, because Google's storage rules are not verified yet. **(designer's call)**

### People

Names of individuals found in sources, such as hiring managers or recruiters, are left out of the pack and not stored anywhere in this version. Finding a contact person belongs to the Phase 3 design, together with the Privacy Act rules for it. **(designer's call)**

### Cost controls

- **Per run:** 4 queries, 6 page reads, 3 explore tool calls, at most 14 model calls, and an estimated US$0.12 ceiling. These are checked before every call. A run that hits a limit finishes with what it has and says which limit stopped it.
- **Per month:** the run count is checked against the limit. The profile page shows "N of 30 deep searches used this month".
- **Places:** a counter keeps calls under Google's free monthly amount.
- **Measured cost:** each run's cost is worked out from the token counts the API returns and stored on the pack.

### Models and settings

- New `.env` settings: `PREP_MODEL` (default `claude-haiku-5-5`) for plan, extract and explore, and `PREP_WRITE_MODEL` (default `claude-sonnet-5-5`) for writing.
- Effort `low` on the Haiku steps (Haiku 5.5's default is `medium`) with capped `max_tokens`.
- Forced `tool_choice` is not supported on these models, so use `auto` with `strict` tools, or structured output.
- The Sonnet call uses the server-side fallback the project already uses.

### Blocklist

The existing `_BLOCKED_DOMAINS` in `app/providers/company/website_reader.py` gains `glassdoor.com` and `glassdoor.co.nz`. The check applies to search results, the user's link, the job URL and every `read_page` call.

### Screens

- **My resume profile:** the Deep search switch, the monthly limit, and the month's usage.
- **Job page:** a **Preparation** tab next to Match, Employer and Contact history. Its states:
  - Not run yet: Run deep search button and the Extra details box.
  - Running: a progress note, refreshed every few seconds.
  - Done: the pack, with sources, run date and cost.
  - Failed: the error and Try again.
  - No Claude key: says deep search needs one.

### Testing

- Unit tests with a scripted LLM and fake tools: the blocklist, quote checks, the gap check, all budget limits, the explore step stopping at 3 calls, and dropping unverified facts.
- Integration tests on the throwaway Postgres: approving a job with the switch on runs deep search; with it off, nothing runs; the monthly limit blocks runs; the API returns the pack.
- A live check on a throwaway database with the invented resume and one real public employer website.
- Measuring real cost on about 10 jobs needs the user's permission first, because it spends their money.

## Left to the builder

- Prompt wording, the Places field mask (choose fields in the cheapest tier that covers them), Tavily search depth, and how the pack is laid out on screen.
- Code structure inside the graph, provided it follows the existing graph layout.

## Not verified yet

Check these before or during the build:

- Which Places fields fall in which price tier, and Google's rules on keeping Places data.
- How many Tavily credits one search uses.
- The NZD/USD rate used for showing costs.
