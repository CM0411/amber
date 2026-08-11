# Archief — de Nederlandse tijd / the Dutch era

Amber's core was written in Dutch from 8 to 11 August 2026, and migrated
to English on 11 August 2026 — between run 3 and run 4, the one moment a
codebase swap cannot disturb a living run.

**Nothing here is dead code to be deleted.** These files are the method
behind measurements that still stand (the fase-1 verslagen in `fase1/`
reference these scripts), and the proof of where she comes from. Her
snapshots from this era carry Dutch weight keys forever; `kern/bridge.py`
carries those into the English core, and `kern/test-bridge.py` proves it
stays that way.

- `nl-kern/` — the Dutch core modules, their test suite, and
  `toets-migratie.py`: the 51 equivalence checks that proved, before the
  originals were retired, that the English mirror produces bit-for-bit
  identical tasks, worlds, learning steps and weights. That proof ran on
  11 Aug 2026 against the run-3 checkpoint; its result is recorded in the
  papieren (sessies/2026-08-11).
- `nl-fase1/` — the measurement scripts of phase 1 (nulmeting C, tweede
  mechanisme, hoeveel herhaling, muren) and `leven.py`, the runner of
  runs 1–3. `fase1/life.py` is its English successor.

The state language never changed: journal kinds and keys, snapshot
container keys, exam files and task texts are Dutch — they are her
memory, not our code.
