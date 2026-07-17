# Agent Log

Shared running log for agents working on this repo. **Read this before starting
work; update it when you start, pause, restart, or finish.** See the
"Multi-agent coordination" section of `CLAUDE.md` for the rules.

Conventions for entries:
- Use the real calendar date (`YYYY-MM-DD`). Newest history entry on top.
- Identify yourself by a short handle + your git branch.
- Keep it factual: what you changed, why, and any follow-ups the next agent
  needs to know.

---

## Active work (in progress)

Add a row when you start; remove it (and add to history below) when you finish.

| Agent | Branch | Task | Started | Status |
|---|---|---|---|---|
| _(none)_ | | | | |

---

## Completed / history (newest first)

### 2026-07-17 — agent "opus" (branch: main)
- Documented the 6-pin encoder connector pinout in `firmware/WIRING.md`
  (A/B phase, Vcc, GND, M-, M+ → Arduino pins) and noted the vendor diagram's
  duplicate "A phase" label on pin 2 is a typo (it's the B phase).
- Committed `chassis/` vendor reference photos (incl. the encoder diagram the
  doc links to). Excluded `.DS_Store`.
- Added `.gitignore` for `.DS_Store` and removed the 3 already-tracked ones
  under `cad/`.
- Added this `AGENT_LOG.md` and `CLAUDE.md` (repo conventions + multi-agent
  coordination rules).
- Pushed to `origin/main`.
- **Follow-ups / open items** (from BUILD.md §13): Jetson-side Python serial
  wrapper + tracking loop (not yet written); MPU6050 heading-hold folded into
  the control loop (firmware reads yaw rate but doesn't act on it — needed for
  precise "turn to angle" since the camera is too slow for fast heading
  feedback); wheel-size/shell fit (63 mm vs ~97 mm); camera calibration.
