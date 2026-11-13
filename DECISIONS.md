# Entscheidungen

Architektur- und Betriebsentscheidungen mit Begründung, neueste zuerst. Experimente zur Modellqualität
stehen in `eval/EXPERIMENTS.md`.

## 2026-11-13 — Tracing mit Langfuse: Callback zentral in `run_graph()`, Inhalte standardmäßig maskiert

**Entscheidung:** Der Langfuse-Callback-Handler wird zentral in `run_graph()` über `config={"callbacks": [...]}`
eingehängt, mit einem neuen Handler pro Lauf; Nodes und `invoke_json()` bleiben unverändert. Inhalte werden
standardmäßig maskiert, über den Export-Hook `mask_otel_spans` mit einer **Allowlist**: Nur bekannte sichere
Attribute (Modell, Tokens, Kosten, Zeiten, Typ, Environment, Release, Tags, `ticket_ref`, `langgraph_node`/`_step`,
`ls_*`) gehen unverändert raus, Input/Output werden durch `[redacted]` ersetzt, alles andere wird gelöscht.
`LANGFUSE_CAPTURE_CONTENT=true` sendet Inhalte, nur für synthetische Demo-Tickets.

**Begründung:**
- Laut Langfuse-Doku der Weg für LangGraph. LangChain reicht den Handler über den Kontext an jedes
  `llm.ainvoke()` weiter, auch durch `asyncio.gather`/`wait_for`; ein Test sichert das ab (3 Votes + 2 Aufrufe).
- Dieselbe DSGVO-Regel wie bei den Logs: kein Ticketinhalt nach außen.
- `mask_otel_spans` statt des älteren `mask`-Hooks: von Langfuse für neue Setups empfohlen und wirkt beim Export
  auf alle Span-Attribute, auch auf Trace-Metadaten.
- Allowlist statt Denylist: fail-closed. Bringt ein SDK-Update oder LangGraph ein neues Attribut mit Inhalt mit,
  geht es nicht unbemerkt nach außen. Die Liste stammt aus einem aufgezeichneten Graph-Lauf (langfuse 4.18.0).

**Konsequenzen:**
- Neue nützliche Attribute fehlen in Langfuse, bis sie in die Allowlist eingetragen sind. Fehlertexte
  (`status_message`) gehen nicht raus, die Stufe (`level`) schon.
- Der Hook muss synchron sein und darf nicht werfen, sonst verwirft Langfuse den ganzen Export-Batch.
- Langfuse kodiert Input/Output als JSON mit `ä` statt `ä`. Tests auf Inhaltslecks suchen deshalb nach
  einem ASCII-Teil des Wächter-Strings.

## 2026-11-13 — Trace-Metadaten: Release, Environment, Tags, Ticket-Referenz per HMAC

**Entscheidung:**
- `release` = Commit-SHA (`GIT_SHA`, wie `/ready`).
- Environment = **Stufe**, nicht Provider: lokal `local`, Container App `production`, über
  `LANGFUSE_TRACING_ENVIRONMENT`. Gelesen über ein Settings-Feld mit Default `local` und als `environment=` an
  den Client übergeben.
- Tags: Provider (`ollama`/`azure`) und Quelle des Tickets, die Quelle beschränkt auf `email`, `web_form`, `api`,
  `eval`; alles andere wird `other`.
- Ticket-ID als gekürzter **HMAC-SHA256** (16 Hex-Zeichen) im Metadaten-Schlüssel `ticket_ref`; Schlüssel
  `TICKET_ID_HMAC_KEY` im Key Vault. Fehlt der Schlüssel, wird keine Ticket-Referenz gesendet.

**Begründung:**
- Release: Vorher/Nachher-Vergleich pro Deployment.
- Environment: Lokale Azure-Tests vermischen sich sonst mit Cloud-Daten. Environments lassen sich in Langfuse nicht
  löschen oder umbenennen. Das SDK 4.18.0 liest die Variable nur aus `os.environ`; die `.env` kommt aber nur in
  den Settings an, und weder uvicorn noch die Skripte setzen die Variable. Ohne Settings-Feld landeten lokale
  Läufe im Environment `default`.
- Tags: wenige feste Werte, keine Personendaten. `ticket.source` ist ein freier String vom Absender (n8n reicht
  `body.source` durch); die feste Liste stellt sicher, dass über Tags kein beliebiger Text nach Langfuse geht.
- HMAC statt einfachem Hash: Ticket-IDs sind vorhersagbar (`EVAL-001` …), ein einfacher Hash wäre durch
  Durchprobieren umkehrbar. Trace-Metadaten werden vom Masking nicht erfasst, wenn man sie nicht ausdrücklich
  behandelt; `ticket_ref` steht deshalb bewusst auf der Allowlist.

