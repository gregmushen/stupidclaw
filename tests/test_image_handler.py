from unittest.mock import MagicMock, patch

from shared.image_handler import MAX_IMAGE_SIZE, download_attachments


def _mock_response(content: bytes, content_type: str = "image/jpeg", status: int = 200):
    response = MagicMock()
    response.content = content
    response.headers = {"content-type": content_type}
    response.status_code = status
    response.raise_for_status = MagicMock()
    if status >= 400:
        response.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return response


@patch("shared.image_handler.httpx.get")
def test_download_mocking(mock_get):
    mock_get.return_value = _mock_response(b"fake-image")
    result = download_attachments([{"url": "https://cdn.example.com/a.jpg"}])
    assert len(result) == 1
    assert result[0]["media_type"] == "image/jpeg"
    assert isinstance(result[0]["data"], str)
    assert len(result[0]["data"]) > 0


@patch("shared.image_handler.httpx.get")
def test_format_filtering(mock_get):
    mock_get.return_value = _mock_response(b"fake-pdf", content_type="application/pdf")
    result = download_attachments([{"url": "https://cdn.example.com/a.pdf"}])
    assert result == []


@patch("shared.image_handler.httpx.get")
def test_size_limits(mock_get):
    mock_get.return_value = _mock_response(b"x" * (MAX_IMAGE_SIZE + 1))
    result = download_attachments([{"url": "https://cdn.example.com/too-large.jpg"}])
    assert result == []


@patch("shared.image_handler.httpx.get")
def test_failed_download_skip(mock_get):
    mock_get.side_effect = Exception("connection error")
    result = download_attachments([{"url": "https://cdn.example.com/fail.jpg"}])
    assert result == []
