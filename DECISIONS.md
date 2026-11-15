# Entscheidungen

Architektur- und Betriebsentscheidungen mit Begründung, neueste zuerst. Experimente zur Modellqualität
stehen in `eval/EXPERIMENTS.md`.

## 2026-11-15 — Fehlermeldungen von LLM-Aufrufen erscheinen trotz Masking in Langfuse

**Entscheidung:** Die Fehlermeldung einer gescheiterten Generation (Status-Message) bleibt in Langfuse sichtbar. Der
Masking-Hook wird dafür nicht erweitert und nicht eingeschränkt.

**Befund (geprüft am 15.11., langfuse 4.18.0):**
- Das Attribut `langfuse.observation.status_message` steht **nicht** auf der Allowlist und wird gelöscht
  (`test_masking_allowlist`).
- Der Callback-Handler setzt dieselbe Meldung (`str(error)`) zusätzlich als OpenTelemetry-Span-Status
  (`set_status(Status(StatusCode.ERROR, description=...))`). Der Span-Status ist kein Attribut, `mask_otel_spans`
  sieht ihn nicht. Langfuse übernimmt ihn als Status-Message.
- Nachweis mit echten Daten: Die beiden Generations aus dem Alarm-Test vom 13.11. (20:03 UTC, Environment
  `production`) zeigen in Langfuse `Error code: 404 - {'error': {'type': 'invalid_request_error', 'code':
  'DeploymentNotFound', 'message': 'The API deployment for this resource does not exist. …'}}`, ohne Ticketinhalt.
- Die Aussage im Eintrag vom 13.11. („Fehlertexte (`status_message`) gehen nicht raus“) gilt damit nur für das
  Attribut, nicht für die sichtbare Meldung.

**Begründung:** Ohne die Meldung wäre ein Ausfall in Langfuse nur als `ERROR` ohne Ursache zu sehen. Bei
Azure-OpenAI-Fehlern wie `DeploymentNotFound`, 401/403 oder 429 besteht die Meldung aus HTTP-Status, Fehlercode und
festem Text von Azure; die Anfrage selbst wird nicht zurückgegeben.

**Content-Filter (geprüft, nichts geändert):**
- Prompt gefiltert: HTTP 400. Laut Azure-Doku („Content filtering for Microsoft Foundry Models (classic)“, Stand
  19.10.2026) enthält der Fehler nur `message`, `type`, `param` (fester Wert `"prompt"`), `code` (`content_filter`)
  und `status`, keinen Eingabetext. Die Doku-Beispiele nutzen die ältere Completions-Form; eine echte
  Chat-Completions-Antwort kann zusätzlich Kategorien und Schweregrade des Filters enthalten. **Nicht live
  getestet**, dafür müsste ein Ticket den Filter auslösen.
- Output gefiltert: keine Exception, sondern HTTP 200 mit `finish_reason: content_filter` und leerem Inhalt. Im
  Code wird daraus `LLMFailure.PARSE`. Das JSON-Parsing läuft außerhalb von LangChain, der Span bekommt dabei
  keinen Fehlertext.
- Timeouts (`asyncio.wait_for`) brechen den Aufruf ab, ohne dass die Meldung Inhalt trägt.

**Konsequenzen:**
- Ändert ein SDK-Update den Fehlerpfad oder kommt ein Anbieter hinzu, dessen Fehlermeldungen die Anfrage
  zurückgeben, landet dieser Text ungefiltert in Langfuse. Vor einem Wechsel eine Fehler-Generation in Langfuse
  ansehen.
- Unabhängig davon schreibt `invoke_json()` die Meldung auch ins Container-Log (`LLM-Fehler nach …: <exc>`).

## 2026-11-15 — Holdout-Lauf in der Cloud (E1–E4)

**Entscheidungen (Suleiman):**
- **E1 Ziel:** Der Holdout läuft gegen die Cloud-URL der Container App mit `--base-url` und `--verify-via-ready`,
  nicht gegen den lokalen Service im Azure-Modus.
- **E2 Vergleich:** Genau ein Cloud-Lauf (gpt-4.1-mini + Prompt-Stand e11) gegen den vorhandenen lokalen Wert
  `holdout-final`. Der Holdout wird einmal benutzt. Modell und Prompt werden zusammen gemessen, das steht beim
  Ergebnis.
