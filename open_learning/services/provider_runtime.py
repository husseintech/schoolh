import os

from . import ai_service


class ResilientProvider:
    """Try Gemini when configured, then fall back to the local free generator."""

    name = 'gemini+local-fallback'

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.model = getattr(primary, 'model', 'local-fallback')

    def generate_lesson_content(self, prompt_data):
        try:
            return self.primary.generate_lesson_content(prompt_data)
        except ai_service.AIServiceUnavailable:
            return self.fallback.generate_lesson_content(prompt_data)

    def generate_section(self, prompt_data, section):
        try:
            return self.primary.generate_section(prompt_data, section)
        except ai_service.AIServiceUnavailable:
            return self.fallback.generate_section(prompt_data, section)


def get_resilient_provider():
    """Production-safe provider selection with a zero-cost local fallback.

    - AI_PROVIDER=none explicitly disables generation.
    - AI_PROVIDER=gemini uses Gemini when a key exists and falls back locally on API/quota/network failure.
    - AI_PROVIDER=mock/local uses the local generator.
    - If AI_PROVIDER is unset, Gemini is used when a key exists; otherwise the local generator is used.
    """
    configured = os.getenv('AI_PROVIDER', '').strip().lower()
    key = os.getenv('AI_API_KEY', '').strip()
    model = os.getenv('AI_MODEL', 'gemini-2.0-flash').strip()

    if configured == 'none':
        return None

    local = ai_service.MockProvider()

    if configured in {'mock', 'local'}:
        return local

    if configured == 'gemini':
        if not key:
            return local
        return ResilientProvider(ai_service.GeminiProvider(key=key, model=model), local)

    # Safe default for production: use Gemini when configured, otherwise stay fully local/free.
    if key:
        return ResilientProvider(ai_service.GeminiProvider(key=key, model=model), local)
    return local


def install_provider_override():
    ai_service.get_provider = get_resilient_provider
