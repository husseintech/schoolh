import os

from . import ai_service


def get_resilient_provider():
    """Select a configured model. Missing credentials never produce template content."""
    configured = os.getenv('AI_PROVIDER', '').strip().lower()
    key = os.getenv('AI_API_KEY', '').strip()
    model = os.getenv('AI_MODEL', 'gemini-2.5-flash').strip()

    if configured == 'none':
        return None

    local = None  # Never disguise template text as real AI output.

    if configured in {'mock', 'local'}:
        return local

    if configured == 'gemini':
        if not key:
            return local
        return ai_service.GeminiProvider(key=key, model=model)

    if key and not configured:
        return ai_service.GeminiProvider(key=key, model=model)
    return local


def install_provider_override():
    ai_service.get_provider = get_resilient_provider
