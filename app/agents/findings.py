"""
Source-attributed findings for verifiable agent outputs.

Each Finding represents a claim with explicit source attribution, allowing
users and LLMs to trace conclusions back to original data.
"""
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    """Types of sources that can back a finding"""
    SEC_FILING = "sec_filing"
    NEWS_ARTICLE = "news"
    MACRO_DATA = "macro"
    PRICE_DATA = "price"
    ANALYST_CONSENSUS = "analyst"
    PORTFOLIO_DATA = "portfolio"


class EvidenceLevel(str, Enum):
    """Reliability level of evidence"""
    PRIMARY = "primary"  # Direct from source (SEC filing, official API)
    SECONDARY = "secondary"  # Derived or aggregated
    DERIVED = "derived"  # Calculated from multiple sources


@dataclass
class SourceRef:
    """Attribution for a finding - where it came from"""
    source_type: SourceType  # What kind of source
    source_name: str  # Human-readable name (e.g., "SEC 10-K", "Reuters", "FRED VIX")
    url: Optional[str]  # Direct link to source or None if not available
    credibility_score: float  # 0-1 (SEC/FRED/broker = 1.0, news = 0.6-0.8, blog = 0.2)
    fetched_at: datetime  # When this data was retrieved

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "url": self.url,
            "credibility_score": self.credibility_score,
            "fetched_at": self.fetched_at.isoformat(),
        }


@dataclass
class Finding:
    """A verifiable claim backed by source attribution"""
    claim: str  # The actual finding (e.g., "P/E ratio is 28.5")
    source: SourceRef  # Where this came from
    evidence_level: EvidenceLevel  # PRIMARY, SECONDARY, or DERIVED
    confidence_score: float  # 0-1 (how confident we are in this finding)
    timestamp: datetime  # When the data was observed/calculated
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "claim": self.claim,
            "source": self.source.to_dict(),
            "evidence_level": self.evidence_level.value,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# URL Builders for common sources

def build_sec_url(accession_number: str) -> str:
    """Generate SEC Edgar URL from accession number"""
    if not accession_number:
        return None
    # Format: 0001234567-89-123456 -> edgar/browse/?accession_number=0001234567-89-123456
    return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=&accession_number={accession_number}"


def build_fred_url(series_id: str) -> str:
    """Generate FRED API URL from series ID"""
    if not series_id:
        return None
    return f"https://fred.stlouisfed.org/series/{series_id}"


def build_frankfurter_url() -> str:
    """Generate Frankfurter exchange rate URL"""
    return "https://www.frankfurter.dev/"
