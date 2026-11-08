# Entscheidungen

Architektur- und Betriebsentscheidungen mit Begründung, neueste zuerst. Experimente zur Modellqualität
stehen in `eval/EXPERIMENTS.md`.

## 2026-11-08 — Container Apps im Standardmodus (Workload Profiles) statt Express

**Entscheidung:** Container-Apps-Umgebung ausdrücklich mit `--environment-mode WorkloadProfiles`, App im kostenlosen
Profil „Consumption“, systemzugewiesene Managed Identity, API-Key als Key-Vault-Referenz.

**Begründung:** Ohne ausdrücklichen Modus legte die CLI eine Express-Umgebung an. Express unterstützt keine
Key-Vault-Referenzen und keine systemzugewiesene Identität (nur benutzerzugewiesene) und kennt nur eine Revision.
Damit hätte der API-Key als Klartext-Secret in die App kopiert werden müssen. Abrechnung und Skalierung auf null
sind in beiden Modi gleich.

**Konsequenz:** Den Modus bei jeder Neuanlage explizit setzen und mit `az containerapp env show --query
properties.environmentMode` prüfen; Standardwerte der CLI können sich mit der Version ändern.

## 2026-11-08 — Nur der Webhook-Workflow spricht mit der Cloud

**Entscheidung:** In n8n zeigt nur der Webhook-Workflow (synthetische Testtickets) auf die Container App. Der
IMAP-Workflow, der echte E-Mails abruft, bleibt beim lokalen Service mit Ollama.

**Begründung:** Das Cloud-Deployment ist GlobalStandard (Verarbeitung ggf. außerhalb der EU, siehe unten); echte
Personendaten gehören dort nicht hin. Der API-Key liegt in n8n als verschlüsseltes Credential, beschränkt auf den
Hostnamen der App.

## 2026-11-07 — Cloud-Modell: gpt-4.1-mini als GlobalStandard in France Central

**Entscheidung:** Azure-OpenAI-Deployment `ticket-llm` mit gpt-4.1-mini (2025-04-14), Typ GlobalStandard,
Kapazität 10 000 Tokens pro Minute, in France Central. In die Cloud gehen ausschließlich synthetische Tickets.

**Begründung:**
- Das Abo (Azure for Students) ist per Azure Policy auf fünf Regionen beschränkt. France Central ist davon die
  einzige EU-Region mit Azure OpenAI.
- Für Chat-Modelle hat das Abo nur GlobalStandard-Kontingent. Bei GlobalStandard können Anfragen in jeder
  Azure-Region weltweit verarbeitet werden.
- gpt-4.1-mini ist kein Reasoning-Modell: `temperature=0` funktioniert wie bei den lokalen Läufen, die
  Ergebnisse bleiben vergleichbar. gpt-5-mini hätte mehr Kontingent, ist aber ein Reasoning-Modell; die
  erlauben `temperature` nicht frei (vor einem Wechsel prüfen).

**Konsequenzen:**
- Für echte Kundendaten wäre ein Standard- oder DataZoneStandard-Deployment Pflicht (Verarbeitung in der EU).
- gpt-4.1-mini wird am 14.04.2027 abgeschaltet. Der Code ruft den Deployment-Namen auf, ein Modellwechsel ist
  ein neues Deployment ohne Codeänderung.
- Die niedrige Kapazität ist die harte Kostengrenze; ein Budget-Alarm ist beim Studentenabo nicht möglich.

## 2026-11-07 — Wiederholungen bei 429/5xx über das SDK, nicht über einen eigenen Retry-Wrapper

**Entscheidung:** `AzureChatOpenAI(max_retries=3)` statt tenacity.

**Begründung:** Das OpenAI-SDK wiederholt Rate-Limits (429) und Serverfehler (5xx) bereits mit
exponentiellem Backoff. Ein eigener Wrapper außerhalb von `invoke_json()` würde nie greifen, weil dort jeder
Fehler abgefangen und als `LLMFailure` zurückgegeben wird. Der Timeout pro Versuch (15 s) und der
Gesamt-Timeout (`LLM_TIMEOUT`, 60 s) sind getrennt einstellbar.

Das andere Problem — ein Ticket geht verloren, wenn `/analyze` unter Last mit 503 antwortet — liegt nicht beim
LLM, sondern beim Load-Shedding des Service. Das löst „Retry On Fail“ im n8n-HTTP-Knoten (3 Versuche, 5 s
Abstand, passend zu `Retry-After: 5`).

## 2026-11-07 — LLM-Ausfälle als eigenes Log-Signal

**Entscheidung:** Jeder gescheiterte LLM-Aufruf schreibt eine Zeile `LLM_FAILURE node=… reason=…`, ohne
Ticketinhalt.

**Begründung:** Fällt das Modell aus, greifen die Fallbacks der Nodes und `/analyze` antwortet weiter mit 200.
Ein Alarm auf fehlgeschlagene Requests würde einen kompletten Modellausfall nie melden. Die Logzeile ist das
Signal für einen eigenen Alarm (Application Insights).
