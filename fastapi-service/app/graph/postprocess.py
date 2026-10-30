"""Deterministische Nachbearbeitung der Extractor-Ausgabe — reine Funktionen ohne LLM."""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from app.models.ticket import null_if_placeholder

logger = logging.getLogger(__name__)

# Regex-Patterns für Fristen (LLM-Output wird damit angereichert).
# Einmalig kompiliert: spart das erneute Kompilieren bei jedem Ticket.
_DEADLINE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # Konkrete Daten: "bis spätestens 25.06.2026", "bis 25.6.2026"
        r"(?:bis(?:\s+spätestens)?|spätestens|fällig\s+am|deadline:?)\s+(\d{1,2}\.\d{1,2}\.\d{2,4})",
        # Relative Angaben: "innerhalb 14 Tagen", "innerhalb von 7 Werktagen"
        r"(innerhalb\s+(?:von\s+)?\d+\s+(?:Werk)?(?:Tagen?|Wochen|Monaten))",
        # Wochentage: "bis Freitag"
        r"(bis\s+(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag))",
        # Uhrzeit: "bis heute 14:00 Uhr", "bis morgen 12 Uhr"
        r"(bis\s+(?:heute|morgen|übermorgen)(?:\s+\d{1,2}(?::\d{2})?\s*Uhr)?)",
        # In den nächsten X Wochen/Tagen
        r"(in\s+den\s+nächsten\s+\d+(?:-\d+)?\s+(?:Tagen?|Wochen|Monaten))",
    )
)

# Platzhalter wie "<NAME>" aus den Few-Shot-Beispielen — nie ein echter Wert.
_PLACEHOLDER_PATTERN = re.compile(r"^<[^>]+>$")

# Felder, deren Wert wörtlich im Ticket-Text stehen muss.
_VERBATIM_FIELDS: frozenset[str] = frozenset({"customer_name", "invoice_number", "error_code"})

# Organisations-/Abteilungs-Marker: ein customer_name damit ist eine Signatur, keine Person
# (Eval: "Einkauf, Röder Maschinenbau GmbH" als Name). Ganzes Wort, ohne Groß/Klein.
_ORG_MARKER_PATTERN = re.compile(
    r"(?<!\w)(?:gmbh|ag|kg|ohg|gbr|e\.\s?v\.|ug|se|mbh|inc|ltd|"
    r"abteilung|einkauf|buchhaltung|verwaltung|vertrieb|betriebsrat|geschäftsführung|"
    r"sekretariat|poststelle|team|filiale|zentrale|kundenservice|personalabteilung)(?!\w)",
    re.IGNORECASE,
)

# Ab dieser Ähnlichkeit wird ein leicht verstümmelter LLM-Name (z.B. "Grwald" statt
# "Grünwald", abgeschnittenes "Sauer" statt "Sauerbeck") auf die Textstelle gezogen.
_SNAP_THRESHOLD = 0.85

# Satzzeichen, die beim Abgleich an Wortgrenzen abgeschnitten werden ("Gruß," -> "Gruß").
_TOKEN_EDGE_CHARS = ",;:!?\"'()[]"


def clean_extracted_data(data: dict) -> dict:
    """Normalisiert 'null'-/Platzhalter-Strings zu None, Booleans bleiben unberührt."""
    return {
        key: value if isinstance(value, bool) else null_if_placeholder(value)
        for key, value in data.items()
    }


def _normalize_for_match(text: str) -> str:
    """Kleinschreibung + jeglicher Whitespace (auch Zeilenumbrüche) zu einem Leerzeichen."""
    return " ".join(text.lower().split())


def _occurs_as_words(value: str, normalized_text: str) -> bool:
    """Wert steht im Text, und zwar an Wortgrenzen — "sauer" zählt nicht in "sauerbeck"."""
    pattern = r"(?<!\w)" + re.escape(_normalize_for_match(value)) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


