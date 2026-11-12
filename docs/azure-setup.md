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
Invoke-RestMethod "$url/analyze" -Method Post -ContentType "application/json" -Headers @{ "X-API-Key" = $key } -Body '{"ticket_id": "T-1", "raw_text": "Seit dem Update startet die App nicht mehr, ich kann nicht arbeiten."}'
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
