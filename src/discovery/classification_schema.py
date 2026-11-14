"""
Centralized AI Classification Schema and Versioned Prompts (Phase D).

Defines the strict JSON Schema for AI outputs and the authoritative zero-hallucination
system prompt enforced across both Groq (Primary) and Google Gemini (Fallback).
"""

import json
from typing import Any, Dict

AI_CLASSIFICATION_PROMPT_VERSION = "v1.0"

# Strict JSON Schema defining required structure and enums
CLASSIFICATION_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CyberScoutOpportunityClassification",
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Verifiable opportunity title extracted from source"
        },
        "description": {
            "type": "string",
            "description": "Concise summary grounded strictly in the source page text"
        },
        "organization": {
            "type": ["string", "null"],
            "description": "Hosting organization, company, university, or platform"
        },
        "category": {
            "type": "string",
            "enum": [
                "job",
                "internship",
                "bug_bounty",
                "vulnerability_disclosure",
                "ctf",
                "hackathon",
                "scholarship",
                "free_course",
                "free_training",
                "research_opportunity",
                "conference",
                "webinar",
                "dfir",
                "open_source_contribution",
                "mentorship",
                "other"
            ],
            "description": "Canonical opportunity category"
        },
        "subcategory": {
            "type": ["string", "null"],
            "description": "Specialized domain or track (e.g. 'web security ctf', 'soc analyst internship')"
        },
        "required_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technical skills explicitly stated as required"
        },
        "preferred_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills stated as nice-to-have or preferred"
        },
        "cybersecurity_domain": {
            "type": ["string", "null"],
            "description": "Primary domain (e.g. 'AppSec', 'Cloud Security', 'DFIR', 'SOC', 'Cryptography')"
        },
        "experience_level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced", "all_levels", "unknown"]
        },
        "eligibility": {
            "type": "object",
            "properties": {
                "education": {"type": ["string", "null"]},
                "academic_year": {"type": ["string", "null"]},
                "experience": {"type": ["string", "null"]},
                "age_restrictions": {"type": ["string", "null"]},
                "countries": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "other_requirements": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["education", "countries", "other_requirements"]
        },
        "location": {
            "type": "object",
            "properties": {
                "country": {"type": ["string", "null"]},
                "region": {"type": ["string", "null"]},
                "city": {"type": ["string", "null"]},
                "work_mode": {
                    "type": "string",
                    "enum": ["remote", "onsite", "hybrid", "unknown"]
                },
                "global_eligibility": {"type": ["boolean", "null"]}
            },
            "required": ["work_mode"]
        },
        "dates": {
            "type": "object",
            "properties": {
                "published_at": {"type": ["string", "null"]},
                "application_open": {"type": ["string", "null"]},
                "application_deadline": {"type": ["string", "null"]},
                "event_start": {"type": ["string", "null"]},
                "event_end": {"type": ["string", "null"]},
                "timezone": {"type": ["string", "null"]}
            }
        },
        "financial": {
            "type": "object",
            "properties": {
                "participation_cost_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNCERTAIN"],
                    "description": "Cost to the participant/applicant. UNCERTAIN if not stated."
                },
                "application_fee_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNKNOWN"]
                },
                "registration_fee_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNKNOWN"]
                },
                "mandatory_purchase_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNKNOWN"]
                },
                "mandatory_paid_certification_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNKNOWN"]
                },
                "mandatory_membership_status": {
                    "type": "string",
                    "enum": ["FREE", "PAID", "UNKNOWN"]
                },
                "compensation_status": {
                    "type": "string",
                    "enum": ["PAID", "UNPAID", "UNKNOWN"],
                    "description": "PAID if the opportunity offers a salary, stipend, bounty, or cash prizes."
                },
                "compensation_details": {
                    "type": ["string", "null"],
                    "description": "Verbatim compensation or prize details (e.g. '$2,000/mo stipend', '$10k prize pool')"
                },
                "pricing_evidence": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": [
                "participation_cost_status",
                "application_fee_status",
                "registration_fee_status",
                "compensation_status",
                "pricing_evidence"
            ]
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string"},
                    "exact_excerpt": {"type": "string"},
                    "source_url": {"type": "string"},
                    "section_identifier": {"type": ["string", "null"]}
                },
                "required": ["field_name", "exact_excerpt", "source_url"]
            },
            "description": "Verbatim citations from the page content corroborating every important claim."
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Classification confidence score based strictly on source clarity"
        }
    },
    "required": [
        "title",
        "description",
        "category",
        "required_skills",
        "experience_level",
        "eligibility",
        "location",
        "dates",
        "financial",
        "evidence",
        "confidence"
    ]
}


CLASSIFICATION_SYSTEM_PROMPT = f"""You are a strict opportunity classification engine for CyberScout AI (Prompt Version: {AI_CLASSIFICATION_PROMPT_VERSION}).

Your task is to analyze the supplied extracted webpage content and classify the cybersecurity opportunity into a clean, structured JSON document.

CRITICAL ZERO-HALLUCINATION INSTRUCTIONS:
1. Use ONLY facts directly supported by the provided source text.
2. DO NOT invent missing information, dates, requirements, or pricing terms.
3. If information is missing or contradictory, preserve the uncertainty:
   - Return null for missing text or date fields.
   - Return "UNKNOWN" or "UNCERTAIN" for missing status fields.
   - Do NOT assume worldwide eligibility from a missing country restriction.
   - Do NOT infer an application deadline from a publication date.
   - Do NOT assume an opportunity is free because no fee is mentioned.
4. Distinguish between economic types carefully:
   - FREE participation: Stated explicitly as free of charge, $0, or no fee.
   - PAID participation: Requires tuition, registration fee, ticket purchase, or paid examination.
   - A job or internship that PAYS the applicant is FREE to apply for (compensation_status="PAID", participation_cost_status="FREE", application_fee_status="FREE").
   - A free CTF or hackathon with cash prizes has compensation_status="PAID" and participation_cost_status="FREE".
   - A course requiring payment for a mandatory certificate is PAID (participation_cost_status="PAID").
5. Verbatim Evidence Requirement:
   - Every important factual claim (deadline, location, remote arrangement, eligibility, pricing) MUST include a supporting entry in the "evidence" array.
   - The "exact_excerpt" must be an exact verbatim substring from the source text.
   - Explanations by you are NOT evidence.
6. Return ONLY valid JSON matching the schema. No markdown formatting, no conversational filler, no code block backticks."""


def build_classification_user_prompt(
    url: str,
    title: str,
    category_hint: str,
    page_content: str,
    metadata: Dict[str, Any],
) -> str:
    """Constructs the bounded input prompt for the AI classification provider."""
    # Truncate content safely if extremely long (cap at 15,000 characters)
    bounded_content = page_content[:15000] if page_content else "No page content available."

    meta_summary = {
        "source_url": url,
        "preliminary_title": title,
        "discovery_category_hint": category_hint,
        "source_domain": metadata.get("source_domain", ""),
        "detected_platform": metadata.get("platform_name", ""),
    }

    return f"""Target URL: {url}
Preliminary Metadata:
{json.dumps(meta_summary, indent=2)}

Extracted Page Content:
---
{bounded_content}
---

Classify this opportunity and respond with structured JSON strictly complying with the schema."""

