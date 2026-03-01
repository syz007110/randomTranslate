---
name: autopilot-manager
description: Manage persistent task execution using AUTOPILOT.md and tasks/*.md. Use when the user assigns a new task or asks to continue previous work, including phrases like "交给你一个任务", "布置一个任务给你", "继续上次xx任务", "接着做xx", "恢复任务", "先停自动任务". Handles task intake, pause/resume, progress logging, milestone updates, and next-step handoff.
---

# Autopilot Manager

Use this skill to run a standing task pool with interruption support.

## Files
- Task index: `/home/medbot/.openclaw/workspace/AUTOPILOT.md`
- Task details: `/home/medbot/.openclaw/workspace/tasks/*.md`

## Required workflow
1. On **new user task**:
   - Pause current `doing` task by updating its detail file.
   - Add/update a task row in `AUTOPILOT.md`.
   - Create a detail file if missing.
   - Set status to `doing` for the active task.
2. On **resume request** (e.g. “继续上次xx任务”):
   - Locate matching task in `AUTOPILOT.md`.
   - Read detail file section `进展与里程碑（合并）` and `下一步`.
   - Continue from the latest `下一步`.
3. On **stage completion / important update**:
   - Append one entry to `进展与里程碑（合并）` with timestamp, what was completed, status transition.
   - Update `下一步` with executable next action.
   - Update index progress and `最后更新`.
4. On **daily task**:
   - Keep status as `daily` in index.
   - Append completion note each day in the task detail file.

## Data rules
- Keep one detail file per task.
- Index is concise; details hold the history.
- Always preserve continuity: every update must include a usable `下一步`.

## Status vocabulary
- `todo`, `doing`, `blocked`, `done`, `daily`
