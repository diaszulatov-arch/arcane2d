"""The small games a quest can be: each one works the way its technology does.

A balancer really is a matter of where the traffic goes, a rate limit really
is a bucket of tokens, a memory leak really does eat the floor from under you.
Each game has a ``_begin_``, a ``_tick_``, and optionally ``_bar_``, ``_marks_``,
``_view_`` and ``_aim_`` methods, found by the name of the step's kind.  They all
stop when nobody is in the room: the problem waits for the party to come back.
"""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING, Any

from .dungeon import FLOOR, TILE, Room
from .game import Player
from .quest_data import (
    COMPOSE_GRAPHS,
    CONFLICTS,
    FAILED_TESTS,
    HAM_LETTERS,
    PEOPLE_ONLINE,
    QUEST_TASKS,
    SPAM_LETTERS,
    Step,
)

if TYPE_CHECKING:
    from .monsters import Monster
    from .quests import QuestUnit, StageQuest, Thing

NS_REACH = 96.0
NS_SPACING = 190.0
NS_REMIND = 9.0
RING = 300.0

BALANCE_RATE = 15.0
BALANCE_MAX_RATE = 17.5
BALANCE_PER_CORE = 3.0
BALANCE_REACH = 84.0
BALANCE_CRASH = 6.0
BALANCE_SETBACK = 0.15

BUCKET_BOT_EVERY = 0.95
BUCKET_PERSON_EVERY = 4.0
BUCKET_PERSON_SPEED = 74.0
BUCKET_ARRIVES = 48.0

LEAK_EVERY = 1.3
LEAK_SPEED = 62.0
LEAK_BAD_SHARE = 0.3
LEAK_MAX_LOOSE = 14
LEAK_REACH = 48.0
LEAK_NEED_PER_MAGE = 2

COMPOSE_REACH = 92.0
CHOICE_REACH = 80.0
CHOICE_SPREAD = 300.0
CHOICE_ZAP = 8.0

RACK_START = 50.0
RACK_LIMIT = 100.0
RACK_COOL = 26.0
RACK_FIRE = 6.0
RACK_RISE = 2.3
RACK_SETBACK = 0.12
RACK_AFTER_FIRE = 65.0
RACK_BLAST = 170.0
RACK_BLAST_DAMAGE = 16.0
FIRE_KINDS = frozenset({"fire", "meteor", "lightning"})

MEMORY_CELL = 2
MEMORY_BITE = 0.5
MEMORY_DAMAGE = 3.5
MEMORY_OOM = 30.0

CART_SPEED = 92.0
CART_REACH = 260.0
CART_SETBACK = 0.2
CART_STOPS = ((0.36, "test"), (0.7, "review"))
CART_BLAST = 22.0
CART_TESTS = 3

MAIL_SPAM_SHARE = 0.55
MAIL_MAX_LOOSE = 12


