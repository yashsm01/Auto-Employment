# ATS and Resume-Job Match Scoring: What the Scores Mean and What ATSs Actually Do

Research date: 2026-11-26. Scope: consumer resume-match tools, real ATS ranking/filtering features, studies on auto-rejection, and honesty principles for a resume builder that scores a resume against one selected job. Claims from vendors are labelled as vendor claims. Several primary pages could not be retrieved (noted under Gaps).

## 1. How consumer tools compute their resume-vs-job scores

### Takeaway
No consumer tool publishes a formula. What is disclosed is a list of input categories and, in some cases, a target number. The numbers (75%, 80%, 85%) are marketing targets, not validated thresholds. A consumer score measures keyword/skill overlap with one job description. It is not an ATS output and nothing shows it predicts interviews.

### Cited Findings
- Jobscan says its Match Rate is "based on your hard skills, education level" and other factors including job title, soft skills and keywords, and that it "checks over 30 parameters." It states the Match Rate is "a Jobscan visualization tool, not a score assigned by the employer's ATS," and that no formula or weighting is given. [Jobscan resume score page](https://www.jobscan.co/resume-score)
- Jobscan's own FAQ says: "We recommend aiming for at least 75% to increase your chances of getting an interview." Its page cites no data or research for the 75% target, and it labels 76% "Competitive for this job." The "Land 3X More Interviews" headline is unsourced on that page. [Jobscan resume score page](https://www.jobscan.co/resume-score)
- Jobscan's resume page says word count and measurable results are not part of the match rate (per the search summary; not verified on the page). [Jobscan](https://www.jobscan.co)
- Third-party blog descriptions of Jobscan's weights (keywords 30–40%, formatting 25–35%) could not be verified against Jobscan. Treat as unconfirmed. [Best Job Search Apps](https://bestjobsearchapps.com/articles/en/how-your-jobscan-ats-score-works-and-what-score-you-need)
- Resume Worded: the overall 0–100 score is a weighted (not averaged) set of checks, "weighted by importance using insights from hiring managers"; a good score is 85+ and ideally 90+. The separate "Relevancy Score" from its Targeted Resume tool compares a resume to one job description, counts required qualifications more than preferred, and treats above 80 as well matched. Its comparison page claims Jobscan does flat keyword matching while Resume Worded weights required over preferred (vendor's own characterisation). Exact weights are not published. [Resume Worded score guide](https://resumeworded.com/score-guide.php); [Resume Worded LLM info](https://resumeworded.com/llm-info)
- Teal: the Match Score "reflects how many job-description keywords appear in your resume content"; keywords are coloured green (present), yellow (optional) or red (missing). Teal says the score is "meant to guide alignment... not to mirror an applicant tracking system score," and marketing pages treat 80%+ as good. It advises against chasing 100%. Weighting and partial-match rules are not disclosed. [Teal help: what is job matching](https://intercom.help/tealhq-9a9274919b13/en/articles/10604396-what-is-job-matching); [Teal help: using job matching](https://intercom.help/tealhq-9a9274919b13/en/articles/9524864-using-job-matching); [Teal resume-JD match tool](https://tealhq.com/tool/resume-job-description-match)
- Enhancv, Rezi, Kickresume, SkillSyncer: no methodology pages were retrieved in this pass. Gap.
- Jobscan's model of "ATS score" is a diagnostic. Jobscan's own text says the match is not an employer-side score.

### Inferences
- Across the tools, the common core is keyword/skill overlap with a single JD, plus some formatting or section checks. Required-versus-preferred weighting is a differentiator that vendors claim (Resume Worded) but do not document.
- The 75/80/85 thresholds are vendor-chosen. There is no published evidence that a higher consumer score improves callback rates. A resume builder should not present them as pass marks.

### Gaps
- No peer-reviewed or independent validation of any consumer score against interview or hire outcomes was found.
- Enhancv, Rezi, Kickresume and SkillSyncer methodology pages were not retrieved.
- Jobscan's full FAQ and weighting were not retrieved directly.

## 2. Do real ATSs score or rank candidates automatically?

### Takeaway
Ranking or "match scoring" exists in several enterprise and mid-market products, but it is mostly opt-in, configured by the employer against criteria the employer sets, and framed by vendors as recruiter-assist with no auto-rejection. Keyword search by recruiters remains common. Vendor documentation consistently says the human makes the decision.

### Cited Findings
- **Workday (HiredScore AI for Recruiting/Talent):** grades candidates with "fit and gap analysis" per required and preferred qualification, with a plain-language explanation for each. Recruiters "stay in control of every decision." Vendor marketing says it is "unbiased." Independent G2 reviews say ranking fails when requirements are vague or undefined, and one asks for more control over the weight of each skill. [Workday blog: screen candidates 50% faster](https://blog.workday.com/en-us/screen-candidates-50-faster-workday-recruiting.html); [Workday HiredScore AI for recruiting](https://www.workday.com/en-hk/products/talent-management/ai-recruiting.html); [G2 Workday HiredScore reviews](https://g2.com/products/workday-hiredscore-ai-for-recruiting/reviews)
- **Greenhouse (Talent Matching):** Greenhouse's support article says Talent Matching "does not automatically advance or reject candidates" and that recruiters make all decisions. The match summary is "based on your calibration" (calibration criteria, with keywords highlighted in the resume preview). Site Admins must enable it, and the article does not say whether it is on by default. Third-party sources say Auto-Reject/Auto-Advance are on higher tiers only; unverified. [Greenhouse Talent Matching support](https://support.greenhouse.io/hc/en-us/articles/41396009937307-Talent-Matching)
- **Lever (Talent Fit):** Talent Fit "automatically identifies top-matched candidates based on job requirements," labels them, and does not reject others. Lever's FAQ says candidates who are not flagged may still have the skills, just not as "top fit." Recruiters "always have the final say." Enabled per job. [Lever Talent Fit help](https://help.lever.co/hc/en-us/articles/26828963215645); [Lever AI features](https://www.lever.co/ai-features)
- **LinkedIn:** Candidate-side "match" is computed from profile/resume vs the job's required and preferred qualifications, including screening questions. Hirers do not see the candidate's match level, per LinkedIn's help. Recruiter/job-poster side: the AI assistant sorts applicants into "Top fit," "Maybe," "Not a fit" based on must-have qualifications and the share of preferred qualifications met; the threshold is adjustable. Third-party claims that this score is keyword-based and does not reach enterprise ATSs are unverified. [LinkedIn: find how you match](https://www.linkedin.com/help/linkedin/answer/a7120158); [LinkedIn AI assistant for job posts](https://business.linkedin.com/au/en/hire/post-jobs/ai-assistant)
- **SmartRecruiters (SmartAssistant / Winston Match):** Vendor says match scores do not use name, age, gender, email, phone or diversity answers. Score scale is contradictory in its own materials: older 0–100, a later help article a 5-point scale. Whitepaper names Claude Sonnet 3.5 as the model (dated; verify). [SmartRecruiters AI recruitment tools](https://www.smartrecruiters.com/recruiting-software/artificial-intelligence-recruitment-tools); [SmartRecruiters AI whitepaper](https://ta.smartrecruiters.com/rs/664-NIC-529/images/SmartRecruiters-AI-Whitepaper.pdf?version=1)
- **iCIMS:** "Job Fit" score and tier per job in Talent Discovery, and a "Candidate Ranking" feature sorting by skills/experience match. Source is a 2021 release note; current behaviour not confirmed. Requires iCIMS Talent Cloud AI subscription. [iCIMS Winter 2021 release notes](https://community.icims.com/articles/Knowledge/Release-Notes-Winter-Release-2021-iCIMS-Talent-Cloud-AI)
- **Taleo (Oracle):** Prescreening uses "disqualification questions," "prescreening questions" and competencies. A mandatory question cannot be skipped. Answers filter and rank candidates on the requisition list, and weights are an optional numeric bonus per answer. This is the clearest documented knockout mechanism of those surveyed. [Oracle Taleo: prescreening candidates](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/21b/otfru/prescreening-candidates.html); [Oracle Taleo: question and competency properties](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/otfru/c-questioncompetencyproperties.html)
- **SEEK (NZ):** No primary documentation of an automatic match score was retrieved. SEEK's NZ employer pages describe AI that "delivers candidates" and shortlisting notes in AdCentre. Treat as vendor framing. [SEEK NZ AI at SEEK](https://nz.employer.seek.com/products/ai-at-seek); [SEEK AdCentre](https://talent.seek.co.nz/products/adcentre)
- Recruiter-side keyword search and filter remain the primary method in most ATSs. Not separately sourced in this pass beyond the Greenhouse and Taleo docs.

### Inferences
- The pattern across vendors is: opt-in per job, criteria set by the employer, required vs preferred split, a "top fit" bucket rather than a hard reject, and recruiter override. A resume builder's score is closest in structure to Lever Talent Fit and LinkedIn's must-have/preferred model, not to a hidden pass/fail gate.
- Knockout questions (Taleo-style yes/no eligibility questions such as work rights or licence) are the most concrete form of automatic exclusion. They are answered on the application form, not inferred from the resume text.

### Gaps
- No document was found that states the default ranking behaviour for Workday, iCIMS, SmartRecruiters or SEEK in a given customer tenancy. Customer configuration decides.
- Current SmartRecruiters score scale and model were not confirmed.
- iCIMS Talent Explorer scoring method was not found beyond the 2021 note.

## 3. Surveys and studies: how often are applications auto-rejected, knocked out or never reviewed?

### Takeaway
The "75% of resumes are rejected by ATS" figure has no traceable study behind it. The best available recruiter evidence (small, vendor-run) says content-based auto-rejection is uncommon. Knockout eligibility questions are common. The Harvard/Accenture "Hidden Workers" report is often misquoted on ATS rejection numbers.

### Cited Findings
- **The 75% claim:** Enhancv (a resume-tools vendor) says the figure traces to a 2012 vendor sales pitch by a company that shut down in 2013, and that it has no study behind it. Other debunking pieces say the same. Treat the origin claim as secondary. [Enhancv: does ATS reject resumes](https://enhancv.com/blog/does-ats-reject-resumes/); [Interview Guys: ATS rejection myth](https://blog.theinterviewguys.com/?p=1967)
- **Enhancv recruiter study (2025):** The 92% headline comes from 25 U.S. recruiters and talent acquisition managers in qualitative structured interviews run Sep–Oct 2025. 23 of 25 said their ATS does not auto-reject for formatting, content or design. Two (8%) configured content-based auto-rejection. Knockout eligibility rules were used by all recruiters where present. Small sample, U.S. only, and run by a vendor that sells ATS-tailoring products. Many syndicated copies of one press release exist. [Enhancv: does ATS reject resumes](https://enhancv.com/blog/does-ats-reject-resumes/); [WBOC press release](https://www.wboc.com/online_features/press_releases/the-75-ats-rejection-myth-shattered-92-of-recruiters-confirm-applicant-tracking-systems-do-not/article_f141f112-dc9e-5082-9be5-1ea7b6444456.html); [BetaNews coverage](https://betanews.com/2025/11/10/study-debunks-viral-claim-that-ai-filters-out-most-job-applicants/)
- **Harvard Business School / Accenture "Hidden Workers: Untapped Talent" (2021):** The Harvard Gazette interview with co-author Joseph Fuller says a "hidden" workforce of **27 million people in the U.S.** would fill jobs. It does not say ATSs reject 27 million people. That "27 million stopped by ATS" wording is a press paraphrase. The Gazette's "about 99 percent of Fortune 500 companies use artificial intelligence tracking systems" appears in the interviewer's question, with no source. Fuller says half of U.S. companies have a filter excluding applicants with employment gaps, with no source given. The report's core argument: ATSs use negative filters (e.g. exclude no-degree, exclude recent gaps) that exclude viable candidates. [Harvard Gazette: new study says hidden workers are being excluded](https://news.harvard.edu/gazette/story/2021/09/new-study-says-hidden-workers-are-being-excluded/); [HBS Working Knowledge: how to tap the talent automated HR platforms miss](https://hbswk.hbs.edu/item/how-to-tap-the-talent-automated-hr-platforms-miss) (full text blocked; summary from search)
- **Hidden Workers sample sizes:** secondary coverage gives 8,720 hidden workers and 2,275 executives across the U.S., UK and Germany. Not verified against the primary PDF (the HBS PDF URL returned 404). [The Register (2021)](https://www.theregister.com/2021/09/08/harvard_jobs_report/)
- **Knockouts exist:** Taleo's documented disqualification questions and mandatory prescreening questions block or filter candidates on answers, not resume text. [Oracle Taleo prescreening](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/21b/otfru/prescreening-candidates.html)
- **Semantic vs keyword studies (academic, mostly simulated):** arXiv 2601.14534 (Jan 2026, preprint) simulates 1,000 resume-job pairs; a keyword baseline counts a match when 40% of required terms appear as whole words; semantic matching reduces false negatives without hurting precision. Ajjam & Al-Raweshidy (Brunel) and Resume2Vec (MDPI Electronics 14(4):794) report embedding-based matching outperforms keyword baselines in simulated or prototype tests. None uses real ATS logs. [arXiv 2601.14534](https://arxiv.org/html/2601.14534); [Resume2Vec, MDPI](https://www.mdpi.com/2079-9292/14/4/794); [Brunel thesis (Ajjam & Al-Raweshidy)](https://bura.brunel.ac.uk/bitstream/2438/32657/1/FullText.pdf)
- **LLM screening bias (arXiv 2509.00462, 2025):** LLM screeners shortlist resumes written by the same model about 23–60% more often than equally qualified human-written resumes, across 24 occupations in simulation. The abstract also reports a 67–82% self-preference figure across models; the paper uses this for a different comparison, so do not merge them. Effects strongest in sales and accounting. University of Maryland summary dated 22 June 2026. [arXiv 2509.00462](https://arxiv.org/abs/2509.00462); [UMD Smith School news](https://www.rhsmith.umd.edu/news/ai-hiring-tools-may-favor-their-own-work-smith-study-finds)
- **NZ adoption:** no NZ survey of ATS use or SEEK-based screening was found. Vendor market pages (Employment Hero, Capterra NZ listings, iSmartRecruit) describe ATS integration with SEEK but give no usage share. [Capterra NZ ATS directory](https://www.capterra.co.nz/directory/30060/applicant-tracking/software); [iSmartRecruit NZ ATS list](https://www.ismartrecruit.com/list/top-applicant-tracking-system-newzealand)

### Inferences
- The best-supported picture is: most applications are read by a human or filtered by a recruiter search and filter, eligibility questions are the most common automatic exclusion, and auto-rejection on resume content is uncommon but not zero. No study measures the share of applications never opened.
- Any claim of "X% auto-rejected" should be labelled as unsupported unless it cites a primary dataset.

### Gaps
- No independent, representative measure of automatic rejection rates in 2025–2026 was found.
- No study measuring "never reviewed" rates was found.
- NZ-specific ATS usage and SEEK screening data were not found. MBIE, Stats NZ or an HR body survey would be needed.
- Primary Hidden Workers PDF not retrieved; figures above are from secondary coverage.

## 4. Keyword stuffing, hidden white text and AI-written wording

### Takeaway
Hidden text is easy to detect and reads as dishonest to recruiters. Keyword stuffing is not documented as a reliable ranking boost in any ATS. AI-polished wording is a live risk because AI-assisted screeners show self-preference bias, but the effect on human recruiters is not measured.

### Cited Findings
- Hidden white text: sources agree parsers strip formatting, so white text becomes visible to the recruiter reviewing the parsed file. Some parsers ingest, expose or break hidden text. A developer's mock ATS test found copied JD text in hidden sections was penalised by modern parsers (single person's test). Greenhouse estimated about 1% of resumes contain hidden text; ManpowerGroup said about 10% of resumes its AI scans contain it (vendor/staffing firm figures, not audited). [BuiltIn: AI resume hacks](https://builtin.com/articles/hidden-ai-prompts-in-resume); [Fortune: white font hack (Dec 2024)](https://fortune.com/2024/12/05/job-applicants-white-font-hack-hr-applications/); [Schneier: hacking AI resume screening with white font (2023)](https://www.schneier.com/blog/archives/2023/08/hacking-ai-resume-screening-with-text-in-a-white-font.html)
- Recruiters who find hidden text tend to reject the applicant, per recruiter commentary (e.g. Penn West career centre blog). [Penn West: why white wording isn't a hack](https://career.pennwest.edu/blog/2022/11/02/i-had-to-reject-the-application-this-recruiter-shared-why-white-wording-isnt-the-resume-hack-people-think-it-is/)
- Keyword stuffing: a Dartmouth career-centre post says repetition may move a resume up, but that modern ATSs down-weight isolated keywords and look for context. No published data. [Dartmouth: new arms race](https://guarinigrad.dartmouth.edu/blog/2025/10/14/the-new-arms-race-ai-used-by-job-seekers-vs-that-used-by-employers/)
- Resume Worded and Simplify both say unnatural repetition is a negative and advise natural wording. Vendor claims. [Resume Worded score guide](https://resumeworded.com/score-guide.php)
- AI-written text: the arXiv 2509.00462 finding (section 3) applies to LLM screeners, not human recruiters. No study found on human recruiter reaction to AI-polished resumes.

### Inferences
- Hidden-text and stuffing tactics carry more downside (human rejection, parser-visible text) than documented upside.
- For a resume builder, the honest default is to report which JD terms appear naturally in the resume and to flag terms that are missing but true, not to inject them.

### Gaps
- No controlled test of hidden text or keyword stuffing against named ATS products was found. Single-person or vendor tests only.
- No independent measure of recruiter reaction to AI-polished wording.

## 5. Scoring approaches that are honest

### Takeaway
An honest score is a transparent overlap measure for one job, with required vs preferred separated, synonyms handled, evidence (where and when a skill was used) shown, and a clear statement that it is not an ATS prediction. It should not give a single "pass mark" number backed by no evidence.

### Cited Findings
- Required vs preferred: Resume Worded weights required above preferred. LinkedIn's "Top fit / Maybe / Not a fit" is must-have first, then share of preferred. Lever's Talent Fit is criteria-driven. [Resume Worded relevancy](https://resumeworded.com/score-guide.php); [LinkedIn AI assistant](https://business.linkedin.com/au/en/hire/post-jobs/ai-assistant); [Lever Talent Fit](https://help.lever.co/hc/en-us/articles/26828963215645)
- Exact vs semantic: the arXiv 2601.14534 simulation reduces false negatives with semantic matching; keyword baselines miss synonyms. Simulated only. [arXiv 2601.14534](https://arxiv.org/html/2601.14534)
- Teal's keyword colour scheme (present / optional / missing) shows the user what is and is not in the resume without a hidden weight. [Teal help](https://intercom.help/tealhq-9a9274919b13/en/articles/10604396-what-is-job-matching)
- Greenhouse's match summary shows "matched experience, industries, and skills based on your calibration." Criteria are explicit and editable. [Greenhouse Talent Matching](https://support.greenhouse.io/hc/en-us/articles/41396009937307-Talent-Matching)
- AWS vs Amazon Web Services and similar acronym pairs: no vendor source found in this pass. Gap.
- Recency and context of skills: no vendor or academic source found that quantifies the effect. Gap.

### Inferences (recommendations for the resume builder)
1. Use a JD-to-resume skill list split into required and preferred. Show the two counts separately. Do not fold them into one number without showing the split.
2. Match with a synonym and acronym table (e.g. AWS / Amazon Web Services; "Kubernetes" / "K8s") plus semantic matching for phrasing variants. Show which rule matched, so the user can confirm it.
3. Require evidence: a skill counts only if it appears in a work or project entry, with the entry's date. Show recency as information, not as a weight, until there is evidence for weighting.
4. Name the score honestly: "Keyword and skill coverage for this job" rather than "ATS score." State that employers' ATSs differ and that the score is not a prediction of interview or hire.
5. Do not show a pass threshold (75%, 80%, 85%). If a band is needed, describe coverage levels (e.g. all required present, n of m preferred present), not a grade.
6. Flag hidden text, repeated keywords and copied JD sentences as warnings in the builder. Do not generate them.
7. Show a plain-text parse preview so the user can see what a parser sees, since parsing (not scoring) is where ATS formatting problems occur.
8. If AI-assisted rewriting is offered, mark generated text, and do not claim it improves ATS ranking.

### Gaps
- No validated method for semantic skill matching in production ATSs was found.
- No study tests whether a coverage score predicts callbacks.
- Synonym tables and recency weighting: no authoritative source found.

## 6. Summary of what is established vs vendor claim vs unsupported

| Claim | Status |
|---|---|
| "75% of resumes are rejected by ATS" | Unsupported. Traced to a 2012 vendor sales pitch (secondary source). |
| "92% of recruiters say ATS doesn't auto-reject" | Small vendor-run interview study (n=25, U.S.). Directionally useful, not representative. |
| "27 million Americans stopped by ATS" (Hidden Workers) | Misattribution. Report/Gazette refers to a hidden workforce of 27 million. |
| "99% of Fortune 500 use ATS" | Unsourced, from an interviewer's question in the Gazette piece. |
| Jobscan 75% target | Vendor target, no cited evidence. |
| Resume Worded 85+ target | Vendor target, no cited evidence. |
| Teal 80%+ good | Vendor target, no cited evidence. |
| Greenhouse Talent Matching does not auto-reject | Vendor support article (primary). |
| Lever Talent Fit does not reject others | Vendor help article (primary). |
| Workday HiredScore grades with explanations | Vendor blog and datasheet (primary vendor, promotional). |
| Semantic matching beats keyword matching | Simulated/prototype studies only. |
| LLM screeners favour LLM-written resumes | Controlled simulation (arXiv 2509.00462). Not measured on human recruiters. |

## 7. Gaps overall
- Enhancv, Rezi, Kickresume and SkillSyncer scoring methodology not retrieved.
- Primary Harvard Hidden Workers PDF (HBS) not retrieved (404); HBS Working Knowledge page blocked (403).
- Greenhouse default configuration for Talent Matching not confirmed.
- SmartRecruiters current score scale and model not confirmed.
- iCIMS current Talent Explorer behaviour not found (only a 2021 release note).
- SEEK and LinkedIn: per instruction, no direct page fetches were made; findings rely on search snippets and the official LinkedIn help page surfaced by search.
- No NZ-specific data on ATS adoption, SEEK screening or automated rejection.
- No independent evaluation of hidden text or keyword stuffing against named ATS products.
- AWS/Amazon Web Services synonym handling and recency weighting: no sourced guidance found.
