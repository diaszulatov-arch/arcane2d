"""Nothing in the drawing code may stop the picture: one throw in a frame once froze the game."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from arcane.game import TICK_RATE, Arena

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
    return json.dumps({"config": arena.world_config(), "snapshot": arena.snapshot()})


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
