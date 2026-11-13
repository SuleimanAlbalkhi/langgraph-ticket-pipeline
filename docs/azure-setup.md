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
az provider register --namespace Microsoft.KeyVault --wait
az provider register --namespace Microsoft.ManagedIdentity --wait
az provider register --namespace Microsoft.Insights --wait
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
$body = '{"ticket_id": "T-1", "raw_text": "Seit dem Update startet die App nicht mehr, ich kann nicht arbeiten."}'
Invoke-RestMethod http://localhost:8000/analyze -Method Post -ContentType "application/json; charset=utf-8" `
  -Headers @{ "X-API-Key" = "lokal-test" } `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Den Body immer als UTF-8-Bytes schicken: Windows PowerShell 5.1 kodiert einen String-Body nicht als UTF-8, bei
Umlauten oder ß antwortet FastAPI dann mit „There was an error parsing the body“. Das gilt für alle
`Invoke-RestMethod`-Beispiele in dieser Datei.

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

## Container Apps (Block B)

### Image nach ghcr.io

Tag = Commit-SHA, `GIT_SHA` als Build-Arg (meldet `/ready`). Login mit einem Personal Access Token (classic,
nur `write:packages`, kurze Laufzeit); danach `docker logout ghcr.io`. Ab Block C pusht die GitHub Action ohne PAT.

```powershell
$token = Read-Host -AsSecureString "GHCR-Token"
[System.Net.NetworkCredential]::new("", $token).Password | docker login ghcr.io -u SuleimanAlbalkhi --password-stdin
$sha = git rev-parse HEAD
$image = "ghcr.io/suleimanalbalkhi/ticket-pipeline-api:$sha"
docker build --build-arg GIT_SHA=$sha --label org.opencontainers.image.source=https://github.com/SuleimanAlbalkhi/langgraph-ticket-pipeline -t $image fastapi-service
docker push $image
```

**Auf GitHub:** Packages → `ticket-pipeline-api` → Package settings → Change visibility → Public (sonst kann die App nicht ziehen).

### Umgebung — Modus ausdrücklich setzen

Ohne `--environment-mode` legte die CLI (11/2026) eine **Express**-Umgebung an, auch mit `--enable-workload-profiles`.
Express unterstützt keine Key-Vault-Referenzen und keine systemzugewiesene Identität. Deshalb explizit:

```powershell
$ws = "workspace-rgticketpipelineLE9z"
$wsId = az monitor log-analytics workspace show --resource-group rg-ticket-pipeline --workspace-name $ws --query customerId --output tsv
$wsKey = az monitor log-analytics workspace get-shared-keys --resource-group rg-ticket-pipeline --workspace-name $ws --query primarySharedKey --output tsv
az containerapp env create --name cae-ticket-pipeline --resource-group rg-ticket-pipeline --location francecentral --environment-mode WorkloadProfiles --logs-workspace-id $wsId --logs-workspace-key $wsKey
az containerapp env show --name cae-ticket-pipeline --resource-group rg-ticket-pipeline --query properties.environmentMode
```

**Im Portal:** Container Apps Environments → + Create → Environment type „Workload profiles“ (nicht Express)

### Key Vault mit API-Key

```powershell
az keyvault create --name kv-ticketpipe-sa --resource-group rg-ticket-pipeline --location francecentral --enable-rbac-authorization true
$me = az ad signed-in-user show --query id --output tsv
$kv = az keyvault show --name kv-ticketpipe-sa --query id --output tsv
az role assignment create --role "Key Vault Secrets Officer" --assignee-object-id $me --assignee-principal-type User --scope $kv
$apiKey = python -c "import secrets; print(secrets.token_urlsafe(32))"
az keyvault secret set --vault-name kv-ticketpipe-sa --name api-key --value $apiKey --output none
```

**Im Portal:** Key vaults → + Create (Access configuration: Azure RBAC); Rolle unter Access control (IAM); Secret unter Secrets → + Generate/Import.
Gelöschte Key Vaults bleiben 90 Tage reserviert (Soft-Delete) → beim Aufräumen zusätzlich `az keyvault purge`.

### Container App — erst intern, dann öffentlich

```powershell
az containerapp create --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --environment cae-ticket-pipeline `
  --workload-profile-name Consumption `
  --image ghcr.io/suleimanalbalkhi/ticket-pipeline-api:<commit-sha> `
  --target-port 8000 --ingress internal --min-replicas 0 --max-replicas 1 --cpu 0.5 --memory 1.0Gi `
  --system-assigned `
  --env-vars LLM_PROVIDER=azure AZURE_OPENAI_ENDPOINT=https://oai-ticketpipe-sa.openai.azure.com/ MAX_CONCURRENT_ANALYSES=4
```

