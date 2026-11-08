# Azure-Setup

Alle Befehle, mit denen die Azure-Umgebung angelegt wurde, in der Reihenfolge der Ausführung.
Unter jedem Befehl steht der Weg im Portal (portal.azure.com bzw. Foundry-Portal ai.azure.com); Menünamen können leicht abweichen.
Shell: Windows `cmd` (bei PowerShell `%VAR%` durch `$env:VAR` ersetzen).

## Voraussetzungen

- Abo „Azure for Students“, eigene Rolle **Owner** (Portal → Subscriptions → Access control → View my access)
- Azure CLI: `winget install --exact --id Microsoft.AzureCLI`, dann `az login`
- Erweiterung für Container Apps: `az extension add --name containerapp --upgrade`

## Ressourcenanbieter registrieren

Ein neues Abo muss jeden Dienst einmal registrieren, sonst scheitert das Anlegen mit `MissingSubscriptionRegistration`.

```cmd
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.CognitiveServices --wait
```

**Im Portal:** Subscriptions → Azure for Students → Resource providers → Anbieter suchen → Register

## Region

Das Abo ist per Azure Policy („Allowed resource deployment regions“) auf fünf Regionen beschränkt:
denmarkeast, belgiumcentral, francecentral, switzerlandnorth, austriaeast.

```cmd
az policy assignment list --query "[].{Name:displayName, Parameter:parameters}" --output json
```

**Im Portal:** Policy → Assignments → „Allowed resource deployment regions“ → Parameters

**Gewählt: `francecentral`.** Liegt in der EU und bietet Container Apps und Azure OpenAI. Switzerland North
liegt nicht in der EU; Denmark East, Belgium Central und Austria East bieten laut Kontingent-Abfrage vom 07.11.2026 kein Azure OpenAI an.

## Ressourcengruppe

Alles für dieses Projekt liegt in einer Gruppe. Die Deploy-Pipeline bekommt Rechte nur auf diese Gruppe,
und aufräumen ist ein Befehl: `az group delete --name rg-ticket-pipeline`.

```cmd
az group create --name rg-ticket-pipeline --location francecentral --tags project=ticket-pipeline env=demo
```

**Im Portal:** Resource groups → + Create → Name, Region → Reiter Tags → Review + create

## Azure OpenAI

### Kontingent prüfen

Kontingent wird pro Abo, Region, Modell und Deployment-Typ vergeben (in Tausend Tokens pro Minute).

```cmd
az cognitiveservices usage list --location francecentral --query "[?starts_with(name.value, 'OpenAI') && limit > `0`].{Name:name.value, Limit:limit}" --output table
```

**Im Portal:** Foundry-Portal → Quota (Limits pro Region, Modell und Deployment-Typ); verfügbare Modelle im Model catalog

Ergebnis: Für Chat-Modelle gibt es nur **GlobalStandard** (gpt-4.1-mini: 200, gpt-5-mini: 500, o4-mini: 100),
kein Standard oder DataZoneStandard. Entscheidung und Begründung: siehe `DECISIONS.md`.

### Ressource

```cmd
az cognitiveservices account create --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline --location francecentral --kind OpenAI --sku S0 --custom-domain oai-ticketpipe-sa --tags project=ticket-pipeline env=demo
```

**Im Portal:** Azure OpenAI → + Create → Ressourcengruppe, Region, Name, Tarif Standard S0, Tags → Review + create (Subdomain = Name, setzt das Portal automatisch)

`--custom-domain` ist Pflicht für die Anmeldung über Entra ID (Managed Identity, `az login`).

### API-Schlüssel abschalten

Zugriff nur noch über Identitäten mit Rolle, nicht über Schlüssel.

```cmd
az resource update --resource-group rg-ticket-pipeline --name oai-ticketpipe-sa --resource-type Microsoft.CognitiveServices/accounts --set properties.disableLocalAuth=true
```

**Im Portal:** kein Schalter dafür — nur per CLI, ARM/Bicep oder Azure Policy.

### Deployment

```cmd
az cognitiveservices account deployment create --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline --deployment-name ticket-llm --model-name gpt-4.1-mini --model-version 2025-04-14 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10
```

