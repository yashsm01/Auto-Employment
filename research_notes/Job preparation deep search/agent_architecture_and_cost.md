# Bounded low-cost deep search agent for job preparation (LangGraph 1.x + Claude)

Research date: 2026-11-24. Scope: one job per run (description, link, employer name, location). Output: sourced preparation notes. Budget: NZ$5-10/month across the whole tool, deep search on only some jobs. SEEK, LinkedIn and Indeed must never be fetched.

Verification status: pricing figures were read from the Anthropic pricing page on 2026-11-24. LangChain behaviour was read from the LangChain docs and release notes, with some points taken from search snippets and forum threads (marked). Tavily, Jina Reader and Google Places pricing were NOT checked in this pass and are listed as gaps.

---

## 1. Agent loop: what to build on in LangChain/LangGraph 1.x

### Takeaway
Use LangChain 1.x `create_agent` (from `langchain.agents`) for a tool-calling loop, or hand-write a small LangGraph `StateGraph` (model node, tool node, conditional edge) if you want a fixed, auditable state machine. Do not start new code on `langgraph.prebuilt.create_react_agent`: it has been deprecated in favour of `create_agent`.

### Cited Findings
- `create_react_agent` in LangGraph has been deprecated in favour of LangChain's `create_agent`, which "provides a simpler interface, and offers greater customization potential through the introduction of middleware" — [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- LangGraph v1 is described as "a stability-focused release for the agent runtime"; core graph APIs and execution model are unchanged; upgrade with `pip install -U langgraph` — [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- `create_agent` is the recommended agent API in the LangChain agents docs; pass `response_format=` to get a validated structured result, read from `result["structured_response"]`; configure retries with `ModelRetryMiddleware` / `ToolRetryMiddleware`; cap model calls with `ModelCallLimitMiddleware` (from `langchain.agents.middleware.model_call_limit`) — [LangChain agents docs](https://docs.langchain.com/oss/python/langchain/agents)
- The same docs say `create_agent` sets the recursion limit to 9,999 steps, and that production code should pass a lower `recursion_limit` in the invoke config — [LangChain agents docs](https://docs.langchain.com/oss/python/langchain/agents)
- LangGraph counts every node run as one step; the default `recursion_limit` is 25, so a model-node + tool-node round trip costs two steps and 25 steps is roughly 12 tool calls. Overrun raises `GraphRecursionError` — [LangChain forum / third-party guide, secondary; official JS error page](https://docs.langchain.com/oss/javascript/langgraph/errors/GRAPH_RECURSION_LIMIT) (official page confirms the error; full text not retrieved)
- Conflict to resolve when coding: the docs page says `create_agent` uses 9,999, while secondary sources describe a default of 25 for LangGraph graphs. Set `recursion_limit` explicitly either way.
- The `RemainingSteps` managed value lets a graph exit gracefully before the limit instead of failing hard — [LangChain forum thread, secondary](https://forum.langchain.com/t/gracefully-handling-graphrecursionerror-from-subgraphs-so-the-parent-agent-can-retry-or-degrade/2018)

### Inferences
- Budgets should be enforced in your own code as well as by `recursion_limit`: a counter in state (tool calls, fetched tokens, search calls, dollars spent so far) checked by a router before every model or tool node. `recursion_limit` is a backstop, not a budget.
- `ModelCallLimitMiddleware` in `create_agent` covers the model-call cap with less code than a hand-written counter, but a hand-written state counter is still needed for per-run dollar or token caps, which no middleware in the docs covers.
- For a bounded job, a hand-written `StateGraph` with a fixed topology (plan → search → read → extract → write) plus one optional bounded loop gives the most predictable cost. Use `create_agent` only if you want the model to choose its own tool sequence.
- `ToolNode` was not covered by the pages I could read. Treat it as the standard prebuilt tool-execution node, and verify its current import path against the installed version.

### Gaps
- Could not confirm the exact current `ToolNode` API or import path from the official docs in this pass.
- Could not confirm the current default recursion limit for a plain `StateGraph` from an official page.

---

## 2. Open-source deep research agents: structure and cost

### Takeaway
Open-source deep research projects (LangChain `open_deep_research`, GPT Researcher) use planner → parallel researchers → writer. Their per-report cost is high for a single-job task. Keep the structure, but drop parallel fan-out and use a single researcher with a hard tool budget.

### Cited Findings
- `open_deep_research` (LangChain, built on LangGraph StateGraph) originally used a supervisor that delegates to sub-researchers via a `ConductResearch` tool, a `think_tool` for reflection, and `ResearchComplete` to stop. Each researcher compresses its findings into a summary, and a final stage writes the report from the compressed notes. The project's own sources say this architecture has since changed significantly, so check the current repo before copying — [LangChain blog](https://www.langchain.com/blog/open-deep-research), [open_deep_research repo](https://github.com/langchain-ai/open_deep_research) (search snippets, repo not fetched)
- Each sub-researcher gets its own context window, which keeps the supervisor's context small — same sources
- GPT Researcher: a planner generates questions, execution agents (crawlers) gather information per question in parallel, each resource is summarised and source-tracked, and a publisher aggregates the report — [GPT Researcher repo](https://github.com/assafelovic/gpt-researcher)
- GPT Researcher's stated default costs: about $0.08 and one minute per standard report with default models; about $1.30 and 7-12 minutes for its Deep Research mode — [GPT Researcher repo](https://github.com/assafelovic/gpt-researcher). The same page's context-filter benchmark shows about $0.115-0.192 per report, so the headline figure and the benchmark disagree; treat both as vendor-reported
- Anthropic's multi-agent research system (Opus 4 lead, Sonnet 4 subagents) beat single-agent Opus 4 by 90.2% on its internal research eval. Agents typically use about 4× the tokens of chat; multi-agent systems about 15×. Token usage explained about 80% of performance variance on BrowseComp — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic's scaling guidance: simple fact-finding needs 1 agent with 3-10 tool calls; direct comparisons 2-4 subagents with 10-15 calls each; complex research more than 10 subagents. It also says multi-agent only pays when "the value of the task is high enough to pay for the increased performance", and that tasks needing shared context or many inter-agent dependencies are a poor fit — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic says "Agents struggle to judge appropriate effort for different tasks, so we embedded scaling rules in the prompts", and recommends explicit guardrails against agents "spiraling out of control" — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
- The Anthropic figures (1 agent, 3-10 tool calls for simple fact-finding) match a single job's preparation notes. A single researcher with 5-10 tool calls is the right shape. The parallel-subagent pattern is for broad multi-source reports and would multiply cost (roughly 4-15× tokens) without a matching quality gain for one job.
- Reuse from these projects: the researcher's compress-then-write step (keeps the final model call's context small); the explicit "think" / reflection step (cheap, improves stop decisions); and the explicit completion signal.
- Drop: the parallel supervisor, the separate publisher model call when a single structured-output call can produce the notes, and any multi-level tree exploration.

### Gaps
- No per-run token counts for `open_deep_research` were found in the pages read. The 4×/15× figures are Anthropic's own multi-agent numbers, not a measured cost for this task.
- Current open_deep_research architecture not verified from the repo.

---

## 3. Claude tool use, server tools, structured output, and cost per run

### Takeaway
Client-side tools (your own Tavily/Jina/Places wrappers) give you full control over domains, budgets and caching, and they can be combined with `messages.parse()` structured output. Anthropic server web search costs $10 per 1,000 searches plus tokens; server web fetch has no per-call fee, only tokens. A realistic Haiku-plus-Sonnet run with 5-10 searches and 5-10 page reads costs about US$0.04 (client search and fetch) to about US$0.19 (Anthropic server search, Haiku loop, Sonnet synthesis).

### Cited Findings
Pricing per million tokens (input / output), Anthropic first-party, from the [pricing page](https://platform.claude.com/docs/en/about-claude/pricing) read 2026-11-24:
- Claude Haiku 5.5: $0.10 / $0.50 for prompts up to 100,000 tokens; $0.50 / $2.50 above 100K. Cache write $0.125 (5-min); cache hit $0.01
- Claude Haiku 4.5 (for comparison): $1 / $5 — Haiku 5.5 is 10× cheaper on input
- Claude Sonnet 5.5: $2 / $10. Cache write $2.50 (5-min); cache hit $0.10
- Claude Sonnet 5: $2 / $10 (introductory pricing made permanent; the scheduled rise to $3/$15 will not happen)
- Claude Sonnet 4.6: $3 / $15
- Claude Opus 5.5: $4 / $20. Cache hit $0.20
- Batch API: 50% off input and output (e.g. Haiku 5.5 $0.05 / $0.25; Sonnet 5.5 $1 / $5) — not usable for a live per-job run, but usable for overnight backfills
- Prompt caching: 5-min write 1.25× base input; 1-hour write 2×; cache hit 0.1× on most models, 0.05× on Sonnet 5.5 and Opus 5.5
- Web search (Anthropic server tool, `web_search_20260209` on current models): $10 per 1,000 searches, plus standard token costs for search results (which count as input tokens). Each search counts once regardless of result count; failed searches are not billed — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Web fetch (server tool, `web_fetch_20260209`): no per-call charge; you pay tokens for fetched content (an average 10 kB page is about 2,500 tokens). Use `max_content_tokens` to cap cost — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Code execution is free when used together with web search or web fetch on the 2026 versions — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Tool-use overhead: the model adds a tool-use system prompt of about 286 tokens (auto) on Haiku 5.5 and Sonnet 5.5; 406 on Haiku 5.5 with forced tool choice — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Haiku 5.5 long-prompt rule: a request whose prompt is over 100K tokens pays the higher rate; keep each request well under 100K — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Data residency `inference_geo: "us"` adds a 1.1× multiplier; default global routing is standard price — [pricing page](https://platform.claude.com/docs/en/about-claude/pricing)
- Server tools: the claude-api skill reference (current 2026 docs) states `web_search_20260209` / `web_fetch_20260209` are current, that web fetch only fetches URLs already in the conversation, and that server-tool errors come back as HTTP 200 result blocks rather than exceptions (not raised as exceptions) — claude-api skill reference, shared docs
- Strict tool use: `strict: true` on a tool definition, with `additionalProperties: false` and `required` in the schema, guarantees valid tool inputs — claude-api skill reference, shared docs
- Structured output: use `output_config: {format: {...}}` (the old `output_format` parameter is deprecated); `client.messages.parse()` validates against a schema — claude-api skill reference, shared docs
- Citations: document citations (`citations: {enabled: true}`) are incompatible with `output_config.format` (returns 400). Plan source tracking with your own source IDs inside the structured output instead — claude-api skill reference, shared docs
- Forced `tool_choice` of `any` or a named tool returns 400 on Opus 5.5, Sonnet 5.5, Haiku 5.5 and Fable/Mythos 5.x. Use `tool_choice: auto` with `strict: true`, or structured output for the final JSON — claude-api skill reference, shared docs
- Thinking: on current models use `thinking: {type: "adaptive"}` or omit; `budget_tokens` returns 400 on 5.x models; default effort is `medium` on Haiku 5.5 — claude-api skill reference, shared docs
- Tool-result JSON: always parse tool inputs with `json.loads` (escaping may differ by model) — claude-api skill reference, shared docs

#### Cost per run (estimate, US$, pricing above, no caching)

Assumptions: one job per run; prompt sizes kept under 100K tokens.

| Scenario | Components | Anthropic cost per run |
|---|---|---|
| A. Recommended fixed pipeline, client-side search and fetch | 1 Haiku plan call (3K in, 0.5K out); 6 Haiku page-summary calls (4K in, 0.4K out each); 1 Sonnet 5.5 structured synthesis (12K in, 1.5K out). Search (Tavily) and reader (Jina) billed outside Anthropic. | Haiku ≈ $0.004; Sonnet ≈ $0.039; total ≈ $0.043 |
| B. Agent loop, Haiku 5.5, Anthropic server web search | 10 searches ($0.10); Haiku loop 10 turns averaging 15K in, 0.3K out ($0.017); Sonnet 5.5 synthesis 25K in, 2K out ($0.07) | ≈ $0.19 |
| C. Same as B but the loop uses Sonnet 5.5 | Sonnet loop 150K in, 3K out ($0.33); plus search and synthesis | ≈ $0.50 |
| D. Scenario A with Opus 5.5 synthesis | Synthesis 12K in, 1.5K out at $4/$20 | ≈ $0.07 total |

Caching: with 5-10 turns re-reading the same prefix, cache hits at 0.1× (or 0.05× on Sonnet 5.5) reduce the loop's input cost, so scenario B's loop cost drops further. Figures above are without caching, so they are upper bounds for the loop.

Monthly budget: NZ$5-10 is about US$3-6 at an assumed exchange rate of about US$0.6 per NZD (assumption, not checked). Scenario A allows roughly 70-140 runs per month before the budget is used; scenario B allows roughly 15-30 runs. Anthropic's own multi-agent post implies a broad agent loop costs roughly 4× a chat turn, so scenario B and C are the higher-risk options.

### Inferences
- Use client-side Tavily search and Jina Reader for the fetch step, not Anthropic server search and fetch. Reasons: (1) Anthropic's $10 per 1,000 searches is about $0.01 per search, and the external search cost is separate; (2) you can enforce the SEEK/LinkedIn/Indeed blocklist in your own code before any URL is fetched, which the server tool cannot guarantee beyond its `blocked_domains` option; (3) client-side tools combine cleanly with strict schemas and `messages.parse()`; citations via server search cannot be combined with structured output.
- If Anthropic server web search is used anyway, its results count as input tokens on every later turn, so cap `max_uses` and trim the result payload.
- Model choice: Haiku 5.5 for per-page extraction and the planning step, Sonnet 5.5 for the final structured synthesis. Keep the loop itself on Haiku. Note the project's own rule in the claude-api skill (default to Opus for new code unless a cheaper model is named) conflicts with a cost budget; this note assumes the user has chosen Haiku/Sonnet for cost reasons.
- Cap per-run budgets in code: max 10 searches, max 8 page reads, max 6K tokens per page after truncation (equivalent to `max_content_tokens` on the server tool), max 12 model calls, and a dollar estimate checked before each call.

### Gaps
- Tavily pricing, free-tier limits and per-credit cost not checked; affects scenario A's real cost.
- Jina Reader pricing and rate limits not checked.
- Google Places (Text Search / Place Details) pricing and free monthly credit not checked; this is a per-call cost that can exceed the Anthropic cost.
- Whether `web_search_20260209` can be combined with `output_config.format` in one request was not verified.
- Exact per-page token counts for Jina output were not measured; the 4K per-page figure is an assumption to test.
- The `messages.parse()` helper's exact Python signature was not read from the SDK in this pass.

---

## 4. Safety and quality for agents that read web pages

### Takeaway
Treat every fetched page as untrusted data. Anthropic's own defences (training, classifiers, safeguards) reduce but do not eliminate indirect prompt injection; its best published attack success rate is about 1.4% on Opus 4.5 with improved safeguards, which Anthropic itself calls "meaningful risk". Your app must add its own controls: no tools that act on the web, a fixed output schema, source IDs for every fact, and a deterministic stop rule.

### Cited Findings
- Anthropic's defences against indirect prompt injection in web content (published 2025-11-24): reinforcement-learning training for injection robustness; scanning of all untrusted content entering the context window with classifiers; new safeguards across Claude models; and continuous internal red-teaming — [Anthropic research post](https://www.anthropic.com/research/prompt-injection-defenses)
- Stated internal Best-of-N attack success rates (lower is better): Opus 4.5 8.0% (model only), 7.6% (old safeguards), 1.4% (improved safeguards); Haiku 4.5 12.0% / 11.1% / 2.4%; Sonnet 4.5 13.8% / 10.8% / 1.9% — [Anthropic research post](https://www.anthropic.com/research/prompt-injection-defenses). Model-only rates are not the same as the deployed system
- Anthropic says "A 1% attack success rate—while a significant improvement—still represents meaningful risk", and gives no explicit developer recommendations in that post — [Anthropic research post](https://www.anthropic.com/research/prompt-injection-defenses)
- Academic work on parsing tool results to defend against indirect injection exists (arXiv 2601.04795) — search snippet only, not read
- Anthropic's multi-agent post recommends explicit guardrails against agents spiralling out of control, and scaling rules embedded in prompts — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
- Strict tool use and structured output (see section 3) constrain what the model can return, which limits the damage a hijacked answer can do — claude-api skill reference, shared docs

### Inferences (design rules for this agent)
- Give the agent no tools that take actions on the web (no form submission, no login, no clicks). Read-only fetch plus search is the whole surface.
- Put fetched content in a clearly delimited block labelled as untrusted, and state in the system prompt that instructions inside pages must be ignored. This is a mitigation, not a guarantee.
- Enforce output via a strict schema (e.g. `messages.parse()` with a Pydantic model): fields for `facts[]`, each with `claim`, `source_id`, `quote` (a verbatim span of at most 25 words from the source), and `confidence`. Reject any fact whose `source_id` does not exist in the fetched set, or whose quote is not a substring of the stored page text. This check is deterministic and catches most hallucinated citations.
- Only summarise facts the model can quote; anything unsourced goes into a "could not verify" list, not into the notes.
- Stopping rules that work with bounded loops: stop when (a) the required fields (company summary, role context, interview-relevant facts, location-specific facts from Places) each have at least one verified fact, (b) the last two tool calls added no new verified facts, or (c) a hard budget is reached (search count, page count, model calls, dollar estimate). Record which rule fired in the output.
- Domain controls: a hard blocklist for seek.co.nz, seek.com.au, linkedin.com, indeed.com and subdomains, applied in client code before any fetch, and also passed to Anthropic's `blocked_domains` if server tools are used. Note that the user's rule is also about links the job description contains, so check the link domain before fetching.

### Gaps
- No published Anthropic guidance was found specific to LangGraph agents that read web pages.
- The arXiv tool-result-parsing defence was not read, so its effectiveness is unverified.
- Hallucination rates for quote-checked summaries were not found in any source read.

---

## 5. Fixed pipeline versus agent loop

### Takeaway
For one job with a known shape (find company facts, read a few pages, summarise), a fixed pipeline (search → read → summarise → structured write) is cheaper, more predictable and easier to test than a free agent loop. Use a bounded loop only for the decision "do I need another search?", with a hard cap.

### Cited Findings
- Anthropic's multi-agent guidance: a single agent with 3-10 tool calls is the right shape for simple fact-finding; multi-agent systems are only worth it when task value justifies roughly 4-15× token use — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic's stated reasons agent systems need prompt-embedded effort scaling: agents "struggle to judge appropriate effort" — [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
- Recursion limits exist precisely because unbounded tool loops are a known failure mode (a loop can repeat until the limit with no state change) — [LangChain GRAPH_RECURSION_LIMIT docs](https://docs.langchain.com/oss/javascript/langgraph/errors/GRAPH_RECURSION_LIMIT)

### Inferences
- Recommended shape (fixed topology with one bounded branch):
  1. `plan` (Haiku): produce up to 4 queries and the list of required fields. No tools.
  2. `search` (Tavily, client code): run up to 4 queries, merge and dedupe URLs, filter blocked domains.
  3. `read` (Jina Reader, client code): fetch up to 6 URLs, truncate to 6K tokens each, store as untrusted text with IDs.
  4. `extract` (Haiku, one call per page, parallel in LangGraph): return facts with `source_id` and a verbatim quote.
  5. `gap_check` (code, not model): if required fields are missing and budget remains, loop back to `search` once with new queries; otherwise go on.
  6. `write` (Sonnet 5.5, `messages.parse()`): produce the structured notes from verified facts only; run quote validation; reject and retry once on failure.
- Cost: about 15-20 model calls and about 10 tool calls in the worst case, with a total dollar estimate close to scenario A (about $0.05). A free Claude-driven loop for the same job typically spends more calls on re-reading the same context, which is where the 4× token multiplier comes from.
- Use a free agent loop (`create_agent` with tools) only if the job's steps genuinely vary (for example, when a company has no web presence and the agent must try alternatives). Even then, cap it with `ModelCallLimitMiddleware` or a state counter.
- Evidence is thin: Anthropic's post supports bounded, prompt-scaled loops and warns about cost, but no source read compares fixed pipelines and free loops on quality for this task. Treat the trade-off as a design judgement to check with a small eval (e.g. 10 real jobs, measure verified-fact recall and cost per run for both shapes).

### Gaps
- No controlled comparison of fixed pipeline versus agent loop for research-notes quality was found.
- No measured per-run token counts for this exact pipeline exist; scenario A figures are estimates to validate.

---

## Recommended architecture (summary for the builder)

- Shape: fixed `StateGraph` (plan → search → read → extract → gap_check → write) with one bounded retry branch, not a free agent loop.
- Framework: LangGraph 1.x `StateGraph` directly. Avoid `langgraph.prebuilt.create_react_agent` (deprecated). Use `create_agent` only if a free loop is later needed.
- Models: Haiku 5.5 for plan and per-page extraction; Sonnet 5.5 for the structured write. Opus 5.5 only if measured quality requires it.
- Tools: Tavily search, Jina Reader, Google Places, all as client-side tools with a blocked-domain check (SEEK, LinkedIn, Indeed) before fetch.
- Output: `messages.parse()` with a Pydantic schema; every fact has `source_id` and a verbatim quote checked against stored text.
- Budgets (per run): max 4 queries, 6 page reads, 6K tokens per page, 12 model calls, one gap-check retry, and a dollar estimate checked before each call. Target cost: about US$0.04-0.05 per run (about NZ$0.07-0.08 at the assumed rate), which gives roughly 70-140 deep-search runs per month within the budget.
- Enable deep search per job (a flag on the job), not for every job.

## Open items to verify before building
1. Tavily, Jina Reader and Google Places current pricing, free tiers and rate limits (affects real monthly cost; Google Places may dominate).
2. Current exchange rate NZD/USD (assumed about 0.6).
3. Whether `web_search_20260209` works together with `output_config.format` (if server search is chosen).
4. Exact `messages.parse()` signature in the installed `anthropic` SDK.
5. Current `ToolNode` import path and default `recursion_limit` for a plain `StateGraph` in the installed LangGraph version.
6. Measured token counts for a real job (a dry run with 10 jobs) to replace the estimates above.

## Sources
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [LangChain agents docs](https://docs.langchain.com/oss/python/langchain/agents)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangGraph GRAPH_RECURSION_LIMIT error page](https://docs.langchain.com/oss/javascript/langgraph/errors/GRAPH_RECURSION_LIMIT)
- [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic prompt injection defenses](https://www.anthropic.com/research/prompt-injection-defenses)
- [LangChain open_deep_research blog](https://www.langchain.com/blog/open-deep-research)
- [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)
- [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- [LangGraph recursion-limit forum thread](https://forum.langchain.com/t/gracefully-handling-graphrecursionerror-from-subgraphs-so-the-parent-agent-can-retry-or-degrade/2018) (secondary)
- arXiv 2601.04795, indirect injection defence via tool-result parsing (search snippet only, not read)
