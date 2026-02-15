"""Lead management models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, validator


class LeadStatus(str, Enum):
    """Lead status enum."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    INTERESTED = "interested"
    NEGOTIATING = "negotiating"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    UNQUALIFIED = "unqualified"


class LeadSource(str, Enum):
    """Lead source enum."""

    WEBSITE = "website"
    FORM = "form"
    EMAIL = "email"
    SOCIAL = "social"
    REFERRAL = "referral"
    API = "api"
    IMPORT = "import"
    ORGANIC = "organic"


class LeadScore(BaseModel):
    """Lead scoring model."""

    engagement_score: int = Field(ge=0, le=100)
    fit_score: int = Field(ge=0, le=100)
    urgency_score: int = Field(ge=0, le=100)
    total_score: int = Field(ge=0, le=300)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("total_score")
    def validate_total(cls, v, values):
        """Validate total score is sum of components."""
        if "engagement_score" in values and "fit_score" in values and "urgency_score" in values:
            expected = values["engagement_score"] + values["fit_score"] + values["urgency_score"]
            if v != expected:
                raise ValueError(f"Total score must equal sum of components: {expected}")
        return v


class Lead(BaseModel):
    """Lead model."""

    id: str
    email: EmailStr
    first_name: str
    last_name: str
    company: str | None = None
    domain: str | None = None
    status: LeadStatus = LeadStatus.NEW
    source: LeadSource
    phone: str | None = None
    title: str | None = None
    score: LeadScore | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    utm_params: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contacted_at: datetime | None = None

    @validator("first_name", "last_name")
    def names_not_empty(cls, v):
        """Validate names are not empty."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    def get_full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    def is_qualified(self) -> bool:
        """Check if lead is qualified."""
        return self.status in {
            LeadStatus.QUALIFIED,
            LeadStatus.INTERESTED,
            LeadStatus.NEGOTIATING,
            LeadStatus.CLOSED_WON,
        }

    def is_hot(self) -> bool:
        """Check if lead is hot (high score)."""
        if not self.score:
            return False
        return self.score.total_score >= 200

    def is_warm(self) -> bool:
        """Check if lead is warm (medium score)."""
        if not self.score:
            return False
        return 100 <= self.score.total_score < 200

    def is_cold(self) -> bool:
        """Check if lead is cold (low score)."""
        if not self.score:
            return True
        return self.score.total_score < 100
