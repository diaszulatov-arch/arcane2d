"""Minimal asyncio HTTP + RFC 6455 WebSocket plumbing.

Arcane 2D intentionally has zero third-party dependencies.  This module wraps
just enough of the WebSocket protocol for the game: text messages, ping/pong,
close frames and fragmentation up to a fixed message limit.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import struct
from typing import Any, Mapping

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_MESSAGE_BYTES = 64 * 1024


class ProtocolError(Exception):
    pass


def websocket_accept(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


async def write_http_response(
    writer: asyncio.StreamWriter,
    status: int,
    body: bytes,
    *,
    content_type: str = "text/plain; charset=utf-8",
    extra_headers: Mapping[str, str] | None = None,
    head_only: bool = False,
) -> None:
    reasons = {
        200: "OK",
        204: "No Content",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        413: "Payload Too Large",
        426: "Upgrade Required",
        500: "Internal Server Error",
    }
    headers = [
        f"HTTP/1.1 {status} {reasons.get(status, 'OK')}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Cache-Control: no-store",
        "X-Content-Type-Options: nosniff",
        "Connection: close",
    ]
    if extra_headers:
        headers.extend(f"{key}: {value}" for key, value in extra_headers.items())
    payload = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8")
    writer.write(payload if head_only else payload + body)
    try:
        await writer.drain()
    except (ConnectionError, RuntimeError):
        pass


class WebSocket:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        self.closed = False
        self.last_seen = asyncio.get_running_loop().time()
        self._write_lock = asyncio.Lock()
        self._close_sent = False
        self._writer_closed = False

    async def handshake(self, key: str) -> None:
        accept = websocket_accept(key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        self.writer.write(response.encode("ascii"))
        await self.writer.drain()

    @staticmethod
    def _frame(opcode: int, payload: bytes) -> bytes:
        if opcode >= 8 and len(payload) > 125:
            raise ValueError("control frame too large")
        first = 0x80 | (opcode & 0x0F)
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, length)
        elif length < 65536:
            header = struct.pack("!BBH", first, 126, length)
        else:
            header = struct.pack("!BBQ", first, 127, length)
        return header + payload

    async def send_frame(self, opcode: int, payload: bytes) -> bool:
        if self.closed:
            return False
        frame = self._frame(opcode, payload)
        async with self._write_lock:
            if self.closed:
                return False
            try:
                self.writer.write(frame)
                await self.writer.drain()
                return True
            except (ConnectionError, RuntimeError):
                self.closed = True
                return False

    def _send_nowait(self, opcode: int, payload: bytes) -> bool:
        """Queue a frame without waiting for the peer to read it.

        The game loop serves every player, so it must never wait on one of
        them.  ``write`` takes the whole frame at once, which keeps it safe
        beside a ``send_frame`` that is parked in ``drain``.
        """

        if self.closed or self.writer.is_closing():
            return False
        try:
            self.writer.write(self._frame(opcode, payload))
            return True
        except (ConnectionError, RuntimeError):
            self.closed = True
            return False

    def send_text_nowait(self, text: str) -> bool:
        return self._send_nowait(0x1, text.encode("utf-8"))

    def send_ping_nowait(self) -> bool:
        return self._send_nowait(0x9, b"arcane")

    @property
    def backlog(self) -> int:
        """Bytes written but not yet taken by the peer's socket."""

        transport = self.writer.transport
        if transport is None or transport.is_closing():
            return 0
        return transport.get_write_buffer_size()

    def abort(self) -> None:
        """Drop a stuck connection at once, without the closing handshake."""

        self.closed = True
        transport = self.writer.transport
        if transport is not None:
            transport.abort()

    async def send_text(self, text: str) -> bool:
        try:
            payload = text.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return await self.send_frame(0x1, payload)

    async def send_json(self, data: Any) -> bool:
        return await self.send_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        )

    async def send_ping(self) -> bool:
        return await self.send_frame(0x9, b"arcane")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        if self._writer_closed:
            return
        self.closed = True
        if not self._close_sent and not self.writer.is_closing():
            self._close_sent = True
            payload = struct.pack("!H", code) + reason.encode("utf-8")[:100]
            try:
                async with self._write_lock:
                    self.writer.write(struct.pack("!BB", 0x88, len(payload)) + payload)
                    await self.writer.drain()
            except (ConnectionError, RuntimeError, asyncio.CancelledError):
                pass
        try:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), timeout=1.0)
        except (ConnectionError, RuntimeError, asyncio.TimeoutError, asyncio.CancelledError):
            pass
        finally:
            self._writer_closed = True

    async def _read_frame(self) -> tuple[bool, int, bytes] | None:
        try:
            header = await self.reader.readexactly(2)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            self.closed = True
            return None
        first, second = header
        fin = bool(first & 0x80)
        rsv = first & 0x70
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if rsv:
            raise ProtocolError("RSV bits are not supported")
        if not masked:
            raise ProtocolError("client frames must be masked")
        if opcode >= 8 and (not fin or length > 125):
            raise ProtocolError("invalid control frame")
        try:
            if length == 126:
                length = struct.unpack("!H", await self.reader.readexactly(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", await self.reader.readexactly(8))[0]
            if length > MAX_MESSAGE_BYTES:
                raise ProtocolError("frame too large")
            mask = await self.reader.readexactly(4)
            data = await self.reader.readexactly(length)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            self.closed = True
            return None

        if opcode >= 8 and length > 125:
            raise ProtocolError("invalid control frame")
        unmasked = bytearray(data)
        for index in range(len(unmasked)):
            unmasked[index] ^= mask[index % 4]
        self.last_seen = asyncio.get_running_loop().time()
        return fin, opcode, bytes(unmasked)

    async def read_message(self) -> str | None:
        """Read the next application text message, or None when disconnected."""

        fragments = bytearray()
        fragment_opcode: int | None = None
        try:
            while True:
                frame = await self._read_frame()
                if frame is None:
                    return None
                fin, opcode, payload = frame
                if opcode == 0x8:  # close
                    await self.close(1000, "")
                    return None
                if opcode == 0x9:  # ping
                    await self.send_frame(0xA, payload)
                    continue
                if opcode == 0xA:  # pong
                    continue
                if opcode in (0x1, 0x2):
                    if fragment_opcode is not None:
                        raise ProtocolError("new message during fragmented message")
                    if len(payload) > MAX_MESSAGE_BYTES:
                        raise ProtocolError("message too large")
                    if fin:
                        if opcode == 0x2:
                            continue
                        try:
                            return payload.decode("utf-8")
                        except UnicodeDecodeError:
                            await self.close(1007, "invalid utf-8")
                            return None
                    fragment_opcode = opcode
                    fragments.extend(payload)
                    continue
                if opcode == 0x0:
                    if fragment_opcode is None:
                        raise ProtocolError("unexpected continuation frame")
                    fragments.extend(payload)
                    if len(fragments) > MAX_MESSAGE_BYTES:
                        raise ProtocolError("message too large")
                    if fin:
                        finished_opcode = fragment_opcode
                        fragment_opcode = None
                        if finished_opcode == 0x2:
                            fragments.clear()
                            continue
                        try:
                            return fragments.decode("utf-8")
                        except UnicodeDecodeError:
                            await self.close(1007, "invalid utf-8")
                            return None
                        finally:
                            fragments.clear()
                    continue
                raise ProtocolError(f"unsupported opcode {opcode}")
        except ProtocolError as exc:
            await self.close(1002, str(exc)[:80])
            return None
        except (ConnectionError, OSError):
            self.closed = True
            return None
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.close(1011, "internal websocket error")
            return None
