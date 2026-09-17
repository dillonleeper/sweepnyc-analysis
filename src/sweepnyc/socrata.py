"""Small helpers for NYC Open Data / Socrata.

These utilities intentionally keep ingestion simple during Phase 1.
Large production pulls should later use incremental extraction and local
columnar storage rather than repeatedly downloading full datasets.
"""

from __future__ import annotations

from typing import Any

import requests

from .config import SOCRATA_DOMAIN


def metadata(dataset_id: str) -> dict[str, Any]:
    """Return Socrata dataset metadata."""
    url = f"https://{SOCRATA_DOMAIN}/api/views/{dataset_id}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def field_names(dataset_id: str) -> list[str]:
    """Return API field names advertised by Socrata metadata."""
    meta = metadata(dataset_id)
    return [
        column["fieldName"]
        for column in meta.get("columns", [])
        if column.get("fieldName")
    ]


def fetch_rows(
    dataset_id: str,
    *,
    limit: int = 1000,
    offset: int = 0,
    where: str | None = None,
    select: str | None = None,
    order: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch a page of rows from a Socrata dataset."""
    url = f"https://{SOCRATA_DOMAIN}/resource/{dataset_id}.json"
    params: dict[str, Any] = {"$limit": limit, "$offset": offset}

    if where:
        params["$where"] = where
    if select:
        params["$select"] = select
    if order:
        params["$order"] = order

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()
