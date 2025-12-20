"""
LLM-based Extraction using Ollama
Extracts structured legal case data from PDF text using local LLM.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .models import (
    ExtractedCase, Party, Attorney, Judge, 
    Citation, Statute, Issue
)

logger = logging.getLogger(__name__)

# System prompt for legal case extraction
SYSTEM_PROMPT = """You are an expert legal document analyzer for Washington State case law. Your task is to extract structured data from court opinions.

CRITICAL RULES - FOLLOW EXACTLY:
1. Return ONLY valid JSON. No explanations, no markdown, no text before OR after the JSON.
2. Extract ONLY information explicitly stated in the document. 
3. If information is NOT explicitly mentioned in the text, return null. Do NOT infer OR guess.
4. Do NOT hallucinate information. If uncertain, use null.
5. Escape all double quotes within string values with backslash.
6. For enum fields with options, choose exactly ONE value OR null if unclear.
7. CRITICAL: Extract ALL distinct legal issues - most appellate cases have 2-5 separate issues.
8. CRITICAL: winner_legal_role is WHO WON (a party role like Appellant/Respondent), NOT the outcome."""

EXTRACTION_PROMPT = """Analyze this Washington State court opinion and extract structured data.

CASE TEXT:
{text}

INSTRUCTIONS:
- Return ONLY the JSON object below. No other text.
- If a field's value is not explicitly stated in the document, use null.
- Do NOT guess OR infer. Only extract what is clearly written.
- Choose exactly ONE value for enum fields, OR null if ambiguous.

CRITICAL ISSUE EXTRACTION RULES:
- Appellate cases typically address 2-5 DISTINCT legal issues. Extract EACH ONE separately.
- Look for: "Issue 1:", "First,", "Second,", "We also address", "The defendant argues", "Appellant contends"
- Each issue should have its OWN entry in the issues array with its specific outcome.
- DO NOT combine multiple issues into one generic summary.
- If the court addresses multiple arguments, each is a separate issue.

CRITICAL WINNER VS OUTCOME DISTINCTION:
- "outcome" = What happened: Affirmed, Reversed, Remanded, Dismissed, or Mixed
- "winner_legal_role" = WHO WON: Appellant, Respondent, Petitioner, State, or Neither
- NEVER put "Affirmed" or "Reversed" in winner_legal_role - those are outcomes, not parties!
- If Affirmed → winner is usually Respondent. If Reversed → winner is usually Appellant.

