from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

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

# Output: was unser LangGraph zurückgibt
class TicketAnalysis(BaseModel):
    ticket_id:        str
    category:         TicketCategory
    urgency:          UrgencyLevel
    summary:          str             = Field(..., description="Kurze Zusammenfassung in 1-2 Sätzen")
    extracted_data:   dict            = Field(default_factory=dict, description="Strukturierte Schlüssel-Wert-Paare")
    risk_flag:        bool            = Field(default=False, description="True wenn kritischer Inhalt erkannt")
    risk_reason:      Optional[str]   = Field(default=None, description="Begründung bei risk_flag=True")
    confidence_score: float           = Field(default=0.0, ge=0.0, le=1.0)