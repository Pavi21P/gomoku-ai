# Gomoku — five in a row

A standalone **Python + Pygame** course project. Play against an explainable,
heuristic-based opponent on a 15×15 board. No Processing, online services,
trained models, or external artwork are required.

## Run

Requires Python 3.11 or newer. After setup, Windows users can double-click
**`Play.bat`**, or run in PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

For a fresh Windows setup, clone or download this repository, open a terminal
in its folder, then run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

On macOS/Linux, use `python3 -m venv .venv`, then
`.venv/bin/python -m pip install -r requirements.txt` and
`.venv/bin/python main.py`.

## Play

Choose Easy, Medium, or Hard, and select your stone color. Black moves first.
Click a board **intersection** to place a stone. Connect **five or more** stones
horizontally, vertically, or diagonally to win. This is **freestyle Gomoku**:
overlines count; there are no Renju forbidden moves or special opening rules.
A full board without a winner is a draw.

- **U / Undo turn:** remove your latest move and the AI's reply, if any.
- **R / New game:** restart with the current settings.
- **Esc:** return to settings; from the menu, exit.
- **Enter:** start from the menu.
- The end screen shows a win, loss, or draw, with replay and board review.
- The orange marker identifies the latest stone; a green line marks the win.
- Resize the window as needed. Drawing and mouse coordinates scale together.

Restart and menu navigation reset the current match. Scores and games are not
saved between sessions. Undo is available during AI thinking and after a game.

## How the AI works

The implementation uses classical game AI, not machine learning:

1. **Tactical checks:** find immediate winning moves, then mandatory blocks,
   including gaps inside four-stone lines. Tactical moves bypass the quiet-move
   limit. If both sides threaten a win, the AI completes its own five first.
2. **Local candidates:** examine empty cells within two intersections of an
   existing stone. An empty board opens at the center.
3. **Pattern recognition:** inspect four directions for open/closed fours,
   broken fours, open/broken threes, and smaller formations. Edges and opponent
   stones block patterns. Multiple threats receive a fork bonus.
4. **Move ordering:** combine offensive and defensive pattern scores, with a
   slight defensive preference and centrality as a tie-breaker. Retain a limited
   number of promising quiet moves to reduce the branching factor.
5. **Search:** iterative-deepening negamax with alpha-beta pruning. Cache exact,
   upper-bound, and lower-bound position evaluations in a per-search
   transposition table. Keep the best move from the last fully completed depth.
6. **Bounded work:** stop on the time limit, node limit, or cancellation. A legal
   fallback is always available. The interface reports actual completed depth,
   visited search nodes, cutoffs, and elapsed time.

| Difficulty | Maximum depth (plies) | Quiet candidates/node | Target time | Node limit |
|---|---:|---:|---:|---:|
| Easy | 1 | 6 | 0.20 s | 800 |
| Medium | 3 | 10 | 0.65 s | 5,000 |
| Hard | 5 | 14 | 1.40 s | 15,000 |

Limits are ceilings, not promised search depths. Dense positions may finish
fewer depths. Immediate wins, mandatory single blocks, and the opening can
return at depth 0 without visiting search nodes. Timing is cooperative and
subject to operating-system scheduling.

The opponent is selective and heuristic: it is **not an unbeatable or complete
Gomoku solver**. Limited depth can miss longer combinations. The decision text
describes local patterns around the selected move, not a proof of its strategy.

## Architecture and real-time state

| File | Responsibility |
|---|---|
| `main.py` | Application entry point |
| `gomoku/game.py` | Board, legal moves, turn ownership, wins, draws, undo |
| `gomoku/ai.py` | Pattern evaluation, move ordering, search, budgets |
| `gomoku/app.py` | Pygame event loop, rendering, menus, result screens |
| `tests/` | Rule, tactical, cancellation, and headless UI checks |

Only the main thread owns the live game and Pygame objects. A single worker
searches a **copied board**. Restart, undo, and menu actions cancel the old job;
revision checking and detached futures prevent stale results from changing a
new game. Search errors appear in the sidebar with a retry button. The draw
loop is capped at 60 FPS; actual frame rate depends on the machine.

Pygame's [display API](https://www.pygame.org/docs/ref/display.html) handles the
window and frame presentation; its [event API](https://www.pygame.org/docs/ref/event.html)
handles input. All graphics are drawn in code using system fonts.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use the standard library's `unittest`. UI tests use Pygame's actual drawing
and event code with SDL's dummy video driver, so they do not open a window.
They cover all four winning directions, overlines, interrupted lines, legal
moves, undo, draw detection, immediate wins and blocks, open-three defense,
fork recognition, search isolation/cancellation, resize mapping, stale results,
error handling, and win/loss/draw rendering.

Headless tests do not replace a manual desktop playthrough. For presentation,
try both colors, resize the window, undo while the AI thinks, and review the
final winning line. Explain the distinction between heuristic scoring and
search depth using the live AI panel.
