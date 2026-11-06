#!/usr/bin/env python3
"""Arcane 2D — browser multiplayer mage arena with Python-written spells."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import mimetypes
import os
import re
import socket
import sys
import time
import webbrowser
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from arcane.campaign import describe_campaign
from arcane.game import SPELL_COSTS, TICK_RATE, Arena
from arcane.interpreter import SpellError, mana_estimate, validate_source
from arcane.lessons import GATES, LESSONS
from arcane.roles import SKILL_COSTS, describe_roles
from arcane.net import (
    ProtocolError,
    WebSocket,
    write_http_response,
)
from arcane.party import PLAYING, Party, new_code
from arcane.profiles import ProfileStore, describe_upgrades

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
SAVE_PATH = ROOT / "saves" / "profiles.json"
SAVE_INTERVAL = 5.0
MAX_TOKEN_CHARS = 64
MAX_FIXES_PER_SECOND = 3
MAX_CLIENTS = 24
MAX_JOIN_NAME = 16
MAX_CHECKS_PER_SECOND = 6
MAX_CLIENT_BACKLOG = 256 * 1024
MAX_STALL_SECONDS = 8.0
MAX_PENDING_EVENTS = 512
AUTO_FILL_MAGES = 4
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}
NAME_ALLOWED = re.compile(r"[^\w\s\-'.]", re.UNICODE)


STORY_MESSAGES = frozenset(
    {
        "profile",
        "party_create",
        "party_join",
        "party_leave",
        "party_ready",
        "party_stage",
        "party_difficulty",
        "upgrade",
        "role_pick",
        "terminal_open",
        "terminal_close",
        "terminal_help",
        "fix_submit",
    }
)


def clean_name(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    name = NAME_ALLOWED.sub("", raw)
    name = " ".join(name.split()).strip()
    if len(name) < 2:
        return None
    return name[:MAX_JOIN_NAME]


class Client:
    __slots__ = (
        "ws",
        "player_id",
        "connected_at",
        "message_times",
        "cast_times",
        "check_times",
        "fix_times",
        "pending_events",
        "stalled_since",
        "token",
        "name",
        "party",
    )

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.player_id: int | None = None
        self.connected_at = time.monotonic()
        self.message_times: deque[float] = deque()
        self.cast_times: deque[float] = deque()
        self.check_times: deque[float] = deque()
        self.fix_times: deque[float] = deque()
        self.token: str | None = None
        self.name: str | None = None
        self.party: Party | None = None
        # Events survive a skipped snapshot: positions go stale, but a missed
        # death or explosion would simply never be shown.
        self.pending_events: deque[dict[str, Any]] = deque(maxlen=MAX_PENDING_EVENTS)
        self.stalled_since: float | None = None

    @property
    def joined(self) -> bool:
        return self.player_id is not None


class ArcaneServer:
    def __init__(
        self, *, bots: int, fill_to: int = 0, save_path: Path | None = None
    ) -> None:
        self.arena = Arena(bots=bots, fill_to=fill_to)
        self.clients: set[Client] = set()
        self.started_at = time.monotonic()
        self.store = ProfileStore(save_path)
        self.parties: dict[str, Party] = {}
        self.saved_at = 0.0

    # ------------------------------------------------------------------ HTTP
    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        websocket: WebSocket | None = None
        try:
            try:
                raw_head = await asyncio.wait_for(
                    reader.readuntil(b"\r\n\r\n"), timeout=12.0
                )
            except (
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
                ConnectionError,
            ):
                return
            if len(raw_head) > 32 * 1024:
                await write_http_response(writer, 413, b"too large")
                return
            try:
                lines = raw_head.decode("latin-1").split("\r\n")
                method, target, _version = lines[0].split(" ", 2)
            except (UnicodeDecodeError, ValueError):
                await write_http_response(writer, 400, b"bad request")
                return
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if not line:
                    continue
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
            path = unquote(urlsplit(target).path)

            upgrade = headers.get("upgrade", "").lower()
            if upgrade == "websocket":
                if method != "GET" or path != "/ws":
                    await write_http_response(writer, 404, b"websocket endpoint: /ws")
                    return
                key = headers.get("sec-websocket-key")
                version = headers.get("sec-websocket-version")
                if not key or version != "13":
                    await write_http_response(
                        writer,
                        426,
                        b"websocket version 13 required",
                        extra_headers={"Sec-WebSocket-Version": "13"},
                    )
                    return
                websocket = WebSocket(reader, writer)
                await websocket.handshake(key)
                await self.handle_websocket(websocket)
                return

            if path == "/health":
                snapshot = self.arena.snapshot()
                body = json.dumps(
                    {
                        "ok": True,
                        "uptime": round(time.monotonic() - self.started_at, 1),
                        "players": snapshot["stats"],
                        "projectiles": len(self.arena.projectiles),
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                await write_http_response(
                    writer,
                    200,
                    body,
                    content_type="application/json; charset=utf-8",
                )
                return
            if path == "/api/world":
                body = json.dumps(
                    self.arena.world_config(), ensure_ascii=False
                ).encode("utf-8")
                await write_http_response(
                    writer,
                    200,
                    body,
                    content_type="application/json; charset=utf-8",
                )
                return
            await self.serve_static(writer, method, path)
        except asyncio.CancelledError:
            raise
        except ProtocolError:
            pass
        except (ConnectionError, OSError, RuntimeError):
            pass
        except Exception:
            try:
                await write_http_response(writer, 500, b"internal server error")
            except Exception:
                pass
        finally:
            if websocket is not None:
                await websocket.close()
            else:
                try:
                    writer.close()
                    await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
                except (ConnectionError, RuntimeError, asyncio.TimeoutError):
                    pass
                except asyncio.CancelledError:
                    pass

    async def serve_static(
        self, writer: asyncio.StreamWriter, method: str, path: str
    ) -> None:
        if method not in ("GET", "HEAD"):
            await write_http_response(
                writer, 405, "только GET".encode(), extra_headers={"Allow": "GET, HEAD"}
            )
            return
        relative = path.lstrip("/") or "index.html"
        if not relative or "\x00" in relative:
            await write_http_response(writer, 404, "не найдено".encode())
            return
        try:
            candidate = (PUBLIC_DIR / relative).resolve()
            candidate.relative_to(PUBLIC_DIR.resolve())
        except (ValueError, OSError):
            await write_http_response(writer, 403, "доступ закрыт".encode())
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            await write_http_response(writer, 404, "страница не найдена".encode())
            return
        try:
            content = candidate.read_bytes()
        except OSError:
            await write_http_response(writer, 404, "страница не найдена".encode())
            return
        content_type = STATIC_TYPES.get(
            candidate.suffix.lower(),
            mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )
        extra_headers = {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
        if candidate.suffix.lower() == ".html":
            extra_headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self' ws: wss:; font-src 'self'"
            )
        await write_http_response(
            writer,
            200,
            content,
            content_type=content_type,
            extra_headers=extra_headers,
            head_only=method == "HEAD",
        )

    # ------------------------------------------------------------- websocket
    async def handle_websocket(self, ws: WebSocket) -> None:
        client = Client(ws)
        if len(self.clients) >= MAX_CLIENTS:
            await ws.send_json(
                {"t": "fatal", "error": "Арена переполнена. Попробуйте позже."}
            )
            await ws.close(1013, "arena full")
            return
        self.clients.add(client)
        counts = self.arena.online_counts()
        await ws.send_json(
            {
                "t": "hello",
                "server": "Arcane 2D",
                "online": counts["humans"],
                "bots": counts["bots"],
                "config": {
                    "name": "Arcane 2D",
                    "cast_lock": 0.72,
                },
            }
        )

        try:
            while True:
                text = await ws.read_message()
                if text is None:
                    break
                now = asyncio.get_running_loop().time()
                while client.message_times and now - client.message_times[0] > 1.0:
                    client.message_times.popleft()
                if len(client.message_times) >= 140:
                    await ws.close(1008, "rate limit")
                    break
                client.message_times.append(now)
                try:
                    message = json.loads(text)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    await ws.send_json({"t": "notice", "text": "Некорректный пакет."})
                    continue
                if not isinstance(message, dict):
                    continue
                await self.handle_message(client, message)
                if ws.closed:
                    break
        finally:
            self.clients.discard(client)
            self.release(client)
            await ws.close()

    def release(self, client: Client) -> None:
        """Take a departing client out of wherever they were playing."""

        if client.party is not None and client.token is not None:
            client.party.disconnect(client.token, asyncio.get_running_loop().time())
            client.party = None
            client.player_id = None
        elif client.player_id is not None:
            self.arena.remove_player(client.player_id)
            client.player_id = None

    def world_of(self, client: Client) -> Arena | None:
        """The simulation this client's mage lives in, if it is in one right now."""

        if client.party is not None:
            return client.party.world
        return self.arena

    async def handle_message(self, client: Client, message: dict[str, Any]) -> None:
        kind = message.get("t")
        if kind == "join":
            await self.handle_join(client, message)
            return
        if kind in STORY_MESSAGES:
            await self.handle_story(client, kind, message)
            return
        if kind == "input":
            world = self.world_of(client)
            if world is None or client.player_id is None:
                return
            up = message.get("up") is True
            down = message.get("down") is True
            left = message.get("left") is True
            right = message.get("right") is True
            aim: float | None = None
            raw_aim = message.get("aim")
            if type(raw_aim) in (int, float):
                candidate = float(raw_aim)
                if math.isfinite(candidate):
                    aim = candidate
            world.set_input(
                client.player_id, up=up, down=down, left=left, right=right, aim=aim
            )
            return
        if kind == "roll":
            world = self.world_of(client)
            if world is None or client.player_id is None:
                return
            raw_aim = message.get("aim")
            roll_aim: float | None = None
            if type(raw_aim) in (int, float) and math.isfinite(float(raw_aim)):
                roll_aim = float(raw_aim)
            result = world.roll(client.player_id, aim=roll_aim)
            result["t"] = "roll_result"
            await client.ws.send_json(result)
            return
        if kind == "cast":
            await self.handle_cast(client, message)
            return
        if kind == "check":
            await self.handle_check(client, message)
            return
        if kind == "ping":
            reply: dict[str, Any] = {"t": "pong"}
            sent_at = message.get("at")
            if type(sent_at) in (int, float):
                reply["at"] = sent_at
            await client.ws.send_json(reply)

    async def handle_check(self, client: Client, message: dict[str, Any]) -> None:
        """Parse a spell for the editor, without casting anything."""

        code = message.get("code")
        slot = message.get("slot")
        if not isinstance(code, str) or type(slot) is not int:
            return
        now = asyncio.get_running_loop().time()
        while client.check_times and now - client.check_times[0] > 1.0:
            client.check_times.popleft()
        if len(client.check_times) >= MAX_CHECKS_PER_SECOND:
            return
        client.check_times.append(now)
        ticket = message.get("ticket")
        reply: dict[str, Any] = {
            "t": "check_result",
            "slot": slot,
            "ticket": ticket if type(ticket) is int else None,
        }
        try:
            costs = {**SPELL_COSTS, **SKILL_COSTS} if client.party else SPELL_COSTS
            low, high = mana_estimate(validate_source(code), costs)
        except SpellError as exc:
            reply.update(ok=False, error=str(exc))
        else:
            reply.update(ok=True, cost=[low, high])
        await client.ws.send_json(reply)

    # ------------------------------------------------------------------- story
    async def handle_story(
        self, client: Client, kind: str, message: dict[str, Any]
    ) -> None:
        if kind == "profile":
            await self.handle_profile(client, message)
            return
        if client.token is None:
            return
        if kind == "party_create":
            await self.enter_party(client, self.create_party())
        elif kind == "party_join":
            code = str(message.get("code", "")).strip().upper()[:8]
            party = self.parties.get(code)
            if party is None:
                await client.ws.send_json(
                    {"t": "party_error", "error": "Группы с таким кодом нет."}
                )
                return
            await self.enter_party(client, party)
        elif kind == "upgrade":
            await self.handle_upgrade(client, message)
        elif client.party is not None:
            await self.handle_party_action(client, kind, message)

    async def handle_profile(self, client: Client, message: dict[str, Any]) -> None:
        token = message.get("token")
        name = clean_name(message.get("name"))
        if (
            not isinstance(token, str)
            or not 16 <= len(token) <= MAX_TOKEN_CHARS
            or name is None
        ):
            await client.ws.send_json(
                {"t": "party_error", "error": "Имя должно содержать от 2 до 16 букв, цифр или пробелов."}
            )
            return
        client.token = token
        client.name = name
        await client.ws.send_json(
            {
                "t": "profile",
                "name": name,
                "profile": self.store.get(token).describe(),
                "campaign": describe_campaign(),
                "lessons": [lesson.describe() for lesson in LESSONS],
                "gates": {
                    task.key: task.describe() for pair in GATES.values() for task in pair
                },
                "roles": describe_roles(),
                "upgrades": describe_upgrades(),
            }
        )

    def create_party(self) -> Party:
        party = Party(new_code(self.parties), self.store)
        self.parties[party.code] = party
        return party

    async def enter_party(self, client: Client, party: Party) -> None:
        if client.party is party:
            return
        if client.player_id is not None:
            self.arena.remove_player(client.player_id)
            client.player_id = None
        if client.party is not None:
            client.party.leave(client.token)
        seat, error = party.join(client.token, client.name)
        if error is not None:
            client.party = None
            await client.ws.send_json({"t": "party_error", "error": error})
            return
        client.party = party
        await client.ws.send_json(party.describe(client.token))
        if party.state == PLAYING and party.world is not None:
            party.place(seat)
            client.player_id = seat.player_id
            await client.ws.send_json(
                {
                    "t": "stage_start",
                    "stage": party.world.stage.describe(),
                    "config": party.world.world_config(),
                    "you": seat.player_id,
                }
            )

    async def handle_party_action(
        self, client: Client, kind: str, message: dict[str, Any]
    ) -> None:
        party = client.party
        now = asyncio.get_running_loop().time()
        if kind == "party_leave":
            party.leave(client.token)
            client.party = None
            client.player_id = None
            await client.ws.send_json({"t": "party_left"})
        elif kind == "role_pick":
            error = party.pick_role(client.token, str(message.get("role", "")))
            await client.ws.send_json(
                {
                    "t": "profile_update",
                    "profile": self.store.get(client.token).describe(),
                    "error": error,
                }
            )
        elif kind == "terminal_open":
            if party.world is not None and client.player_id is not None:
                terminal, error = party.world.link(client.player_id)
                await client.ws.send_json(
                    {
                        "t": "terminal_state",
                        "linked": terminal is not None,
                        "task": terminal.task.key if terminal else None,
                        "role": terminal.role if terminal else None,
                        "help": party.world.help_plan(),
                        "error": error,
                    }
                )
        elif kind == "terminal_close":
            if party.world is not None and client.player_id is not None:
                party.world.unlink(client.player_id)
        elif kind == "terminal_help":
            index = message.get("index")
            if party.world is not None and client.player_id is not None and type(index) is int:
                step = party.world.terminal_help(client.player_id, index)
                await client.ws.send_json({"t": "terminal_help", **step})
        elif kind == "fix_submit":
            await self.handle_fix(client, party, message)
        elif kind == "party_ready":
            party.set_ready(client.token, message.get("ready") is True, now)
        elif kind == "party_stage":
            stage = message.get("stage")
            if type(stage) is int:
                error = party.choose_stage(client.token, stage)
                if error:
                    await client.ws.send_json({"t": "party_error", "error": error})
        elif kind == "party_difficulty":
            level = message.get("level")
            if type(level) is int:
                error = party.choose_difficulty(client.token, level)
                if error:
                    await client.ws.send_json({"t": "party_error", "error": error})

    async def handle_upgrade(self, client: Client, message: dict[str, Any]) -> None:
        profile = self.store.get(client.token)
        error = profile.buy(str(message.get("stat", "")))
        if error is None:
            self.store.mark()
        await client.ws.send_json(
            {"t": "profile_update", "profile": profile.describe(), "error": error}
        )

    async def handle_fix(
        self, client: Client, party: Party, message: dict[str, Any]
    ) -> None:
        code = message.get("code")
        if party.world is None or client.player_id is None or not isinstance(code, str):
            return
        now = asyncio.get_running_loop().time()
        while client.fix_times and now - client.fix_times[0] > 1.0:
            client.fix_times.popleft()
        if len(client.fix_times) >= MAX_FIXES_PER_SECOND:
            return
        client.fix_times.append(now)
        result = party.world.submit_fix(client.player_id, code)
        reply: dict[str, Any] = {"t": "fix_result", **result}
        if result["ok"]:
            reply["reward"] = party.reward_fix(client.token, result["task"])
            reply["profile"] = self.store.get(client.token).describe()
        await client.ws.send_json(reply)

    async def handle_join(self, client: Client, message: dict[str, Any]) -> None:
        if client.joined:
            await client.ws.send_json(
                {"t": "join_error", "error": "Вы уже вошли на арену."}
            )
            return
        name = clean_name(message.get("name"))
        if not name:
            await client.ws.send_json(
                {
                    "t": "join_error",
                    "error": "Имя должно содержать от 2 до 16 букв, цифр или пробелов.",
                }
            )
            return
        if client.party is not None:
            client.party.leave(client.token)
            client.party = None
        humans = sum(
            1
            for c in self.clients
            if c.joined and c is not client
        )
        if humans + 1 > MAX_CLIENTS:
            await client.ws.send_json(
                {"t": "join_error", "error": "На арене нет свободных мест."}
            )
            return
        player = self.arena.add_player(name)
        client.player_id = player.id
        await client.ws.send_json(
            {
                "t": "welcome",
                "you": player.id,
                "name": player.name,
                "color": player.color,
                "config": self.arena.world_config(),
                "online": self.arena.online_counts(),
            }
        )
        await client.ws.send_json(self.arena.snapshot())
        await client.ws.send_json(
            {
                "t": "notice",
                "text": f"Добро пожаловать на арену, {player.name}.",
                "kind": "welcome",
            }
        )

    async def handle_cast(self, client: Client, message: dict[str, Any]) -> None:
        world = self.world_of(client)
        if world is None or client.player_id is None:
            return
        now = asyncio.get_running_loop().time()
        while client.cast_times and now - client.cast_times[0] > 2.0:
            client.cast_times.popleft()
        if len(client.cast_times) >= 7:
            await client.ws.send_json(
                {
                    "t": "cast_result",
                    "ok": False,
                    "error": "Слишком часто. Дайте гримуару остыть.",
                    "slot": int(message.get("slot", 0))
                    if type(message.get("slot")) is int
                    else 0,
                }
            )
            return
        client.cast_times.append(now)
        code = message.get("code")
        slot = message.get("slot", 0)
        slot = slot if type(slot) is int and 0 <= slot <= 2 else 0
        aim = message.get("aim")
        if code is not None and not isinstance(code, str):
            result = {"ok": False, "error": "Код заклинания должен быть текстом."}
        elif code is not None and len(code) > 12_000:
            result = {"ok": False, "error": "Слишком длинное заклинание."}
        else:
            aim_value: float | None = None
            if type(aim) in (int, float) and math.isfinite(float(aim)):
                aim_value = float(aim)
            target_x: float | None = None
            target_y: float | None = None
            raw_target_x = message.get("target_x")
            raw_target_y = message.get("target_y")
            if type(raw_target_x) in (int, float) and type(raw_target_y) in (int, float):
                candidate_x = float(raw_target_x)
                candidate_y = float(raw_target_y)
                if math.isfinite(candidate_x) and math.isfinite(candidate_y):
                    target_x = candidate_x
                    target_y = candidate_y
            result = world.cast(
                client.player_id,
                code if isinstance(code, str) else "",
                slot,
                aim_value,
                target_x,
                target_y,
            )
        result["t"] = "cast_result"
        result["slot"] = slot
        await client.ws.send_json(result)

    # -------------------------------------------------------------- game loop
    def drop_client(self, client: Client) -> None:
        self.clients.discard(client)
        self.release(client)
        client.ws.abort()

    def broadcast(self, now: float, events: list[dict[str, Any]]) -> None:
        """Send one tick to everyone, never waiting on any single reader.

        People on the login screen get it too: they watch the arena live
        behind the form, which is also why it runs with no one joined.
        """

        self.send_world(self.arena, [c for c in self.clients if c.party is None], now, events)

    def send_world(
        self,
        world: Arena,
        readers: list[Client],
        now: float,
        events: list[dict[str, Any]],
    ) -> None:
        snapshot = world.snapshot()
        snapshot["events"] = events
        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        for client in readers:
            if client.ws.backlog > MAX_CLIENT_BACKLOG:
                client.pending_events.extend(events)
                if client.stalled_since is None:
                    client.stalled_since = now
                elif now - client.stalled_since > MAX_STALL_SECONDS:
                    self.drop_client(client)
                continue
            client.stalled_since = None
            if client.pending_events:
                caught_up = {
                    **snapshot,
                    "events": [*client.pending_events, *events],
                }
                client.pending_events.clear()
                client.ws.send_text_nowait(
                    json.dumps(caught_up, ensure_ascii=False, separators=(",", ":"))
                )
            elif not client.ws.send_text_nowait(payload):
                self.drop_client(client)

    def party_members(self, party: Party) -> list[Client]:
        return [client for client in self.clients if client.party is party]

    def update_parties(self, now: float) -> None:
        for party in list(self.parties.values()):
            party.tick(now)
            members = self.party_members(party)
            for message in party.outbox:
                self.deliver(party, members, message)
            party.outbox.clear()
            if party.world is not None:
                self.send_world(party.world, members, now, party.world.drain_events())
            if party.changed:
                party.changed = False
                for client in members:
                    client.ws.send_text_nowait(
                        json.dumps(
                            party.describe(client.token),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
            if party.expired(now):
                del self.parties[party.code]

    def deliver(self, party: Party, members: list[Client], message: dict[str, Any]) -> None:
        for client in members:
            seat = party.seat_of(client.token)
            if seat is None:
                continue
            client.player_id = seat.player_id
            personal = {**message, "you": seat.player_id}
            if message["t"] == "stage_start" and party.world is not None:
                mage = party.world.players.get(seat.player_id)
                personal["role"] = mage.role if mage else ""
            if message["t"] == "stage_end":
                personal["profile"] = self.store.get(client.token).describe()
                personal["essence"] = party.rewards.get(client.token, message["essence"])
            client.ws.send_text_nowait(
                json.dumps(personal, ensure_ascii=False, separators=(",", ":"))
            )

    async def game_loop(self) -> None:
        tick = 1.0 / TICK_RATE
        next_tick = asyncio.get_running_loop().time()
        last_ping = next_tick
        while True:
            now = asyncio.get_running_loop().time()
            self.arena.update(now)
            events = self.arena.drain_events()
            self.update_parties(now)
            if now - self.saved_at > SAVE_INTERVAL:
                self.saved_at = now
                self.store.save()
            if self.clients:
                self.broadcast(now, events)
                if now - last_ping > 20.0:
                    last_ping = now
                    for client in list(self.clients):
                        client.ws.send_ping_nowait()

            timeout_threshold = 60.0
            for client in list(self.clients):
                if now - client.ws.last_seen > timeout_threshold:
                    self.drop_client(client)

            next_tick += tick
            delay = next_tick - asyncio.get_running_loop().time()
            if delay < -0.5:
                next_tick = asyncio.get_running_loop().time()
                delay = 0
            await asyncio.sleep(max(0.0, delay))

    async def shutdown(self) -> None:
        self.store.save()
        for client in list(self.clients):
            await client.ws.close(1001, "server shutdown")
        self.clients.clear()


def bots_setting(raw: str) -> int | None:
    """A fixed number of spirits, or None for ``auto``."""

    text = raw.strip().lower()
    if text == "auto":
        return None
    try:
        return max(0, min(6, int(text)))
    except ValueError:
        raise argparse.ArgumentTypeError("ожидается число или auto") from None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arcane 2D — онлайн-арена магов, заклинания на Python."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ARCANE_HOST", "0.0.0.0"),
        help="интерфейс сервера (по умолчанию 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="порт (по умолчанию 8000)",
    )
    parser.add_argument(
        "--bots",
        type=bots_setting,
        default=os.environ.get("ARCANE_BOTS", "auto"),
        help=(
            "маги-духи: число 0..6 или auto, чтобы на арене "
            f"было {AUTO_FILL_MAGES} мага с учётом людей (по умолчанию auto). "
            "Как только на арене двое людей, духи уходят"
        ),
    )
    parser.add_argument(
        "--saves",
        type=Path,
        default=Path(os.environ.get("ARCANE_SAVES", SAVE_PATH)),
        help="файл с прогрессом сюжета (по умолчанию saves/profiles.json)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        default=os.environ.get("ARCANE_NO_BROWSER", "") == "1",
        help="не открывать браузер автоматически",
    )
    return parser.parse_args(argv)


