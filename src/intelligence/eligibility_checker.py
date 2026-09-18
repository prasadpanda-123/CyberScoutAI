"""
Eligibility Checker for CyberScout AI.

Maintains strict separation between Ranking and Eligibility:
- ELIGIBLE: Verified criteria met based on profile attributes.
- INELIGIBLE: Proven violation of opportunity criteria (e.g. requires 5+ years, profile is beginner).
- UNKNOWN: Incomplete criteria or unspecified user attributes (NEVER assumed eligible or ineligible).
"""

from typing import Any, Dict, List, Optional
import re

from src.models.recommendation_models import EligibilityResult, EligibilityStatus, UserPreferencesDTO


class EligibilityChecker:
    """Evaluates whether a user qualifies for an opportunity independently of ranking score."""

    @staticmethod
    def check_eligibility(
        opportunity: Any,
        user_preferences: Optional[UserPreferencesDTO] = None,
    ) -> EligibilityResult:
        """
        Evaluates opportunity eligibility criteria against user preferences and profile.

        Args:
            opportunity: Opportunity instance, DTO, or dictionary.
            user_preferences: Optional UserPreferencesDTO.

        Returns:
            EligibilityResult with status ELIGIBLE, INELIGIBLE, or UNKNOWN and audit reasons.
        """
        # Extract eligibility text and requirements safely
        eligibility_text = ""
        opp_exp_level = ""

        if isinstance(opportunity, dict):
            eligibility_text = str(opportunity.get("eligibility") or "").strip()
            opp_exp_level = str(opportunity.get("experience_level") or "").strip().lower()
        else:
            eligibility_text = str(getattr(opportunity, "eligibility", "") or "").strip()
            opp_exp_level = str(getattr(opportunity, "experience_level", "") or "").strip().lower()

        # If opportunity has zero declared eligibility constraints: UNKNOWN
        if not eligibility_text and not opp_exp_level:
            return EligibilityResult(
                status=EligibilityStatus.UNKNOWN,
                reasons=["No explicit eligibility criteria specified by provider."],
            )

        reasons: List[str] = []
        user_exp = (user_preferences.experience_level or "").lower() if user_preferences else ""

        # 1. Evaluate Experience Level Discrepancies
        if opp_exp_level:
            if opp_exp_level in ("advanced", "senior") and user_exp == "beginner":
                return EligibilityResult(
                    status=EligibilityStatus.INELIGIBLE,
                    reasons=[f"Requires {opp_exp_level} experience, but user profile indicates beginner."],
                )
            elif user_exp and user_exp == opp_exp_level:
                reasons.append(f"Matches required {opp_exp_level} experience level.")

        # 2. Check for citizenship / clearance requirements in text
        # If opportunity specifies citizenship/clearance and user profile does not confirm it, mark UNKNOWN
        lower_text = eligibility_text.lower()
        if re.search(r"\b(us citizenship|security clearance|top secret|secret clearance)\b", lower_text):
            return EligibilityResult(
                status=EligibilityStatus.UNKNOWN,
                reasons=["Requires specific citizenship or security clearance (not specified in user preferences)."],
            )

        # 3. Check for student / enrollment requirements
        if re.search(r"\b(currently enrolled|enrolled in college|undergraduate student|must be a student)\b", lower_text):
            if user_exp in ("advanced", "senior"):
                # Professional advanced user vs college student requirement
                return EligibilityResult(
                    status=EligibilityStatus.INELIGIBLE,
                    reasons=["Requires active student enrollment; profile indicates experienced professional."],
                )
            elif user_exp in ("beginner", "student"):
                reasons.append("Matches student / early career enrollment criteria.")
            else:
                return EligibilityResult(
                    status=EligibilityStatus.UNKNOWN,
                    reasons=["Requires active student enrollment (not verified in profile)."],
                )

        # 4. If all parsed criteria are satisfied
        if reasons:
            return EligibilityResult(
                status=EligibilityStatus.ELIGIBLE,
                reasons=reasons,
            )

        # Default when criteria text exists but cannot be definitively validated against available profile fields
        return EligibilityResult(
            status=EligibilityStatus.UNKNOWN,
            reasons=["Opportunity has custom eligibility criteria that must be verified on provider portal."],
        )