def _person_part(name: str) -> str | None:
    """Verwirft Signaturen ohne Person. Bei "Name, Abteilung, Firma" bleibt der Teil vor
    dem ersten Komma, sofern er selbst kein Organisations-Marker ist."""
    if not _ORG_MARKER_PATTERN.search(name):
        return name
    head = name.split(",", 1)[0].strip()
    if head != name.strip() and head and not _ORG_MARKER_PATTERN.search(head):
        return head
    return None


def _snap_to_text(value: str, raw_text: str) -> str | None:
    """Sucht die ähnlichste Wortfolge im Text (gleiche Wortzahl ±1) und gibt sie im
    Original-Wortlaut zurück, wenn die Ähnlichkeit mindestens _SNAP_THRESHOLD ist."""
    tokens = [token.strip(_TOKEN_EDGE_CHARS) for token in raw_text.split()]
    tokens = [token for token in tokens if token]
    target = _normalize_for_match(value)
    n_words = len(target.split())
    best_span, best_ratio = None, 0.0
    for size in {max(1, n_words - 1), n_words, n_words + 1}:
        for start in range(len(tokens) - size + 1):
            span = " ".join(tokens[start:start + size])
            ratio = SequenceMatcher(None, target, span.lower()).ratio()
            if ratio > best_ratio:
                best_span, best_ratio = span, ratio
    return best_span if best_ratio >= _SNAP_THRESHOLD else None


def ground_to_text(extracted: dict, raw_text: str) -> dict:
    """Setzt Regel 1 des Prompts ("nur wörtlich im Text") im Code durch.
    Kleine Modelle übernehmen Platzhalter wie "<NAME>" oder erfinden Werte —
    beides wird hier verworfen. amount/product/deadline werden bewusst NICHT
    auf Wörtlichkeit geprüft (Formatvarianten wie "€" vs. "Euro").
    customer_name zusätzlich: Signaturen ohne Person werden verworfen, leicht
    verstümmelte Namen auf die passende Textstelle gezogen ("snap to text").
    Geloggt werden nur Feldname und Grund, nie der Wert (DSGVO)."""
    normalized_text = _normalize_for_match(raw_text)
    grounded = dict(extracted)
    for key, value in extracted.items():
        if not isinstance(value, str):
            continue
        if _PLACEHOLDER_PATTERN.match(value.strip()):
            grounded[key] = None
            logger.info("[Node 2 - Extractor] Feld verworfen: %s (Platzhalter)", key)
            continue
        if key == "customer_name":
            value = _person_part(value)
            if value is None:
                grounded[key] = None
                logger.info("[Node 2 - Extractor] Feld verworfen: %s (Organisation statt Person)", key)
                continue
            grounded[key] = value
            if not _occurs_as_words(value, normalized_text):
                grounded[key] = _snap_to_text(value, raw_text)
                logger.info("[Node 2 - Extractor] Feld %s: %s", key,
                            "auf Textstelle gezogen" if grounded[key] else "verworfen (nicht im Text)")
        elif key in _VERBATIM_FIELDS and not _occurs_as_words(value, normalized_text):
            grounded[key] = None
            logger.info("[Node 2 - Extractor] Feld verworfen: %s (nicht im Text)", key)
    return grounded


def extract_deadline_regex(text: str) -> str | None:
    """Sucht via Regex nach typischen Fristen im Text — als Fallback zum LLM."""
    for pattern in _DEADLINE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


def apply_deadline_regex(extracted: dict, raw_text: str, summary: str) -> tuple[dict, str]:
    """Hybrid Fallback: Regex-Postprocessor für Fristen. Kleine LLMs übersehen
    deterministische Datums-Patterns häufig — Regex ist hier zuverlässiger.
    Greift nur, wenn der LLM selbst keine deadline gefunden hat."""
    if extracted.get("deadline"):
        return extracted, summary

    regex_deadline = extract_deadline_regex(raw_text)
    if not regex_deadline:
        return extracted, summary

    extracted["deadline"] = regex_deadline
    extracted["deadline_mentioned"] = True
    if regex_deadline.lower() not in summary.lower():
        summary = f"{summary.rstrip('.')} (Frist: {regex_deadline})."
    logger.info("[Node 2 - Extractor] Regex-Fallback fand Frist: %s", regex_deadline)
    return extracted, summary