Intern, bis der API-Key-Schutz steht — sonst wäre `/analyze` kurz ungeschützt erreichbar.

### Rollen der App-Identität

```powershell
$principal = az containerapp show --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --query identity.principalId --output tsv
$oai = az cognitiveservices account show --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline --query id --output tsv
$kv = az keyvault show --name kv-ticketpipe-sa --query id --output tsv
az role assignment create --role "Cognitive Services OpenAI User" --assignee-object-id $principal --assignee-principal-type ServicePrincipal --scope $oai
az role assignment create --role "Key Vault Secrets User" --assignee-object-id $principal --assignee-principal-type ServicePrincipal --scope $kv
```

**Im Portal:** Ressource → Access control (IAM) → Add role assignment → Members: Managed identity → Container App

### API-Key als Key-Vault-Referenz

URL ohne Version → ein neuer Key im Key Vault wird automatisch übernommen (Rotation).

```powershell
az containerapp secret set --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --secrets "api-key=keyvaultref:https://kv-ticketpipe-sa.vault.azure.net/secrets/api-key,identityref:system"
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --set-env-vars API_KEY=secretref:api-key
```

### Probes (Liveness `/health`, Readiness `/ready`)

Die CLI hat dafür keine Optionen; Konfiguration holen, ergänzen, zurückspielen:

```powershell
$f = "$env:TEMP\ca-ticket-pipeline.json"
$app = az containerapp show --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --output json | ConvertFrom-Json
$app.properties.template.containers[0] | Add-Member -Force -NotePropertyName probes -NotePropertyValue @(
  @{ type = "Liveness";  httpGet = @{ path = "/health"; port = 8000 } },
  @{ type = "Readiness"; httpGet = @{ path = "/ready";  port = 8000 } }
)
[IO.File]::WriteAllText($f, ($app | ConvertTo-Json -Depth 50))
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --yaml $f
```

**Im Portal:** Container App → Revisions and replicas → Create new revision → Container → Health probes

### Öffentlich schalten und Smoke-Test

```powershell
az containerapp ingress enable --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --type external --target-port 8000 --transport auto
$url = "https://" + (az containerapp show --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --query properties.configuration.ingress.fqdn --output tsv)
Invoke-RestMethod "$url/ready"
$key = az keyvault secret show --vault-name kv-ticketpipe-sa --name api-key --query value --output tsv
$body = '{"ticket_id": "T-1", "raw_text": "Seit dem Update startet die App nicht mehr, ich kann nicht arbeiten."}'
Invoke-RestMethod "$url/analyze" -Method Post -ContentType "application/json; charset=utf-8" -Headers @{ "X-API-Key" = $key } -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

### n8n an die Cloud anschließen

Nur der **Webhook-Workflow** (synthetische Testtickets) zeigt auf die Cloud. Der IMAP-Workflow mit echten E-Mails
bleibt beim lokalen Service (`http://fastapi-service:8000/analyze`).

- Credential „Header Auth“ `Ticket-Pipeline Cloud`: Header `X-API-Key`, Wert aus dem Key Vault, Allowed Domains = Hostname der App
- HTTP-Knoten: URL `https://<fqdn>/analyze`, Authentication Header Auth, Timeout 60000 ms (Kaltstart), Retry On Fail 3× / 5 s
- n8n ohne lokalen FastAPI-Container starten: `docker compose up -d --no-deps n8n`

## CI/CD (Block C)

### Deploy-Identität mit OIDC

GitHub meldet sich ohne Passwort an: Azure vertraut einem kurzlebigen GitHub-Token, wenn es aus diesem Repo und
von `main` kommt (Federated Credential). Contributor nur auf der Ressourcengruppe — kann keine Rollen vergeben.

```powershell
az identity create --name id-github-deploy --resource-group rg-ticket-pipeline --location francecentral
$principalId = az identity show --name id-github-deploy --resource-group rg-ticket-pipeline --query principalId --output tsv
az identity federated-credential create --name github-main --identity-name id-github-deploy --resource-group rg-ticket-pipeline `
  --issuer https://token.actions.githubusercontent.com `
  --subject repo:SuleimanAlbalkhi/langgraph-ticket-pipeline:ref:refs/heads/main `
  --audiences api://AzureADTokenExchange
$rg = az group show --name rg-ticket-pipeline --query id --output tsv
az role assignment create --role Contributor --assignee-object-id $principalId --assignee-principal-type ServicePrincipal --scope $rg
```

