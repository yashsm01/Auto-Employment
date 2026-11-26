# ATS and job board resume differences (NZ, 2025-2026)

Scope: whether resume format should vary by provider (Workday, Greenhouse, Lever, SEEK, Trade Me Jobs, JobAdder, PageUp, SnapHire) or whether one conservative format plus per-job content tailoring is enough. Sources are official help/docs where found; vendor blogs are labelled. SEEK pages were not fetched (search snippets only). LinkedIn and Indeed were not touched.

## 1. Do specific ATSs have documented quirks that change resume format?

### Takeaway
Yes, but the documented quirks are about parseability, not provider-specific layouts. Greenhouse publishes concrete limits (2.5 MB parse ceiling, no image-only files, columns/tables/text boxes/header-footer contact details can fail). Workday's official guide says results depend on format and word order and recommends no images. The same conservative format (single-column, text-based DOCX or PDF, no images, contact details in the body, under 2.5 MB) satisfies all of these.

### Cited Findings
- Greenhouse accepts .doc, .docx, .pdf, .rtf and .txt, and candidate uploads can be up to 100 MB. Verified on the official page: [Greenhouse, Supported file types for resumes and cover letters](https://support.greenhouse.io/hc/en-us/articles/360052218132-Supported-file-types-for-resumes-and-cover-letters). That page does not state a parse size limit.
- Greenhouse states it "can't parse resumes larger than 2.5MB" and says files over 2.5 MB fail, often because of high-quality images. Verified on the official unsuccessful-parse article: [Greenhouse, Unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse). The same article lists these failure causes:
  - image-only uploads
  - graphics, photos or word art
  - "complex resumes with tables, headers, and footers"
  - columned layouts
  - name and contact information in a header, footer or text box
  - letters with spaces between them
- Workday's official admin guide says parsing "populates fields from a resume", does not auto-fill fields configured as hidden, or the Languages and Skills fields, and that "Resume parsing results can vary based on resume format and order of words." It recommends "resumes that don't have images or image-based styles." Verified: [Workday admin guide, Set up prospects and candidates](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/set-up-prospects-and-candidates/hdc1552497830785.html). The page gives no file type or size guidance. Search snippets say it was last updated June 2023.
- Workday autofill is reported as unreliable by users, but this comes from forums and vendor blogs, not Workday. A Teal guide says Workday often struggles to parse the Work Experience section into job fields ([Teal, Parsable Workday resume](https://www.tealhq.com/post/workday-resume)). A 1Password community thread from March 2026 reports the same kind of problem (line breaks, wrong job descriptions) (search snippet: [1Password community](https://www.1password.community/discussions/1password/autofill-forms--resum%C3%A9-autofill/168566)).
- A Workday Nevada alert from mid-2025 says resume parsing on external career sites was not auto-populating. It is marked resolved, and its retirement date (28 June 2026) has passed. Search snippet only: [workday.nevada.edu](https://workday.nevada.edu/?p=3262).
- Vendor guides (lower-quality evidence) disagree on Workday's preferred file type. One recommends DOCX; another says DOCX or text-based PDF. One vendor claims Workday caches the first successful import, so re-uploading a corrected file may not update the profile. None of these claims are confirmed by Workday ([hireflow.net Workday guide](https://hireflow.net/guides/workday-ats-resume)).
- Lever's help article says its parser adds details from the resume, including name, organization and contact information, to the candidate's profile ([Lever, Understanding resume parsing](https://help.lever.co/hc/en-us/articles/20087345054749), seen as a search snippet; my fetch returned an error page). Whether the visible application form is pre-filled is not confirmed by the official snippet. A vendor blog (JobWizard) says fields can be blank or wrong depending on formatting, but this is not Lever documentation.
- Vendor claims that Lever accepts .docx, PDF, RTF, HTML and WordPerfect are unverified (third-party guide only).
- Generic parser behaviour (vendor glossary, Recruiterflow): parsers may check email, phone, profile URL and name against existing records to detect duplicates. Not verified for any specific platform.
- Counter-evidence: Enhancv argues modern parsers detect a column separator and read columns independently, and that two-column PDFs are not rejected outright. This is a resume-tool vendor claim and conflicts with Greenhouse's documented failure list.

### Inferences
- The documented constraints (size, images, tables/columns, text boxes, header/footer contact details, file type) all point to one conservative format. No documented per-ATS difference requires a different layout.
- Workday and Lever differ mainly in which fields they fill (profile vs. form) and how reliably they map work history. The resume content should be unchanged, but the user should check the parsed fields after upload.
- Greenhouse is the only platform with a published numeric parse ceiling (2.5 MB). A builder should keep exports well under this (text-based PDFs of a few pages are typically far smaller; image-heavy exports are the risk).

### Gaps
- No official Workday file type or size limits were found.
- No official Lever documentation on accepted formats, size limits, or whether the application form is pre-filled. The Lever help page could not be fetched.
- No official Taleo/Oracle or iCIMS, SmartRecruiters or SuccessFactors parsing limits were checked. Oracle has a "Plain Text Resume Parsing for Mobile Devices" doc (https://docs.oracle.com/en/cloud/saas/taleo-enterprise/22c/otcug/c-plaintextresumeparsingmobile.html), not read.

## 2. NZ job board apply flows (SEEK, Trade Me Jobs, JobAdder, PageUp, SnapHire)

### Takeaway
SEEK and Trade Me both store a reusable CV and profile, and both publish general advice for a simple one- or two-page CV. I found no vendor documentation for file limits, parsing, or form questions on SEEK, Trade Me, JobAdder, PageUp or SnapHire, so provider-specific claims for these platforms stay unverified.

### Cited Findings
- SEEK NZ career advice says you can upload a resumé to your SEEK Profile and attach it to applications without re-uploading. Snippet only: [SEEK NZ, resume and profile articles](https://nz.seek.com/career-advice/article/resume-profile).
- SEEK says that if your profile is public, you are searchable by anyone looking for talent, but only employers can see your full profile, resume and contact details (snippet, [SEEK NZ, How your SEEK Profile could land you a job](https://www.seek.co.nz/career-advice/article/how-your-seek-profile-could-land-you-a-job)).
- SEEK says recruiters search by keyword and advises using keywords in the profile ([SEEK NZ, 5 keywords employers are searching for in your SEEK profile](https://www.seek.co.nz/career-advice/5-keywords-employers-are-searching-for-in-your-seek-profile)). SEEK also advises including specific skills relevant to each job, even if the resume is adjusted per application (snippet, [SEEK NZ, resume-cv article](https://nz.seek.com/career-advice/article/resume-cv)).
- An AUT careers resource recommends saving the CV as a PDF before uploading to preserve formatting ([AUT Employability, digital platform recruitment tips](https://employability.aut.ac.nz/news-and-views/digital-platform-recruitment-tips)). This is general advice, not SEEK documentation.
- Trade Me Jobs lets users store up to 100 CVs and documents under "CVs & Documents," and offers an "Apply with Trade Me Jobs Profile" button on some ads. Snippet from [Trade Me Jobs, Create and edit your Job Profile](https://help.trademe.co.nz/hc/en-us/articles/360007000152) and the Trade Me Jobs profile guidance.
- A Trade Me community post says a cover letter must be uploaded with each application and a saved one cannot be selected. This may be out of date. [Trade Me community post](https://help.trademe.co.nz/hc/en-us/community/posts/12205319454479-Option-to-use-CV-uploaded-to-account-but-not-a-cover-letter-but-account-shows-cover-letter-uploaded).
- Trade Me careers advice recommends a CV of about two pages in a simple, clean layout without multi-column designs. It does not state an accepted file format ([Trade Me careers, how long can my CV be](https://www.trademe.co.nz/c/jobs/article/how-long-can-my-cv-be-)).
- Trade Me has a developer API endpoint for uploading a CV, cover letter or document ([Trade Me developer docs](https://developer.trademe.co.nz/api-reference/document-service-methods/upload-a-cv-cover-letter-or-document)). This is for integrators only.
- JobAdder, PageUp and SnapHire/Martian Logic: searches returned only review-aggregator listings. SnapHire returned nothing. No vendor documentation on parsing, accepted formats, or profile mapping was found.

### Inferences
- A SEEK or Trade Me user will usually upload one stored resume and then answer any ad-specific questions in the form. The per-job work is mostly in the cover letter and the form answers, not in the resume file.
- Because Trade Me sometimes requires a fresh cover letter per application, a builder that generates per-job cover letters has a real provider-specific job to do.

### Gaps
- SEEK accepted file types, size limits and parsing behaviour: not found in official sources in this pass. Not fetched directly (constraint).
- SEEK Quick Apply and role-requirement question behaviour: no source found describing how the questions are asked or how they are scored.
- Trade Me accepted formats and size limits: not found.
- JobAdder, PageUp, SnapHire/Martian Logic: no official parsing, format or match-signal documentation found. These need direct checking in a sandbox or by contacting vendors.

## 3. Do recruiters search by keyword, filter by questions, or rely on AI matching?

### Takeaway
On SEEK, recruiter search is keyword-based against the profile, and the profile (not only the uploaded file) drives discoverability. No independent study compares keyword and AI matching in recruiting. Vendor claims exist but are unverified, so the evidence for AI matching changing outcomes is weak.

### Cited Findings
- SEEK says recruiters search by keyword, so profile keywords matter ([SEEK NZ, 5 keywords](https://www.seek.co.nz/career-advice/5-keywords-employers-are-searching-for-in-your-seek-profile)).
- Pin (vendor) cites a 2025 Information Sciences paper finding that semantic matching beat keyword methods across technical roles. Not checked directly ([Pin, Boolean search productivity tax](https://www.pin.com/blog/boolean-search-productivity-tax/)).
- Scale.jobs (vendor) claims BERT-based matching reaches 90-94% accuracy and that ATS keyword rules cause "false rejections." Unverified ([Scale.jobs, AI matching vs ATS](https://blog.scale.jobs/ai-matching-vs-ats-resumes-rejected)).
- The most-cited older recall evidence is Blair and Maron (1985), on a legal database, where experts expected over 75% recall but achieved about 20%. Not about recruiting; cited secondhand via Pin.
- Crelate (vendor) and ERE (trade publication) both argue AI should not replace Boolean or human judgement. These are opinion pieces ([ERE, AI resume matching vs human cognition](https://www.ere.net/articles/artificial-intelligence-resume-matching-vs-human-cognition)).

### Inferences
- Resume-derived signals (job titles, skills, tools, dates) feed the parser and any keyword index. Form questions (eligibility, notice period, salary, work rights) are set by the employer and are not in the resume. Profile fields (SEEK profile, Trade Me Jobs profile) sit between the two.
- A provider-specific resume is therefore less useful than a provider-specific profile and form answer. The resume should use the exact role vocabulary of the ad, and the profile should be kept in sync.

### Gaps
- No source found on how any NZ platform ranks or filters applicants.
- No source found on whether ATS or SEEK show employers a match score.
- Employer question-filtering behaviour (knockout questions) on SEEK, Trade Me or JobAdder: not found.

## 4. What experienced recruiters and career advisers say about ATS-specific resume versions

### Takeaway
The "separate ATS resume" idea is mostly treated as a myth by recruiters and career sources, with a caveat: a plain, parseable layout matters. Most authors have a commercial interest in resume tools, so evidence quality is low.

### Cited Findings
- A ClearanceJobs piece (July 2026) reports recruiters saying the ATS is not what rejects most resumes; volume is. None of the recruiters mentioned fonts, template restrictions or design elements causing rejection ([ClearanceJobs news](https://news.clearancejobs.com/2026/07/29/recruiters-reveal-ats-doesnt-kill-your-resume-its-overwhelming-volume/)).
- The same coverage reports that 68% of recruiters said the ATS myths came from viral social posts (secondhand snippet; check original before citing).
- Rezi (vendor) lists ATS myths including "ATS can't read PDFs," which it calls a myth ([Rezi, ATS myths](https://www.rezi.ai/posts/ats-myths)).
- Adobe suggests keeping two files, a DOCX for uploads and a PDF for direct submission, and following the file type the listing specifies ([Adobe, ATS resume tips](https://www.adobe.com/express/discover/tips/ats-resume-tips)).
- Trade Me's careers advice recommends a simple layout without multi-column designs (see section 2).

### Inferences
- The consensus across sources is one clean, single-column, text-based resume, plus per-job tailoring. Two files (DOCX plus PDF) is an optional convenience, not a requirement.
- The parseability test that is supported by documentation is: paste the resume into plain text and check that the reading order and sections still make sense. This is consistent with Greenhouse's failure list.

### Gaps
- No controlled study on ATS-specific resume versions was found.
- Recruiter opinion is mostly from vendor-hosted content; no NZ recruiter-specific survey was found.

## 5. Provider-specific cover letters or selection-criteria responses (NZ public sector)

### Takeaway
NZ public sector applications usually ask for an online form, a CV and a cover letter tied to the role's key requirements. The cover letter does the criteria mapping, and the panel scores it. I found no current source describing a separate written selection-criteria document, so that format may be role-specific or older.

### Cited Findings
- Te Puni Kōkiri asks for an application form, an up-to-date CV and a cover letter, and says to refer to the ad and job description to match key requirements ([TPK, applying for a job](https://tpk.govt.nz/en/mo-te-puni-kokiri/careers/applying-for-a-job)).
- NZQA says a selection panel assesses the CV and covering letter against the role's required criteria ([NZQA, recruitment process](https://www2.nzqa.govt.nz/about-us/working-at-nzqa/recruitment-process/)).
- Public Service Commission guidance for chief executive roles asks for a short cover letter expressing interest and fit, plus a current CV ([PSC, Guide for Applicants 2024](https://www.publicservice.govt.nz/assets/DirectoryFile/Public-Service-Commissioner-Guide-for-Applicants-2024-v3.pdf)).
- The Digital Investment Agency's GovTechTalent pathway replaces the cover letter with a video introduction and asks applicants not to use AI to generate it ([DIA, How we hire](https://www.dia.govt.nz/About-Us---Careers-with-us---GovTechTalent---How-We-Hire)). This is a provider-specific difference inside NZ public sector.
- careers.govt.nz's job application checklist recommends labelling the CV and cover letter with the job title, your name and the application date ([careers.govt.nz checklist](https://careers.govt.nz/job-hunting/cvs-and-cover-letters/job-application-checklist)). This is a filename convention, not a platform rule.
- Career advice on selection criteria recommends concrete examples, often in STAR form (Michael Page, Australian; [Michael Page, selection criteria](https://michaelpage.com.au/advice/career-advice/starting-out/how-answer-key-selection-criteria-government-job)).

### Inferences
- The variable that matters in NZ public sector is the employer's requested structure (CV plus cover letter, or a criteria-response document, or a video introduction), not the portal. Per-job generation of the cover letter against the ad's criteria covers most cases.
- A builder could offer an optional "criteria response" section that maps each stated requirement to evidence, reusing the same content as the resume.

### Gaps
- No source found describing the current careers.govt.nz CV or selection-criteria pages. Attempted search returned only links to them; not fetched in this pass.
- Written selection-criteria responses (common in older NZ public service ads) are not covered by any current source found here.
- No provider-specific portal rules found for NZ public sector (e.g. Workday or PageUp instances used by government agencies).

## Bottom line for the product decision

### Takeaway
Do not build per-provider resume formats. Build one conservative format that meets the documented constraints, plus per-job tailoring of content and cover letter, and a parse-check preview. Provider-specific work is justified only in the places where the platform really differs: file size and type checks at upload, profile and keyword fields (SEEK, Trade Me), form-answer handling, and the NZ public sector response structure.

### Inferences
- Recommended single format: single-column, text-based DOCX (or text-based PDF), no images, no text boxes, contact details in the body, standard headings, dates in one consistent format, under 2.5 MB (Greenhouse's documented parse ceiling), two pages for most roles.
- Per-job tailoring: copy role vocabulary from the ad into the skills and experience bullets. This is what recruiter-facing advice repeatedly recommends.
- Provider-specific features worth building: (a) a parse-check that pastes the resume into plain text and flags tables, columns, images and header/footer contact details; (b) a file-size check against 2.5 MB; (c) a profile keyword sync for SEEK and Trade Me; (d) a per-job cover letter for Trade Me, which may require one per application; (e) an optional criteria-response section for NZ public sector roles.
- Do not build separate Workday, Greenhouse or Lever resume files. The documented failures are shared across them.

### Gaps
- No verified data for SEEK, Trade Me, JobAdder, PageUp or SnapHire file limits, parsing, or match signals. Those would need direct testing or vendor contact.
- Workday and Lever autofill behaviour in practice is supported only by forum and vendor reports.
- Evidence that ATS-specific resume versions change hiring outcomes: none found. The available evidence suggests formatting failures are real but narrow, and volume is the larger issue.

## Source quality summary
- Official or primary: Greenhouse support (file types; unsuccessful parse), Workday admin guide, Lever help snippet, SEEK NZ career advice (snippets), Trade Me help and careers pages (snippets), NZ government pages (TPK, NZQA, PSC, DIA) (snippets or fetched where noted).
- Trade press or news: ClearanceJobs (July 2026), ERE.
- Vendor or resume-tool content (lower quality, marketing risk): Jobscan, Rezi, Enhancv, Teal, hireflow, resumegeni, Scale.jobs, Pin, Crelate, Recruiterflow, JobWizard, resumeadapter, Adobe Express.
