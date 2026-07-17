# CLAUDE.md — guidance for agents working in this repo

This is the **MSE-6 "Mouse Droid"** build: a CNC-plywood Star Wars mouse-droid
shell over an off-the-shelf 4WD encoder chassis, made autonomous with an
Arduino (real-time motion) + NVIDIA Jetson Orin Nano (vision). It is a
hardware project — the repo is **documentation, CAD, and firmware**, not a
conventional software app.

**Read `BUILD.md` first.** It is the master document and the single source of
truth for architecture, BOM, power, wiring, firmware config, and design
rationale. Do not duplicate its content elsewhere — link to it by section
(e.g. "see BUILD.md §4").

---

## Architecture in one breath

Two brains, talking over one USB serial cable (115200 baud):
- **Arduino Uno = reflexes** (hard real-time): reads encoders, runs a 50 Hz
  per-side PID velocity loop, drives two BTS7960 H-bridges in **skid-steer**
  (both left motors on one driver, both right on the other).
- **Jetson Orin Nano = cortex** (perception): camera tracking, turns
  high-level goals into `L<mm/s> R<mm/s>` / `stop` commands.

Serial protocol and pin map live in `BUILD.md` §6–§7 and `firmware/WIRING.md`.

## Repo layout

| Path | What it is | Edit by hand? |
|---|---|---|
| `BUILD.md` | Master build doc (source of truth) | Yes (text) |
| `firmware/mouse_droid_controller/*.ino` | Arduino sketch (the only code) | Yes |
| `firmware/WIRING.md` | Pin map + wiring diagrams | Yes (text) |
| `cad/*.blend`, `Mse-6/*.fbx/.obj/.mtl` | 3D models | **No** — binary; edit in Blender only |
| `cad/mouse-droid-panels.svg` | Shaper Origin cut file | Only with care (CNC-critical) |
| `cad/assembly-guide.html`, `cad/renders/` | Assembly guide + renders | Guide: yes; renders: regenerate from Blender |
| `chassis/` | Vendor reference photos | Add only |

## Conventions

- **Commit/push only when the user asks.** Don't auto-commit.
- End commit messages with the required `Co-Authored-By` trailer.
- `.DS_Store` is git-ignored — never re-add it.
- Don't hand-edit binary assets (`.blend`, `.fbx`, `.obj`). Regenerate renders
  from Blender; note in the log if you do.
- **Firmware safety constants must be verified against real hardware before
  trusting them** — especially `WHEEL_DIAMETER_MM` (placeholder 80; the shell
  was designed for 63 mm wheels, chassis ships ~97 mm) and `COUNTS_PER_REV`
  (360, assumes 6 PPR × 2 edges × 1:30 gear — verify by hand-rotating a wheel).
  See BUILD.md §7 and the §9 bring-up checklist. Flag, don't silently change.
- Keep a single source of truth: dimensions/BOM/rationale live in `BUILD.md`;
  other docs link to it rather than restating.

---

## Multi-agent coordination

Two (or more) agents may work in this repo. `CLAUDE.md` sets shared
*conventions*; it does **not** lock files. Real coordination is git + the log
below. Rules:

1. **One branch per agent. Do not both commit to `main` at the same time.**
   Name your branch for the work (e.g. `jetson-serial`, `firmware-turn-mode`).
   Merge to `main` only when a unit of work is complete and the user approves.
2. **Prefer separate git worktrees** if running concurrently in the same clone,
   so each agent has its own working tree and index (avoids clobbering).
3. **Before starting work, read `AGENT_LOG.md`** to see what the other agent is
   doing and what's already done. Claim your task by adding a row to the
   *Active work* table.
4. **When you finish (or pause/restart), update `AGENT_LOG.md`**: move your item
   to the *Completed / history* log with what changed and any follow-ups. On a
   restart, read the log first to recover where you left off.
5. If two agents need the same file, coordinate through the log rather than
   editing in parallel.

The log is the shared memory between agents. Keep it current — it's how an
interrupted agent (or the other one) knows the state of the world.