Return this JSON structure:
{{
    "summary": "Comprehensive 5-6 sentence summary: 1) Key background facts, 2) Procedural history, 3) Primary legal issues, 4) Court's reasoning, 5) Final disposition. Use null if document is unclear.",
    "case_category": "Choose ONE: Criminal, Civil, Family, Administrative, Juvenile, Real Property, Tort Law, Contract, Constitutional, Employment, Tax, Insurance, Probate, Guardianship, Environmental, Bankruptcy, Workers Compensation, Medical Malpractice, Personal Injury, DUI, Domestic Violence, OR Other",
    "originating_court": {{
        "county": "County name only (e.g., 'King', 'Spokane') OR null if not stated",
        "court_name": "Full lower court name OR null if not stated",
        "trial_judge": "Trial judge name OR null if not mentioned",
        "source_docket_number": "Lower court case number OR null if not mentioned"
    }},
    "outcome": {{
        "disposition": "Choose ONE: Affirmed, Reversed, Remanded, Dismissed, Mixed",
        "details": "Specific outcome details OR null",
        "prevailing_party": "Choose ONE party role: Appellant, Respondent, Petitioner, Plaintiff, Defendant, Neither, OR null. NEVER use 'Affirmed' or 'Reversed' here.",
        "winner_personal_role": "Choose ONE if clearly applicable: Employee, Employer, Landlord, Tenant, Parent, Child, Patient, Doctor, Insurer, Insured, Homeowner, Contractor, State, Defendant, Plaintiff, OR null if not applicable OR unclear"
    }},
    "parties_parsed": [
        {{
            "name": "Full party name as stated in document",
            "appellate_role": "Choose ONE: Appellant, Respondent, Petitioner, Cross-Appellant",
            "trial_role": "Choose ONE: Plaintiff, Defendant, State, Intervenor, OR null if not stated",
            "type": "Choose ONE: Individual, Government, Corporation, Organization, Union",
            "personal_role": "Choose ONE if clearly applicable: Employee, Employer, Landlord, Tenant, Parent, Child, Patient, Doctor, Insurer, Insured, Buyer, Seller, Homeowner, Contractor, Student, School, Prisoner, Victim, OR null if not applicable"
        }}
    ],
    "legal_representation": [
        {{
            "attorney_name": "Full attorney name from 'FOR APPELLANT', 'FOR RESPONDENT', OR 'COUNSEL' sections, OR null",
            "representing": "Party name they represent OR null",
            "firm_or_agency": "Law firm, Prosecutor's Office, Public Defender, OR Agency name, OR null"
        }}
    ],
    "judicial_panel": [
        {{
            "judge_name": "Appellate judge last name",
            "role": "Choose ONE: Author, Concurring, Dissenting, Signatory"
        }}
    ],
    "cases_cited": [
        {{
            "full_citation": "Full citation as written (e.g., 'State v. Smith, 150 Wn.2d 489, 78 P.3d 1014 (2003)')",
            "case_name": "Short name (e.g., 'State v. Smith')",
            "relationship": "Choose ONE: relied_upon, distinguished, cited, overruled"
        }}
    ],
    "legal_analysis": {{
        "key_statutes_cited": ["List ALL specific RCWs cited, e.g., 'RCW 9.94A.525', 'RCW 42.56.010'"],
        "issues": [
            {{
                "case_type": "Choose ONE top-level case type: Criminal, Civil, Family, Administrative, Constitutional, Juvenile, Probate, Real Property, Employment, OR Other",
                "category": "The specific LEGAL TOPIC being addressed. MUST be different from case_type! Examples: For Criminal→'Sentencing','Evidence','Search & Seizure'. For Family→'Parenting Plan','Child Custody','Property Division'. For Civil→'Contract Breach','Negligence','Summary Judgment'. NEVER repeat the case_type name here!",
                "subcategory": "Even more specific detail within the category. Examples: For Sentencing→'Exceptional Sentence','Drug Offender Sentencing'. For Parenting Plan→'Residential Schedule','Decision Making'. For Contract→'Statute of Limitations','Implied Warranty'. Use null if no specific subcategory applies.",
                "question": "The specific legal question for THIS issue - be precise and distinct from other issues",
                "ruling": "How the court specifically ruled on THIS issue",
                "outcome": "Choose EXACTLY ONE: Affirmed, Reversed, Remanded, Dismissed, Mixed",
                "winner_legal_role": "WHO WON this issue - Choose ONE party role: Appellant, Respondent, Petitioner, State, Neither. NEVER put 'Affirmed' or 'Reversed' here!",
                "winner_personal_role": "Choose ONE if applicable: Employee, Employer, Landlord, Tenant, Parent, Child, State, Defendant, Plaintiff, Insurer, Insured, OR null",
                "related_rcws": ["Specific RCWs cited for THIS issue only"],
                "keywords": ["2-4 key legal terms specific to this issue"],
                "confidence": "0.0-1.0 based on how clearly this info appears in text",
                "appellant_argument": "Appellant's main argument on THIS specific issue (1-2 sentences) OR null if not stated",
                "respondent_argument": "Respondent's main argument on THIS specific issue (1-2 sentences) OR null if not stated"
            }}
        ]
    }},
    "procedural_dates": {{
        "oral_argument_date": "Date in YYYY-MM-DD format OR null if not mentioned",
        "opinion_filed_date": "Date in YYYY-MM-DD format OR null if not clear"
    }}
}}

HIERARCHY RULES - VERY IMPORTANT:
- case_type is the BROAD area: Criminal, Civil, Family, etc.
- category is the SPECIFIC topic: Sentencing, Evidence, Parenting Plan, Negligence, etc.
- subcategory is the DETAIL: Exceptional Sentence, Residential Schedule, Comparative Fault, etc.
- NEVER use the same value for case_type and category! They must be different!
- Examples of CORRECT hierarchies:
  * Criminal → Sentencing → Exceptional Sentence
  * Criminal → Evidence → Hearsay
  * Family → Child Custody → Residential Schedule
  * Civil → Negligence → Comparative Fault
  * Employment → Wrongful Termination → Retaliation
