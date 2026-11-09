"""Nothing in the drawing code may stop the picture: one throw in a frame once froze the game."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from arcane.campaign import STAGES
from arcane.game import TICK_RATE, Arena
from arcane.story import StoryArena

ROOT = Path(__file__).parent.parent
NODE = shutil.which("node")


def run_module(source: str) -> str:
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", source],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=ROOT,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout


def real_arena_state() -> str:
    """A world from the real server, with real mages in it, for the drawing code to draw."""

    arena = Arena(bots=3)
    arena.add_player("Маг")
    now = 0.0
    for _ in range(TICK_RATE * 2):
        now += 1 / TICK_RATE
        arena.update(now)
        arena.drain_events()
    return json.dumps({"config": arena.world_config(), "snapshot": arena.snapshot(), **real_foes()})


def real_foes() -> dict[str, list]:
    """Every new creature as the server really reports it, with what it leaves on the floor."""

    monsters: dict[str, dict] = {}
    fields: dict[str, dict] = {}
    for stage in STAGES:
        for key in (stage.mini, *stage.fresh):
            arena = StoryArena(stage, 1, seed=3, now=1.0, known_upto=19)
            mage = arena.add_player("Маг")
            mage.invuln_until = 1e9
            room = [r for r in arena.dungeon.path if r.kind == "combat"][-1]
            arena.active_room = room
            mage.x, mage.y = arena.dungeon.open_near(room.center[0] - 130, room.center[1], 20.0)
            arena.spawn_monster(key, *arena.dungeon.open_near(room.center[0] + 130, room.center[1], 30.0))
            now = 1.0
            for tick in range(TICK_RATE * 9):
                now += 1 / TICK_RATE
                arena.update(now)
                arena.drain_events()
                if tick % TICK_RATE == 0:
                    state = arena.snapshot()
                    for entry in state["monsters"]:
                        marks = json.dumps(entry.get("marks"), sort_keys=True)
                        monsters[f'{entry["kind"]} {marks[:40]}'] = entry
                    for entry in state.get("fields", []):
                        fields[f'{entry["k"]} {"arming" in entry}'] = entry
    return {"monsters": list(monsters.values()), "fields": list(fields.values())}


@unittest.skipUnless(NODE, "needs node")
class DrawingNeverThrowsTests(unittest.TestCase):
    STUB_CTX = "const ctx = { fillRect() {}, fillStyle: '', globalAlpha: 1 };"

    def test_a_glyph_with_no_number_is_still_a_glyph(self) -> None:
        """Healing made rune sparks without saying which symbol: that froze the arena."""

        output = run_module(
            f"""
            import {{ drawGlyph }} from './public/js/vfx.js';
            {self.STUB_CTX}
            for (const variant of [undefined, null, NaN, -3, 0.5, 7, 1000]) drawGlyph(ctx, 0, 0, 2, variant);
            console.log('ok');
            """
        )
        self.assertEqual(output.strip(), "ok")

    def test_a_ring_with_nonsense_in_it_draws_nothing_rather_than_hanging(self) -> None:
        output = run_module(
            f"""
            import {{ pixelRing }} from './public/js/vfx.js';
            {self.STUB_CTX}
            for (const radius of [0, -1, NaN, 1e9]) pixelRing(ctx, 0, 0, radius, 3, '#ffffff', 1);
            console.log('ok');
            """
        )
        self.assertEqual(output.strip(), "ok")

    def test_every_event_draws_through_its_whole_life_at_every_quality(self) -> None:
        result = subprocess.run(
            [NODE, "tests/client_smoke.mjs"],
            input=real_arena_state(),
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertGreater(report["events"], 60, "the list of events comes from the handler itself")
        self.assertGreater(report["frames"], 1000)
        self.assertEqual(report["failures"], {})
        self.assertGreater(report["foes"], 61, "every new creature, in more than one state")
        self.assertGreaterEqual(report["field_kinds"], 8)


class ThePictureKeepsGoingTests(unittest.TestCase):
    def test_the_next_frame_is_asked_for_before_anything_can_throw(self) -> None:
        source = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
        loop = source[source.index("function animate(now) {"):]
        loop = loop[:loop.index("\n}\n")]
        first_call = next(line for line in loop.splitlines()[1:] if line.strip() and "//" not in line)
        self.assertEqual(first_call.strip(), "window.requestAnimationFrame(animate);")
        self.assertEqual(loop.count("requestAnimationFrame"), 1, "or the frames would multiply")

    def test_a_frame_that_throws_leaves_the_canvas_clean(self) -> None:
        source = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
        self.assertIn("renderer.recoverFrame();", source)


if __name__ == "__main__":
    unittest.main()
