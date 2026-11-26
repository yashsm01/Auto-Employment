# NZ legal limits on finding and messaging employer contacts (job-application app)

Status: research notes, not legal advice. Several primary sources could not be retrieved (legislation.govt.nz returned HTTP 403 to the fetch tool), so statutory wording below is mostly from secondary sources and is flagged where unverified. Verify against legislation.govt.nz before relying on it.

## 1. Privacy Act 2020 (collecting work emails, phones, names from public sources)

### Takeaway
Public availability does not switch off the Privacy Act. Collecting a named individual's work contact details from public web pages is personal information collection, and the "publicly available" exceptions are the key question. Auto-harvesting many staff contacts for bulk outreach is the highest-risk pattern. Looking up a single advertised HR or hiring contact is lower risk. Neither question has a clean OPC answer found in this research.

### Cited Findings
- OPC position: information being publicly available does not remove it from the Act; agencies collecting public data must still account for the Act's safeguards. Source: [IAPP notes on OPC statements, 2023](https://iapp.org/news/a/notes-from-the-asia-pacific-region-8-sept-2023) and [OPC scraping statement](https://privacy.org.nz/news/statements-media-releases/new-zealand-part-of-global-effort-on-data-scraping) (secondary summary; the OPC statement itself was not fetched in full).
- NZ joined a 2023 global regulators' statement on data scraping, framing mass scraping of personal information as a privacy risk; a 2024 follow-up addressed platform operators. Source: [OPC statement](https://privacy.org.nz/news/statements-media-releases/new-zealand-part-of-global-effort-on-data-scraping).
- OPC AI guidance warns against relying on the "publicly available" exception where data may have been obtained unlawfully. Source: [Russell McVeagh summary of OPC AI guidance](https://www.russellmcveagh.com/insights-news/ai-tools-opc-releases-guidance-for-organisations-using-ai-tools/).
- IPP 2 generally requires collection directly from the individual, with exceptions including where the information is publicly available. Source: [Consumer NZ privacy law](https://consumer.org.nz/consumer-rights-and-campaigns/data-and-privacy/privacy-law); [digital.govt.nz](https://www.digital.govt.nz/standards-and-guidance/privacy-security-and-risk/privacy/information-sharing/information-sharing-agreement/legal-authority-to-share-information/what-legal-authority-to-use/privacy-act-2020-for-sharing-information).
- IPP 10 (use) has a publicly-available exception. Source: [CookieYes NZ Privacy Act guide](https://www.cookieyes.com/blog/new-zealand-privacy-act/) (vendor guide, not a law firm; the Consumer NZ summary labels this principle inconsistently).
- Principle titles per OPC: IPP 1 purpose of collection; IPP 2 source (collect from the individual); IPP 3 what to tell the individual; IPP 4 manner of collection; IPP 10 limits on use; IPP 11 disclosure. Source: [OPC privacy principles page](https://www.privacy.org.nz/the-privacy-act-and-codes/privacy-principles/). OPC page gives titles only, no wording.
- IPP 3A was added by the Privacy Amendment Act 2025 and took effect 1 May 2026 (concerns indirect collection; relevant to collecting from third-party sources). Source: [Law Society guidance on IPP 3A](https://www.lawsociety.org.nz/professional-practice/practice-briefings/guidance-on-information-privacy-principle-3a-for-lawyers/) (search-result summary; not verified against the Act text).
- A commentator (IAPP, 2023) reads the Act as applying IPP 1 to scraping and treats the publicly-available exception to IPP 2 as making scraping generally compliant with that principle, while noting public availability is not a blanket exemption. This is one firm's interpretation, not an OPC position. Source: [IAPP](https://iapp.org/news/a/notes-from-the-asia-pacific-region-8-sept-2023).

### Inferences
- Collecting a company's published HR/recruitment address or a careers-page contact is the most defensible public-source collection, since it is published for exactly this purpose.
- Compiling a list of individual staff names and personal work emails from LinkedIn or directories, at scale, is the riskiest pattern under IPP 1 (purpose and necessity) and IPP 2 (source), even though the data is visible. Scraping LinkedIn also breaches its terms, which is a separate issue.
- Whether a single-user personal job-search tool is an "agency" depends on the definition in s 7 (not retrieved). Working assumption, unverified: an individual acting in a personal capacity is generally outside "agency", but a tool operated as a service for others, or by a business, likely is inside. Confirm before relying on it.

### Gaps
- Could not retrieve Privacy Act 2020 text (s 7 "agency" and "publicly available publication" definitions, IPP 2(2) and IPP 10 exception wording). From memory, the "agency" definition excludes an individual acting in a personal capacity; treat as unverified.
- No OPC guidance or case note found specifically on scraping for job-application or recruitment purposes.

## 2. Unsolicited Electronic Messages Act 2007 (UEMA): are job emails "commercial electronic messages"?

### Takeaway
A job application is probably not a commercial electronic message on the ordinary reading, since it does not market goods, services or an investment. A follow-up email promoting the applicant's own services (e.g. a contractor or freelancer pitching) is a closer call. Recruiter or head-hunting messages are treated as commercial by DIA. Where a message is commercial, deemed consent for a conspicuously published business address applies only if the message is relevant to the recipient's business role. Sender identification and an unsubscribe facility are required for commercial messages.

### Cited Findings
- A message is commercial if it markets or promotes goods, services, land, an interest in land, or an investment opportunity, or contains a link to those. A single message can be spam; bulk is not required. Source: [DIA, What anti-spam law means for businesses](https://www.dia.govt.nz/Spam-NZ-Spam-Law-for-Businesses) (fetched via summary).
- Messages that facilitate, complete or confirm a commercial transaction the recipient previously agreed to are not commercial. Source: [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions).
- DIA FAQ on head-hunting: "We consider that your purpose would be commercial as you are marketing or promoting a service." Source: [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions).
- Deemed consent may apply where an address is "conspicuously published by a person in a business or official capacity", but not if the publication says the holder does not want unsolicited messages. Deemed consent requires the message to be "relevant to the business, role, functions or duties" of the person. Source: [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions).
- A single correspondence does not reasonably allow inference of consent to promotional email (DIA FAQ). Source: [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions).
- Unsubscribe facility must be clear and conspicuous, free, and functional for at least 30 days; requests honoured within five working days. Source: [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions).
- Commercial messages must identify the authorising sender. Sender must be able to show consent. Source: [Otago summary of UEMA](https://www.otago.ac.nz/its/services/security-services/unsolicited-electronic-messages-act-2007) (search-result summary).
- Address-harvesting software: sending to addresses gathered with it, or using lists generated with it, is prohibited for commercial messages. Source: [DIA address-harvesting page](https://dia.govt.nz/Spam-Electronic-Address-Harvesting-Software).
- Penalty: DIA guidance says non-compliance "could mean a fine of up to $500,000" (business). Source: [DIA, What anti-spam law means for businesses](https://www.dia.govt.nz/Spam-NZ-Spam-Law-for-Businesses). The DIA FAQ mentions individuals can seek compensation and damages. Individual-penalty figure not verified.
- Press summary (2007, NZ Herald): messages relating to a person's job are deemed consent where the person's address is on their website. Source: [NZ Herald Q&A, 2007](https://nzherald.co.nz/business/itop-tipsi-laws-to-beat-spamming/NBUINJKLJW4FO3MFYNY23RDIKI). Press summary, possibly dated.
- UEMA covers email, instant messages and SMS/MMS with a NZ link; it does not cover voice calls or faxes in the sense of telemarketing calls, and DIA guidance notes telemarketing calls are outside it. Source: [DIA business page](https://www.dia.govt.nz/Spam-NZ-Spam-Law-for-Businesses); [Otago summary](https://www.otago.ac.nz/its/services/security-services/unsolicited-electronic-messages-act-2007).

### Inferences
- A one-off application email, with a CV attached and no promotion, is likely outside "commercial". Confidence: moderate. The DIA page does not address job applications directly.
- A follow-up email to a named HR or hiring contact about a specific advertised role is likely low-risk. Its relevance to the recipient's role supports deemed consent if it is treated as commercial.
- Bulk templated outreach to many staff, or messages promoting a recruitment or contracting service, is more likely commercial and needs consent or deemed consent plus sender ID and an unsubscribe facility.
- An app should, for any outreach it could treat as commercial: restrict recipients to published business addresses, check relevance to the recipient's role, identify the user, and include a working unsubscribe line.

### Gaps
- Statute text not retrieved (s 6 definitions, s 7 consent, s 9-12, penalty sections). Wording above is from DIA and secondary summaries.
- No DIA or court guidance found on job applications specifically.
- Individual penalty amount not verified.

## 3. WhatsApp: unsolicited messaging, automation, unofficial clients

### Takeaway
WhatsApp's Business Messaging Policy allows contact only with consent (the person gave their number or username and opt-in), and outside a 24-hour window only with approved templates. Unofficial clients such as Baileys are not expressly addressed in the policy text retrieved, but third-party sources say they carry account-ban risk and may breach the consumer Terms of Service. Cold messages to people who never contacted the sender are the highest-risk pattern.

### Cited Findings
- Policy: "You may only contact people on WhatsApp if: (a) they have given you their mobile phone number or username..." and businesses must not "spam or surprise people". Opt-outs must be respected. Source: [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/) (fetched). Page "last updated" September 23, 2026.
- Outside the 24-hour customer-service window, only approved Message Templates may be sent. Automation is allowed inside the window if human escalation is available. Source: [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/).
- Enforcement: access may be restricted or removed; messaging volume may be capped; violations can lead to a permanent ban; detection uses automated processing and human review. Policy may change without notice. Source: [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/).
- The Messaging Guidelines prohibit unofficial clients, auto-messaging and automation "to harm WhatsApp or our users" (the "to harm" qualifier matters). Source: [WhatsApp messaging guidelines](https://www.whatsapp.com/legal/messaging-guidelines?lang=en) (search-result summary; not fetched in full).
- Third-party sources say Baileys-type libraries drive the consumer app over the WhatsApp Web protocol, may violate the ToS, carry non-deterministic ban risk, and that risk rises with cold outreach, new numbers and high volume. Sources: [WhatsApp Cloud API vs unofficial libraries, checkleaked.cc](https://whatsapp.checkleaked.cc/ja/blog/whatsapp-cloud-api-vs-unofficial); [Baileys-based library README/disclaimer, as summarised in search](https://dev.to/muhammad_yasin_2347c75f3c/phrolova-baileys-9fn). Vendor and community sources, not Meta documentation.
- Supply-chain caution: a reported malicious npm fork of Baileys stole auth tokens. Source: [checkleaked.cc guide](https://whatsapp.checkleaked.cc/bn/blog/avoid-whatsapp-ban) (vendor blog; unverified).
- Official route: WhatsApp Business Platform (Cloud API) with opt-in and templates. Source: [Meta developer docs, getting opt-in](https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in).

### Inferences
- Messaging a business owner's or HR person's personal WhatsApp number cold, about a job, is outside the policy's consent basis and would be a template-only contact for a business account. A personal account using automation is also likely a ToS problem regardless of purpose.
- Messaging a number the person published for business contact is still not clearly permitted. Treat it as needing a human-initiated, one-off message at most.
- Apps should not send WhatsApp messages automatically to employer contacts. Keep it user-initiated, with the user sending from their own account.

### Gaps
- Consumer WhatsApp Terms of Service (whatsapp.com/legal/terms-of-service) not retrieved. The whatsapp.com business-policy URL redirected and the Meta/WhatsApp consumer ToS text on unofficial clients was not verified.
- No primary Meta statement on Baileys enforcement found.
- Whether a job-related message to a personal number is "consent" under the policy is untested; no source addresses it.

## 4. Cold calling or texting employers: Do Not Call, Fair Trading Act

### Takeaway
No statutory NZ Do Not Call register was found in this research. UEMA covers texts and emails, not telemarketing voice calls. The Fair Trading Act was not confirmed to address unsolicited job-related calls. Practical risk for a job seeker: low for a single, relevant, user-initiated call to a published number; higher for scripted or automated calling.

### Cited Findings
- UEMA is the main law on unsolicited electronic messages; DIA enforces it. Source: [DIA spam law page](https://www.dia.govt.nz/SPAM-NZ-SPAM-Law).
- Privacy Commissioner in 2008 urged a legal review of a national do-not-call database; no statutory register confirmed since. Source: [OPC report on UEMA](https://privacy.org.nz/publications/reports-to-parliament-and-government/unsolicited-electronic-messages-act-2007) (search summary). Current status not confirmed.
- Industry sources mention do-not-call and do-not-mail registers, but who runs them and whether they are statutory was not confirmed. No source fetched.

### Inferences
- Automated voice calls (robocalls, IVR-style) to employers would need separate review; UEMA does not cover them but other rules may (not researched).
- Automated SMS to a person's mobile is within UEMA and should follow section 2 above.

### Gaps
- Fair Trading Act 1986 text and any application to unsolicited calls not found. Recommend a targeted search of legislation.govt.nz and the Marketing Association's current register information.
- Current status of any NZ Do Not Call register unverified.

## Summary for the app design (inference, not legal advice)

- Find automatically: published business contact details from a company's own careers or contact page, and job-advert contacts. These are published for this purpose.
- Find with care or leave to the user: named individuals and personal work emails from LinkedIn or directories. Do not scrape at scale.
- Send automatically, with conditions: application emails tied to a specific advertised role, with user identification and a note the user can reply to stop further contact. Keep volume low and the content non-promotional. Treat follow-ups as needing the same care.
- Leave to the user: all WhatsApp contact with employers or individuals, and any phone calls or texts. Do not automate WhatsApp through unofficial clients.
- Do not use unofficial WhatsApp libraries for automated outreach given ban and ToS risk.

## Source list
- [Privacy Act 2020, legislation.govt.nz](https://www.legislation.govt.nz/act/public/2020/31/en/latest/) (not retrieved, 403)
- [UEMA 2007, legislation.govt.nz](https://www.legislation.govt.nz/act/public/2007/0007/latest/DLM405134.html) (not retrieved, 403)
- [DIA spam law for businesses](https://www.dia.govt.nz/Spam-NZ-Spam-Law-for-Businesses)
- [DIA FAQ](https://dia.govt.nz/Spam-Frequently-Asked-Questions)
- [DIA address-harvesting software](https://dia.govt.nz/Spam-Electronic-Address-Harvesting-Software)
- [OPC privacy principles](https://www.privacy.org.nz/the-privacy-act-and-codes/privacy-principles/)
- [OPC scraping statement](https://privacy.org.nz/news/statements-media-releases/new-zealand-part-of-global-effort-on-data-scraping)
- [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/)
- [Meta developer docs, opt-in](https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in)
