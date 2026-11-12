# Ein Eval-Lauf gegen den lokal laufenden Service im Azure-Modus (Terminal 2).
# Vorher in Terminal 1: .\scripts\start-azure-service.ps1
#
# Aufruf aus dem Repo-Root:
#   .\scripts\run-eval.ps1 -Name e13-beispiel -Note "Was in diesem Lauf geändert wurde"
#
# Ablauf: Kapazität des Deployments auf 100k TPM hoch (sonst bremst das Rate-Limit die Eval
# und Fallbacks verfälschen die Messung) -> run_eval.py -> report.py -> compare.py ->
# Kapazität zurück auf 10k TPM, auch wenn unterwegs etwas schiefgeht (finally).

param(
    [Parameter(Mandatory = $true)] [string] $Name,
    [Parameter(Mandatory = $true)] [string] $Note
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"

function Set-Capacity([int] $Tpm) {
    Write-Host "Kapazität ticket-llm -> ${Tpm}k TPM" -ForegroundColor Cyan
    az cognitiveservices account deployment create `
        --name oai-ticketpipe-sa --resource-group rg-ticket-pipeline `
        --deployment-name ticket-llm --model-name gpt-4.1-mini --model-version 2025-04-14 `
        --model-format OpenAI --sku-name GlobalStandard --sku-capacity $Tpm --output none
    if ($LASTEXITCODE -ne 0) { throw "Kapazität konnte nicht gesetzt werden" }
}

$env:EVAL_API_KEY = "lokal-test"   # muss zum API_KEY in start-azure-service.ps1 passen

Set-Capacity 100
try {
    & $py eval\run_eval.py --run-name $Name --base-url http://localhost:8000 --verify-via-ready `
        --model gpt-4.1-mini --hardware "Azure OpenAI gpt-4.1-mini GlobalStandard (France Central), 100k TPM" `
        --note $Note
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py ist fehlgeschlagen (Ausgabe oben)" }
    & $py eval\report.py --run $Name
    & $py eval\compare.py
}
finally {
    Set-Capacity 10
}
