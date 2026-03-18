import anthropic
from shared.config import get_anthropic_api_key, get_claude_model

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    return _client


def call_claude(
    system: str,
    messages: list[dict],
    tools: list[dict] = None,
    max_tokens: int = 4096,
) -> anthropic.types.Message:
    """Call Claude with text, images, and optional tools.
    Returns the full Message object (caller reads content + usage)."""
    kwargs = {
        "model": get_claude_model(),
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
    return _get_client().messages.create(**kwargs)


# Alias used by Stage 3 (calls with tool loop)
call_claude_with_tools = call_claude


def build_user_message(text: str, images: list[dict] = None) -> dict:
    """Build a user message with optional images.
    images: list of {"media_type": "image/jpeg", "data": "<base64>"}
    Pure function — no SDK or network dependency.
    """
    content = []
    if images:
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["data"],
                }
            })
    content.append({"type": "text", "text": text})
    return {"role": "user", "content": content}
