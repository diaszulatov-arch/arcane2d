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
from server import (
    MAX_CHECKS_PER_SECOND,
    MAX_CLIENT_BACKLOG,
    MAX_STALL_SECONDS,
    ArcaneServer,
    Client,
    clean_name,
)


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

    async def test_head_answers_once_with_the_real_length(self) -> None:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"HEAD /app.js HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=3)
        writer.close()
        with contextlib.suppress(ConnectionError):
            await writer.wait_closed()
        self.assertEqual(raw.count(b"HTTP/1.1"), 1, raw)
        head, _, body = raw.partition(b"\r\n\r\n")
        self.assertEqual(body, b"")
        _, headers, full = await self.http_get("/app.js")
        self.assertIn(f"Content-Length: {len(full)}".encode(), head)
        self.assertEqual(headers["content-length"], str(len(full)))

    async def test_a_visitor_watches_the_arena_before_joining(self) -> None:
        self.app.arena.add_player("Гость")
        reader, writer = await self.ws_connect()
        try:
            await self.wait_for_type(reader, "hello")
            state = await self.wait_for_type(reader, "state")
            self.assertEqual(state["players"][0]["name"], "Гость")
        finally:
            writer.close()

    async def test_ping_echoes_the_client_clock(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            await self.send_json(writer, {"t": "ping", "at": 1234.5})
            self.assertEqual((await self.wait_for_type(reader, "pong"))["at"], 1234.5)
        finally:
            writer.close()

    async def test_check_reads_a_spell_without_casting_it(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            await self.send_json(
                writer, {"t": "check", "slot": 1, "ticket": 7, "code": "fireball(0)"}
            )
            good = await self.wait_for_type(reader, "check_result")
            self.assertTrue(good["ok"])
            self.assertEqual((good["slot"], good["ticket"]), (1, 7))
            self.assertEqual(good["cost"], [11, 11])

            await self.send_json(
                writer, {"t": "check", "slot": 0, "ticket": 8, "code": "x = 1\nimport os"}
            )
            bad = await self.wait_for_type(reader, "check_result")
            self.assertFalse(bad["ok"])
            self.assertTrue(bad["error"].startswith("Строка 2:"), bad["error"])
        finally:
            writer.close()

    async def test_check_cannot_be_used_to_hammer_the_parser(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            for ticket in range(MAX_CHECKS_PER_SECOND + 4):
                await self.send_json(
                    writer, {"t": "check", "slot": 0, "ticket": ticket, "code": "x = 1"}
                )
            await self.send_json(writer, {"t": "ping", "at": 1})
            replies = 0
            while True:
                message = await self.read_json(reader)
                if message["t"] == "pong":
                    break
                replies += message["t"] == "check_result"
            self.assertEqual(replies, MAX_CHECKS_PER_SECOND)
        finally:
            writer.close()

    async def story_client(self, name: str, token: str):
        reader, writer = await self.ws_connect()
        await self.wait_for_type(reader, "hello")
        await self.send_json(writer, {"t": "profile", "token": token, "name": name})
        profile = await self.wait_for_type(reader, "profile")
        return reader, writer, profile

    async def test_two_mages_meet_by_code_and_enter_a_dungeon(self) -> None:
        reader_a, writer_a, profile = await self.story_client("Лидер", "a" * 32)
        reader_b, writer_b, _ = await self.story_client("Друг", "b" * 32)
        try:
            self.assertEqual(len(profile["lessons"]), 20)
            self.assertEqual(len(profile["campaign"]["stages"]), 20)

            await self.send_json(writer_a, {"t": "party_create"})
            party = await self.wait_for_type(reader_a, "party")
            self.assertTrue(party["leader"])

            await self.send_json(writer_b, {"t": "party_join", "code": party["code"].lower()})
            joined = await self.wait_for_type(reader_b, "party")
            self.assertEqual(len(joined["seats"]), 2)
            self.assertFalse(joined["leader"])

            for writer in (writer_a, writer_b):
                await self.send_json(writer, {"t": "party_ready", "ready": True})
            started = await self.wait_for_type(reader_a, "stage_start")
            self.assertEqual(started["config"]["mode"], "story")
            self.assertEqual(started["config"]["runes"], ["fireball"])
            self.assertTrue(started["you"])

            state = await self.wait_for_type(reader_a, "state")
            self.assertEqual(len(state["players"]), 2)
            self.assertIn("story", state)

            await self.send_json(writer_a, {"t": "cast", "code": "beam(0)", "slot": 0})
            result = await self.wait_for_type(reader_a, "cast_result")
            self.assertIn("не изучена", result["error"])
            self.assertEqual(self.app.arena.online_counts()["humans"], 0, "the arena stays apart")
        finally:
            writer_a.close()
            writer_b.close()

    async def test_a_cleared_stage_sends_everyone_back_to_camp_and_onward(self) -> None:
        reader, writer, _ = await self.story_client("Маг", "9" * 32)
        try:
            await self.send_json(writer, {"t": "party_create"})
            party = await self.wait_for_type(reader, "party")
            await self.send_json(writer, {"t": "party_ready", "ready": True})
            first = await self.wait_for_type(reader, "stage_start")
            self.app.parties[party["code"]].world.outcome = "cleared"
            ended = await self.wait_for_type(reader, "stage_end")
            self.assertEqual(ended["result"], "cleared")
            self.assertGreater(ended["profile"]["essence"], 0)
            self.assertEqual(ended["profile"]["cleared"], 1)
            camp = await self.wait_for_type(reader, "party")
            self.assertEqual(camp["stage"]["index"], 1)

            await self.send_json(writer, {"t": "party_ready", "ready": True})
            second = await self.wait_for_type(reader, "stage_start")
            self.assertEqual(second["stage"]["index"], 1)
            self.assertIn("frostbolt", second["config"]["runes"])
            self.assertNotEqual(first["config"]["map_id"], second["config"]["map_id"])
            cast = {"t": "cast", "code": "frostbolt(0)", "slot": 0}
            await self.send_json(writer, cast)
            self.assertTrue((await self.wait_for_type(reader, "cast_result"))["ok"])
        finally:
            writer.close()

    async def test_a_dropped_mage_walks_back_into_the_running_dungeon(self) -> None:
        reader_a, writer_a, _ = await self.story_client("Первый", "1" * 32)
        reader_b, writer_b, _ = await self.story_client("Второй", "2" * 32)
        try:
            await self.send_json(writer_a, {"t": "party_create"})
            party = await self.wait_for_type(reader_a, "party")
            await self.send_json(writer_b, {"t": "party_join", "code": party["code"]})
            await self.wait_for_type(reader_b, "party")
            for writer in (writer_a, writer_b):
                await self.send_json(writer, {"t": "party_ready", "ready": True})
            await self.wait_for_type(reader_b, "stage_start")

            writer_b.close()
            world = self.app.parties[party["code"]].world
            for _ in range(60):
                if len(world.players) == 1:
                    break
                await asyncio.sleep(0.02)
            self.assertEqual(len(world.players), 1)

            reader_c, writer_c, _ = await self.story_client("Второй", "2" * 32)
            await self.send_json(writer_c, {"t": "party_join", "code": party["code"]})
            back = await self.wait_for_type(reader_c, "stage_start")
            self.assertEqual(len(world.players), 2)
            self.assertTrue(back["you"])
            writer_c.close()
        finally:
            writer_a.close()

    async def test_a_wrong_party_code_is_explained(self) -> None:
        reader, writer, _ = await self.story_client("Маг", "c" * 32)
        try:
            await self.send_json(writer, {"t": "party_join", "code": "ZZZZ"})
            self.assertIn("кодом", (await self.wait_for_type(reader, "party_error"))["error"])
        finally:
            writer.close()

    async def test_story_messages_need_a_profile_first(self) -> None:
        reader, writer = await self.ws_connect()
        try:
            await self.send_json(writer, {"t": "party_create"})
            await self.send_json(writer, {"t": "ping", "at": 1})
            await self.wait_for_type(reader, "pong")
            self.assertEqual(self.app.parties, {})
        finally:
            writer.close()

    async def test_a_repair_goes_through_a_terminal_and_pays_once(self) -> None:
        reader, writer, _ = await self.story_client("Ученик", "d" * 32)
        try:
            await self.send_json(writer, {"t": "party_create"})
            party = await self.wait_for_type(reader, "party")
            await self.send_json(writer, {"t": "party_ready", "ready": True})
            start = await self.wait_for_type(reader, "stage_start")
            world = self.app.parties[party["code"]].world

            await self.send_json(writer, {"t": "terminal_open"})
            self.assertFalse((await self.wait_for_type(reader, "terminal_state"))["linked"])

            terminal = world.terminals[0]
            mage = world.players[start["you"]]
            mage.x, mage.y = terminal.x, terminal.y + 40
            await self.send_json(writer, {"t": "terminal_open"})
            state = await self.wait_for_type(reader, "terminal_state")
            self.assertTrue(state["linked"])
            self.assertEqual(state["task"], "call")

            await self.send_json(writer, {"t": "fix_submit", "code": "firebal(aim())"})
            self.assertFalse((await self.wait_for_type(reader, "fix_result"))["ok"])
            await self.send_json(writer, {"t": "fix_submit", "code": "fireball(aim())"})
            solved = await self.wait_for_type(reader, "fix_result")
            self.assertTrue(solved["ok"])
            self.assertGreater(solved["reward"], 0)
            self.assertIn("call", solved["profile"]["lessons"])
            self.assertTrue(world.portal_ready)
        finally:
            writer.close()

    async def test_a_terminal_ignores_junk(self) -> None:
        reader, writer, _ = await self.story_client("Шум", "f" * 32)
        try:
            await self.send_json(writer, {"t": "fix_submit", "code": "fireball(aim())"})
            await self.send_json(writer, {"t": "terminal_close"})
            await self.send_json(writer, {"t": "party_create"})
            await self.wait_for_type(reader, "party")
            await self.send_json(writer, {"t": "fix_submit", "code": 7})
            await self.send_json(writer, {"t": "terminal_open"})
            await self.send_json(writer, {"t": "ping", "at": 1})
            await self.wait_for_type(reader, "pong")
        finally:
            writer.close()

    async def test_help_is_rationed_by_the_server_and_answers_stay_on_it(self) -> None:
        reader, writer, profile = await self.story_client("Сеньор", "9" * 32)
        try:
            self.assertNotIn("fireball(aim())", json.dumps(profile["lessons"][0]["task"]))
            await self.send_json(writer, {"t": "party_create"})
            party = await self.wait_for_type(reader, "party")
            self.assertEqual(party["difficulty"], 1)
            await self.send_json(writer, {"t": "party_difficulty", "level": 3})
            await self.send_json(writer, {"t": "party_difficulty", "level": "3"})
            for _ in range(20):
                party = await self.wait_for_type(reader, "party")
                if party["difficulty"] == 3:
                    break
            self.assertEqual(party["difficulty"], 3)
            await self.send_json(writer, {"t": "party_ready", "ready": True})
            start = await self.wait_for_type(reader, "stage_start")
            self.assertEqual(start["config"]["difficulty"], 3)
            world = self.app.parties[party["code"]].world
            terminal = world.terminals[0]
            mage = world.players[start["you"]]
            mage.x, mage.y = terminal.x, terminal.y + 40
            await self.send_json(writer, {"t": "terminal_open"})
            state = await self.wait_for_type(reader, "terminal_state")
            self.assertEqual(state["help"], {"hints": 0, "solution": False, "theory": False})
            await self.send_json(writer, {"t": "terminal_help", "index": 0})
            self.assertEqual((await self.wait_for_type(reader, "terminal_help"))["kind"], "")
            await self.send_json(writer, {"t": "terminal_help", "index": "0"})
            await self.send_json(writer, {"t": "ping", "at": 1})
            await self.wait_for_type(reader, "pong")
        finally:
            writer.close()

    async def test_upgrades_spend_essence_on_the_server(self) -> None:
        reader, writer, _ = await self.story_client("Маг", "e" * 32)
        try:
            await self.send_json(writer, {"t": "upgrade", "stat": "max_hp"})
            refused = await self.wait_for_type(reader, "profile_update")
            self.assertIn("токенов", refused["error"])
            self.app.store.get("e" * 32).essence = 500
            await self.send_json(writer, {"t": "upgrade", "stat": "max_hp"})
            bought = await self.wait_for_type(reader, "profile_update")
            self.assertIsNone(bought["error"])
            self.assertEqual(bought["profile"]["upgrades"], {"max_hp": 1})
        finally:
            writer.close()

    async def test_arena_mages_never_see_a_party_and_party_mages_skip_the_arena(self) -> None:
        reader_story, writer_story, _ = await self.story_client("Сюжет", "f" * 32)
        reader_arena, writer_arena = await self.ws_connect()
        try:
            await self.send_json(writer_arena, {"t": "join", "name": "Арена"})
            await self.wait_for_type(reader_arena, "welcome")
            await self.send_json(writer_story, {"t": "party_create"})
            await self.wait_for_type(reader_story, "party")
            await self.send_json(writer_story, {"t": "party_ready", "ready": True})
            await self.wait_for_type(reader_story, "stage_start")
            story_state = await self.wait_for_type(reader_story, "state")
            self.assertEqual([p["name"] for p in story_state["players"]], ["Сюжет"])
            for _ in range(4):
                arena_state = await self.wait_for_type(reader_arena, "state")
            self.assertEqual([p["name"] for p in arena_state["players"]], ["Арена"])
            self.assertNotIn("monsters", arena_state)
        finally:
            writer_story.close()
            writer_arena.close()

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

    async def wait_for_bots(self, reader: asyncio.StreamReader, wanted: int) -> None:
        for _ in range(60):
            state = await self.wait_for_type(reader, "state")
            if state["stats"]["bots"] == wanted:
                return
        self.fail(f"the arena never settled on {wanted} spirits")

    async def test_spirits_go_when_a_second_person_joins_and_return_when_alone(self) -> None:
        self.app.arena.fill_to = 4
        reader_a, writer_a = await self.ws_connect()
        reader_b, writer_b = await self.ws_connect()
        try:
            await self.wait_for_type(reader_a, "hello")
            await self.wait_for_type(reader_b, "hello")
            await self.send_json(writer_a, {"t": "join", "name": "Первый"})
            await self.wait_for_type(reader_a, "welcome")
            await self.wait_for_bots(reader_a, 3)

            await self.send_json(writer_b, {"t": "join", "name": "Второй"})
            await self.wait_for_type(reader_b, "welcome")
            await self.wait_for_bots(reader_a, 0)

            writer_b.close()
            await self.wait_for_bots(reader_a, 3)
        finally:
            writer_a.close()
            writer_b.close()

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


class StubSocket:
    """A peer whose socket buffer we control, to play a slow connection."""

    def __init__(self, backlog: int = 0) -> None:
        self.backlog = backlog
        self.sent: list[dict] = []
        self.aborted = False
        self.last_seen = 0.0

    def send_text_nowait(self, text: str) -> bool:
        self.sent.append(json.loads(text))
        return True

    def abort(self) -> None:
        self.aborted = True


class SlowClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = ArcaneServer(bots=0)
        self.quick = Client(StubSocket())
        self.slow = Client(StubSocket())
        self.app.clients.update((self.quick, self.slow))

    def test_a_stuck_reader_is_skipped_and_others_still_get_the_tick(self) -> None:
        self.slow.ws.backlog = MAX_CLIENT_BACKLOG + 1
        self.app.broadcast(1.0, [{"e": "hit"}])
        self.assertEqual(len(self.quick.ws.sent), 1)
        self.assertEqual(self.slow.ws.sent, [])

    def test_a_reader_that_recovers_catches_up_on_missed_events(self) -> None:
        self.slow.ws.backlog = MAX_CLIENT_BACKLOG + 1
        self.app.broadcast(1.0, [{"e": "death", "id": 1}])
        self.app.broadcast(1.1, [{"e": "hit", "id": 2}])
        self.slow.ws.backlog = 0
        self.app.broadcast(1.2, [{"e": "respawn", "id": 1}])
        self.assertEqual(len(self.slow.ws.sent), 1)
        self.assertEqual(
            [event["e"] for event in self.slow.ws.sent[0]["events"]],
            ["death", "hit", "respawn"],
        )
        self.assertEqual([e["e"] for e in self.quick.ws.sent[-1]["events"]], ["respawn"])

    def test_a_reader_stuck_for_too_long_is_cut_off(self) -> None:
        player = self.app.arena.add_player("Тормоз")
        self.slow.player_id = player.id
        self.slow.ws.backlog = MAX_CLIENT_BACKLOG + 1
        self.app.broadcast(1.0, [])
        self.app.broadcast(1.0 + MAX_STALL_SECONDS + 0.1, [])
        self.assertTrue(self.slow.ws.aborted)
        self.assertNotIn(self.slow, self.app.clients)
        self.assertNotIn(player.id, self.app.arena.players)


class NameSanitisingTests(unittest.TestCase):
    def test_clean_name(self) -> None:
        self.assertEqual(clean_name("  <Маг>  "), "Маг")
        self.assertEqual(clean_name("Маг\nОгня"), "Маг Огня")
        self.assertIsNone(clean_name("!"))
        self.assertIsNone(clean_name(42))
        self.assertEqual(len(clean_name("я" * 40)), 16)


if __name__ == "__main__":
    unittest.main()
