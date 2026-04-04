from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class TransactionStreamManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections = [conn for conn in self._connections if conn is not websocket]

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)

        stale: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)

        if stale:
            async with self._lock:
                stale_ids = {id(conn) for conn in stale}
                self._connections = [conn for conn in self._connections if id(conn) not in stale_ids]


transaction_stream = TransactionStreamManager()
