# Legal case extraction prompts - proven and effective

SYSTEM_PROMPT = """Extract legal case data using Pydantic models. Use exact enum values.

ENUMS: Court Level: "Appeals"/"Supreme", District: "Division I/II/III"/"N/A", Legal Roles: "Appellant"/"Respondent"/"Petitioner"/"Appellant/Cross Respondent"/"Respondent/Cross Appellant", Personal Roles: "Husband"/"Wife"/"Parent"/"Other"/"Estate", Judge Roles: "Authored by"/"Concurring"/"Dissenting", Publication Status: "Published"/"Unpublished"/"Partially Published", Appeal Outcomes: "reversed"/"affirmed"/"remanded"/"dismissed"/"partial"/"remanded_partial"/"remanded_full", Overall Outcome: "affirmed"/"reversed"/"remanded_full"/"remanded_partial"/"dismissed"/"split"/"partial"/"other", Argument Side: "Appellant"/"Respondent"/"Court"

PUBLICATION STATUS: Return ONLY "Published", "Unpublished", or "Partially Published" - no variations like "Published Only".

JUDGE EXTRACTION: Look for "Authored by [Name]", "Concurring: [Name]", "[Name], J.", "WE CONCUR:", and "Judge signing: Honorable [Name]". Extract ALL judges found.

APPEAL OUTCOME EXTRACTION: Look for "Affirmed", "Reversed", "Remanded", "We affirm", "We reverse", "We remand", "The trial court's decision is affirmed", "The judgment is reversed". Extract appeal outcomes for each issue.

OVERALL CASE OUTCOME: Determine the overall case outcome based on all issues. If ANY issue is remanded, overall cannot be "affirmed". If all issues affirmed → "affirmed", if all reversed → "reversed", if mixed without remand → "split" or "partial".

ARGUMENT EXTRACTION: Extract key arguments from each issue - separate appellant arguments, respondent arguments, and court reasoning. Each argument should be a separate entry with the appropriate side.

WASHINGTON STATE DIVORCE APPEALS ISSUE CATEGORIZATION:
Use this EXACT hierarchy from ChatGPT conversation for all issues:

TOP-LEVEL CATEGORIES (use exactly):
- "Spousal Support / Maintenance"
- "Child Support" 
- "Parenting Plan / Custody / Visitation"
- "Property Division / Debt Allocation"
- "Attorney Fees & Costs"
- "Procedural & Evidentiary Issues"
- "Jurisdiction & Venue"
- "Enforcement & Contempt Orders"
- "Modification Orders"
- "Miscellaneous / Unclassified"

SUBCATEGORIES BY CATEGORY:
Spousal Support / Maintenance: "Duration (temp vs. permanent)", "Amount calculation errors", "Imputed income disputes", "Failure to consider statutory factors", "Misinterpretation of evidence"

Child Support: "Income determination / imputation", "Deviations from standard calculation", "Allocation of expenses", "Retroactive support", "Support arrears & interest"

Parenting Plan / Custody / Visitation: "Residential schedule", "Decision-making authority", "Relocation disputes", "Restrictions (DV, SA, etc.)", "Failure to follow best-interest factors"

Property Division / Debt Allocation: "Valuation of assets", "Characterization (community vs. separate)", "Division fairness", "Omitted assets or debts", "Tax consequences ignored"

Attorney Fees & Costs: "Fee awards", "Sanctions", "Improper basis for award"

Procedural & Evidentiary Issues: "Abuse of discretion", "Failure to enter findings/conclusions", "Improper evidentiary rulings", "Denial of due process", "Judicial bias"

Jurisdiction & Venue: "Subject matter jurisdiction", "Personal jurisdiction", "Improper venue"

Enforcement & Contempt Orders: "Willfulness findings", "Sanctions", "Purge conditions"

Modification Orders: "Substantial change of circumstances", "Improper application of statute", "Retroactive application"

Miscellaneous / Unclassified: "Catch-all rare issues"

RCW REFERENCES & KEYWORDS:
Include Washington RCW statutes (e.g., "RCW 26.09.090", "RCW 26.19.071") and appeal keywords (e.g., ["rehabilitative maintenance", "indefinite award"]) when relevant.

AI LEGAL CONTENT EXTRACTION:
- FOCUS ON CONTENT: Extract all legal entities, issues, decisions, arguments
- CASE FILE NUMBER: Only extract if clearly present in document
- NO RELATIONSHIP MANAGEMENT: Database auto-generates all entity relationships  
- ✅ AI DECIDES: What legal content to extract and how to categorize it

CRITICAL CASE FILE NUMBER EXTRACTION:
- Extract legal case file number ONLY if clearly present in document (e.g., "73404-1" from "Case Info/File: 73404-1")
- Look for "Case Info/File: 71391-4" patterns in case information sections
- Look for "File Date: 2015-06-15" patterns for filing dates
- If no clear case file number found, leave as null
- Do NOT generate or invent case file numbers

DATABASE AUTO-GENERATES ALL RELATIONSHIPS:
- All entity relationships use auto-generated database keys
- AI focuses on extracting content, not managing relationships

CRITICAL DATE EXTRACTION - FOCUS ON ACTUAL PATTERNS:

TRIAL DATES (rare, found in narrative text):
- Look for "trial began on [date]" or "trial commenced [date]" in document body
- Look for "filed a petition for dissolution on [date]" → trial_start_date
- Look for "entered a decree of dissolution on [date]" → trial_published_date
- Look for "judgment entered on [date]" → trial_published_date
- Trial dates are usually in narrative text, not structured sections

APPEAL DATES (common, found in headers):
- Look for "FILED: [date]" in document headers → appeal_published_date
- Look for "opinion filed [date]" → appeal_published_date
- Look for "appeal filed on [date]" → appeal_start_date
- Appeal dates are typically in FILED sections at document top
- Calculate appeal_end_date from appeal_published_date (usually same day)

FILING DATES (very common, found in Case Information):
- Look for "Date filed: [date]" in Case Information sections
- Look for "filed on [date]" patterns
- Look for "File Date: [date]" patterns

SOURCE DOCKET EXTRACTION:
- Look for trial court case numbers different from appellate docket
- Often appears as "superior court cause no." or "trial court case"
- May be referenced in case history sections

COUNTY EXTRACTION:
- Look for county information in case headers, footers, or case information sections
- Extract county names like "King County", "Pierce County", "Spokane County"
- Often appears near court information or case filing details
- Look for "Appeal from [County] Superior Court" patterns

DOCKET NUMBER EXTRACTION:
- Look for appellate court docket numbers in case headers
- Format often like "No. 37841-1-III" or "Docket No. 12345-6"
- Extract the full docket number including any suffixes
- Look for "No. 71391-4-1" patterns in document headers
- Check case information sections for docket numbers

SOURCE DOCKET NUMBER EXTRACTION:
- Look for trial court case numbers different from appellate docket
- Often appears as "superior court cause no." or "trial court case"
- May be referenced in case history sections or case information
- Look for "Docket No: 12-3-04246-6" patterns in case information
- Check "SOURCE OF APPEAL" sections for trial court docket numbers

WINNER EXTRACTION - ANALYZE OUTCOMES:
For each issue, determine winners based on appeal outcomes:
- "affirmed" → respondent wins (trial court decision upheld)
- "reversed" → appellant wins (trial court overturned)

JUDGE EXTRACTION PATTERNS:
- Look for "Authored by Linda Lau" patterns in judge sections
- Look for "Concurring: Stephen J. Dwyer, Ann Schindler" patterns
- Look for "Judge signing: Honorable Barbara L Linde" patterns
- Extract judge names with titles (e.g., "Honorable Barbara L Linde")
- Look for "Lau, J." patterns in document text
- Check "JUDGES" sections in case information

ADDITIONAL WINNER PATTERNS:
- "remanded" → appellant wins (partial victory, gets new hearing)
- "vacated and remanded" → appellant wins (decision thrown out)

OTHER RULES: Return null for missing dates (not "Not specified" text)."""