class QuestGames:
    """Mixed into ``StageQuest``: it brings the arena, the room and the helpers."""

    def _engaged(self: "StageQuest") -> bool:
        return bool(self.quest_room is not None and self._inside(self.quest_room))

    def _harass(self: "StageQuest", step: Step, now: float) -> None:
        """A few ordinary bugs now and then, so nobody gets to just stand and think."""

        harass = step.opts.get("harass")
        if not harass or len(self.arena.monsters) > 16:
            return
        due = self.state.setdefault("harass_at", now + float(harass[0]))
        if now < due:
            return
        self.state["harass_at"] = now + float(harass[0]) * self.arena.difficulty.tempo
        self._pack(self.quest_room, float(harass[1]))

    def _mark_device(self: "StageQuest") -> list[tuple[float, float, int]]:
        return [(self.device.x, self.device.y, self.quest_room.index)]

    def _wall_point(self: "StageQuest", room: Room, inset: float = 1.6) -> tuple[float, float]:
        """A spot along one of the room's walls, for whatever comes in from outside."""

        left, right = (room.x + inset) * TILE, (room.x + room.w - inset) * TILE
        top, bottom = (room.y + inset) * TILE, (room.y + room.h - inset) * TILE
        for _ in range(20):
            along = self.rng.uniform(0.1, 0.9)
            side = self.rng.randrange(4)
            if side == 0:
                x, y = left + (right - left) * along, top
            elif side == 1:
                x, y = left + (right - left) * along, bottom
            elif side == 2:
                x, y = left, top + (bottom - top) * along
            else:
                x, y = right, top + (bottom - top) * along
            if self.arena.can_stand(x, y, 22.0):
                return x, y
        return room.center

    def _quiet_remove(self: "StageQuest", monster: "Monster") -> None:
        """Off the field with no explosion: a letter delivered is not a kill."""

        self.arena.monsters.pop(monster.id, None)
        monster.dead = True

    def _tagged(self: "StageQuest", tag: str) -> list["Monster"]:
        return [monster for monster in self.arena.monsters.values() if monster.quest == tag]

    # ---------------------------------------------------- DNS: walk the chain
    def _begin_resolve(self: "StageQuest", step: Step) -> None:
        chain = step.opts["chain"]
        rooms = [room for _, room in self._rooms(step.at, len(chain) * 2)]
        self.rng.shuffle(rooms)
        servers: list[Thing] = []
        for hop, (real, fake, _) in enumerate(chain):
            for offset, (label, forged) in enumerate(((real, False), (fake, True))):
                x, y = self._apart_spot(rooms[hop * 2 + offset], servers)
                servers.append(
                    self._add(
                        "ns", x, y, rooms[hop * 2 + offset], label=label,
                        data={"hop": hop, "forged": forged, "told": -100.0},
                    )
                )
        x, y = self.arena.dungeon.rooms[0].center
        npc = self._add_unit("request", str(step.opts["npc"]), x + 120, y + 90, 60.0, 16.0)
        self.state.update(servers=servers, hop=0, chain=chain, npc=npc, fmt={"next": chain[0][0]})

    def _apart_spot(self: "StageQuest", room: Room, others: list["Thing"]) -> tuple[float, float]:
        spot = self._spot(room, 40.0)
        for _ in range(30):
            if all(math.hypot(o.x - spot[0], o.y - spot[1]) >= NS_SPACING for o in others):
                break
            spot = self._spot(room, 40.0)
        return spot

    def _tick_resolve(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        state = self.state
        for server in state["servers"]:
            if server.on or server.gone or self._toucher(server.x, server.y, NS_REACH) is None:
                continue
            if server.data["forged"]:
                self._forged_server(step, server)
            elif server.data["hop"] == state["hop"]:
                self._next_hop(step, server)
                return
            elif now - server.data["told"] > NS_REMIND:
                server.data["told"] = now
                wanted = state["chain"][state["hop"]][0]
                self._say(((step.opts["npc"], f"Этот ответит позже. Сначала нужен {wanted}."),))

    def _forged_server(self: "StageQuest", step: Step, server: "Thing") -> None:
        server.on = True
        server.bad = True
        self.arena.emit({"e": "ns_forged", "x": round(server.x, 1), "y": round(server.y, 1)})
        self._pack(self.arena.dungeon.rooms[server.room], 0.35, near=(server.x, server.y))
        self._say(step.fail, urgent=True)

    def _next_hop(self: "StageQuest", step: Step, server: "Thing") -> None:
        state = self.state
        hop = state["hop"]
        server.on = True
        for other in state["servers"]:
            if other.data["hop"] == hop and other.data["forged"]:
                other.gone = True
        self._say(state["chain"][hop][2], urgent=True)
        npc = state["npc"]
        npc.x, npc.y = server.x + 70, server.y + 50
        self.arena.emit({"e": "npc_found", "id": npc.id, "x": round(npc.x, 1), "y": round(npc.y, 1)})
        state["hop"] = hop + 1
        state["done"] = hop + 1
        if hop + 1 >= len(state["chain"]):
            npc.x, npc.y = self.device.x + 100, self.device.y + 60
            self._complete()
            return
        state["fmt"] = {"next": state["chain"][hop + 1][0]}

    def _aim_resolve(self: "StageQuest", player: Player) -> tuple[float, float] | None:
        server = next(
            s for s in self.state["servers"]
            if s.data["hop"] == self.state["hop"] and not s.data["forged"]
        )
        return server.x, server.y

    # ------------------------------------------- balancer: where the traffic goes
    def _begin_balance(self: "StageQuest", step: Step) -> None:
        room = self.quest_room
        spots = self._ring(room, 3, RING)
        nodes = [
            self._add(
                "node", x, y, room, label=f"node-{index + 1} · ядер: {cores}",
                data={"capacity": cores * BALANCE_PER_CORE, "down_until": 0.0},
            )
            for index, ((x, y), cores) in enumerate(zip(spots, step.opts["cores"]))
        ]
        rate = BALANCE_RATE + self.arena.party_size - 1
        rate /= math.sqrt(self.arena.difficulty.tempo)
        self.state.update(
            nodes=nodes,
            route=[nodes[0]],
            served=0.0,
            time=float(step.opts["time"]),
            rate=min(BALANCE_MAX_RATE, rate),
        )
        nodes[0].data["view"] = {"route": True}

    def _tick_balance(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        nodes = state["nodes"]
        for node in nodes:
            if node.on and now >= node.data["down_until"]:
                node.on = False
                node.charge = 0.4
        living = self._living()
        holding = [
            node for node in nodes
            if not node.on and any(math.hypot(p.x - node.x, p.y - node.y) <= BALANCE_REACH for p in living)
        ]
        if holding:
            state["route"] = holding
        route = [node for node in state["route"] if not node.on]
        if not route:
            route = [node for node in nodes if not node.on][:1] or []
            state["route"] = route
        share = state["rate"] / len(route) if route else 0.0
        for node in nodes:
            routed = node in route
            node.data["view"] = {"route": routed}
            if node.on:
                continue
            inflow = share if routed else 0.0
            node.charge = max(0.0, node.charge + (inflow - node.data["capacity"]) * dt / 100.0)
            if node.charge >= 1.0:
                self._melt(step, node, now)
        if route:
            state["served"] = min(state["time"], state["served"] + dt)
        self._harass(step, now)
        if state["served"] >= state["time"]:
            self._complete()

    def _melt(self: "StageQuest", step: Step, node: "Thing", now: float) -> None:
        state = self.state
        node.on = True
        node.charge = 1.0
        node.data["down_until"] = now + BALANCE_CRASH
        state["served"] = max(0.0, state["served"] - state["time"] * BALANCE_SETBACK)
        self.arena.emit({"e": "unit_down", "id": node.id, "x": round(node.x, 1), "y": round(node.y, 1)})
        self._pack(self.quest_room, 0.25, near=(node.x, node.y))
        self._say(step.fail, urgent=True)

    def _bar_balance(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        value = state["served"] / state["time"]
        return {"value": round(value, 3), "label": f"Обслужено {round(value * 100)}%"}

    def _marks_balance(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_balance(self: "StageQuest", player: Player) -> tuple[float, float]:
        nodes = [node for node in self.state["nodes"] if not node.on] or self.state["nodes"]
        for node in nodes:
            if math.hypot(player.x - node.x, player.y - node.y) <= BALANCE_REACH and node.charge < 0.6:
                return node.x, node.y
        node = min(nodes, key=lambda n: n.charge / n.data["capacity"])
        return node.x, node.y

    # ----------------------------------------------- rate limit: a bucket of tokens
    def _begin_bucket(self: "StageQuest", step: Step) -> None:
        now = self.arena.now
        self.state.update(
            need=int(step.opts["need"]),
            tokens=float(step.opts["capacity"]),
            capacity=float(step.opts["capacity"]),
            refill=float(step.opts["refill"]),
            people=[],
            next_bot=now + 2.0,
            next_person=now + 3.0,
        )

    def _tick_bucket(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        state["tokens"] = min(state["capacity"], state["tokens"] + state["refill"] * dt)
        tempo = self.arena.difficulty.tempo
        if now >= state["next_bot"]:
            state["next_bot"] = now + BUCKET_BOT_EVERY * math.sqrt(tempo) / (1 + 0.5 * (self.arena.party_size - 1))
            x, y = self._wall_point(self.quest_room)
            bot = self.arena.spawn_monster("ratebot", x, y)
            if bot is not None:
                bot.quest = "bucket"
                bot.leaked = True
        if now >= state["next_person"]:
            state["next_person"] = now + BUCKET_PERSON_EVERY
            x, y = self._wall_point(self.quest_room)
            state["people"].append(
                self._add("walker", x, y, self.quest_room, label=self.rng.choice(PEOPLE_ONLINE))
            )
        goal = self.runner_goal()
        for person in state["people"]:
            if person.gone:
                continue
            distance = math.hypot(goal[0] - person.x, goal[1] - person.y)
            if distance <= BUCKET_ARRIVES:
                self._person_arrives(step, person)
                continue
            person.x += (goal[0] - person.x) / distance * BUCKET_PERSON_SPEED * dt
            person.y += (goal[1] - person.y) / distance * BUCKET_PERSON_SPEED * dt
        self._harass(step, now)
        if state["done"] >= state["need"]:
            for person in state["people"]:
                person.gone = True
            for bot in self._tagged("bucket"):
                self.arena.remove_monster(bot)
            self._complete()

    def _person_arrives(self: "StageQuest", step: Step, person: "Thing") -> None:
        state = self.state
        person.gone = True
        x, y = round(person.x, 1), round(person.y, 1)
        if state["tokens"] >= 1.0:
            state["tokens"] -= 1.0
            state["done"] += 1
            self.arena.emit({"e": "quest_note", "x": x, "y": y, "text": "200 OK", "good": True})
            return
        self.arena.emit({"e": "quest_note", "x": x, "y": y, "text": f"{person.label}: 429"})
        if self.arena.now - state.get("told", -100.0) > 10.0:
            state["told"] = self.arena.now
            self._say(step.fail)

    def _bar_bucket(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        tokens = state["tokens"]
        return {
            "value": round(tokens / state["capacity"], 3),
            "label": f"Токены {math.floor(tokens)}/{round(state['capacity'])}",
            "warn": tokens < 2.0,
        }

    def _marks_bucket(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_bucket(self: "StageQuest", player: Player) -> tuple[float, float]:
        return self.device.x, self.device.y + 110

    # --------------------------------------------- bucket left public: files leak
    def _begin_leak(self: "StageQuest", step: Step) -> None:
        room = self.quest_room
        left, right = (room.x + 0.9) * TILE, (room.x + room.w - 0.9) * TILE
        bottom = (room.y + room.h - 0.9) * TILE
        cx, cy = room.center
        holes = [
            self._add("hole", x, y, room, label="public")
            for x, y in ((left, cy), (right, cy), (cx, bottom))
        ]
        self.state.update(
            need=int(step.opts["need"]) + LEAK_NEED_PER_MAGE * (self.arena.party_size - 1),
            holes=holes,
            files=[],
            next_file=self.arena.now + 1.0,
            leaks=0,
        )

    def _tick_leak(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        loose = [item for item in state["files"] if not item.gone]
        if now >= state["next_file"] and len(loose) < LEAK_MAX_LOOSE:
            state["next_file"] = now + LEAK_EVERY / (1 + 0.4 * (self.arena.party_size - 1))
            loose.append(self._spill(step))
            state["files"] = loose
        for item in loose:
            taker = self._toucher(item.x, item.y, LEAK_REACH)
            if taker is not None:
                item.gone = True
                if item.bad:
                    self._burst(item)
                else:
                    state["done"] += 1
                    self.arena.emit({
                        "e": "quest_item", "id": taker.id, "x": round(item.x, 1),
                        "y": round(item.y, 1), "label": item.label,
                    })
                continue
            hole = item.data["hole"]
            distance = math.hypot(hole.x - item.x, hole.y - item.y)
            if distance <= 30.0:
                item.gone = True
                if not item.bad:
                    self._leaked(step, hole, item)
                continue
            item.x += (hole.x - item.x) / distance * LEAK_SPEED * dt
            item.y += (hole.y - item.y) / distance * LEAK_SPEED * dt
        if state["done"] >= state["need"]:
            for item in state["files"]:
                item.gone = True
            self._complete()

    def _spill(self: "StageQuest", step: Step) -> "Thing":
        device = self.device
        hole = self.rng.choice(self.state["holes"])
        bad = self.rng.random() < LEAK_BAD_SHARE
        names = step.opts["bad"] if bad else step.opts["labels"]
        x = device.x + self.rng.uniform(-50, 50)
        y = device.y + self.rng.uniform(30, 70)
        extra: dict[str, Any] = {"bad": True, "color": "#ff5a4f"} if bad else {}
        return self._add(
            "item", x, y, self.quest_room, label=self.rng.choice(names), data={"hole": hole}, **extra
        )

    def _leaked(self: "StageQuest", step: Step, hole: "Thing", item: "Thing") -> None:
        state = self.state
        state["leaks"] += 1
        self.arena.emit({"e": "quest_note", "x": round(hole.x, 1), "y": round(hole.y, 1), "text": f"{item.label} утёк"})
        # Whatever leaks gets found: every other lost file brings something back in.
        if state["leaks"] % 2 == 0 and len(self.arena.monsters) < 14:
            self._pack(self.quest_room, 0.2, near=(hole.x, hole.y))
        if self.arena.now - state.get("told", -100.0) > 12.0:
            state["told"] = self.arena.now
            self._say(step.fail)

    def _marks_leak(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_leak(self: "StageQuest", player: Player) -> tuple[float, float]:
        files = [item for item in self.state["files"] if not item.gone and not item.bad]
        if not files:
            return self.device.x, self.device.y + 120
        item = min(files, key=lambda f: math.hypot(f.x - player.x, f.y - player.y))
        return item.x, item.y

    # ------------------------------------------------- docker: the dependency graph
    def _begin_compose(self: "StageQuest", step: Step) -> None:
        room = self.quest_room
        graph = self.rng.choice(COMPOSE_GRAPHS)
        hp = float(step.opts["hp"]) * self.scale
        names = list(graph)
        self.rng.shuffle(names)
        containers = {
            name: self._add_unit("container", name, x, y, hp, 30.0)
            for name, (x, y) in zip(names, self._ring(room, len(names), RING))
        }
        for unit in containers.values():
            unit.status = "exited"
        lines = ["services:"]
        for name, needs in graph.items():
            lines.append(f"  {name}:")
            if needs:
                lines.append(f"    depends_on: [{', '.join(needs)}]")
        self.state.update(
            need=len(graph),
            graph=graph,
            containers=containers,
            hold=float(step.opts["hold"]),
            card={"room": room.index, "title": "docker-compose.yml", "code": "\n".join(lines)},
        )

    def _tick_compose(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        living = self._living()
        for name, unit in state["containers"].items():
            if unit.status == "up":
                continue
            presser = next(
                (p for p in living if math.hypot(p.x - unit.x, p.y - unit.y) <= COMPOSE_REACH), None
            )
            if presser is None:
                unit.charge = max(0.0, unit.charge - dt)
                continue
            unit.charge += dt / state["hold"]
            if unit.charge >= 1.0:
                self._start_container(step, name, unit, presser, now)
        state["done"] = sum(1 for unit in state["containers"].values() if unit.status == "up")
        self._compose_bugs(step, now)
        if state["done"] >= state["need"]:
            for unit in state["containers"].values():
                unit.targetable = False
            self._complete()

    def _start_container(
        self: "StageQuest", step: Step, name: str, unit: "QuestUnit", presser: Player, now: float
    ) -> None:
        state = self.state
        unit.charge = 0.0
        missing = [
            need for need in state["graph"][name] if state["containers"][need].status != "up"
        ]
        x, y = round(unit.x, 1), round(unit.y, 1)
        if missing:
            self.arena.emit({"e": "quest_note", "x": x, "y": y, "text": f"{name}: Exited (1)"})
            self.arena.damage(
                target=presser, amount=CHOICE_ZAP, source=None, kind="zap",
                hit_x=presser.x, hit_y=presser.y,
            )
            if now - state.get("told", -100.0) > 6.0:
                state["told"] = now
                self._say(((self.quest.giver, f"{name}: connection refused. Сначала нужен {missing[0]}."),), urgent=True)
            return
        unit.status = "up"
        unit.targetable = True
        unit.hp = unit.max_hp
        self.arena.emit({"e": "zone_on", "id": unit.id, "x": x, "y": y, "label": f"{name}: Up"})

    def _compose_bugs(self: "StageQuest", step: Step, now: float) -> None:
        harass = step.opts.get("harass")
        due = self.state.setdefault("harass_at", now + float(harass[0]))
        up = [u for u in self.state["containers"].values() if u.status == "up"]
        if now < due or not up or len(self.arena.monsters) > 14:
            return
        self.state["harass_at"] = now + float(harass[0]) * self.arena.difficulty.tempo
        self._pack(self.quest_room, float(harass[1]), focus=self.rng.choice(up))

    def _container_down(self: "StageQuest", step: Step, unit: "QuestUnit") -> None:
        """One falls, and everything that needed it falls after it, up the graph."""

        state = self.state
        name = next(key for key, value in state["containers"].items() if value is unit)
        fallen = {name}
        grew = True
        while grew:
            grew = False
            for other, needs in state["graph"].items():
                if other not in fallen and fallen & set(needs):
                    fallen.add(other)
                    grew = True
        for other in fallen:
            box = state["containers"][other]
            box.status = "exited"
            box.targetable = False
            box.hp = box.max_hp
            box.charge = 0.0
            self.arena.emit({"e": "unit_down", "id": box.id, "x": round(box.x, 1), "y": round(box.y, 1)})
        self._say(step.fail, urgent=True)

    def _bar_compose(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        return {"value": state["done"] / state["need"], "label": f"Up {state['done']}/{state['need']}"}

    def _marks_compose(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_compose(self: "StageQuest", player: Player) -> tuple[float, float]:
        state = self.state
        for name, needs in state["graph"].items():
            box = state["containers"][name]
            if box.status != "up" and all(state["containers"][n].status == "up" for n in needs):
                return box.x, box.y
        return self.device.x, self.device.y

    # ---------------------------------------------------- git and journald: choose
    def _begin_choice(self: "StageQuest", step: Step) -> None:
        pool = list(CONFLICTS) if step.opts.get("pool") == "conflicts" else []
        self.rng.shuffle(pool)
        self.state.update(pool=pool, hold=float(step.opts["hold"]), circles=[], answer=0)
        self._ask(step)

    def _ask(self: "StageQuest", step: Step) -> None:
        state = self.state
        for circle in state["circles"]:
            circle.gone = True
        room = self.quest_room
        cx, cy = self.device.x, self.device.y + 70
        question = step.opts.get("question")
        if question is not None:
            title, names, answer = question
            # The middle one sits below the console, not on top of it.
            spots = [(cx + CHOICE_SPREAD * (i - 1), cy + (210 if i == 1 else 0)) for i in range(len(names))]
            code = "\n".join(f"  {name}" for name in names)
        else:
            if not state["pool"]:
                state["pool"] = list(CONFLICTS)
                self.rng.shuffle(state["pool"])
            title, good, bad = state["pool"].pop()
            answer = self.rng.randrange(2)
            first, second = (good, bad) if answer == 0 else (bad, good)
            names = ("main", "feature")
            spots = [(cx - CHOICE_SPREAD, cy), (cx + CHOICE_SPREAD, cy)]
            code = f"<<<<<<< main\n{first}\n=======\n{second}\n>>>>>>> feature"
        state["circles"] = [
            self._add("zone", x, y, room, label=name) for (x, y), name in zip(spots, names)
        ]
        state["answer"] = answer
        state["card"] = {"room": room.index, "title": title, "code": code}

    def _tick_choice(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        living = self._living()
        for index, circle in enumerate(state["circles"]):
            inside = any(math.hypot(p.x - circle.x, p.y - circle.y) <= CHOICE_REACH for p in living)
            circle.charge = (
                min(1.0, circle.charge + dt / state["hold"]) if inside
                else max(0.0, circle.charge - dt)
            )
            if circle.charge >= 1.0:
                self._answered(step, index, circle)
                return
        self._harass(step, now)

    def _answered(self: "StageQuest", step: Step, index: int, circle: "Thing") -> None:
        state = self.state
        x, y = round(circle.x, 1), round(circle.y, 1)
        if index != state["answer"]:
            self.arena.emit({"e": "zones_fail", "x": x, "y": y})
            for player in self._living():
                if math.hypot(player.x - circle.x, player.y - circle.y) <= CHOICE_REACH:
                    self.arena.damage(
                        target=player, amount=CHOICE_ZAP, source=None, kind="zap",
                        hit_x=player.x, hit_y=player.y,
                    )
            self._say(step.fail, urgent=True)
            circle.charge = 0.0
            if step.opts.get("pool"):
                self._pack(self.quest_room, 0.3, near=(circle.x, circle.y))
                self._ask(step)
            return
        state["done"] += 1
        self.arena.emit({"e": "zone_on", "id": circle.id, "x": x, "y": y, "label": circle.label})
        self._each(step, state["done"])
        if state["done"] >= state["need"]:
            for other in state["circles"]:
                other.gone = True
            self._complete()
            return
        self._ask(step)

    def _bar_choice(self: "StageQuest") -> dict[str, Any] | None:
        state = self.state
        if state["need"] <= 1:
            return None
        return {"value": state["done"] / state["need"], "label": f"{state['done']}/{state['need']}"}

    def _marks_choice(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_choice(self: "StageQuest", player: Player) -> tuple[float, float]:
        circle = self.state["circles"][self.state["answer"]]
        return circle.x, circle.y

    # ---------------------------------------------- overheating: frost on the racks
    def _begin_racks(self: "StageQuest", step: Step) -> None:
        rise = RACK_RISE * (1 + 0.25 * (self.arena.party_size - 1)) / self.arena.difficulty.tempo
        self.state.update(temps=None, time=float(step.opts["time"]), elapsed=0.0, rise=rise)

    def _power_racks(self: "StageQuest", step: Step) -> None:
        """They heat up from the moment someone walks in, not from the start of the stage."""

        temps: dict[int, float] = {}
        for x, y in self._ring(self.quest_room, int(step.opts["racks"]), RING + 20):
            rack = self.arena.spawn_monster("hotrack", x, y)
            if rack is None:
                continue
            rack.quest = "racks"
            rack.leaked = True
            rack.spawned_at = self.arena.now
            temps[rack.id] = RACK_START + self.rng.uniform(-8, 8)
            rack.text = f"{round(temps[rack.id])}°C"
        self.state["temps"] = temps

    def _tick_racks(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        if state["temps"] is None:
            self._power_racks(step)
        state["elapsed"] += dt
        for monster in self._tagged("racks"):
            wobble = 0.7 + 0.6 * math.sin(now * 0.5 + monster.id)
            temp = state["temps"][monster.id] + state["rise"] * wobble * dt
            if temp >= RACK_LIMIT:
                temp = self._rack_fire(step, monster)
            state["temps"][monster.id] = temp
            monster.text = f"{round(temp)}°C"
        self._harass(step, now)
        if state["elapsed"] >= state["time"]:
            for monster in self._tagged("racks"):
                self._quiet_remove(monster)
            self._complete()

    def _rack_fire(self: "StageQuest", step: Step, rack: "Monster") -> float:
        state = self.state
        state["elapsed"] = max(0.0, state["elapsed"] - state["time"] * RACK_SETBACK)
        self.arena.trap_blast(rack.x, rack.y, RACK_BLAST, 0.8, RACK_BLAST_DAMAGE)
        self.arena.emit({"e": "unit_down", "id": rack.id, "x": round(rack.x, 1), "y": round(rack.y, 1)})
        self._say(step.fail, urgent=True)
        return RACK_AFTER_FIRE

    def spell_hit(
        self: "StageQuest", monster: "Monster", source: Player | None, kind: str
    ) -> bool:
        """Whether this hit was not damage at all: a rack only ever changes temperature."""

        if monster.quest != "racks":
            return False
        temps = self.state.get("temps")
        if temps is None or monster.id not in temps or source is None:
            return True
        x, y = round(monster.x, 1), round(monster.y, 1)
        if kind == "frost":
            temps[monster.id] = max(25.0, temps[monster.id] - RACK_COOL)
            self.arena.emit({"e": "quest_note", "x": x, "y": y, "text": f"-{round(RACK_COOL)}°C", "good": True})
        elif kind in FIRE_KINDS:
            temps[monster.id] += RACK_FIRE
            self.arena.emit({"e": "quest_note", "x": x, "y": y, "text": f"+{round(RACK_FIRE)}°C"})
        monster.text = f"{round(temps[monster.id])}°C"
        return True

    def _bar_racks(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        value = state["elapsed"] / state["time"]
        return {"value": round(value, 3), "label": f"Запуск кулеров {round(value * 100)}%"}

    def _marks_racks(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_racks(self: "StageQuest", player: Player) -> tuple[float, float]:
        return self.device.x, self.device.y + 130

    def bot_racks(self: "StageQuest", player: Player) -> tuple["Monster | None", str | None]:
        racks = self._tagged("racks")
        if racks and self.quest_room.holds(player.x, player.y):
            hottest = max(racks, key=lambda rack: self.state["temps"][rack.id])
            if self.state["temps"][hottest.id] >= 62.0:
                return hottest, "if me().mana >= 9:\n    frostbolt(aim())\n"
        bugs = [m for m in self.arena.monsters.values() if m.quest != "racks" and m.spawned_at <= self.arena.now]
        if not bugs:
            return None, None
        return min(bugs, key=lambda m: math.hypot(m.x - player.x, m.y - player.y)), None

    # --------------------------------------------- memory leak: the floor is the RAM
    def _begin_memory(self: "StageQuest", step: Step) -> None:
        room = self.quest_room
        cols = room.w // MEMORY_CELL
        rows = room.h // MEMORY_CELL
        self.state.update(
            cols=cols,
            rows=rows,
            used=set(),
            next_spread=self.arena.now + 1.0,
            next_bite=self.arena.now + 1.0,
            spawned=False,
            tag=f"{self.quest.key}:leak",
        )

    def _memory_cell(self: "StageQuest", x: float, y: float) -> tuple[int, int] | None:
        room = self.quest_room
        col = int((x / TILE - room.x) // MEMORY_CELL)
        row = int((y / TILE - room.y) // MEMORY_CELL)
        if 0 <= col < self.state["cols"] and 0 <= row < self.state["rows"]:
            return col, row
        return None

    def _tick_memory(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        state = self.state
        if not state["spawned"]:
            if not self._engaged():
                return
            x, y = self._far_from_mages(self.quest_room)
            leak = self.arena.spawn_monster("leak", x, y)
            if leak is None:
                return
            leak.quest = state["tag"]
            leak.leaked = True
            state["spawned"] = True
            return
        leaks = self._tagged(state["tag"])
        if not leaks:
            state["used"].clear()
            self.arena.emit({"e": "memory_free"})
            self._complete()
            return
        if now >= state["next_spread"]:
            state["next_spread"] = now + float(step.opts["spread"]) * self.arena.difficulty.tempo
            self._spread_memory(leaks[0])
        if len(state["used"]) >= state["cols"] * state["rows"]:
            self._out_of_memory(step)
        if now >= state["next_bite"]:
            state["next_bite"] = now + MEMORY_BITE
            for player in self._living():
                if self._memory_cell(player.x, player.y) in state["used"]:
                    player.slow_until = max(player.slow_until, now + MEMORY_BITE + 0.2)
                    self.arena.damage(
                        target=player, amount=MEMORY_DAMAGE, source=None, kind="memory",
                        hit_x=player.x, hit_y=player.y,
                    )

    def _spread_memory(self: "StageQuest", leak: "Monster") -> None:
        state = self.state
        used = state["used"]
        here = self._memory_cell(leak.x, leak.y)
        if here is not None and here not in used:
            used.add(here)
            return
        frontier = [
            cell
            for col, row in used
            for cell in ((col + 1, row), (col - 1, row), (col, row + 1), (col, row - 1))
            if cell not in used and 0 <= cell[0] < state["cols"] and 0 <= cell[1] < state["rows"]
        ]
        if frontier:
            used.add(self.rng.choice(frontier))

    def _out_of_memory(self: "StageQuest", step: Step) -> None:
        state = self.state
        cells = sorted(state["used"])
        self.rng.shuffle(cells)
        state["used"] = set(cells[: len(cells) // 2])
        self.arena.emit({"e": "memory_oom"})
        for player in self._living():
            self.arena.damage(
                target=player, amount=MEMORY_OOM, source=None, kind="memory",
                hit_x=player.x, hit_y=player.y,
            )
        self._say(step.fail, urgent=True)

    def _bar_memory(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        value = len(state["used"]) / (state["cols"] * state["rows"])
        return {"value": round(value, 3), "label": f"Память {round(value * 100)}%", "warn": value > 0.75, "hot": True}

    def _marks_memory(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _view_memory(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        room = self.quest_room
        used = state["used"]
        bits = "".join(
            "1" if (col, row) in used else "0"
            for row in range(state["rows"])
            for col in range(state["cols"])
        )
        return {"goo": {"x": room.x, "y": room.y, "c": state["cols"], "s": MEMORY_CELL, "b": bits}}

    def _aim_memory(self: "StageQuest", player: Player) -> tuple[float, float] | None:
        leaks = self._tagged(self.state["tag"])
        if not leaks:
            return self.device.x, self.device.y + 120
        return leaks[0].x, leaks[0].y

    # ----------------------------------------- CI/CD: a build that rides the pipeline
    def _begin_payload(self: "StageQuest", step: Step) -> None:
        start = self.tagged[str(step.opts["start"])].center
        end = (self.device.x, self.device.y + 90)
        route = self._cart_route(start, end)
        lengths = [0.0]
        for (x1, y1), (x2, y2) in zip(route, route[1:]):
            lengths.append(lengths[-1] + math.hypot(x2 - x1, y2 - y1))
        total = lengths[-1] or 1.0
        cart = self._add_unit("artifact", "сборка #9999", start[0], start[1], 100.0, 26.0)
        stops = [(total * share, kind) for share, kind in CART_STOPS]
        self.state.update(
            cart=cart,
            route=route,
            lengths=lengths,
            total=total,
            pos=0.0,
            stops=stops,
            mode="roll",
            rival=0.0,
            rival_time=float(step.opts["rival"]) * self.arena.difficulty.tempo,
            floor=0.0,
            terminal=None,
            tag=f"{self.quest.key}:tests",
            fmt={"note": ""},
        )
        for distance, kind in stops:
            x, y = self._cart_point(distance)
            room = self.arena.dungeon.room_at(x, y) or self.quest_room
            label = "test" if kind == "test" else "review"
            self._add("station", x, y, room, label=label)
        self._cart_note()

    def _cart_route(
        self: "StageQuest", start: tuple[float, float], end: tuple[float, float]
    ) -> list[tuple[float, float]]:
        """The shortest walk between two points, cut down to where it really turns."""

        grid = self.arena.dungeon.grid
        first = (int(start[0] // TILE), int(start[1] // TILE))
        goal = (int(end[0] // TILE), int(end[1] // TILE))
        came: dict[tuple[int, int], tuple[int, int] | None] = {goal: None}
        frontier = deque([goal])
        while frontier and first not in came:
            x, y = frontier.popleft()
            for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                tx, ty = tile
                if tile in came or not (0 <= ty < len(grid) and 0 <= tx < len(grid[0])):
                    continue
                if grid[ty][tx] != FLOOR:
                    continue
                came[tile] = (x, y)
                frontier.append(tile)
        tiles: list[tuple[int, int]] = []
        tile: tuple[int, int] | None = first if first in came else None
        while tile is not None:
            tiles.append(tile)
            tile = came[tile]
        points = [((x + 0.5) * TILE, (y + 0.5) * TILE) for x, y in tiles] or [start, end]
        dungeon = self.arena.dungeon
        route = [start]
        index = 0
        while index < len(points) - 1:
            reach = index + 1
            for later in range(len(points) - 1, index, -1):
                if dungeon.path_clear(route[-1][0], route[-1][1], points[later][0], points[later][1], 24.0):
                    reach = later
                    break
            route.append(points[reach])
            index = reach
        route.append(end)
        return route

    def _cart_point(self: "StageQuest", distance: float) -> tuple[float, float]:
        state = self.state
        route, lengths = state["route"], state["lengths"]
        for index in range(len(lengths) - 1):
            if distance <= lengths[index + 1]:
                span = lengths[index + 1] - lengths[index] or 1.0
                at = (distance - lengths[index]) / span
                x1, y1 = route[index]
                x2, y2 = route[index + 1]
                return x1 + (x2 - x1) * at, y1 + (y2 - y1) * at
        return route[-1]

    def _cart_note(self: "StageQuest") -> None:
        state = self.state
        mode = state["mode"]
        if mode == "test":
            note = f"Тесты упали, сборка стоит: сбейте их, осталось {len(self._tagged(state['tag']))}"
        elif mode == "review":
            note = "Ревью: соберите тег релиза в консоли у сборки"
        else:
            note = f"Ведите сборку: она едет, пока маг рядом · {round(state['pos'] / state['total'] * 100)}%"
        state["fmt"] = {"note": note}

    def _tick_payload(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        state = self.state
        cart = state["cart"]
        arena = self.arena
        living = self._living()
        close = any(math.hypot(p.x - cart.x, p.y - cart.y) <= CART_REACH for p in living)
        mode = state["mode"]
        if mode == "test" and not self._tagged(state["tag"]):
            state["mode"] = mode = "roll"
            self._say(((self.quest.giver, "Тесты зелёные, сборка едет дальше."),))
        if mode == "roll" and close and arena.active_room is None:
            state["pos"] = min(state["total"], state["pos"] + CART_SPEED * dt)
            cart.x, cart.y = self._cart_point(state["pos"])
            if state["stops"] and state["pos"] >= state["stops"][0][0]:
                state["floor"] = state["pos"]
                self._cart_stop(state["stops"].pop(0)[1])
        self._cart_note()
        if state["pos"] >= state["total"]:
            for monster in self._tagged(state["tag"]):
                arena.remove_monster(monster)
            self._complete()
            return
        if close:
            state["rival"] += dt / state["rival_time"]
            if state["rival"] >= 1.0:
                self._rival_ships(step)
            self._cart_bugs(step, now, cart)

    def _cart_stop(self: "StageQuest", kind: str) -> None:
        state = self.state
        cart = state["cart"]
        if kind == "test":
            state["mode"] = "test"
            names = list(FAILED_TESTS)
            self.rng.shuffle(names)
            count = CART_TESTS + self.arena.party_size - 1
            for index in range(count):
                angle = index / count * math.tau + self.rng.uniform(-0.3, 0.3)
                monster = self._spawn_near_cart(cart, angle)
                if monster is not None:
                    monster.quest = state["tag"]
                    monster.leaked = True
                    monster.text = names[index % len(names)]
            self._say(((self.quest.giver, "Этап test: сборка встала, тесты красные. Сбейте их!"),), urgent=True)
            return
        state["mode"] = "review"
        step = self.step
        state["terminal"] = self.arena._add_terminal(
            cart.x, cart.y - 80, QUEST_TASKS[str(step.opts["review"])], "quest"
        )
        self._say(((self.quest.giver, "Этап review: сборку нельзя выкатить без тега релиза. Консоль прямо у сборки."),), urgent=True)

    def _spawn_near_cart(self: "StageQuest", cart: "QuestUnit", angle: float) -> "Monster | None":
        arena = self.arena
        for reach in (230.0, 180.0, 130.0, 90.0):
            x = cart.x + math.cos(angle) * reach
            y = cart.y + math.sin(angle) * reach
            if arena.can_stand(x, y, 20.0):
                return arena.spawn_monster("failtest", x, y)
        return None

    def _rival_ships(self: "StageQuest", step: Step) -> None:
        state = self.state
        arena = self.arena
        cart = state["cart"]
        state["rival"] = 0.0
        state["pos"] = max(state["floor"], state["pos"] - state["total"] * CART_SETBACK)
        cart.x, cart.y = self._cart_point(state["pos"])
        arena.emit({
            "e": "boss_cast", "id": cart.id, "x": round(cart.x, 1), "y": round(cart.y, 1),
            "color": "#ff4f6a", "error": "git push --force origin main", "tip": "",
        })
        for player in self._living():
            arena.damage(
                target=player, amount=CART_BLAST, source=None, kind="deploy",
                hit_x=player.x, hit_y=player.y,
            )
        self._say(step.fail, urgent=True)

    def _cart_bugs(self: "StageQuest", step: Step, now: float, cart: "QuestUnit") -> None:
        harass = step.opts.get("harass")
        due = self.state.setdefault("harass_at", now + float(harass[0]))
        if now < due or self.state["mode"] != "roll" or len(self.arena.monsters) > 14:
            return
        self.state["harass_at"] = now + float(harass[0]) * self.arena.difficulty.tempo
        room = self.arena.dungeon.room_at(cart.x, cart.y) or self.quest_room
        self._pack(room, float(harass[1]), near=(cart.x, cart.y))

    def _bar_payload(self: "StageQuest") -> dict[str, Any]:
        rival = self.state["rival"]
        return {"value": round(rival, 3), "label": f"Деплой PGT {round(rival * 100)}%", "warn": rival > 0.75, "hot": True}

    def _marks_payload(self: "StageQuest") -> list[tuple[float, float, int]]:
        cart = self.state["cart"]
        room = self.arena.dungeon.room_at(cart.x, cart.y)
        return [(cart.x, cart.y, room.index if room else self.quest_room.index)]

    def _view_payload(self: "StageQuest") -> dict[str, Any]:
        state = self.state
        ahead = [
            [round(x, 1), round(y, 1)]
            for (x, y), length in zip(state["route"], state["lengths"])
            if length > state["pos"]
        ]
        cart = state["cart"]
        return {"route": [[round(cart.x, 1), round(cart.y, 1)], *ahead]}

    def _aim_payload(self: "StageQuest", player: Player) -> tuple[float, float]:
        cart = self.state["cart"]
        if self.state["mode"] == "test":
            tests = self._tagged(self.state["tag"])
            if tests:
                target = min(tests, key=lambda m: math.hypot(m.x - player.x, m.y - player.y))
                return target.x, target.y
        return cart.x, cart.y

    # ---------------------------------------------------- spam filter: read the mail
    def _begin_inbox(self: "StageQuest", step: Step) -> None:
        self.state.update(
            need=int(step.opts["need"]),
            spam={},
            next_letter=self.arena.now + 1.0,
            spam_pool=[],
            ham_pool=[],
        )

    def _tick_inbox(self: "StageQuest", step: Step, now: float, dt: float) -> None:
        if not self._engaged():
            return
        state = self.state
        if now >= state["next_letter"] and len(self._tagged("inbox")) < MAIL_MAX_LOOSE:
            pace = 1 + 0.35 * (self.arena.party_size - 1)
            state["next_letter"] = now + float(step.opts["every"]) * self.arena.difficulty.tempo / pace
            self._send_letter()
        self._harass(step, now)
        if state["done"] >= state["need"]:
            for monster in self._tagged("inbox"):
                self._quiet_remove(monster)
            self._complete()

    def _send_letter(self: "StageQuest") -> None:
        state = self.state
        spam = self.rng.random() < MAIL_SPAM_SHARE
        pool = state["spam_pool" if spam else "ham_pool"]
        if not pool:
            pool.extend(SPAM_LETTERS if spam else HAM_LETTERS)
            self.rng.shuffle(pool)
        x, y = self._wall_point(self.quest_room)
        letter = self.arena.spawn_monster("letter", x, y)
        if letter is None:
            return
        letter.quest = "inbox"
        letter.leaked = True
        letter.text = pool.pop()
        state["spam"][letter.id] = spam

    def _mail_score(self: "StageQuest", right: bool, x: float, y: float, text: str) -> None:
        state = self.state
        state["done"] = max(0, state["done"] + (1 if right else -1))
        self.arena.emit({"e": "quest_note", "x": round(x, 1), "y": round(y, 1), "text": text, "good": right})
        if not right and self.arena.now - state.get("told", -100.0) > 10.0:
            state["told"] = self.arena.now
            self._say(self.step.fail)

    def runner_goal(self: "StageQuest") -> tuple[float, float] | None:
        step = self.step
        if step is None or step.kind not in ("bucket", "inbox"):
            return None
        return self.device.x, self.device.y + 20

    def runner_arrived(self: "StageQuest", monster: "Monster") -> None:
        step = self.step
        self._quiet_remove(monster)
        if step is None:
            return
        state = self.state
        x, y = monster.x, monster.y
        if step.kind == "bucket":
            state["tokens"] = max(0.0, state["tokens"] - 1.0)
            self.arena.emit({"e": "quest_note", "x": round(x, 1), "y": round(y, 1), "text": "-1 токен"})
        elif step.kind == "inbox":
            spam = state["spam"].pop(monster.id, False)
            self._mail_score(not spam, x, y, "спам во входящих" if spam else "доставлено")

    def _died_inbox(self: "StageQuest", monster: "Monster") -> None:
        spam = self.state["spam"].pop(monster.id, None)
        if spam is None:
            return
        self._mail_score(spam, monster.x, monster.y, "в спам" if spam else "это было письмо!")

    def _marks_inbox(self: "StageQuest") -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _aim_inbox(self: "StageQuest", player: Player) -> tuple[float, float]:
        return self.device.x, self.device.y + 120

    def bot_inbox(self: "StageQuest", player: Player) -> tuple["Monster | None", str | None]:
        spam = [
            letter for letter in self._tagged("inbox")
            if self.state["spam"].get(letter.id)
        ]
        if not spam:
            return None, None
        return min(spam, key=lambda m: math.hypot(m.x - player.x, m.y - player.y)), None
