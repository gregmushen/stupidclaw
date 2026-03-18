import base64

import httpx

SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024


def _attachment_type_hint(attachment: dict) -> str:
    metadata = attachment.get("metadata") or {}
    return (metadata.get("mimeType") or "").strip().lower()


def download_attachments(attachments: list[dict]) -> list[dict]:
    images: list[dict] = []
    for attachment in attachments:
        url = attachment.get("url")
        if not url:
            continue

        hinted_type = _attachment_type_hint(attachment)
        if hinted_type and hinted_type not in SUPPORTED_TYPES:
            continue

        try:
            response = httpx.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
        except Exception:
            continue

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in SUPPORTED_TYPES:
            continue
        if len(response.content) > MAX_IMAGE_SIZE:
            continue

        images.append(
            {
                "media_type": content_type,
                "data": base64.b64encode(response.content).decode("utf-8"),
            }
        )
    return images
