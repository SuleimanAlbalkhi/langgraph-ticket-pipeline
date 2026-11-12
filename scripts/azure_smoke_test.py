"""Smoke-Test: ruft das Azure-OpenAI-Deployment ohne API-Schluessel auf.

Prueft drei Dinge, auf denen Block A aufbaut:
  1. Anmeldung ueber Entra ID (lokal: "az login", in der Cloud: Managed Identity)
  2. temperature=0 wird vom Modell akzeptiert
  3. JSON-Modus (response_format json_object) liefert ein JSON-Objekt

Aufruf (aus dem Repo-Root, mit einer venv, in der openai und azure-identity installiert sind):
    python scripts/azure_smoke_test.py
"""
import json

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

ENDPOINT = "https://oai-ticketpipe-sa.openai.azure.com/"
DEPLOYMENT = "ticket-llm"  # Deployment-Name, nicht Modellname
API_VERSION = "2024-10-21"

# DefaultAzureCredential probiert mehrere Anmeldewege nacheinander; lokal greift der
# Login der Azure CLI. Der Token-Provider holt kurzlebige Tokens (ca. 1 h) fuer
# Azure OpenAI und erneuert sie selbst.
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version=API_VERSION,
)

response = client.chat.completions.create(
    model=DEPLOYMENT,
    temperature=0,
    # JSON-Modus: das Wort "JSON" muss in den Nachrichten vorkommen.
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": "Antworte ausschliesslich als JSON-Objekt."},
        {
            "role": "user",
            "content": 'Klassifiziere dieses Ticket als JSON mit den Feldern "category" '
                       '(technical_support, billing_dispute, general_inquiry) und "urgency" '
                       '(low, medium, high, critical): "Seit dem Update startet die App nicht '
                       'mehr, ich kann nicht arbeiten."',
        },
    ],
)

content = response.choices[0].message.content
print("Antwort:", content)
print("Als JSON geparst:", json.loads(content))
print("Modell:", response.model)
print("Tokens:", response.usage.prompt_tokens, "rein /", response.usage.completion_tokens, "raus")
