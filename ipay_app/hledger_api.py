"""Simple Python client for the hledger HTTP API (httpx + Pydantic).

Endpoints covered:
- GET /version
- GET /accountnames
- GET /transactions
- GET /prices
- GET /commodities
- GET /accounts
- GET /accounttransactions/{ACCOUNTNAME}

Default base URL: http://127.0.0.1:5000

Pydantic models validate key responses:
- AccountNames: list[str]
- Transactions: list[Transaction] (with Posting/Amount)

Usage:
    client = HLedgerClient()
    names = client.get_accountnames()  # -> AccountNames
    txns = client.get_transactions()   # -> Transactions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Optional

import httpx
from pydantic import BaseModel, RootModel
from pydantic.config import ConfigDict

__all__ = [
    "HLedgerClient",
    "HLedgerAPIError",
    "AccountNames",
    "Transactions",
    "Transaction",
    "Posting",
    "Amount",
]


# ------------------------ Pydantic models ------------------------
class AccountNames(RootModel[list[str]]):
    """Represents the /accountnames response: a list of account name strings."""


class Amount(BaseModel):
    """Represents an amount object within a posting.

    The exact schema may vary by hledger API version; unknown fields are ignored.
    """

    acommodity: Optional[str] = None
    aismultiplier: Optional[bool] = None
    aprice: Optional[Any] = None
    aquantity: Optional[Any] = None

    model_config = ConfigDict(extra="ignore")


class Posting(BaseModel):
    paccount: str
    pamount: Optional[list[Amount]] = None
    pcomment: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Transaction(BaseModel):
    tcode: Optional[str] = ""
    tcomment: Optional[str] = ""
    tdate: date
    tdate2: Optional[date] = None
    tdescription: str
    tindex: int
    tpostings: list[Posting]

    model_config = ConfigDict(extra="ignore")


class Transactions(RootModel[list[Transaction]]):
    """Represents the /transactions response: a list of transactions."""


# ------------------------ Errors ------------------------
class HLedgerAPIError(Exception):
    """Represents an error returned by or encountered calling the hledger API."""


# ------------------------ Client ------------------------
@dataclass(slots=True)
class HLedgerClient:
    """Lightweight client for the hledger API using httpx.

    Attributes:
        base_url: Base URL for the API (no trailing slash required).
        timeout: Request timeout, in seconds.
        default_headers: Optional headers to include with each request.
    """

    base_url: str = "http://127.0.0.1:5000"
    timeout: float = 10.0
    default_headers: Optional[Mapping[str, str]] = None
    _client: Optional[httpx.Client] = None

    # ---- lifecycle ----
    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url.rstrip("/") + "/",
                timeout=self.timeout,
                headers={"Accept": "application/json", **(self.default_headers or {})},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "HLedgerClient":  # context manager support
        self._ensure_client()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --------------- Public endpoint methods ---------------
    def get_version(self) -> Any:
        return self._get_json("version")

    def get_accountnames(
        self, params: Optional[Mapping[str, Any]] = None
    ) -> AccountNames:
        data = self._get_json("accountnames", params)
        return AccountNames.model_validate(data)

    def get_transactions(
        self, params: Optional[Mapping[str, Any]] = None
    ) -> Transactions:
        data = self._get_json("transactions", params)
        return Transactions.model_validate(data)

    def get_prices(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self._get_json("prices", params)

    def get_commodities(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self._get_json("commodities", params)

    def get_accounts(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self._get_json("accounts", params)

    def get_account_transactions(
        self, account_name: str, params: Optional[Mapping[str, Any]] = None
    ) -> Transactions | Any:
        # If the endpoint mirrors /transactions schema, validate; otherwise return raw.
        data = self._get_json(f"accounttransactions/{account_name}", params)
        try:
            return Transactions.model_validate(data)
        except Exception:
            return data

    # --------------- Internal helpers ---------------
    def _get_json(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        client = self._ensure_client()
        try:
            resp = client.get(path.lstrip("/"), params=params)
            resp.raise_for_status()
            # httpx automatically decodes based on response headers
            return resp.json()
        except httpx.HTTPStatusError as e:
            body = _safe_body(e.response)
            raise HLedgerAPIError(
                f"GET {e.request.url} failed: {e.response.status_code}. Body: {body}"
            ) from e
        except httpx.RequestError as e:
            raise HLedgerAPIError(
                f"GET {getattr(e.request, 'url', path)} failed: {e}"
            ) from e


def _safe_body(response: Optional[httpx.Response]) -> str:
    if not response:
        return ""
    try:
        return response.text
    except Exception:
        return "<unreadable body>"
