# ATS resume parsing: engines, formats, layouts, headings (NZ focus)

Research date: 2026-11-26. Evidence tiers used below:
- **[V] Vendor-documented**: stated in an ATS or parser vendor's own help/docs/KB.
- **[T] Controlled/independent test**: a test with a stated method. Most available tests are run by resume-tool vendors, so they are marked [T-v] (vendor-run) where applicable.
- **[B] Blog folklore**: resume-tool marketing blogs and third-party guides (Jobscan, Teal, Enhancv-style guides, ResumeOptimizerPro, JobWizard, ResumeGeni, etc.). Treat as low-quality; used only to show what job seekers are told.

Coverage caveat: the vendor help centres for Workday, SuccessFactors, Taleo, iCIMS, SmartRecruiters, JobAdder, PageUp, SnapHire and Daxtra were either not reachable or returned only snippets/gated pages in this session. Where a claim rests on snippets only, it is marked as such.

---

# Which engines sit behind the ATSs

## Which parsing engine is used

### Takeaway
Most mainstream ATSs either license a third-party parser (Textkernel/Sovren, Daxtra, RChilli, or a Microsoft/partner service) or run a native one. Vendors rarely document the engine. Treat the ATS as a black box and design for the lowest common denominator.

### Cited Findings
- Oracle's own Taleo docs say resume parsing "is delivered using a third party partner service", and that customers needing other parsing capabilities should look to partners. [V] — via search snippet of [Oracle Taleo language scope doc / Oracle language table](https://support.oracle.com/knowledge/Oracle%20Cloud/2594454_1.html) (snippet only; full article gated).
- Bullhorn's own KB has a "Parsing – Technical Specifications and Sovren FAQ" page, and a separate "Resume Parsing with Daxtra" KB page, showing Bullhorn offers both engines depending on product line. [V] — [Bullhorn Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm); [Bullhorn Daxtra page](https://kb.bullhorn.com/bh4sf/Content/BH4SF/Topics/resumeParsing.htm) (snippet title only).
- SAP SuccessFactors parsing is a configurable feature that must be enabled in Provisioning / Manage Recruiting Settings; parsing only runs on manual upload to a candidate profile, not CSV or API imports. [V] — SAP KBAs via search snippets: [KBA 2582786](https://userapps.support.sap.com/sap/support/knowledge/en/2582786), [KBA 3599424](https://userapps.support.sap.com/sap/support/knowledge/en/3599424), [KBA 2768761](https://userapps.support.sap.com/sap/support/knowledge/en/2768761). Snippets only; not opened.
- Microsoft's CandidateZip connector (Resume/Job Parser) is a parser exposed as a Microsoft Power Platform connector, used by Greenhouse-style integrations. [V] — [CandidateZip connector page](https://learn.microsoft.com/connectors/candidatezip/). Greenhouse's help centre references a "CandidateZip integration" permissions article, consistent with this. [V] — [Greenhouse CandidateZip permissions article](https://support.greenhouse.io/hc/en-us/articles/4413632139803-CandidateZip-integation) (snippet only).
- Greenhouse's help centre references a "Parsetalent integration" article, indicating a third-party parser integration option. [V] — [Greenhouse Parsetalent integration](https://support.greenhouse.io/hc/en-us/articles/37962063973403-Parsetalent-integration) (title/snippet only).
- Sovren (now Textkernel) states it parses "any non-image resume and CV format" and "has no document limits", and that parsing happens in memory with nothing written to disk. [V] — [Textkernel/Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm) (the Bullhorn-hosted Sovren FAQ page).
- RChilli publishes its own format and tips help articles, and states that real-world accuracy depends more on text quality, layout and formatting than file type. [V] — [RChilli supported formats](https://help.rchilli.com/hc/en-us/articles/360011281033-What-Resume-file-formats-can-the-RChilli-Parser-process); [RChilli best format article](https://help.rchilli.com/hc/en-us/articles/50944742931097-Which-resume-format-PDF-DOCX-or-TXT-provides-the-best-parsing-accuracy-and-performance-when-processed-through-RChilli) (snippet).
- iCIMS community articles say a parser auto-populates the Edit Candidate page; some third-party guides claim iCIMS uses a Textkernel-based parser, but the official iCIMS materials reviewed did not confirm the engine. [V for auto-populate] — [iCIMS community: Creating a New Candidate Manually](https://community.icims.com/articles/Knowledge/Creating-a-New-Candidate-Manually-in-the-Platform-or-via-Email-Import) (snippet). [B] for the Textkernel claim — [ResumeGeni iCIMS guide](https://resumegeni.com/blog/icims-ats-resume-guide).
- Lever's help article says the parser pulls "name, organization, and contact information" into the profile. [V] — [Lever: Understanding Resume Parsing](https://help.lever.co/hc/en-us/articles/20087345054749) (snippet; the page itself failed to render in fetch, so field list is from search snippet only).
- Workday: the official admin guide says resume parsing fills prospect/candidate fields, the recruiter can review parsed data, and hidden fields plus Languages and Skills are NOT auto-filled. [V] — [Workday admin guide](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/set-up-prospects-and-candidates/hdc1552497830785.html) (snippet).

### Inferences
- Because Textkernel/Sovren, Daxtra and RChilli are each embedded in several ATSs, a parse failure in one ATS is likely to be a parser-level failure that recurs elsewhere. Vendor docs for the engines are therefore more useful than ATS-specific blogs.
- The engine's file-format list (below) is a useful upper bound for ATSs that embed it, but ATS-side settings (file size caps, upload restrictions, whether the ATS calls the parser at all) can make the effective list narrower.

### Gaps
- Official, current engine attribution for Workday, SuccessFactors, Taleo, iCIMS, SmartRecruiters and Greenhouse's native parser was not found in the sources reachable this session.
- Daxtra's own format documentation was not found (only a product page with language and field counts, and an unverified SlideShare).

---

## Supported file types (vendor-documented)

### Takeaway
DOCX and PDF are the universally accepted formats. Textkernel/Sovren and RChilli both list DOC, DOCX, PDF, RTF, TXT, HTML (and ODT in some lists). Scanned/image PDFs are the main exclusion: they need an OCR add-on or are rejected or flagged for manual entry.

### Cited Findings
- Textkernel platform docs: "supports more than 70 document formats", named as PDF, Word (doc/docx), HTML, RTF, TXT, ODT and Apple Pages; unlisted formats require contacting Textkernel to confirm. [V] — [Textkernel TK Platform file formats](https://developer.textkernel.com/TKPlatform/master/file-formats).
- Textkernel: scanned PDFs are handled only through an optional OCR add-on for CV/resume use, and "images take considerably longer to parse due to the additional OCR step." [V] — same page.
- Textkernel archives: ZIP and EML accepted for CV use, max 10 files per archive. [V] — same page.
- Sovren (Textkernel) resume parser: "any non-image resume and CV format", listing Word (incl. DOCX), PDF, HTML, RTF, OpenOffice 2.x, MS Office HTML and text-based Excel; PDF marked with an asterisk. [V] — [Bullhorn-hosted Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm).
- Bullhorn's resume parsing page lists PDF, DOC/DOCX, RTF, TXT and HTML, and says "scanned or image-based resumes may require manual data entry" unless on the updated parser. [V] — [Bullhorn: Resume Parsing](https://kb.bullhorn.com/ats/Content/BHATS/Topics/resumeParsingBHATS.htm).
- RChilli: Word (.doc, .docx, .docm, .dot, .dotx, .dotm), PDF, TXT and HTML/HTM; a separate tips article adds RTF and ODT. Excel is not accepted; ZIP is preferred for bulk. [V] — [RChilli formats](https://help.rchilli.com/hc/en-us/articles/360011281033-What-Resume-file-formats-can-the-RChilli-Parser-process); [RChilli tips](https://help.rchilli.com/hc/en-us/articles/360011188234-Tips-to-Ensure-that-Our-Resume-Parser-Reads-Your-Resumes-with-Perfection) (snippet).
- Greenhouse: the unsuccessful-parse article names ".docx or .pdf" as the expected types and says "files uploaded as images are not parsed." [V] — [Greenhouse: Unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse) (fetched).
- Greenhouse file size cap: resumes over 2.5 MB cannot be parsed. [V] — same Greenhouse article.
- Taleo: attachment formats are configurable by administrators; Taleo Business Edition accepts PNG/JPEG uploads but image-format resumes are NOT parsed. [V] — [Oracle Taleo attachment doc](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/22d/otrcg/c-attachment.html) (snippet; list truncated); [Oracle release note on image resumes](https://docs.oracle.com/en/cloud/saas/readiness/hcm/24a/tale-24a/24A-tbe-wn-f32282.htm) (snippet). A third-party guide reports a default 1,048,576-byte limit across up to ten files, unverified [B].
- Lever: help snippets do not confirm a format list. A third-party guide claims DOCX, PDF, RTF, HTML, WordPerfect and OpenOffice [B, unverified].
- Workday: no official format list found. Teal says the upload accepts DOC, DOCX, HTML, PDF, TXT, and recommends DOCX or PDF [B].
- iCIMS: pasted text is shown as text-only; resumes must be at least 70 characters when pasted. [V] — [iCIMS community](https://community.icims.com/articles/Knowledge/Creating-a-New-Candidate-Manually-in-the-Platform-or-via-Email-Import) (snippet).

### Inferences
- A file that is DOCX or text-based PDF, under 2.5 MB, is accepted by every engine and ATS reviewed. This is the safe baseline.
- Scanned or image-only PDFs and PNG/JPG resumes should be avoided entirely (they fail or require manual entry in Greenhouse, Taleo and Bullhorn).

### Gaps
- Workday, SuccessFactors, iCIMS, SmartRecruiters, JobAdder, PageUp, SnapHire, Martian Logic: no official format list reached this session.
- Whether PDF generated from Word is treated identically to native DOCX is not vendor-documented.

---

# NZ-relevant ATSs

## NZ ATS landscape and what their docs say

### Takeaway
The NZ market is dominated by a mix of enterprise (Workday, SuccessFactors, Taleo, PageUp) and SME/agency ATS (JobAdder, Bullhorn, SnapHire/Martian Logic, Greenhouse/Lever/SmartRecruiters for tech). Only Bullhorn, Greenhouse, Lever, Taleo, Bullhorn/Daxtra and SuccessFactors gave usable official parsing docs in this session. JobAdder, PageUp and SnapHire gave none.

### Cited Findings
- **PageUp**: resume parsing is listed as a feature on Capterra NZ, Software Advice and GoodFirms, but no official upload/parsing documentation was found. [B/listing] — [Capterra NZ PageUp](https://www.capterra.co.nz/software/167529/pageup-people) (listing only).
- **JobAdder**: no native parsing help article found. The only JobAdder-specific result is its Allsorter integration, which sends a resume to a third-party tool that extracts information and merges it into a template. [V for integration existence] — [JobAdder + Allsorter](https://jobadder.com/integration/allsorter/).
- **SnapHire / Martian Logic**: no SnapHire results at all. Martian Logic's blog describes "smart resume parsing and screening filters" with no independent evaluation. [V (vendor claim only)] — [Martian Logic ATS explainer](https://martianlogic.com/blogs/ats-recruitment-explained-applicant-tracking-systems).
- **Bullhorn**: official KB covers the parser fields affected by the overwrite-prevention setting (Categories, Skills, Education, Work History, Certifications), and states that scanned/image resumes need manual entry on the older parser. [V] — [Bullhorn resume parsing](https://kb.bullhorn.com/ats/Content/BHATS/Topics/resumeParsingBHATS.htm).
- **Workday**: official admin guide is the only official Workday parsing source reached. Teal, a third-party guide, says Workday's parser "often struggles" with the Work Experience section and the "My Experience" step needs the most manual correction [B].
- **Greenhouse**: see parse-failure section below. Greenhouse's MyGreenhouse candidate FAQ says parsing "can make mistakes" and candidates should review fields before saving. [V] — [MyGreenhouse FAQ](https://support.greenhouse.io/hc/en-us/articles/43418495049499-MyGreenhouse-FAQ-for-Candidates) (snippet).
- **Lever**: parser extracts name, organization and contact details. [V — snippet].
- **SuccessFactors**: parsing requires enabling; field mapping follows the Standardization Mapping configuration; some fields (supervisor, salary, reason for leaving) reportedly do not populate even when mapped; date fields and "Year Graduated" have documented or reported issues; company name can come back as "UNSPECIFIED". [V — KB snippets, reported by SAP KB 2951470, 2733185, 3110716, 2514324].
- **iCIMS**: resume must have a candidate name in the body (not only in a document header) or the profile is not created; email imports need name plus phone or email. [V] — iCIMS community snippets.
- **Taleo**: parsing is delivered by a third-party partner; English is "Supported", some other languages "Limited". [V — snippet].
- **SmartRecruiters**: no official candidate-upload parser page reached; SAP KBA snippets indicate PDF data sometimes fails to populate profiles in SuccessFactors-embedded SmartRecruiters. [V-snippet].

### Inferences
- Five of the NZ-relevant ATSs (JobAdder, PageUp, SnapHire, SmartRecruiters, Daxtra-powered products) have no documentation reached. Any claim about them in blogs is unverified.
- Name-in-header failure (iCIMS, Greenhouse) is a concrete, documented failure mode that matters for any template that puts contact details in the page header.

### Gaps
- No NZ-specific test or documentation on how any of these ATSs parse NZ resume conventions (e.g. NZ address/phone formats, "Drivers licence" or "Referees" sections).
- Need the help centres for JobAdder, PageUp, SnapHire and SmartRecruiters to be fetched directly (login may be required for SmartRecruiters).

---

# Layout and format evidence

## DOCX vs PDF

### Takeaway
Across the tests found, DOCX parses more reliably than PDF, but the gap comes mostly from PDF quality (text-based vs image, and generator), not from PDF itself. The evidence is mostly vendor-run and self-selected.

### Cited Findings
- [T-v] atsverification.com (Oct 2026 large sample, 8,220 resumes, 7,151 PDFs and 1,069 DOCX, self-selected users checking their own resumes): no reading problems 32.4% PDF vs 51.8% DOCX; median score 95 vs 100; words glued together 24.1% vs 7.8%; missing standard headings 13.2% vs 5.4%; no readable text 3.5% vs 0.5%. PDFs saved from Word were clean 36.8% vs 31.2% for PDFs from other apps. The author issued a correction removing an earlier claimed Workday/Greenhouse/Lever/iCIMS/Taleo test ("We have no records of that test"). — [atsverification.com](https://atsverification.com/blog/pdf-vs-word-for-ats/). Quality: low (self-selected, the scanner is a parser not an employer ATS, and the author states this).
- [T-v] ResumeOptimizerPro cites a self-reported 97% DOCX vs 72% PDF across six platforms, about 500 resumes; no method given [B]. — [ResumeOptimizerPro](https://resumeoptimizerpro.com/blog/why-not-to-use-pdf).
- [T-v] ResumeMate (2026) states clean text-based PDFs parse reliably and DOCX offers no real advantage [B]. — [ResumeMate](https://www.resumemate.io/blog/pdf-vs-docx-for-resumes-in-2025-what-recruiters-ats-really-prefer/).
- [T-v] Enhancv's tests of PDF and DOC found similar outcomes for popular builders [B]. — [Enhancv ATS myths](https://enhancv.com/blog/busting-ats-myths/).
- [V] Greenhouse names .docx or .pdf as expected, and images are not parsed. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse).
- [V] Textkernel: scanned PDFs require OCR add-on; text PDFs handled as documents. — [Textkernel formats](https://developer.textkernel.com/TKPlatform/master/file-formats).
- [V] Sovren recommends checking a suspect PDF by opening in Adobe Reader and choosing "Save as Text": if the saved text is garbled, the parser will struggle too. — [Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm). This is a useful, vendor-neutral, reproducible test.

### Inferences
- The "Save as Text" test is the best cheap check for any PDF the builder produces: run it, and if reading order or words are broken, the parser will also break.
- The 2026 atsverification correction is a warning that blog test claims in this niche are unreliable. Use only the self-reported aggregate numbers with heavy caveats.

### Gaps
- No independent test (academic or recruiter-run, with a fixed corpus and multiple ATSs) comparing DOCX and PDF was found.

---

## Multi-column layouts

### Takeaway
Two-column layouts parse inconsistently. Word order and section grouping can break, even though word count stays the same. The most credible test (Enhancv, vendor-run with a published method) shows the damage is mostly structural (section intact 35% vs 60% for worst-performing extractor), and that single-column is safer.

### Cited Findings
- [T-v] Enhancv two-column test: 17 templates, same content, 357 runs, seven extraction methods. Word recovery nearly identical (gap ≤0.5 pts). Contact details extracted in all runs. Under the worst-performing method, section structure intact 35% for two-column vs 60% for one-column; under a common method, the drop was about one point. Geometry-sorted readers read straight across columns, joining fragments. The LLM sub-test: structural loss shrank to about 3 points, but employer-name recovery fell from 100% to 83% because titles and employers were interleaved; the article says a single-column layout removes that risk. Enhancv is a commercial resume builder. — [Enhancv two-column test](https://enhancv.com/blog/two-column-resume-ats-test/) (fetched).
- [T-v] Textkernel (vendor): its parser handles single and multi-column resumes; column detection uses visual gaps and a rule-based system, then was replaced by a gradient-boosting classifier. On over 600 visual gaps, accuracy 91% vs 82% for the old rules; for column-separator gaps specifically, 60% to 82%. In a review of about 700 CVs, "well-rendered CVs" rose from 62% to 90%. The old system broke key-value layouts by splitting keys from values. — [Textkernel column blog](https://textkernel.com/learn-support/blog/improving-extraction-from-column-resumes) (fetched). Vendor-reported, no method for the 700-CV review given.
- [B] atsverification: two-column PDFs read inconsistently, sometimes column-by-column, sometimes across. — [atsverification](https://atsverification.com/blog/pdf-vs-word-for-ats/).
- Note on tension: Enhancv's search-summary line says "virtually all modern ATS read two-column resumes correctly", but its own full test shows column order and section structure can break under some extractors (35% vs 60% intact). Quote the full test, not the headline. — [Enhancv two-column test](https://enhancv.com/blog/two-column-resume-ats-test/).
- [V] Greenhouse: "columns" and "tables" are listed as formatting problems that cause partial or failed parses. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse).

### Inferences
- Single-column is the safest structure. Textkernel's own work confirms columns are a known hard case.
- A two-column header (name in wide column, contact in narrow column) can lose the name (Enhancv "contemporary" template). Put name and contact details in the main body, full width, in the first lines.

### Gaps
- No ATS-specific (non-vendor) test of multi-column with named ATSs.

---

## Tables

### Takeaway
Tables are the most consistently flagged problem. Vendor docs name tables as a parse failure cause; controlled tests show cells glued together in PDF.

### Cited Findings
- [V] Greenhouse: tables, columns, images or word art, and headers/footers holding contact details each cause unsuccessful or partial parses. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse).
- [T-v] atsverification single-resume illustration: a two-column skills table, saved as PDF from several tools, scored 84–85 (cells glued, e.g. "LanguagesGo"); the same content as Word scored 99–100. Author calls this "an illustration rather than a ranking." — [atsverification](https://atsverification.com/blog/pdf-vs-word-for-ats/).
- [T-v] DEV Community (single tool test, 5 ATS, author's own method): a skills table collapsed into a single line; Workday and iCIMS parsed DOCX more cleanly; Greenhouse, Lever, Ashby tied. [B] — [DEV Community](https://dev.to/charliemorrison/i-reverse-engineered-5-ats-systems-here-is-what-your-resume-actually-looks-like-to-them-36ce).
- [B] ResumeOptimizerPro cites a 2025 study with 4% DOCX failure for plain text, 18% for PDF, 31% for tables in DOCX; could not be located, so unverified. — [ResumeOptimizerPro](https://resumeoptimizerpro.com/blog/ats-resume-sample).
- [V] Textkernel: no table-specific handling documented in sources reached. [gap]

### Inferences
- Replace skills tables with a plain bulleted or comma-separated list. Tables are the single easiest thing to remove without losing content.

### Gaps
- No vendor-documented table-handling behaviour for Workday, SuccessFactors, Taleo, iCIMS, JobAdder, PageUp.

---

## Text boxes, headers/footers, images, graphics (skill bars)

### Takeaway
Text boxes, shapes, header/footer content, images and icon-based or graphic skill bars are invisible or partially read. Header content is the most consequential because it contains contact details and, for iCIMS, the candidate name.

### Cited Findings
- [V] Greenhouse: "headers or footers holding contact details" and "images or word art" cause failed or partial parses. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse).
- [V] iCIMS: if the name is only in a document header, the parser cannot read it, and bulk imports fail; the resume is rejected. — [iCIMS community](https://community.icims.com/articles/HowTo/Creating-New-Candidates-via-Bulk-File-Transfer-Migrating-Legacy-Resumes-during-Implementation) (snippet).
- [V] Textkernel: image-only and scanned inputs need OCR; the standard path does not read image content. — [Textkernel formats](https://developer.textkernel.com/TKPlatform/master/file-formats).
- [V] Bullhorn: scanned or image-based resumes may need manual data entry. — [Bullhorn](https://kb.bullhorn.com/ats/Content/BHATS/Topics/resumeParsingBHATS.htm).
- [T-v] atsverification: text-as-graphics headers (vector-shape headings) are invisible to parsers. [T-v, self-reported, see caveat]. — [atsverification](https://atsverification.com/blog/pdf-vs-word-for-ats/).
- [B] Teal and Jobscan-style guides say graphics, icons and skill bars break parsing. Not tested by a credible source here. — [Teal Workday guide](https://www.tealhq.com/post/workday-resume) (secondary).
- [V] Taleo: image-format resumes are not parsed. — [Oracle](https://docs.oracle.com/en/cloud/saas/readiness/hcm/24a/tale-24a/24A-tbe-wn-f32282.htm) (snippet).

### Inferences
- Put contact details in body text, not header/footer. Keep the candidate's full name as the first body line in plain text.
- Skill bars, icons, progress meters and logos: remove. No source found that these are read correctly.

### Gaps
- No controlled test on skill bars or icons across named ATSs was found.

---

## Fonts and bullet characters

### Takeaway
No vendor documentation found that specifies accepted fonts. Bullet glyphs are a known source of garbled text in PDFs. The safe defaults are standard fonts and standard bullets.

### Cited Findings
- [B] Multiple guides recommend standard fonts and standard bullets (circle, dot). No credible test was found. — e.g. [Adobe resume formatting mistakes](https://www.adobe.com/acrobat/resources/resume-formatting-mistakes.html) (search snippet; not opened).
- [V] The "Save as Text" test (Sovren) will surface glyph and reading-order problems in PDFs, including font-encoding issues. — [Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm).

### Inferences
- Use a common sans or serif font embedded in the PDF, standard bullet glyphs, and no decorative symbols.

### Gaps
- No vendor or independent test of font or bullet-glyph handling was found.

---

# Structure: headings and order

## Section headings

### Takeaway
Use plain, conventional headings: "Experience" or "Work Experience", "Education", "Skills", optionally "Certifications" and "Summary"/"Profile". Creative headings are reliably flagged as risky in vendor guides. The one specific vendor heading recommendation found is Workday's "Experience, Education, Skills" (via a Teal blog quote, so [B]).

### Cited Findings
- [V] Bullhorn: its parser populates Categories, Skills, Education, Work History and Certifications; parsed certifications go to the Certification field on the Education tab. — [Bullhorn](https://kb.bullhorn.com/ats/Content/BHATS/Topics/resumeParsingBHATS.htm).
- [V] SuccessFactors: Parsed values follow the Standardization Mapping configuration; fields must be mapped for parsing to populate them. — [SAP KBA 2951470](https://userapps.support.sap.com/sap/support/knowledge/en/2951470) (snippet).
- [B] Workable and Teal recommend "Work Experience" and "Education" as standard headings. — [Workable](https://resources.workable.com/blog/how-ATS-reads-resumes/); [Teal](https://www.tealhq.com/post/workday-resume).
- [B] ATS headings guide (atsverification, July 2026) claims a 100 vs lower score benchmark for standard headings; single-vendor, unverified. — [atsverification headings](https://atsverification.com/blog/ats-resume-section-headings/) (search snippet).
- [B] Generic headings like "Where I've Been" or "What I'm Good At" are described as risky by several guides; no test was found. — [Enhancv headings](https://enhancv.com/blog/resume-headings/) (snippet).
- [V] Atsverification's 2026 large sample shows 13.2% of PDFs and 5.4% of DOCX resumes had "missing standard headings" — indicating heading-detection is a measurable failure category in the wild. [T-v] — [atsverification](https://atsverification.com/blog/pdf-vs-word-for-ats/).

### Inferences
- Recommended order (vendor-neutral consensus from guides, not tested): Name and contact (body, first lines) → Summary (optional) → Skills (plain list) → Experience (reverse-chronological, title, employer, dates on separate lines) → Education → Certifications (optional). Experience-first is safer for most professionals; Education-first only for recent graduates.
- Ensure every section label is an exact, common phrase; a parser that does not recognise a heading may misroute content.

### Gaps
- No controlled test of heading vocabulary across named ATSs was found.

---

## Date formats, contact placement

### Takeaway
Date formats are a documented source of error (SuccessFactors "Year Graduated" and date-field limitations). Contact details placed in headers or narrow columns are lost. The Enhancv test shows contact fields survive two-column layouts when they are in the body; the name is lost in one template when it sits in a narrow column.

### Cited Findings
- [V] SuccessFactors: date fields have a documented limitation; Year Graduated has had parsing problems. — [SAP KBA 2733185](https://userapps.support.sap.com/sap/support/knowledge/en/2733185), [KBA 3110716](https://userapps.support.sap.com/sap/support/knowledge/en/3110716) (snippets only).
- [V] Greenhouse: contact details in headers or footers can cause a partial parse. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse).
- [T-v] Enhancv: email, location, phone and portfolio link extracted correctly in all 357 runs; one template lost the name because it was in the wide column while contact sat in a narrow side column. — [Enhancv](https://enhancv.com/blog/two-column-resume-ats-test/).
- [V] iCIMS: email import needs full name plus phone or email. — [iCIMS community](https://community.icims.com/articles/Knowledge/Adding-Candidates-in-iCIMS-Nurture) (snippet).
- Date formats: no vendor doc or controlled test comparing "Jan 2020" vs "01/2020" vs "2020–2023" was found.

### Inferences
- Use one consistent date format (e.g. "Mon YYYY – Mon YYYY" or "YYYY–YYYY"), and place dates on their own line next to the job title. Avoid "Present" in ambiguous forms only if you know the target parser; otherwise use "Present".
- Put name and contact in body text at the top, single column, no icons (phone/email icon glyphs can be parsed as garbage characters — inference, not tested).

### Gaps
- Date-format handling for NZ-style dates (DD/MM/YYYY) across ATSs is not documented.

---

## Fields extracted and failure behaviour

### Takeaway
Parsers extract name, contact, employer, title, dates, skills, education and certifications, but field coverage and accuracy vary. When parsing fails the candidate usually must re-enter details manually, or the profile is left partially filled and the recruiter must correct it.

### Cited Findings
- [V] Greenhouse: failed parse means "the resume is attached to the candidate but not read… you'll need to manually input the candidate's details." Partial parses "may result in a partial resume parse that will need to be manually corrected and verified." Parser skips fabricated names, company names and job titles. — [Greenhouse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse) (fetched).
- [V] Bullhorn: scanned or image resumes may need manual entry; parsed data can overwrite existing field values unless overwrite prevention is set. — [Bullhorn](https://kb.bullhorn.com/ats/Content/BHATS/Topics/resumeParsingBHATS.htm).
- [V] Lever: parser extracts name, organisation, contact information. — [Lever](https://help.lever.co/hc/en-us/articles/20087345054749) (snippet).
- [V] Workday: parser populates recruiter fields; hidden fields, Languages and Skills are not auto-filled. — [Workday admin guide](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/set-up-prospects-and-candidates/hdc1552497830785.html) (snippet). Workday's Experience step is reported to need manual correction [B, Teal].
- [V] iCIMS: no name means no candidate profile; the resume is rejected. — [iCIMS community](https://community.icims.com/articles/HowTo/Creating-New-Candidates-via-Bulk-File-Transfer-Migrating-Legacy-Resumes-during-Implementation) (snippet).
- [V] Textkernel: reports coverage increased for contact-field fill rates by 4–10 points on 12,000 random CVs after model change. — [Textkernel column blog](https://textkernel.com/learn-support/blog/improving-extraction-from-column-resumes).
- [V] Sovren: no document limits; no fields listed in the FAQ. — [Sovren FAQ](https://kb.bullhorn.com/invenias/Content/Invenias/Topics/parsingTechnicalSpecificationsAndSovrenFAQ.htm).
- [V] RChilli: publishes a supported fields list (help article 61520309257753, not opened). [gap]
- [T-v] Enhancv LLM sub-test (10 resumes, four LLMs, directional only): contact fields recovered perfectly; employer names fell to 83% from 100% when layout interleaved. — [Enhancv](https://enhancv.com/blog/two-column-resume-ats-test/).
- [V] SuccessFactors: some fields (supervisor name/phone, salary, reason for leaving) reportedly do not populate even when mapped. — [SAP KBA 2951470](https://userapps.support.sap.com/sap/support/knowledge/en/2951470) (snippet).

### Inferences
- A candidate should assume the profile will be partially wrong and check it. Builder output should include the same facts in plain text so the candidate can paste or re-enter quickly.
- For parsing-heavy ATSs, job titles and employers are the fields most likely to be scrambled in multi-column layouts.

### Gaps
- Field-level accuracy numbers for named ATSs (Workday, SuccessFactors, iCIMS, JobAdder, PageUp) were not found.

---

# Cross-cutting guidance for the resume builder (inference)

These are inferences from the cited findings above, not tested claims, except where noted.

1. Export DOCX as the default, and a text-based PDF as an alternative. Never ship image or scanned PDF. [V: Greenhouse, Bullhorn, Textkernel, Taleo]
2. Single column, full width, no tables, no text boxes, no shapes, no skill bars or icons. [V: Greenhouse; T-v: Enhancv; V: Textkernel on column difficulty]
3. Contact details and full name in the body at the top, not header/footer. [V: Greenhouse, iCIMS]
4. Standard headings: Summary (optional), Skills, Experience / Work Experience, Education, Certifications. Keep them as plain text. [B for wording; V-consistent with Bullhorn field categories]
5. Plain-text job lines: Title, Employer, Dates on separate lines, one date format throughout. [inference]
6. Standard bullet glyphs and a common font, embedded in PDF. [B only; untested]
7. Test any PDF with "Save as Text" in Adobe Reader and read the output in Notepad. [V: Sovren FAQ]
8. Keep file size under 2.5 MB (Greenhouse cap). [V]

---

# Evidence quality summary

| Claim | Tier | Source quality |
|---|---|---|
| Textkernel formats, OCR add-on, columns handled via ML | V | Vendor docs |
| Greenhouse formats (.docx/.pdf), 2.5 MB cap, tables/columns/headers/images fail, manual entry on failure | V | Vendor help centre (fetched) |
| Bullhorn heading/field categories, scanned needs manual entry | V | Vendor KB (fetched) |
| Lever: parser extracts name/org/contact | V | Vendor help (snippet; page didn't render) |
| Workday: fields auto-fill, hidden/Languages/Skills excluded | V | Vendor admin guide (snippet) |
| SuccessFactors specific field issues | V | SAP KBA (snippets only) |
| iCIMS: name must be in body, not header | V | Vendor community (snippet) |
| Taleo: image resumes not parsed; third-party parser | V | Vendor docs (snippet) |
| RChilli formats | V | Vendor help (snippets) |
| DOCX 51.8% clean vs PDF 32.4%; tables glued in PDF | T-v (self-selected) | Blog with correction; low-medium |
| Enhancv two-column test (357 runs, method published) | T-v | Commercial blog; method is the strongest in this set |
| Textkernel column ML accuracy (91% vs 82%) | V (self-reported) | Vendor blog |
| DOCX 97% vs PDF 72% (~500 resumes) | B | Blog, no method |
| "Standard headings score 100" | B | Blog, single vendor, unverified |
| "2025 study: 31% table failure in DOCX" | B | Unlocatable, unverified |
| Workday "often struggles" with experience section | B | Teal |
| iCIMS uses Textkernel parser | B | Unconfirmed |
| Lever accepts WordPerfect/OpenOffice | B | Unconfirmed |

# Coverage gaps (for follow-up)
- JobAdder, PageUp, SnapHire, Martian Logic and SmartRecruiters: no official parsing/upload docs reached. Next step: fetch their help centres directly (SmartRecruiters may require login).
- Daxtra official format and field docs not found.
- Workday, SuccessFactors, Taleo, iCIMS: no official format list or heading guidance reached; SAP KB and Oracle doc pages were only available as snippets.
- No independent, multi-ATS, controlled test of tables, text boxes, icons, fonts, bullets or date formats was found. All controlled data in this file is vendor-run.
- No NZ-specific parsing data (NZ address/phone formats, NZ-specific sections like "Referees").