**Im Portal:** Managed Identities → + Create; dann Federated credentials → „GitHub Actions deploying Azure resources“

### GitHub

- Repository secrets (Settings → Secrets and variables → Actions → **Secrets**, nicht Variables):
  `AZURE_CLIENT_ID` (clientId der Identität), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- Paket `ticket-pipeline-api` → Package settings → Manage Actions access → Repo mit Rolle **Write**
  (sonst `permission_denied: write_package`, weil das Paket mit einem persönlichen Token angelegt wurde)

### Ablauf (`.github/workflows/ci.yml`, Job `deploy`)

Nur nach grünem Test-Job und nur bei Push auf `main`: Image bauen und mit `GITHUB_TOKEN` nach ghcr.io pushen
(Tag = Commit-SHA) → `azure/login` per OIDC → `az containerapp update --image` → Smoke-Test fragt `/ready` ab,
bis der neue Commit gemeldet wird (max. 5 Minuten).

### Rollback

```powershell
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --image ghcr.io/suleimanalbalkhi/ticket-pipeline-api:<vorheriger-sha>
Invoke-RestMethod "$url/ready"   # git_sha zeigt, welcher Stand live ist
```

Gilt bis zum nächsten Push auf `main`; den Fehler danach auf `main` beheben (z. B. `git revert`).

## Observability (Block D)

Jede Ticket-Analyse wird ein Trace in Langfuse Cloud (EU): ein Span pro Node, eine Generation pro LLM-Aufruf mit
Latenz, Modell, Tokens und Kosten. Ticketinhalte werden vor dem Export maskiert (Allowlist in
`app/observability.py`). Ein Log-Suchalarm meldet Modellausfälle (`LLM_FAILURE`) per E-Mail. Entscheidungen und
Begründungen: siehe `DECISIONS.md`.

### 1. Langfuse-Projekt

Konto in der Region **EU** (Plan Hobby), Projekt `ticket-pipeline`, dann API Keys anlegen. Den Secret Key zeigt
Langfuse nur einmal an.

**In Langfuse:** cloud.langfuse.com → Sign up (Region EU) → New project `ticket-pipeline` → Settings → API Keys → Create new API keys

### 2. Lokal testen

Werte nach `fastapi-service\.env` (gitignored; der Service liest `.env` aus seinem Arbeitsverzeichnis):

```powershell
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
TICKET_ID_HMAC_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
```

`LANGFUSE_TRACING_ENVIRONMENT` lokal nicht setzen, der Default ist `local`. Dann den Service starten
(`.\scripts\start-azure-service.ps1` oder uvicorn) und ein Ticket schicken (siehe „Service lokal im Azure-Modus starten“).
Die Startzeile im Log muss `Tracing: an (…, Environment local, Inhalte maskiert, HMAC-Schlüssel vorhanden)` zeigen.

**In Langfuse:** Projekt → Tracing → Traces → Environment `local` → Trace `ticket-analysis` öffnen. Prüfen:
- Spans `classifier`, `extractor`, `risk_guard`, darunter Generations mit Modell, Tokens und Kosten
- Input/Output überall `[redacted]`, **nirgends Tickettext**
- Tags `azure`/`ollama` und Quelle, Metadaten `ticket_ref`, Release = Commit-SHA

Für denselben Test lokal den HMAC-Schlüssel nehmen, der später auch im Key Vault liegt, oder bewusst einen eigenen.
Die Ticket-Referenz ist nur mit demselben Schlüssel vergleichbar.

### 3. Key Vault und Container App

Drei Secrets: Langfuse Public Key, Langfuse Secret Key, HMAC-Schlüssel. Werte über `Read-Host`, damit sie nicht in der
Shell-Historie landen. Die App-Identität hat schon „Key Vault Secrets User“ (Block B).

```powershell
$v = Read-Host -AsSecureString "Langfuse Public Key"
az keyvault secret set --vault-name kv-ticketpipe-sa --name langfuse-public-key --value ([System.Net.NetworkCredential]::new("", $v).Password) --output none
$v = Read-Host -AsSecureString "Langfuse Secret Key"
az keyvault secret set --vault-name kv-ticketpipe-sa --name langfuse-secret-key --value ([System.Net.NetworkCredential]::new("", $v).Password) --output none
$v = python -c "import secrets; print(secrets.token_hex(32))"
az keyvault secret set --vault-name kv-ticketpipe-sa --name ticket-id-hmac-key --value $v --output none
Remove-Variable v

$kvUrl = "https://kv-ticketpipe-sa.vault.azure.net/secrets"
az containerapp secret set --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --secrets `
  "langfuse-public-key=keyvaultref:$kvUrl/langfuse-public-key,identityref:system" `
  "langfuse-secret-key=keyvaultref:$kvUrl/langfuse-secret-key,identityref:system" `
  "ticket-id-hmac-key=keyvaultref:$kvUrl/ticket-id-hmac-key,identityref:system"
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --set-env-vars `
  LANGFUSE_PUBLIC_KEY=secretref:langfuse-public-key `
  LANGFUSE_SECRET_KEY=secretref:langfuse-secret-key `
  TICKET_ID_HMAC_KEY=secretref:ticket-id-hmac-key `
  LANGFUSE_TRACING_ENVIRONMENT=production