def local_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except OSError:
        return None


def should_open_browser() -> bool:
    if os.environ.get("ARCANE_NO_BROWSER") == "1":
        return False
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


async def main(args: argparse.Namespace) -> None:
    auto_bots = args.bots is None
    bots = 0 if auto_bots else args.bots
    app = ArcaneServer(
        bots=bots,
        fill_to=AUTO_FILL_MAGES if auto_bots else 0,
        save_path=args.saves,
    )
    try:
        server = await asyncio.start_server(
            app.handle_connection,
            args.host,
            args.port,
            limit=256 * 1024,
        )
    except OSError as exc:
        print(f"Не удалось открыть порт {args.port}: {exc}", file=sys.stderr)
        print("Попробуйте: python3 server.py --port 8080", file=sys.stderr)
        return

    local_url = f"http://127.0.0.1:{args.port}"
    net_ip = local_ip() if args.host in ("0.0.0.0", "::") else None
    print()
    print("  \033[38;5;183m✦  A R C A N E   2 D  ✦\033[0m")
    print("  Арена магов · заклинания на Python")
    print()
    print(f"  Локально:   \033[36m{local_url}\033[0m")
    if net_ip:
        print(f"  В сети:     http://{net_ip}:{args.port}")
    bots_label = f"авто, до {AUTO_FILL_MAGES} магов на арене" if auto_bots else str(bots)
    print(f"  Духов:      {bots_label}   ·   порт {args.port}")
    print("  Остановка:  Ctrl+C")
    print()

    game_task = asyncio.create_task(app.game_loop(), name="arcane-game-loop")
    if not args.no_open and should_open_browser():
        try:
            asyncio.get_running_loop().call_later(0.8, webbrowser.open, local_url)
        except Exception:
            pass
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        game_task.cancel()
        try:
            await game_task
        except asyncio.CancelledError:
            pass
        await app.shutdown()
        server.close()
        await server.wait_closed()
        print("\nАрена растворяется в тумане. До встречи, маг.")


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        pass
