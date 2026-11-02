"""Integration tests for the HTTP server and the WebSocket protocol."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import struct
import unittest

from arcane.net import WebSocket
from server import ArcaneServer, clean_name


class ServerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = ArcaneServer(bots=0)
        self.connections: set[asyncio.Task] = set()

        async def handle(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            task = asyncio.current_task()
            if task is not None:
                self.connections.add(task)
            try:
                await self.app.handle_connection(reader, writer)
            finally:
                if task is not None:
                    self.connections.discard(task)

        self.server = await asyncio.start_server(handle, "127.0.0.1", 0)
        sock = self.server.sockets[0]
        self.port = sock.getsockname()[1]
        self.game_task = asyncio.create_task(self.app.game_loop())

    async def asyncTearDown(self) -> None:
        self.game_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.game_task
        await self.app.shutdown()
        self.server.close()
        await self.server.wait_closed()
        pending = [task for task in self.connections if not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.sleep(0)

    async def http_get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(request.encode("latin-1"))
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=3)
        writer.close()
        with contextlib.suppress(ConnectionError):
            await writer.wait_closed()
        head, _, body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status = int(lines[0].split(" ")[1])
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        return status, headers, body

    async def ws_connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            "GET /ws HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        writer.write(request.encode("latin-1"))
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=3)
        self.assertTrue(head.startswith(b"HTTP/1.1 101"), head)
        accept = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        self.assertIn(f"Sec-WebSocket-Accept: {accept}".encode(), head)
        return reader, writer

    async def read_frame(
        self, reader: asyncio.StreamReader
    ) -> tuple[int, bytes] | None:
        header = await asyncio.wait_for(reader.readexactly(2), timeout=3)
        first, second = header
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", await reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await reader.readexactly(8))[0]
        if second & 0x80:
            mask = await reader.readexactly(4)
            payload = bytearray(await reader.readexactly(length))
            for index in range(len(payload)):
                payload[index] ^= mask[index % 4]
            payload = bytes(payload)
        else:
            payload = await reader.readexactly(length)
        return opcode, payload

    async def send_json(
        self, writer: asyncio.StreamWriter, message: dict[str, object]
    ) -> None:
        payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
        mask = os.urandom(4)
        masked = bytes(
            byte ^ mask[index % 4] for index, byte in enumerate(payload)
        )
        header = bytearray([0x81])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", len(payload)))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", len(payload)))
        writer.write(bytes(header) + mask + masked)
        await writer.drain()

    async def read_json(self, reader: asyncio.StreamReader) -> dict[str, object]:
        while True:
            frame = await self.read_frame(reader)
            self.assertIsNotNone(frame, "websocket closed unexpectedly")
            opcode, payload = frame
            if opcode == 0x8:
                self.fail("server closed the websocket")
            if opcode == 0x9:
                continue
            if opcode in (0x1, 0x2):
                return json.loads(payload.decode("utf-8"))

    async def wait_for_type(
        self, reader: asyncio.StreamReader, kind: str
    ) -> dict[str, object]:
        for _ in range(120):
            message = await self.read_json(reader)
            if message.get("t") == kind:
                return message
        self.fail(f"did not receive {kind}")

    async def test_health_and_world_endpoints(self) -> None:
        status, headers, body = await self.http_get("/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        health = json.loads(body)
        self.assertTrue(health["ok"])
        self.assertEqual(health["players"]["online"], 0)

        status, _, body = await self.http_get("/api/world")
        self.assertEqual(status, 200)
        world = json.loads(body)
        self.assertEqual(len(world["spawns"]), 6)
        self.assertEqual(world["arena"]["w"], 1900)
        self.assertIn("spell_costs", world)

    async def test_static_files_and_headers(self) -> None:
        status, headers, body = await self.http_get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])
        self.assertIn("content-security-policy", headers)
        self.assertIn(b'type="module"', body)
        self.assertIn(b'id="gameCanvas"', body)

        status, headers, body = await self.http_get("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["content-type"])
        self.assertIn(b"castSlot", body)

        status, headers, body = await self.http_get("/favicon.svg")
        self.assertEqual(status, 200)
        self.assertIn("image/svg+xml", headers["content-type"])

        status, headers, body = await self.http_get("/fonts/pixelify-sans-400.woff2")
        self.assertEqual(status, 200)
        self.assertIn("font/woff2", headers["content-type"])
        self.assertGreater(len(body), 1000)

        status, headers, body = await self.http_get("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["content-type"])
        self.assertIn(b'font-family: "Press Start 2P"', body)

    async def test_path_traversal_is_denied(self) -> None:
        status, _, _ = await self.http_get("/../server.py")
        self.assertEqual(status, 403)

    async def test_websocket_join_and_cast(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            hello = await self.wait_for_type(reader, "hello")
            self.assertEqual(hello["server"], "Arcane 2D")

            await self.send_json(writer, {"t": "join", "name": "Тест"})
            welcome = await self.wait_for_type(reader, "welcome")
            self.assertEqual(welcome["name"], "Тест")
            self.assertIn("roll", welcome["config"])
            self.assertIn("chain_lightning", welcome["config"]["spell_costs"])
            self.assertIn("lightning_strike", welcome["config"]["spell_costs"])
            player_id = welcome["you"]
            self.assertIsInstance(player_id, int)

            state = await self.wait_for_type(reader, "state")
            ids = [player["id"] for player in state["players"]]
            self.assertIn(player_id, ids)

            await self.send_json(
                writer,
                {
                    "t": "cast",
                    "code": "fireball(aim())",
                    "slot": 0,
                    "aim": 0,
                },
            )
            result = await self.wait_for_type(reader, "cast_result")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["actions"], 1)

            await self.send_json(
                writer,
                {"t": "cast", "code": "log('later')", "slot": 0, "aim": 0},
            )
            cooling = await self.wait_for_type(reader, "cast_result")
            self.assertFalse(cooling["ok"])
            self.assertIn("перезаряжается", cooling["error"])

            player = self.app.arena.players[player_id]
            player.x, player.y = 700.0, 600.0
            await self.send_json(writer, {"t": "roll", "aim": 0})
            rolled = await self.wait_for_type(reader, "roll_result")
            self.assertTrue(rolled["ok"], rolled)
            self.assertAlmostEqual(player.x, 700.0 + 165.0, places=0)
            self.assertGreater(rolled["cooldown"], 0)

            await self.send_json(writer, {"t": "roll", "aim": 0})
            blocked = await self.wait_for_type(reader, "roll_result")
            self.assertFalse(blocked["ok"])
            self.assertIn("восстанавливается", blocked["error"])
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
            writer.transport.abort()

    async def test_bad_join_name_is_rejected(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            await self.wait_for_type(reader, "hello")
            await self.send_json(writer, {"t": "join", "name": "!"})
            error = await self.wait_for_type(reader, "join_error")
            self.assertIn("от 2 до 16", error["error"])
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
            writer.transport.abort()


class WebSocketCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_after_eof_releases_transport(self) -> None:
        class FakeWriter:
            def __init__(self) -> None:
                self.closed = False
                self.chunks: list[bytes] = []

            def is_closing(self) -> bool:
                return self.closed

            def write(self, data: bytes) -> None:
                self.chunks.append(data)

            async def drain(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

            async def wait_closed(self) -> None:
                pass

        writer = FakeWriter()
        websocket = WebSocket(
            asyncio.StreamReader(), writer  # type: ignore[arg-type]
        )
        websocket.closed = True  # the read loop saw EOF before close() was called
        await websocket.close()
        self.assertTrue(writer.closed)
        await websocket.close()
        self.assertTrue(writer.closed)


class NameSanitisingTests(unittest.TestCase):
    def test_clean_name(self) -> None:
        self.assertEqual(clean_name("  <Маг>  "), "Маг")
        self.assertEqual(clean_name("Маг\nОгня"), "Маг Огня")
        self.assertIsNone(clean_name("!"))
        self.assertIsNone(clean_name(42))
        self.assertEqual(len(clean_name("я" * 40)), 16)


if __name__ == "__main__":
    unittest.main()