HUMAN_TEMPLATE = """Extract legal case data.

Case Info: {case_info}
Case Text: {case_text}

AI EXTRACTS CONTENT AUTOMATICALLY:
- NO ID GENERATION: System handles all ID assignment
- EXTRACT CONTENT: Focus on names, text, decisions, legal analysis
- NO MANUAL INTERVENTION: AI decides content extraction based on legal document analysis

ISSUES & DECISIONS EXTRACTION - CRITICAL:
- For EACH issue, use EXACT Washington State divorce appeals categorization above
- Choose correct top-level category (e.g., "Spousal Support / Maintenance")
- Choose matching subcategory (e.g., "Duration (temp vs. permanent)")
- Include RCW reference if applicable (e.g., "RCW 26.09.090")
- Add relevant keywords (e.g., ["rehabilitative maintenance", "indefinite award"])
- Provide issue_summary: Specific description of the issue from the case
- Provide decision_summary: What the court decided on this issue
- Extract appeal_outcome for each issue: "affirmed", "reversed", "remanded", "dismissed", "partial"

ARGUMENTS EXTRACTION - CRITICAL:
- For EACH issue, extract separate arguments from appellant, respondent, and court
- Each argument should be a separate entry with appropriate side: "Appellant", "Respondent", "Court"
- Extract the actual argument text for each side

OVERALL CASE OUTCOME:
- Determine based on all issues: if ANY remanded → cannot be "affirmed"
- All affirmed → "affirmed", all reversed → "reversed", mixed without remand → "split" or "partial"

DATE EXTRACTION - CRITICAL (Based on actual document analysis):
- TRIAL DATES (rare): Look for "trial began on [date]" in narrative text
- APPEAL DATES (common): Look for "FILED: [date]" in document headers
- FILING DATES (very common): Look for "Date filed: [date]" in Case Information sections
- Extract trial_start_date, trial_end_date, trial_published_date (often null)
- Extract appeal_start_date, appeal_end_date, appeal_published_date (usually available)
- Look for "FILED: [date]" patterns in document headers for appeal dates
- Look for "Date filed: [date]" patterns in Case Information sections
- Look for "filed on [date]" patterns throughout document

CASE INFORMATION EXTRACTION - CRITICAL:
- Extract county information from case headers or case information sections
- Look for "Appeal from King County Superior Court" patterns
- Extract docket_number from appellate court case headers (format like "No. 71391-4-1")
- Look for "No. 71391-4-1" patterns in document headers
- Extract source_docket_number from trial court references or case history
- Look for "Docket No: 12-3-04246-6" patterns in case information
- Check "SOURCE OF APPEAL" sections for trial court docket numbers
- Look for "Case Info/File: 71391-4" patterns for case file numbers

CASE TYPE EXTRACTION - CRITICAL:
- Extract case type from document content and context
- Look for "In Re Marriage Of" → "divorce" or "marriage"
- Look for "In the Matter of the Marriage of" → "divorce" or "marriage"
- Look for criminal case indicators → "criminal"
- Look for civil case indicators → "civil"
- Look for family law indicators → "family"
- Look for business/commercial indicators → "business"
- Default to "divorce" for marriage dissolution cases

JUDGE EXTRACTION - CRITICAL:
- Look for "Authored by Linda Lau" patterns in judge sections
- Look for "Concurring: Stephen J. Dwyer, Ann Schindler" patterns
- Look for "Judge signing: Honorable Barbara L Linde" patterns
- Extract judge names with titles (e.g., "Honorable Barbara L Linde")
- Look for "Lau, J." patterns in document text
- Check "JUDGES" sections in case information

WINNER ANALYSIS - CRITICAL:
- Analyze overall case outcome to determine winner_legal_role and winner_personal_role
- Determine appeal_outcome based on all issues combined
- Use winner extraction rules: affirmed → respondent wins, reversed → appellant wins, etc.

SPECIFIC WINNER FIELD EXTRACTION:
- winner_legal_role: Extract "appellant", "respondent", "petitioner" based on who won
- winner_personal_role: Extract "husband", "wife", "parent" based on personal roles
- appeal_outcome: Extract "affirmed", "reversed", "remanded", "dismissed", "partial" based on court decision
- Look for phrases like "we affirm", "we reverse", "remanded for further proceedings"
- Analyze case outcomes to determine who won each issue

PUBLICATION STATUS EXTRACTION - CRITICAL:
- Look for publication status in document headers or case information
- Return ONLY these exact values: "Published", "Unpublished", or "Partially Published"
- Do NOT return variations like "Published Only", "Unpublished Only", etc.
- If document says "Published Only" → return "Published"
- If document says "Unpublished Only" → return "Unpublished"
- If document says "Partially Published Only" → return "Partially Published"
- Default to "Published" if unclear

PARTIES EXTRACTION - CRITICAL:
- Extract all parties with their legal roles (Appellant, Respondent, Petitioner)
- For compound roles like "Appellant/Cross Respondent", extract as "Appellant/Cross Respondent"
- Extract personal roles (Husband, Wife, Parent, Estate) ONLY when clearly identifiable
- For civil/criminal cases, leave personal_role as null unless it's clearly an Estate
- Look for party names in case headers, case information sections
- Extract attorney information with firm names and addresses

ATTORNEY REPRESENTATION EXTRACTION - CRITICAL:
- For attorney "representing" field, extract ONLY the basic legal role: "Appellant", "Respondent", "Petitioner", "Third Party"
- Do NOT extract descriptive text like "Appellants Keith and Lisa Blume" or "Guardian ad litem for J. H."
- Extract the core legal role that the attorney represents
- Look for patterns like "Attorney for Appellant" → "Appellant", "Counsel for Respondent" → "Respondent"

Extract: case_file_id, title, court, district, county, docket_number, source_docket_number, case_type, trial judge, trial dates, appeal dates, attorneys (with firms), appeals judges, parties, CATEGORIZED ISSUES WITH DECISIONS (using Washington hierarchy), ARGUMENTS (separated by side), precedents, overall_case_outcome, winner_legal_role, winner_personal_role, appeal_outcome."""
