from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

# String-Werte, die ein LLM gerne statt echtem null liefert — werden zu None.
_NULL_LIKE = {"null", "none", "n/a", "na", "-", "", "kein", "keiner", "unbekannt"}

# Enum: TicketCategory
class TicketCategory(str, Enum):
    TECHNICAL_SUPPORT = "technical_support"
    BILLING_DISPUTE   = "billing_dispute"
    GENERAL_INQUIRY   = "general_inquiry"
    UNKNOWN           = "unknown"

class UrgencyLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    CRITICAL = "critical"

# Input: Was n8n an unsere Service schickt 

class TicketInput(BaseModel):
    ticket_id: str = Field(..., description="Eindeutige Ticket-ID")
    raw_text: str  = Field(..., min_length=10, description="Der rohe, unstrukturierte Text des Tickets")
    source: str    = Field(default="email", description="Herkunft: email, web_form, api")

# Strukturierte Felder, die der Extractor (Node 2) aus dem Text zieht.
# Ein getyptes Schema statt eines freien dict: unbekannte Keys werden verworfen,
# Typen erzwungen, "null"-Strings zu echtem None normalisiert.
class ExtractedData(BaseModel):
    model_config = {"extra": "ignore"}   # unbekannte LLM-Keys (z.B. Tippfehler) verwerfen

    customer_name:      Optional[str] = None
    product:            Optional[str] = None
    error_code:         Optional[str] = None
    invoice_number:     Optional[str] = None
    amount:             Optional[str] = None
    deadline_mentioned: bool          = False
    deadline:           Optional[str] = None

    @field_validator("customer_name", "product", "error_code",
                     "invoice_number", "amount", "deadline", mode="before")
    @classmethod
    def _nullify_placeholder(cls, v):
        if isinstance(v, str) and v.strip().lower() in _NULL_LIKE:
            return None
        return v


# Output: was unser LangGraph zurückgibt
class TicketAnalysis(BaseModel):
    ticket_id:        str
    category:         TicketCategory
    urgency:          UrgencyLevel
    summary:          str             = Field(..., description="Kurze Zusammenfassung in 1-2 Sätzen")
    extracted_data:   ExtractedData   = Field(default_factory=ExtractedData, description="Strukturierte Felder aus dem Ticket")
    risk_flag:        bool            = Field(default=False, description="True wenn kritischer Inhalt erkannt")
    risk_reason:      Optional[str]   = Field(default=None, description="Begründung bei risk_flag=True")
    confidence_score: float           = Field(default=0.0, ge=0.0, le=1.0)