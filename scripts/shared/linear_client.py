import httpx
from shared.config import get_linear_api_key, LINEAR_API_URL


def graphql(query: str, variables: dict = None) -> dict:
    """Execute a Linear GraphQL query/mutation. Returns the 'data' dict.
    Raises on HTTP errors or GraphQL errors."""
    response = httpx.post(
        LINEAR_API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": get_linear_api_key()},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if "errors" in body:
        raise Exception(f"GraphQL error: {body['errors']}")
    return body["data"]
