"""
LSP Client Adapter for Voss (M10-02).

Strict isolation: pygls is never imported at module level and never leaks
into any public API or other modules.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from .models import CodeLocation, ReferenceHit, SymbolHit


class LspClientAdapter(ABC):
    """Voss-owned LSP client interface. All implementations must return
    only Voss types or structured error dicts."""

    @abstractmethod
    async def initialize(self, root_uri: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    @abstractmethod
    async def find_definition(
        self, uri: str, line: int, character: int
    ) -> list[CodeLocation] | dict[str, Any]:
        ...

    @abstractmethod
    async def find_references(
        self, uri: str, line: int, character: int
    ) -> list[ReferenceHit] | dict[str, Any]:
        ...

    @abstractmethod
    async def workspace_symbol(self, query: str) -> list[SymbolHit] | dict[str, Any]:
        ...


# ------------------------------------------------------------------
# pygls-backed implementation (pygls is imported only inside this class)
# ------------------------------------------------------------------

class _PyglsLspClient(LspClientAdapter):
    """Real implementation using pygls as a client."""

    def __init__(self, language: str):
        self.language = language
        self._proc: asyncio.subprocess.Process | None = None
        self._client: Any = None  # pygls client
        self._initialized = False

    async def connect(self, proc: asyncio.subprocess.Process) -> None:
        """Wire this adapter to an already-started server process."""
        self._proc = proc
        try:
            from pygls.client import JsonRPCClient
            self._client = JsonRPCClient()
            # pygls JsonRPCClient can take streams
            await self._client.start_io(proc.stdout, proc.stdin)
        except Exception as exc:
            # If pygls fails to start, we still want graceful degradation
            self._client = None
            raise RuntimeError(f"Failed to start pygls client for {self.language}: {exc}") from exc

    async def initialize(self, root_uri: str) -> dict[str, Any] | None:
        if self._client is None:
            return self._unavailable()

        try:
            params = {
                "processId": None,
                "rootUri": root_uri,
                "capabilities": {},
            }
            result = await self._client.send_request("initialize", params)
            await self._client.send_notification("initialized", {})
            self._initialized = True
            return result
        except Exception:
            return self._unavailable()

    async def shutdown(self) -> None:
        if self._client and self._initialized:
            try:
                await self._client.send_request("shutdown")
                await self._client.send_notification("exit")
            except Exception:
                pass
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._initialized = False
        self._client = None

    async def find_definition(
        self, uri: str, line: int, character: int
    ) -> list[CodeLocation] | dict[str, Any]:
        if not self._initialized or self._client is None:
            return self._unavailable()

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }
        try:
            result = await self._client.send_request("textDocument/definition", params)
            return self._convert_locations(result)
        except Exception:
            return self._unavailable()

    async def find_references(
        self, uri: str, line: int, character: int
    ) -> list[ReferenceHit] | dict[str, Any]:
        if not self._initialized or self._client is None:
            return self._unavailable()

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True},
        }
        try:
            result = await self._client.send_request("textDocument/references", params)
            return self._convert_references(result)
        except Exception:
            return self._unavailable()

    async def workspace_symbol(self, query: str) -> list[SymbolHit] | dict[str, Any]:
        if not self._initialized or self._client is None:
            return self._unavailable()
        try:
            result = await self._client.send_request("workspace/symbol", {"query": query})
            return self._convert_symbols(result)
        except Exception:
            return self._unavailable()

    def _unavailable(self) -> dict[str, Any]:
        return {
            "result": "lsp_unavailable",
            "language": self.language,
            "fallback": "ast-grep",
        }

    # Very small converters — real ones would be more complete
    def _convert_locations(self, result: Any) -> list[CodeLocation]:
        if not result:
            return []
        locations = []
        for item in (result if isinstance(result, list) else [result]):
            if isinstance(item, dict) and "uri" in item and "range" in item:
                loc = self._range_to_location(item["uri"], item["range"])
                if loc:
                    locations.append(loc)
        return locations

    def _convert_references(self, result: Any) -> list[ReferenceHit]:
        if not result:
            return []
        hits = []
        for item in (result if isinstance(result, list) else [result]):
            if isinstance(item, dict) and "uri" in item and "range" in item:
                loc = self._range_to_location(item["uri"], item["range"])
                if loc:
                    hits.append(ReferenceHit(location=loc, language=self.language))
        return hits

    def _convert_symbols(self, result: Any) -> list[SymbolHit]:
        # Simplified
        return []

    def _range_to_location(self, uri: str, rng: dict) -> CodeLocation | None:
        try:
            path = uri.replace("file://", "")
            start = rng.get("start", {})
            return CodeLocation(
                file=path,
                line=start.get("line", 0),
                column=start.get("character", 0),
            )
        except Exception:
            return None


def create_lsp_client(language: str) -> LspClientAdapter:
    return _PyglsLspClient(language)


def is_lsp_available() -> bool:
    try:
        import pygls  # noqa: F401
        return True
    except ImportError:
        return False
