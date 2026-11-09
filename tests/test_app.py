"""Real Pygame rendering/input using SDL's headless video driver."""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import unittest
from concurrent.futures import Future

import pygame

from gomoku.ai import Analysis
from gomoku.app import App, WIDTH, HEIGHT
from gomoku.game import BLACK, WHITE


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.window = pygame.display.set_mode((WIDTH, HEIGHT))

    def tearDown(self):
        self.app.close()

    def click(self, pos):
        self.app.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_menu_start_board_input_and_occupied_cell(self):
        app = self.app
        app.draw()
        self.click((560, 600))
        self.assertEqual("play", app.screen)
        app.draw()
        self.click(app.point(7, 7))
        self.assertEqual(BLACK, app.game.board.cells[7][7])
        self.click(app.point(7, 8))
        self.assertEqual(1, len(app.game.board.history))
        app.game.play(7, 8)
        self.click(app.point(7, 7))
        self.assertEqual(2, len(app.game.board.history))

    def test_restart_discards_old_ai_result(self):
        app = self.app
        app.start_game()
        app.game.play(7, 7)
        old = Future()
        old.set_running_or_notify_cancel()
        app.future = old
        app.job_revision = app.revision
        old_cancel = app.cancel
        app.start_game()
        old.set_result(Analysis((7, 8), "old", 1, 1, 0.01))
        app.update()
        self.assertTrue(old_cancel.is_set())
        self.assertEqual([], app.game.board.history)

    def test_ai_reply_and_loss_screen(self):
        app = self.app
        app.start_game()
        for col in range(4):
            app.game.play(0, col * 2)
            app.game.play(2, col)
        app.game.play(4, 0)
        future = Future()
        future.set_result(Analysis((2, 4), "Complete five", 0, 0, 0.01))
        app.future, app.job_revision = future, app.revision
        app.update()
        self.assertEqual(WHITE, app.game.winner)
        self.assertTrue(app.result_open)
        app.draw()
        self.click((450, 525))
        self.assertFalse(app.result_open)
        app.draw()
        self.assertTrue(app.game.finished)
        app.undo()
        self.assertFalse(app.game.finished)
        self.assertEqual(BLACK, app.game.turn)

    def test_win_and_draw_screens_render(self):
        app = self.app
        app.start_game()
        for col in range(4):
            app.game.play(0, col)
            app.game.play(2, col)
        app.draw()
        self.click(app.point(0, 4))
        self.assertEqual(BLACK, app.game.winner)
        self.assertTrue(app.result_open)
        app.draw()
        app.game.winner, app.game.draw = 0, True
        app.draw()

    def test_coordinate_mapping_after_resize(self):
        app = self.app
        app.window = pygame.display.set_mode((560, 500))
        # 0.5 scale with a 50px top letterbox.
        x, y = app.point(7, 7)
        mapped = app.to_canvas((x / 2, y / 2 + 50))
        self.assertEqual((7, 7), app.cell_at(mapped))
        self.assertIsNone(app.cell_at((-1, -1)))

    def test_ai_error_is_visible_and_retryable(self):
        app = self.app
        app.start_game()
        app.game.play(7, 7)
        future = Future()
        future.set_exception(RuntimeError("test error"))
        app.future, app.job_revision = future, app.revision
        app.update()
        self.assertTrue(app.error)
        self.assertIsNone(app.future)
        app.draw()
        app.retry()
        self.assertEqual("", app.error)


if __name__ == "__main__":
    unittest.main()
