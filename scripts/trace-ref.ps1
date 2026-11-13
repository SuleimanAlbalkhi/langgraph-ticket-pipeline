# Gibt die Ticket-Referenz (ticket_ref) zu einer Ticket-ID aus, nach der man in Langfuse sucht.
# Aufruf aus dem Repo-Root:   .\scripts\trace-ref.ps1 -TicketId EVAL-001
#
# Rechnet dasselbe wie app/observability.py: HMAC-SHA256 über die UTF-8-Bytes der Ticket-ID,
# Hex, die ersten 16 Zeichen. Der Schlüssel kommt direkt aus dem Key Vault in eine Variable:
# Er wird nicht ausgegeben, steht nicht in der Shell-Historie (nur der Skriptaufruf) und
# landet in keiner Datei. Voraussetzung: "az login" und Leserecht auf die Secrets.

param(
    [Parameter(Mandatory = $true)] [string] $TicketId
)

$ErrorActionPreference = "Stop"

$key = az keyvault secret show --vault-name kv-ticketpipe-sa --name ticket-id-hmac-key --query value --output tsv
if ($LASTEXITCODE -ne 0 -or -not $key) { throw "HMAC-Schlüssel konnte nicht aus dem Key Vault gelesen werden" }

$hmac = [System.Security.Cryptography.HMACSHA256]::new([System.Text.Encoding]::UTF8.GetBytes($key))
try {
    $hash = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($TicketId))
}
finally {
    $hmac.Dispose()
    Remove-Variable key
}

$ref = (-join ($hash | ForEach-Object { $_.ToString("x2") })).Substring(0, 16)
Write-Output $ref
