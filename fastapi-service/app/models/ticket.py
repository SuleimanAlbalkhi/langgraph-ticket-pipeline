from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from enum import Enum

# String-Werte, die ein LLM gerne statt echtem null liefert — werden zu None.
_NULL_LIKE: frozenset[str] = frozenset(
    {"null", "none", "n/a", "na", "-", "", "kein", "keiner", "unbekannt"}
)


# Enum: TicketCategory
class TicketCategory(str, Enum):
    TECHNICAL_SUPPORT = "technical_support"
    BILLING_DISPUTE   = "billing_dispute"
    GENERAL_INQUIRY   = "general_inquiry"
    UNKNOWN           = "unknown"

    @classmethod
    def coerce(cls, value: object) -> "TicketCategory":
        """Snappt einen (ggf. halluzinierten) LLM-Wert auf ein gültiges Enum.
        Single Source of Truth für die Kategorie-Defensive — genutzt vom
        Classifier (Inter-Node) und vom Orchestrator (Egress)."""
        try:
            return cls(value)
        except (ValueError, TypeError):
            return cls.UNKNOWN


class UrgencyLevel(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

    @classmethod
    def coerce(cls, value: object) -> "UrgencyLevel":
        """Snappt einen (ggf. halluzinierten) LLM-Wert auf ein gültiges Enum;
        unbekannte/fehlende Dringlichkeit fällt sicher auf MEDIUM zurück."""
        try:
            return cls(value)
        except (ValueError, TypeError):
            return cls.MEDIUM


# Input: Was n8n an unsere Service schickt

class TicketInput(BaseModel):
    ticket_id: str = Field(..., description="Eindeutige Ticket-ID")
    raw_text: str  = Field(..., min_length=10, description="Der rohe, unstrukturierte Text des Tickets")
    source: str    = Field(default="email", description="Herkunft: email, web_form, api")


# Strukturierte Felder, die der Extractor (Node 2) aus dem Text zieht.
# Ein getyptes Schema statt eines freien dict: unbekannte Keys werden verworfen,
# Typen erzwungen, "null"-Strings zu echtem None normalisiert.
class ExtractedData(BaseModel):
    # extra: unbekannte LLM-Keys (z.B. Tippfehler) verwerfen.
    # coerce_numbers_to_str: kleine LLMs liefern Beträge/Nummern gern als JSON-Zahl
    # (z.B. "amount": 1247.80) — Pydantic v2 würde das sonst als ValidationError
    # abweisen und der Egress crashte mit 500. Hier wird die Zahl zum String.
    model_config = {"extra": "ignore", "coerce_numbers_to_str": True}

    customer_name:      str | None = None
    product:            str | None = None
    error_code:         str | None = None
    invoice_number:     str | None = None
    amount:             str | None = None
    deadline_mentioned: bool       = False
    deadline:           str | None = None

    @field_validator("customer_name", "product", "error_code",
                     "invoice_number", "amount", "deadline", mode="before")
    @classmethod
    def _nullify_placeholder(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in _NULL_LIKE:
            return None
        return v


# Output: was unser LangGraph zurückgibt
class TicketAnalysis(BaseModel):
    ticket_id:        str
    category:         TicketCategory
    urgency:          UrgencyLevel
    summary:          str           = Field(..., description="Kurze Zusammenfassung in 1-2 Sätzen")
    extracted_data:   ExtractedData = Field(default_factory=ExtractedData, description="Strukturierte Felder aus dem Ticket")
    risk_flag:        bool          = Field(default=False, description="True wenn kritischer Inhalt erkannt")
    risk_reason:      str | None    = Field(default=None, description="Begründung bei risk_flag=True")
    confidence_score: float         = Field(default=0.0, ge=0.0, le=1.0)