**Im Portal:** Foundry-Portal → Ressource → Deployments → + Deploy model → gpt-4.1-mini → Customize: Name, Typ Global Standard, Version, Kapazität. Kapazität ändern: Deployment → Edit → Tokens per Minute.

- Deployment-Name `ticket-llm` = Rolle in der Pipeline, nicht Modellname. Modellwechsel = neues Deployment
  unter demselben Namen, keine Codeänderung. gpt-4.1-mini wird am **14.04.2027** abgeschaltet.
- `--sku-capacity 10` = 10 000 Tokens pro Minute: harte Kostengrenze (ein Budget-Alarm ist beim
  Studentenabo nicht möglich, Cost Management unterstützt das Angebot nicht).

### Rolle für die eigene Identität

Owner gilt nur für die Verwaltung (Control Plane). Zum Aufrufen des Modells (Data Plane) braucht jede
Identität die Rolle „Cognitive Services OpenAI User“, auch die eigene.

```cmd
for /f "delims=" %i in ('az ad signed-in-user show --query id --output tsv') do set ME=%i
for /f "delims=" %i in ('az cognitiveservices account show --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline --query id --output tsv') do set SCOPE=%i
az role assignment create --role "Cognitive Services OpenAI User" --assignee-object-id %ME% --assignee-principal-type User --scope %SCOPE%
```

**Im Portal:** OpenAI-Ressource → Access control (IAM) → + Add → Add role assignment → Rolle wählen → Members → + Select members → Review + assign. Prüfen im Reiter Role assignments.

### Smoke-Test

```cmd
python scripts\azure_smoke_test.py
```

**Im Portal:** Foundry-Portal → Chat-Playground → Deployment `ticket-llm` wählen (testet das Modell, aber nicht die Anmeldung aus deinem Code).

Braucht eine venv mit `openai` und `azure-identity`. Prüft Anmeldung ohne Schlüssel, `temperature=0` und JSON-Modus.

## Service lokal im Azure-Modus starten

Im lokalen Docker-Container gibt es weder den Login der Azure CLI noch eine Managed Identity. Den
Azure-Modus deshalb mit uvicorn direkt auf dem Rechner testen (PowerShell, aus `fastapi-service/`):

```powershell
venv\Scripts\pip install -r requirements.txt
$env:LLM_PROVIDER = "azure"
$env:AZURE_OPENAI_ENDPOINT = "https://oai-ticketpipe-sa.openai.azure.com/"
$env:API_KEY = "lokal-test"
$env:MAX_CONCURRENT_ANALYSES = "4"
venv\Scripts\uvicorn app.main:app --port 8000
```

In einem zweiten Terminal:

```powershell
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/analyze -Method Post -ContentType "application/json" `
  -Headers @{ "X-API-Key" = "lokal-test" } `
  -Body '{"ticket_id": "T-1", "raw_text": "Seit dem Update startet die App nicht mehr, ich kann nicht arbeiten."}'
```

## Eval gegen das Azure-Modell (lokal)

1. Kapazität vorübergehend erhöhen, sonst bremst das Rate-Limit die Eval aus (danach wieder `--sku-capacity 10`):

   ```powershell
   az cognitiveservices account deployment create --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline --deployment-name ticket-llm --model-name gpt-4.1-mini --model-version 2025-04-14 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 100
   ```

   **Im Portal:** Foundry-Portal → Deployments → `ticket-llm` → Edit → Tokens per Minute

2. Service im Azure-Modus starten (Abschnitt oben) und vorher den Commit setzen: `$env:GIT_SHA = (git rev-parse HEAD)`

3. Eval aus dem Repo-Root:

   ```powershell
   $env:EVAL_API_KEY = "lokal-test"
   fastapi-service\venv\Scripts\python eval\run_eval.py --run-name <name> --base-url http://localhost:8000 --verify-via-ready --model gpt-4.1-mini --hardware "Azure OpenAI gpt-4.1-mini GlobalStandard (France Central)"
   python eval\report.py --run <name>
   python eval\compare.py
   ```

4. Im Service-Log dürfen keine `LLM_FAILURE`-Zeilen stehen, sonst hat das Rate-Limit Ergebnisse verfälscht.
