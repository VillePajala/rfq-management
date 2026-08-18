"""AI client factory — returns an OpenAI-compatible client based on env vars.

Single switch between demo and production AI providers, controlled by env:

- Demo (default):
    OPENAI_API_KEY=sk-...     → uses OpenAI directly (current PoC behaviour)

- Production (in-tenant AI):
    AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
    AZURE_OPENAI_API_VERSION=2024-08-01-preview          (optional, sensible default)
    AZURE_OPENAI_API_KEY=...                             (or use Managed Identity)
                                                         → uses Azure OpenAI Service / AI Foundry

Both client classes share the same call surface
(`client.chat.completions.create(...)`), so call sites don't need to change.

For the `model` argument:
  - OpenAI direct: pass the model ID (e.g. "gpt-4o-mini")
  - Azure OpenAI:  pass the *deployment name* you chose at deploy time
                   (configurable via OPENAI_MODEL env, same variable for both).
"""
import os

from openai import OpenAI, AzureOpenAI


def get_ai_client(timeout: float = 60.0):
    """Return an OpenAI-compatible client (or None if no credentials present).

    Detection rule: if AZURE_OPENAI_ENDPOINT is set we use AzureOpenAI;
    otherwise we fall back to OpenAI direct. Both honour OPENAI_MODEL.
    """
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if azure_endpoint:
        api_key = (os.getenv("AZURE_OPENAI_API_KEY")
                   or os.getenv("OPENAI_API_KEY"))   # fallback for convenience
        return AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            api_key=api_key,
            timeout=timeout,
        )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=timeout)