- Examples of INCORRECT (redundant) hierarchies to AVOID:
  * Criminal → Criminal Law → ... (WRONG! Don't repeat)
  * Family → Family Law → ... (WRONG! Don't repeat)
  * Juvenile → Juvenile → ... (WRONG! Don't repeat)

REMEMBER: Most appellate opinions have 2-5 distinct issues. Extract EACH issue as a separate entry in the issues array."""


class LLMExtractor:
    """
    Extract structured legal case data using Ollama LLM.
    """
    
    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        timeout: int = 300
    ):
        """
        Initialize the LLM extractor.
        
        Args:
            model: Ollama model name (default: from OLLAMA_MODEL env or 'llama3.1:8b')
            base_url: Ollama server URL (default: from OLLAMA_BASE_URL env or 'http://localhost:11434')
            timeout: Request timeout in seconds
        """
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = timeout
        
        logger.info(f"LLM Extractor initialized with model: {self.model}")
    
    def extract(self, text: str, max_chars: int = 25000) -> Dict[str, Any]:
        """
        Extract structured data from case text using LLM.
        
        Args:
            text: Full text of the legal document (slip opinion notice already removed by PDFExtractor)
            max_chars: Maximum characters to send to LLM (default 25000 for optimal performance)
            
        Returns:
            Dictionary with extracted data
        """
        # Smart truncation: Keep header (parties, court info), footer (outcome), sample middle
        if len(text) > max_chars:
            # Header: first 40% - contains parties, court, case number, facts
            header_size = int(max_chars * 0.40)
            # Footer: last 25% - contains outcome, ruling, disposition  
            footer_size = int(max_chars * 0.25)
            # Middle sample: 35% - contains analysis, citations
            middle_size = max_chars - header_size - footer_size
            
            header = text[:header_size]
            footer = text[-footer_size:]
            
            # Get middle sample from document center
            middle_start = len(text) // 2 - middle_size // 2
            middle = text[middle_start:middle_start + middle_size]
            
            text = header + "\n\n[...document continues...]\n\n" + middle + "\n\n[...document continues...]\n\n" + footer
            logger.info(f"Smart truncation: {len(text)} chars (header={header_size}, middle={middle_size}, footer={footer_size})")
        else:
            logger.info(f"Processing full text: {len(text)} chars")
        
        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(text=text)
        
        try:
            # Call Ollama
            response = self._call_ollama(prompt)
            
            # Parse JSON response
            extracted = self._parse_json_response(response)
            
            return extracted
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {"error": str(e)}
    
    def _call_ollama(self, prompt: str) -> str:
        """
        Make a request to Ollama API.
        
        Args:
            prompt: The prompt to send
            
        Returns:
            Response text from the model
        """
        import requests
        
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,      # Low temperature for consistent extraction
                "num_predict": 8192,     # Reduced from 16384 - sufficient for case JSON
                "num_ctx": 32768,        # Reduced from 128k to 32k - saves memory/time
            }
        }
        
        logger.info(f"Calling Ollama ({self.model})...")
        
        response = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Ollama request failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result.get("response", "")
    
    def _parse_date(self, date_str: Optional[str]):
        """
        Parse a date string from LLM output into a date object.
        Handles various formats like '2024-01-16', 'January 16, 2024', '1/16/2024'.
        
        Args:
            date_str: Date string from LLM or None
            
        Returns:
            date object or None if parsing fails
        """
        from datetime import date
        from dateutil import parser as date_parser
        
        if not date_str or date_str.lower() in ('null', 'none', 'n/a', 'not mentioned', 'not specified'):
            return None
        
        try:
            parsed = date_parser.parse(date_str)
            return parsed.date()
        except Exception:
            return None
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling common issues.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Parsed dictionary
        """
        # Clean up response
        text = response.strip()
        
        # Debug: log first 500 chars of raw response
        logger.debug(f"Raw LLM response (first 500 chars): {text[:500]}")
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start == -1:
            logger.warning(f"No JSON object found in response. Response preview: {text[:300]}...")
            return {}
        
        # Check if JSON was truncated (no closing brace)
        if end == 0:
            logger.warning(f"JSON response appears truncated (no closing brace). Attempting regex extraction...")
            return self._fix_and_parse_json(text[start:])
        
        json_str = text[start:end]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            # Try to fix common issues
            return self._fix_and_parse_json(json_str)
    
    def _fix_and_parse_json(self, json_str: str) -> Dict[str, Any]:
        """
        Attempt to fix common JSON issues from LLM output.
        Uses multiple strategies to recover malformed JSON.
        """
        import re
        
        original = json_str
        
        # Strategy 1: Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        try:
            return json.loads(json_str)
        except:
            pass
        
        # Strategy 2: Fix single quotes
        json_str = original.replace("'", '"')
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        try:
            return json.loads(json_str)
        except:
            pass
        
        # Strategy 3: Fix unescaped quotes in strings
        # Replace \" patterns that might be broken
        json_str = original
        json_str = re.sub(r'(?<!\\)"(?=[^:,\[\]{}]*"[^:,\[\]{}]*":)', r'\\"', json_str)
        
        try:
            return json.loads(json_str)
        except:
            pass
        
        # Strategy 4: Try to extract just the top-level keys we need
        result = {}
        try:
            # Extract summary
            summary_match = re.search(r'"summary"\s*:\s*"([^"]*(?:\\"[^"]*)*)"', original)
            if summary_match:
                result['summary'] = summary_match.group(1).replace('\\"', '"')
            
            # Extract case_type
            case_type_match = re.search(r'"case_type"\s*:\s*"([^"]*)"', original)
            if case_type_match:
                result['case_type'] = case_type_match.group(1)
            
            # Extract county
            county_match = re.search(r'"county"\s*:\s*"([^"]*)"', original)
            if county_match:
                result['county'] = county_match.group(1)
            
            # Extract trial_judge
            trial_judge_match = re.search(r'"trial_judge"\s*:\s*"([^"]*)"', original)
            if trial_judge_match:
                result['trial_judge'] = trial_judge_match.group(1)
            
            # Extract source_docket_number
            source_docket_match = re.search(r'"source_docket_number"\s*:\s*"([^"]*)"', original)
            if source_docket_match:
                result['source_docket_number'] = source_docket_match.group(1)
            
            # Extract appeal_outcome
            appeal_outcome_match = re.search(r'"appeal_outcome"\s*:\s*"([^"]*)"', original)
            if appeal_outcome_match:
                result['appeal_outcome'] = appeal_outcome_match.group(1)
            
            # Extract winner fields
            winner_legal_match = re.search(r'"winner_legal_role"\s*:\s*"([^"]*)"', original)
            if winner_legal_match:
                result['winner_legal_role'] = winner_legal_match.group(1)
            
            winner_personal_match = re.search(r'"winner_personal_role"\s*:\s*"([^"]*)"', original)
            if winner_personal_match:
                result['winner_personal_role'] = winner_personal_match.group(1)
            
            # Try to extract arrays using a more robust approach
            # Find parties_parsed array (or parties for legacy)
            parties_match = re.search(r'"parties_parsed"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if not parties_match:
                parties_match = re.search(r'"parties"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if parties_match:
                try:
                    parties_json = '[' + parties_match.group(1) + ']'
                    parties_json = re.sub(r',\s*]', ']', parties_json)
                    result['parties_parsed'] = json.loads(parties_json)
                except:
                    pass
            
            # Find judicial_panel array (or judges for legacy)
            judges_match = re.search(r'"judicial_panel"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if not judges_match:
                judges_match = re.search(r'"judges"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if judges_match:
                try:
                    judges_json = '[' + judges_match.group(1) + ']'
                    judges_json = re.sub(r',\s*]', ']', judges_json)
                    result['judicial_panel'] = json.loads(judges_json)
                except:
                    pass
            
            # Find legal_representation array
            legal_rep_match = re.search(r'"legal_representation"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if legal_rep_match:
                try:
                    legal_rep_json = '[' + legal_rep_match.group(1) + ']'
                    legal_rep_json = re.sub(r',\s*]', ']', legal_rep_json)
                    result['legal_representation'] = json.loads(legal_rep_json)
                except:
                    pass
            
            # Find citations array
            citations_match = re.search(r'"citations"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if citations_match:
                try:
                    citations_json = '[' + citations_match.group(1) + ']'
                    citations_json = re.sub(r',\s*]', ']', citations_json)
                    result['citations'] = json.loads(citations_json)
                except:
                    pass
            
            # Find statutes array
            statutes_match = re.search(r'"statutes"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if statutes_match:
                try:
                    statutes_json = '[' + statutes_match.group(1) + ']'
                    statutes_json = re.sub(r',\s*]', ']', statutes_json)
                    result['statutes'] = json.loads(statutes_json)
                except:
                    pass
            
            # Find issues array
            issues_match = re.search(r'"issues"\s*:\s*\[(.*?)\]', original, re.DOTALL)
            if issues_match:
                try:
                    issues_json = '[' + issues_match.group(1) + ']'
                    issues_json = re.sub(r',\s*]', ']', issues_json)
                    result['issues'] = json.loads(issues_json)
                except:
                    pass
            
            if result:
                logger.info(f"Recovered {len(result)} fields from malformed JSON")
                return result
                
        except Exception as e:
            logger.error(f"JSON recovery also failed: {e}")
        
        logger.error("Could not parse JSON even after fixes")
        return {}
    
    def build_extracted_case(self, llm_result: Dict[str, Any]) -> ExtractedCase:
        """
        Convert LLM extraction result to ExtractedCase dataclass.
        
        Args:
            llm_result: Dictionary from LLM extraction
            
        Returns:
            ExtractedCase object
        """
        case = ExtractedCase()
        
        # Normalize keys from new prompt schema to expected keys
        # parties_parsed -> parties
        if "parties_parsed" in llm_result and "parties" not in llm_result:
            llm_result["parties"] = llm_result["parties_parsed"]
        # judicial_panel -> judges
        if "judicial_panel" in llm_result and "judges" not in llm_result:
            llm_result["judges"] = llm_result["judicial_panel"]
        # legal_representation -> attorneys
        if "legal_representation" in llm_result and "attorneys" not in llm_result:
            logger.info(f"Normalizing legal_representation -> attorneys: {len(llm_result['legal_representation'])} entries")
            llm_result["attorneys"] = llm_result["legal_representation"]
        # cases_cited -> citations
        if "cases_cited" in llm_result and "citations" not in llm_result:
            llm_result["citations"] = llm_result["cases_cited"]
        # originating_court nested fields
        if "originating_court" in llm_result and isinstance(llm_result["originating_court"], dict):
            orig = llm_result["originating_court"]
            if not llm_result.get("county"):
                llm_result["county"] = orig.get("county")
            if not llm_result.get("trial_court"):
                llm_result["trial_court"] = orig.get("court_name")
            if not llm_result.get("trial_judge"):
                llm_result["trial_judge"] = orig.get("trial_judge")
            if not llm_result.get("source_docket_number"):
                llm_result["source_docket_number"] = orig.get("source_docket_number")
        # outcome nested fields
        if "outcome" in llm_result and isinstance(llm_result["outcome"], dict):
            out = llm_result["outcome"]
            if not llm_result.get("appeal_outcome"):
                llm_result["appeal_outcome"] = out.get("disposition")
            if not llm_result.get("outcome_detail"):
                llm_result["outcome_detail"] = out.get("details")
            if not llm_result.get("winner_legal_role"):
                llm_result["winner_legal_role"] = out.get("prevailing_party")
            if not llm_result.get("winner_personal_role"):
                llm_result["winner_personal_role"] = out.get("winner_personal_role")
        # case_category -> case_type
        if "case_category" in llm_result and not llm_result.get("case_type"):
            llm_result["case_type"] = llm_result["case_category"]
        # legal_analysis -> issues and statutes
        if "legal_analysis" in llm_result and isinstance(llm_result["legal_analysis"], dict):
            analysis = llm_result["legal_analysis"]
            # issues from legal_analysis (new format with rich fields)
            if "issues" in analysis and "issues" not in llm_result:
                llm_result["issues"] = analysis["issues"]
            # major_issues -> issues (legacy format fallback)
            elif "major_issues" in analysis and "issues" not in llm_result:
                llm_result["issues"] = []
                for issue in analysis.get("major_issues", []):
                    if isinstance(issue, dict):
                        llm_result["issues"].append({
                            "summary": issue.get("question", ""),
                            "decision_summary": issue.get("ruling", ""),
                            "outcome": issue.get("outcome"),
                            "category": "Other"
                        })
            # key_statutes_cited -> statutes
            if "key_statutes_cited" in analysis and "statutes" not in llm_result:
                llm_result["statutes"] = []
                for statute in analysis.get("key_statutes_cited", []):
                    if isinstance(statute, str):
                        llm_result["statutes"].append({"citation": statute})
        
        # procedural_dates -> date fields
        if "procedural_dates" in llm_result and isinstance(llm_result["procedural_dates"], dict):
            dates = llm_result["procedural_dates"]
            llm_result["opinion_filed_date"] = dates.get("opinion_filed_date")
        
        # Simple fields
        case.summary = llm_result.get("summary", "")
        # Normalize case_type - take only the first value if pipe-separated
        case_type_raw = llm_result.get("case_type", "")
        if "|" in case_type_raw:
            case.case_type = case_type_raw.split("|")[0].strip()
        else:
            case.case_type = case_type_raw
        case.county = llm_result.get("county")
        case.trial_court = llm_result.get("trial_court")
        case.trial_judge = llm_result.get("trial_judge")
        case.source_docket_number = llm_result.get("source_docket_number")
        case.appeal_outcome = llm_result.get("appeal_outcome")
        case.outcome_detail = llm_result.get("outcome_detail")
        case.winner_legal_role = llm_result.get("winner_legal_role")
        case.winner_personal_role = llm_result.get("winner_personal_role")
        
        # Parse procedural dates
        case.opinion_filed_date = self._parse_date(llm_result.get("opinion_filed_date"))
        
        # Parties (handles both old and new schema field names)
        for p in llm_result.get("parties", []):
            if isinstance(p, dict):
                name = p.get("name")
                # Build role from appellate_role and trial_role if present
                role = p.get("role") or p.get("appellate_role") or "Unknown"
                if p.get("trial_role") and p.get("trial_role") != "null":
                    role = f"{role} ({p.get('trial_role')})"
                party_type = p.get("party_type") or p.get("type")
                personal_role = p.get("personal_role")
                # Normalize null string to None
                if personal_role and personal_role.lower() == "null":
                    personal_role = None
                if name:
                    case.parties.append(Party(
                        name=name,
                        role=role,
                        party_type=party_type,
                        personal_role=personal_role
                    ))
        
        # Attorneys (handles both old and new schema field names)
        for a in llm_result.get("attorneys", []):
            if isinstance(a, dict):
                name = a.get("name") or a.get("attorney_name")
                representing = a.get("representing", "Unknown")
                firm_name = a.get("firm_name") or a.get("firm_or_agency")
                if name:
                    case.attorneys.append(Attorney(
                        name=name,
                        representing=representing,
                        firm_name=firm_name
                    ))
        
        # Judges (handles both old and new schema field names)
        for j in llm_result.get("judges", []):
            if isinstance(j, dict):
                name = j.get("name") or j.get("judge_name")
                role = j.get("role", "Unknown")
                if name:
                    case.judges.append(Judge(
                        name=name,
                        role=role
                    ))
        
        # Citations
        for c in llm_result.get("citations", []):
            if isinstance(c, dict) and c.get("full_citation"):
                case.citations.append(Citation(
                    full_citation=c["full_citation"],
                    case_name=c.get("case_name"),
                    relationship=c.get("relationship")
                ))
        
        # Statutes
        for s in llm_result.get("statutes", []):
            if isinstance(s, dict) and s.get("citation"):
                case.statutes.append(Statute(
                    citation=s["citation"],
                    title=s.get("title")
                ))
        
        # Issues - map all fields including new rich extraction fields
        for i in llm_result.get("issues", []):
            if isinstance(i, dict):
                # Handle both "summary" and "question" field names
                summary = i.get("summary") or i.get("question")
                if summary:
                    # Parse confidence score
                    confidence = None
                    if i.get("confidence"):
                        try:
                            confidence = float(i["confidence"])
                        except (ValueError, TypeError):
                            pass
                    
                    case.issues.append(Issue(
                        case_type=i.get("case_type", "Other"),
                        category=i.get("category", "General"),
                        subcategory=i.get("subcategory") or "General",
                        summary=summary,
                        outcome=i.get("outcome"),
                        winner=i.get("winner") or i.get("winner_legal_role"),
                        # New fields
                        rcw_references=i.get("related_rcws") or i.get("rcw_references"),
                        keywords=i.get("keywords"),
                        decision_stage=i.get("decision_stage", "appeal"),
                        decision_summary=i.get("ruling") or i.get("decision_summary"),
                        winner_personal_role=i.get("winner_personal_role"),
                        confidence_score=confidence,
                        # Arguments from each side
                        appellant_argument=i.get("appellant_argument"),
                        respondent_argument=i.get("respondent_argument")
                    ))
        
        case.extraction_timestamp = datetime.now()
        case.llm_model = self.model
        case.extraction_successful = "error" not in llm_result
        
        if "error" in llm_result:
            case.error_message = llm_result["error"]
        
        return case
    
    def test_connection(self) -> bool:
        """Test if Ollama is available and the model is loaded."""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(self.model in name for name in model_names):
                    logger.info(f"Ollama connection OK, model {self.model} available")
                    return True
                else:
                    logger.warning(f"Model {self.model} not found. Available: {model_names}")
                    return False
            return False
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False