```

**Im Portal:** Key vaults → `kv-ticketpipe-sa` → Secrets → + Generate/Import; Container App → Settings → Secrets → + Add
(Key Vault reference, Managed identity: System assigned); Container App → Containers → Environment variables → Reference a secret

Umgebungsvariablen bleiben bei `az containerapp update --image` im Deploy-Job erhalten, die Pipeline muss nichts
davon kennen. Prüfen: Log der neuen Revision zeigt `Tracing: an (…, Environment production, Inhalte maskiert,
HMAC-Schlüssel vorhanden)`; in Langfuse erscheint nach einem Ticket ein Trace im Environment `production`.

Ticket-Referenz zu einer Ticket-ID nachschlagen (gibt nur den gekürzten HMAC aus, nie den Schlüssel):

```powershell
.\scripts\trace-ref.ps1 -TicketId T-1
```

**In Langfuse:** Traces → Suche bzw. Filter Metadata `ticket_ref` = Ausgabe des Skripts

### 4. Rotation des Langfuse-Schlüsselpaars

Das Paar wird gemeinsam rotiert. Laufende Container übernehmen neue Key-Vault-Werte erst nach einem Neustart.

1. In Langfuse ein neues Schlüsselpaar anlegen (das alte bleibt vorerst gültig).
2. Beide Secrets im Key Vault neu setzen (Befehle aus Abschnitt 3, nur die beiden `langfuse-*`-Zeilen).
3. Neustart:

   ```powershell
   $rev = az containerapp show --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --query properties.latestRevisionName --output tsv
   az containerapp revision restart --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --revision $rev
   ```

4. Ein Ticket schicken, Trace in Langfuse prüfen, dann das alte Paar in Langfuse löschen.

**Im Portal:** Container App → Revisions and replicas → aktive Revision → Restart

Den HMAC-Schlüssel nicht routinemäßig rotieren: Danach passen alte Ticket-Referenzen nicht mehr zu neuen.

### 5. Alarm-Test Schritt A: Abfrage prüfen

Tabellen und Spalten heißen je nach Log-Ziel der Umgebung unterschiedlich. Erst die Abfrage im Arbeitsbereich
ausführen, dann die Regel mit **genau der Variante** anlegen, die funktioniert. Die Abfrage beginnt mit der Tabelle.

Standardvariante:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "ca-ticket-pipeline" and Log_s has "LLM_FAILURE"
| project TimeGenerated, Log_s
```

Meldet sie „Tabelle nicht gefunden“, die Variante ohne Suffix:

```kusto
ContainerAppConsoleLogs
| where ContainerAppName == "ca-ticket-pipeline" and Log has "LLM_FAILURE"
| project TimeGenerated, Log
```

```powershell
$ws = "workspace-rgticketpipelineLE9z"
$wsId = az monitor log-analytics workspace show --resource-group rg-ticket-pipeline --workspace-name $ws --query customerId --output tsv
az monitor log-analytics query --workspace $wsId --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'ca-ticket-pipeline' and Log_s has 'LLM_FAILURE' | project TimeGenerated, Log_s" --timespan P7D
```

**Im Portal:** Log Analytics workspaces → `workspace-rgticketpipelineLE9z` → Logs → Abfrage einfügen → Run

Ohne bisherige Ausfälle ist ein leeres Ergebnis richtig; entscheidend ist, dass die Abfrage ohne Fehler läuft.

### 6. Alarm anlegen

Action Group mit E-Mail, dann die Regel: Schwelle > 0, Fenster und Intervall 15 min, Severity 2, Entwarnung an.
Bei einem Komplettausfall erzeugt ein Ticket nur 2 `LLM_FAILURE`-Zeilen; jede höhere Schwelle wäre bei Demo-Verkehr blind.

