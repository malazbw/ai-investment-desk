from typing import Dict, List


def build_assessment(
    *,
    finding: str,
    evidence: List[str],
    meaning: str,
    counterpoint: str,
    confidence: str,
    missing: List[str],
) -> Dict[str, object]:
    """Return a consistent, evidence-led summary for a specialist agent."""
    return {
        "finding": finding,
        "evidence": evidence,
        "meaning": meaning,
        "counterpoint": counterpoint,
        "confidence": confidence,
        "missing": missing,
    }