**Konsequenzen:** Nachschlagen einer Ticket-ID über `scripts/trace-ref.ps1` (holt den Schlüssel aus dem Key Vault).
Ein neuer HMAC-Schlüssel macht alte Referenzen unvergleichbar.

## 2026-11-13 — Langfuse-SDK v4 (4.18.0) mit `langchain==0.3.30`

**Entscheidung:** `langfuse==4.18.0` plus `langchain==0.3.30`.

**Begründung:** Der v5-Upgrade-Guide verlangt `langchain-core>=1`, das Projekt steht auf 0.3. Der v4-Handler
importiert das Paket `langchain`. Mit dieser Kombination laufen alle Tests, `pip check` ist sauber.

**Konsequenzen:** Ein Wechsel auf Langfuse v5 hängt am Upgrade auf LangChain 1.x. Danach die Allowlist mit einem
neuen aufgezeichneten Lauf prüfen (v5 kodiert Metadaten anders).

## 2026-11-13 — Langfuse- und HMAC-Schlüssel im Key Vault

**Entscheidung:** Public **und** Secret Key von Langfuse sowie der HMAC-Schlüssel liegen im Key Vault
(`langfuse-public-key`, `langfuse-secret-key`, `ticket-id-hmac-key`) und kommen als `secretref` in die Container App.

**Begründung:** Gleiches Muster wie `api-key`. Das Langfuse-Paar wird gemeinsam rotiert.

**Konsequenzen:** Laufende Container übernehmen neue Key-Vault-Werte erst nach `az containerapp revision restart`.

## 2026-11-13 — Alarm auf `LLM_FAILURE`: Schwelle > 0, 15 min, E-Mail, mit Entwarnung

**Entscheidung:** Log-Suchalarm auf `LLM_FAILURE` im Log-Analytics-Arbeitsbereich: Schwelle > 0, Fenster und
Intervall 15 min, Severity 2, E-Mail über eine Action Group, Entwarnung an (auto-mitigate). Getestet in zwei
Schritten: erst die KQL-Abfrage im Arbeitsbereich (Tabellenname), dann ein echter Fehler über einen falschen
Deployment-Namen (`AZURE_FAST_DEPLOYMENT`), sofort zurückgesetzt, Warten auf Alarm- und Entwarnungs-Mail.

**Begründung:**
- Bei einem Komplettausfall erzeugt ein Ticket nur 2 Zeilen (Classifier, Extractor; der Risk Guard wird bei
  Fallback-Urgency `medium` übersprungen). Jede höhere Schwelle wäre bei Demo-Verkehr blind.
- Tabellen und Spalten heißen je nach Log-Ziel der Umgebung unterschiedlich (`ContainerAppConsoleLogs_CL` vs.
  `ContainerAppConsoleLogs`); eine Regel mit falscher Tabelle meldet nie etwas.
- Der echte Fehler prüft die ganze Kette inklusive Entwarnung.

**Konsequenzen:** `/ready` prüft das Modell nicht; ein vergessenes Zurücksetzen fällt nur durch den Alarm auf.

## 2026-11-13 — Kein `model=` an `AzureChatOpenAI`

**Entscheidung:** `AzureChatOpenAI` bekommt weiterhin nur den Deployment-Namen, kein `model=`, und es gibt keine
Einstellung `AZURE_MODEL_NAME`. Ursprünglich geplant (laut Langfuse-Doku nötig für Modellerkennung und Kosten),
nach der Prüfung verworfen.

**Begründung:** Geprüft mit langfuse 4.18.0 und langchain-openai 0.3.35, Request über gemockten HTTP-Transport:
- `model=` verändert den Request: Das Body-Feld `model` wechselt von `null` auf den Modellnamen. URL-Pfad
  (Deployment), `response_format` und `temperature` bleiben gleich.
- Der v4-Handler übernimmt den Modellnamen am Ende jeder Generation aus der Antwort (`model`-Feld, z. B.
  `gpt-4.1-mini-2025-04-14`), mit und ohne `model=`.
- Ohne `model=` bleibt der Request unverändert, kein Dev-Set-Lauf nötig, und keine Einstellung kann vom
  Deployment abweichen.

**Konsequenzen:**
- Bei gescheiterten Aufrufen (keine Antwort) steht in Langfuse `ticket-llm` als Modell; ohne Tokens kostenneutral.
- Beim ersten echten Trace prüfen, dass Langfuse `gpt-4.1-mini-2025-04-14` einem Preis zuordnet. Ein Test sichert ab,
  dass der Request kein `model` enthält.

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
