# Amber

**A lifelong-learning agent, built measurement-first.**

Amber is a from-scratch experiment in continual learning: one small
transformer (14.4M parameters) that lives on a single machine for months,
keeps learning new material without forgetting the old, survives restarts
bit-for-bit, and picks her own work.

This is not a frozen LLM with a database bolted on. The core learns — its
weights change every step — and everything around it exists to *measure*
whether that works.

## What is here

| module | what it does |
|---|---|
| `kern/determinisme.py` | determinism as a latch, not a promise — refuses to run if it can't guarantee bit-identical replay |
| `kern/checkpoint.py` | hardware-independent snapshots: fsync + atomic rename + checksum; restores across GPUs and torch versions |
| `kern/logboek.py` | append-only journal beside the snapshot; a power cut loses seconds, not hours |
| `kern/tekens.py` | byte-level codec, frozen forever |
| `kern/netwerk.py` | hand-written decoder-only transformer that can **grow**: inserting a layer changes the output bit-for-bit not at all |
| `kern/wereld.py` | her world — a grammar of composable tasks (arithmetic, sequences, code) where difficulty is a dial, not five steps |
| `kern/proefwerken.py` | frozen exams she can never train on, guarded in code |
| `kern/leren.py` | the learning loop: curiosity-driven choice, worked-out answers, replay through a memory bottleneck |
| `kern/toets-*.py` | 151 tests, including real SIGKILL crash tests |
| `brein/` | a live window into her brain: real activations, real wiring (green = positive weights, red = negative), her memories |

## Honest numbers so far

- **Catastrophic forgetting is real on this setup:** without protection she
  retains **7–13%** of a learned skill after learning something else.
- **Replay (37.5% of each batch) retains ~90%** — at a measured, reported cost.
- **EWC was tried and rejected**: it froze the whole network instead of
  protecting selectively. Negative results are kept.
- All headline numbers are measured over multiple seeds with spread reported;
  two out of three single-seed conclusions did not survive replication.

## Status

Phase 0 (machine, determinism, portable state) is done. Phase 1 (her world,
rest/recovery, first anti-forgetting mechanism) is underway — she is currently
in the middle of a 170,000-step run.

*The codebase is currently written in Dutch (the project's working language);
a full English migration is scheduled, with a compatibility shim so her
existing checkpoints survive the rename.*