```powershell
az monitor action-group create --name ag-ticket-pipeline --resource-group rg-ticket-pipeline `
  --short-name ticketalarm --action email betreiber <eigene-mail>
$ag = az monitor action-group show --name ag-ticket-pipeline --resource-group rg-ticket-pipeline --query id --output tsv
$wsRes = az monitor log-analytics workspace show --resource-group rg-ticket-pipeline --workspace-name $ws --query id --output tsv

az monitor scheduled-query create --name alert-llm-failure --resource-group rg-ticket-pipeline `
  --scopes $wsRes `
  --condition "count 'Placeholder_1' > 0" `
  --condition-query Placeholder_1="ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'ca-ticket-pipeline' and Log_s has 'LLM_FAILURE'" `
  --evaluation-frequency 15m --window-size 15m --severity 2 `
  --action-groups $ag --auto-mitigate true `
  --description "Modellausfall: LLM_FAILURE im Log von ca-ticket-pipeline"
```

`--condition-query` durch die Variante aus Schritt A ersetzen, falls dort die Tabelle ohne Suffix funktioniert hat.
`az monitor scheduled-query` ist eine CLI-Erweiterung und wird beim ersten Aufruf automatisch installiert.
Die Action Group schickt sofort eine Bestätigungs-Mail („added to action group“).

**Im Portal:** Monitor → Alerts → Action groups → + Create (Notifications: Email); Monitor → Alerts → + Create → Alert rule →
Scope: Log-Analytics-Arbeitsbereich → Condition: Custom log search (Abfrage, Measurement Count, Threshold > 0,
Frequency 15 min, Lookback 15 min) → Actions: Action Group → Details: Severity 2, „Automatically resolve alerts“ an

### 7. Alarm-Test Schritt B: echter Fehler

Prüft die ganze Kette inklusive Entwarnung. Genau diese Reihenfolge:

```powershell
$url = "https://" + (az containerapp show --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --query properties.configuration.ingress.fqdn --output tsv)
$key = az keyvault secret show --vault-name kv-ticketpipe-sa --name api-key --query value --output tsv
$body = '{"ticket_id": "ALARM-TEST-1", "raw_text": "Seit dem Update startet die App nicht mehr, ich kann nicht arbeiten."}'

# (1) Deployment-Namen auf einen nicht existierenden Wert setzen
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --set-env-vars AZURE_FAST_DEPLOYMENT=gibt-es-nicht
# (2) Ein Ticket schicken (Antwort 200 mit Fallback-Werten; im Log 2 LLM_FAILURE-Zeilen)
Invoke-RestMethod "$url/analyze" -Method Post -ContentType "application/json; charset=utf-8" -Headers @{ "X-API-Key" = $key } -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
# (3) SOFORT zurücksetzen: Variable entfernen (existierte vorher nicht; ohne sie nimmt der Code ticket-llm)
az containerapp update --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --remove-env-vars AZURE_FAST_DEPLOYMENT
# (3b) Warten, bis die neueste Revision 100 % Verkehr hat
az containerapp revision list --name ca-ticket-pipeline --resource-group rg-ticket-pipeline --query "[].{name:name, active:properties.active, traffic:properties.trafficWeight, created:properties.createdTime}" --output table
# (4) Prüfen, dass alles wieder läuft: /ready und ein zweites Ticket mit echter Kategorie statt Fallback
Invoke-RestMethod "$url/ready"
Invoke-RestMethod "$url/analyze" -Method Post -ContentType "application/json; charset=utf-8" -Headers @{ "X-API-Key" = $key } -Body ([System.Text.Encoding]::UTF8.GetBytes($body.Replace("ALARM-TEST-1", "ALARM-TEST-2")))
```

`az containerapp update` kehrt zurück, bevor die neue Revision Verkehr bekommt (gemessen: ca. 1 Minute). Vor dem
Kontrollticket mit `az containerapp revision list` prüfen, dass die neueste Revision 100 % Verkehr hat, sonst
antwortet noch die alte Revision mit dem falschen Deployment.

5. Auf die Alarm-Mail warten: bis ca. 20 min (Fenster plus Log-Latenz).
6. Auf die Entwarnung warten: kommt, sobald ein 15-min-Fenster ohne `LLM_FAILURE` ausgewertet wurde.

**Wichtig:** `/ready` prüft das Modell nicht (bewusst, sonst kostet jede Probe Tokens). Ein vergessenes Zurücksetzen
in Schritt 3 fällt nur durch den Alarm auf.

**Im Portal:** Monitor → Alerts → Alert-Liste (Status Fired → Resolved); Container App → Revisions and replicas (neue Revision je `update`)
