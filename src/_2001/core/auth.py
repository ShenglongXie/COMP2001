from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any

import httpx

VERIFIED_STATUS = "verified"
TRUTHY = frozenset({"true", "1", "yes", "y"})
FALSY = frozenset({"false", "0", "no", "n"})
VERDICT_KEYS = ("verified", "isverified", "authenticated", "valid", "success")


class AuthUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    email: str


def _as_flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUTHY:
            return True
        if normalized in FALSY:
            return False
    return None


def is_verified(payload: Any) -> bool | None:
    if isinstance(payload, (list, tuple)):
        if len(payload) >= 2:
            status = str(payload[0]).strip().lower()
            flag = _as_flag(payload[1])
            if flag is not None:
                return flag and status == VERIFIED_STATUS
            return None
        if len(payload) == 1:
            return is_verified(payload[0])
        return None
    if isinstance(payload, dict):
        for key in VERDICT_KEYS:
            if key in payload:
                return _as_flag(payload[key])
        return None
    return _as_flag(payload)


class AuthenticatorClient:
    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        cache_ttl: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url
        self._cache_ttl = cache_ttl
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport)
        self._cache: dict[str, tuple[float, AuthenticatedUser]] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def authenticate(
        self, email: str, password: str
    ) -> AuthenticatedUser | None:
        key = self._cache_key(email, password)

        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                if cached[0] > time.monotonic():
                    return cached[1]
                del self._cache[key]

        user = await self._call(email, password)
        if user is not None and self._cache_ttl > 0:
            async with self._lock:
                self._cache[key] = (time.monotonic() + self._cache_ttl, user)
        return user

    async def _call(self, email: str, password: str) -> AuthenticatedUser | None:
        try:
            response = await self._http.post(
                self._url, json={"email": email, "password": password}
            )
        except httpx.HTTPError as exc:
            raise AuthUnavailable(f"authenticator unreachable: {exc}") from exc

        if response.status_code in (401, 403):
            return None
        if response.status_code == 429 or response.status_code >= 500:
            raise AuthUnavailable(
                f"authenticator returned {response.status_code}"
            )
        if response.status_code != 200:
            return None

        try:
            payload = response.json()
        except ValueError:
            return None

        return AuthenticatedUser(email=email) if is_verified(payload) else None

    @staticmethod
    def _cache_key(email: str, password: str) -> str:
        material = f"{email}\x00{password}".encode()
        return hashlib.sha256(material).hexdigest()