- **E3 Vorregistrierung:** Messgrößen, Vergleichsbasis und erwarteter `/ready`-SHA stehen vor dem Lauf in
  `eval/EXPERIMENTS.md`, mit dem Satz „einmaliger Lauf, Ergebnis wird unverändert übernommen“, und sind vor dem
  Lauf committet (`27de201`). Vergleichsbasis 30 Tickets; ein Ausfall zählt als falsch (HOLD-014 lokal).
- **E4 Kosten:** Durchschnitt über die 30 Holdout-Traces aus Langfuse, beschriftet als Langfuse-Schätzung nach
  Listenpreis, gpt-4.1-mini, Stand 11/2026.

**Begründung:** Ein zweiter Lauf oder eine Auswahl unter mehreren Läufen würde den Holdout zum Dev-Set machen. Die
Cloud-URL misst den Stand, der tatsächlich ausgeliefert wird (Image aus ghcr.io, Managed Identity, Netzweg).

**Konsequenzen:**
- Ergebnis am 15.11.: Kategorie 26/30, Urgency 27/30, Risk 7/7 bei 7/7 Precision, Name 15/15, Latenz 2.2 / 2.9 s,
  0 `LLM_FAILURE`, 0.000813 USD pro Ticket (Details in `eval/EXPERIMENTS.md`).
- Der Lauf trennt nicht, welcher Anteil vom Modell und welcher von e11 kommt.
- Der Vorregistrierungs-Commit wird nicht deployt (Deploy nur von `main`). Der Lauf brauchte deshalb
  `--code-commit` mit dem deployten SHA.
- `scripts/run-eval.ps1` deckt diesen Fall nicht ab (fest `localhost`, Dev-Set, lokaler API-Key); die Schritte
  wurden von Hand ausgeführt, mit derselben `finally`-Rückstellung auf 10k TPM.
- Der alte Langfuse-Endpunkt `GET /api/public/traces` antwortet mit 410 (Abschaltung 16.11.2026 laut Langfuse).
  Kosten werden über `GET /api/public/v2/observations` je `traceId` summiert oder in der Langfuse-UI abgelesen.

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
- Am 13.11. in der Cloud gemessen: Ein Ticket bei ausgefallenem Modell erzeugt genau 2 `LLM_FAILURE`-Zeilen
  (Classifier, Extractor; Risk Guard übersprungen). Die Zeilen waren nach wenigen Minuten im Arbeitsbereich abfragbar.
- Am 13.11. in der Cloud nachgewiesen: Fehler über falschen Deployment-Namen um ca. 21:04 → Alarm Fired 21:08
  (Wert 2 > 0, Fenster 20:52–21:07), Action Group `ag-ticket-pipeline` ausgelöst. Ca. 4 Minuten vom Fehler bis zum Alarm.
  Resolved 21:54, Action Group auch bei der Entwarnung ausgelöst.
- Früherer Testlauf: 2 Tickets um 18:47/18:48 (Revision 0000007, je 2 `LLM_FAILURE`-Zeilen) → Alarm Fired 18:53,
  danach automatisch Resolved. Die Regel war um 18:44 angelegt und hat den Fehler mit ihrer ersten Auswertung erfasst.
  *(Korrigiert am 15.11. nach Prüfung im Portal; vorher stand hier, dieser Versuch habe nicht ausgelöst.)*

**Konsequenzen:** `/ready` prüft das Modell nicht; ein vergessenes Zurücksetzen fällt nur durch den Alarm auf.

**Bekannte Einschränkung:** Die Zustellung an Empfänger scheitert. E-Mail (Uni- und private Adresse) und
Azure-App-Push kommen nicht an; die von Azure verlangte Bestätigungsmail für E-Mail-Empfänger (Einmalcode,
30-Minuten-Frist) kam nie an, und „Test action group“ bricht für beide Kanäle mit „There was a problem completing
this test“ ab. Vermutete Ursache: Einschränkung im Studenten-Tenant. Regel und Action Group funktionieren
nachweislich; offen ist nur die Zustellung.

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
- Am 13.11. lokal geprüft: Langfuse ordnet `gpt-4.1-mini-2025-04-14` einem Preis zu (≈ 0,00082 $ pro Ticket,
  Extractor teuerster Schritt). Ein Test sichert ab, dass der Request kein `model` enthält.

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
