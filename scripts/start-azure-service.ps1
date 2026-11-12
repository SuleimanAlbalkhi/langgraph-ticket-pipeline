# Startet den Service lokal im Azure-Modus (Terminal 1).
# Aufruf aus dem Repo-Root:   .\scripts\start-azure-service.ps1
#
# Setzt alle Umgebungsvariablen selbst; GIT_SHA ist immer der aktuelle Commit, damit
# run_eval.py --verify-via-ready den richtigen Code-Stand prüft. Nach jedem Commit neu starten.
# Voraussetzung: "az login" ist erfolgt (die Anmeldung bei Azure OpenAI läuft darüber).

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $repo "fastapi-service")

$env:LLM_PROVIDER            = "azure"
$env:AZURE_OPENAI_ENDPOINT   = "https://oai-ticketpipe-sa.openai.azure.com/"
$env:API_KEY                 = "lokal-test"   # nur lokal; in der Cloud kommt der Key aus dem Key Vault
$env:MAX_CONCURRENT_ANALYSES = "4"
$env:GIT_SHA                 = (git rev-parse HEAD)

Write-Host "Service im Azure-Modus, Commit $($env:GIT_SHA.Substring(0, 7)) - Stoppen mit Strg+C" -ForegroundColor Cyan
& .\venv\Scripts\uvicorn.exe app.main:app --port 8000
