# Agent Handoff — Isaac Co-op Authority Research

Public repository: <https://github.com/AnonNetizen/isaac-authority>

This repository contains two related tracks:

1. **`Watch out, laser!` stability patch v2** — a small, user-facing patch for a
   specific Repentance+ co-op desync source. This is usable as a targeted fix, but it
   is **not** a general co-op repair.
2. **Host-authoritative co-op research (`authority/`)** — a Windows x86 injector and
   read-only/experimental probes that study the J460 engine. **It is not playable yet.**
   `playable=false` in every current report is accurate.

Read this file before changing engine-facing code. The operating rule is:
**verify before claiming; keep the game’s saves and the public repository clean.**

---

## 1. Where we are (2026-11-02)

### Confirmed engine facts (J460, `v1.9.7.17`, exe SHA256 `210cade2...3ea4831`)

- Image base in reports is the runtime module base; offsets below are RVAs.
- `Game*` singleton: `base + 0x871678`
- Frame counter: `Game + 0x264F8` (u32)
- Level pointer: `Game + 0x18300`
- Current room index: `Game + 0x18304` (u32)
- Previous room index: `Game + 0x18308` (u32)
- Room-index duplicate: `Game + 0x1B850` (u32, normally equal to `0x18304`)
- Player vector: `Game + 0x1BAA8` (start), `Game + 0x1BAAC` (end), elements are
  `EntityPlayer*`
- Entity array: `Level + 0x125C` (pointer), `Level + 0x1260` (capacity bytes),
  `Level + 0x1264` (count)
- Entity fields:
  - Type `+0x28` (u32)
  - Variant `+0x2C` (u32)
  - Position `+0x33C` (float x, y); `+0x38C` is a lagging copy, **not** authoritative
  - Velocity `+0x360` (float x, y)
  - Size `+0x370` (float)
  - InitSeed `+0x3EC` (u32); `+0x3DC` is a different seed field
- **`0x2fadc0` is a per-frame sub-update**, not the complete simulation entry.
  It is called once per frame with `ecx = Game*` and increments the frame counter.
  Skipping it leaves the player moving.
- **`0x554cd0` is the real per-frame gameplay update** used for takeover/skip.
  It is `__thiscall`-like with **one argument** and ends in `ret 4`. It runs about
  60 times/second. Skipping it freezes player position; the hook must return with
  `ret 4`, not `ret`.
- `0x2f7ac0` is a higher-level caller with `ret 8` (two arguments). Not yet used.
- Stage offset is still **unknown**; `Level + 0x8` was proven not to be Stage.

Evidence (local, not committed because run artifacts are large):
`authority/runs/skip-20261102-5`, `skip-20261102-7`, `skip-20261102-9`,
`state-20261101-2`, `state-20261101-3`, `packet-20261102-2`, `packet-20261102-3`.
Summaries: `authority/docs/ENGINE_LAYOUT_P0.md`, `authority/docs/AUTHORITY_P1.md`.

### Verified runtime behavior

- Read-only state discovery works: player vector, entity array, entity fields, room
  index, and frame counter can be read from the injected DLL.
- Native state packet (binary layout in `native/probe.cpp`):
  `frame, roomIndex, previousRoom, playerCount, players[], entityCount, entities[]`.
  At low entity counts: 116–260 bytes/frame, ~231 µs/frame after block reads.
- Skipping `0x554cd0` for 2 s and 5 s freezes player movement and frame counter;
  the hook is then removed and the game recovers. See `skip-probe.json` in the runs.
- The game pauses when unfocused. A stalled frame counter while the foreground window
  is not `isaac-ng` is expected, not a hook bug.

### Not done (do not claim otherwise)

- Guest-side render inside the game. Offline `apply_guest_view()`
  (`native/guest_apply.*`) can apply a `GuestView` plan through a replaceable
  memory interface: position `+0x33C`, velocity `+0x360`, and size `+0x370`,
  and only when the bound token is a non-null pointer in the live entity array
  whose Type `+0x28`, Variant `+0x2C`, and InitSeed `+0x3EC` match the snapshot.
  Spawn and despawn are reported and not performed. The probe DLL does not call
  it. No live process has skipped `0x554cd0` while applying host state, and
  this does not render.
- In-game use of the pointer-free snapshot. The offline model
  (`native/state_model.*`) keeps a network id across `kIdentityGraceCaptures`
  (3) missed publishes when Type `+0x28`, Variant `+0x2C`, and InitSeed
  `+0x3EC` match. The host pointer is only a tie-break hint. Deltas, version,
  checksum, and loss/reorder are unit-tested. Host capture bytes still contain
  pointers; the guest wire does not. No live process has confirmed that
  InitSeed stays stable, or how `isaac-ng` reuses pointers.
- Steam wiring. `AuthorityLink` handshake, state/input channels, reconnect, and
  snapshot recovery are tested on `LoopbackHub` only. `SteamTransport` still
  speaks the older JSON/CBOR session on channel 197460.
- Per-player UI/menu/language/position/key/save/unlock isolation.
- Stage offset, room descriptor/tile state, complete player stats/items/animation.
- Dual-machine acceptance and 30-minute soak.
- Any “playable” status. Keep `playable=false` until the acceptance table in
  `authority/GOAL_STATUS.md` is satisfied.

---

## 2. Repository layout

```
.
├─ README.md                     # v2 stability patch + how to use
├─ coop_guard.lua                # v2 guard module
├─ patch_watch_out_laser.py/.ps1 # v2 installer, status/restore/verify/diagnose
├─ test_stability_patch.py       # 49 Python tests
├─ build_release.py              # builds artifacts/ISAAC-Coop-Stability-v2.zip
├─ legacy/                       # v1 rollback fixture
└─ authority/
   ├─ CMakeLists.txt             # x86 injector/probe build
   ├─ native/                    # DLL: Lua bridge, probes, MinHook, Steam adapter
   ├─ tools/                     # build/run scripts, samplers, analyzers, verifiers
   ├─ tests/                     # native tests (38 when last run)
   ├─ docs/                      # research records; start with P0/P1/TOOLING_FIXES
   ├─ research/                  # frozen Lua/JSON research fixtures (large but text)
   ├─ fixtures/                  # Lua test mods
   ├─ third_party/               # Lua 5.3.3, MinHook, nlohmann/json, Steam headers
   └─ lua/                       # observer probe Lua
```

Not committed on purpose:

- `authority/reports/` (~31 GB of generated JSON), `authority/runs/` (~177 MB),
  `authority/build-*/`, `authority/artifacts/`, `authority/*.log`;
- top-level `backups/` (save backups), `artifacts/` (release ZIP), `.tools/`
  (local Python packages);
- `authority/research/slice3_ui_inputs/` — vendored third-party mod sources used only
  as local input; not redistributed.

A fresh clone is **source + docs + fixtures**, not a copy of the experiment outputs.
Re-run the probes to reproduce evidence.

---

## 3. Prerequisites

- Windows 10/11 x64; target game is **32-bit** (`isaac-ng.exe`, J460).
- Visual Studio 2026 C++ x86 toolchain + CMake (the scripts locate `vswhere`).
- Python 3.12; `lupa` and `capstone` are optional for tools and live in `.tools/`.
- The installed game must match the hashed baseline; the launcher refuses unknown exe
  hashes. The current accepted hash is in `authority/README.md` and launch reports.
- The game must be **closed** before building the probe DLL (Windows locks loaded DLLs).
- Save backups must exist before any experiment that can touch an existing save.
  Use a seed run or a disposable save; never commit saves.

## 4. Build and test

```powershell
# Game MUST be closed; the build refuses while isaac-ng is running.
authority\tools\build.ps1 -BuildDirectory build-engine-layout

# Native tests are part of the build; last result: 38 passed.
# Stability patch tests:
py -3 -m pytest -q test_stability_patch.py

# Python tool syntax check:
py -3 -m py_compile authority\tools\sample_room_transition.py `
  authority\tools\analyze_state_offsets.py authority\tools\sample_game_stacks.py
```

The probe binary is `authority/build-engine-layout/Release/isaac_authority_probe.dll`;
the launcher is `isaac-authority.exe` in the same directory.

## 5. Running probes

General shape:

```powershell
authority\tools\run.ps1 -Game '<game dir>' -Mode attach -ProcessId <pid> `
  -BinaryDirectory 'authority\build-engine-layout\Release' `
  -OutputDirectory 'authority\runs\<fresh-name>' <probe flags>
```

Important runtime rules:

- The DLL stays resident until the game exits. A second `--attach` returns
  “observer already initialized”; restart the game for a new probe.
- The launcher waits for a fresh output directory; never reuse one.
- Keep the game window focused while a frame-dependent probe is running.
  Isaac pauses when unfocused; probes may wait up to 10 minutes for gameplay.
- The probe mode stops after writing its report and disables its hooks. Check
  `call-probe.json` / `state-probe.json` / `skip-probe.json` and `native.jsonl`.
- Do not run experiments against a save you are not willing to lose.

Useful commands:

```powershell
# State fields (waits for a run; read-only)
... -StateProbe

# Per-frame call count + packet stats; candidate 0x2fadc0 is the sub-update
... -CallProbe -CandidateRva '0x2fadc0' -ProbeMs 15000 -CapturePacket

# Skip the real gameplay update; 0x554cd0 requires ret 4
... -SkipProbe -CandidateRva '0x554cd0' -SkipRet 4 -SkipCycles '5000,5000'

# Optional second hook for packet size/time. Not verified in-game after the
# null-entry fix. 0x2fadc0 is the sub-update, not the skip target.
... -SkipProbe -CandidateRva '0x554cd0' -SkipRet 4 -SkipCycles '2000,5000,2000' -PacketRva '0x2fadc0'
```

`--skip-cycles` is a comma-separated list of milliseconds (500–10000, max 5).
`--capture-state` and `--capture-packet` require `-CallProbe`.
`--packet-rva` requires `-SkipProbe` and must differ from `-CandidateRva`.
`--skip-probe` is one-shot per game process. The owner checklist is
`authority/tools/live_acceptance.py`.

## 6. Current probes and what they write

- `--state-probe` → `state-probe.json` (Lua truth + Game/Level/entity dumps).
- `--call-probe` → `call-probe.json` (calls/frame, ecx, optional packet stats).
- `--skip-probe` → `skip-probe.json` (cycles, frame deltas, player displacement,
  recovery, hook disabled). With `--packet-rva`, the same file also gets
  `packet_hook`, `packet_rva`, and `packet_phases`. That combined report has
  not been produced in-game since the packet hook was made opt-in.
- `--layout-probe`, `--api-probe`, `--runtime-probe` are older diagnostics; keep
  their documented scope and do not treat them as playable acceptance.

## 7. Known traps (read before editing)

- **Frame reads for arbitrary hooks must use the global `Game*`**, not the hook’s
  `ecx`. `0x554cd0`’s `ecx` is not `Game*`; using it caused a false “not in run”.
- **Respect the callee’s return cleanup.** `0x2fadc0` = `ret`, `0x554cd0` = `ret 4`,
  `0x2f7ac0` = `ret 8`. Wrong cleanup corrupts the caller’s stack.
- **`0x2fadc0` is not enough to freeze the simulation.** Use `0x554cd0`.
- **Focus loss pauses the game.** Check the foreground window before treating a
  frame stall as a bug. A notification helper is in `authority/tools/notify.ps1`.
- The observer overlay disappearing/stopping in a skip run is expected; skip mode
  disables the Lua observer.
- Build while the game is running fails with `LNK1104`; close the game.
- Never commit `authority/runs`, `authority/reports`, `backups`, or build trees.
- Public docs were sanitized of local `C:/Users/<name>` paths; keep them placeholder.

## 8. Next work, in priority order

Offline pieces below are implemented and covered by `authority-state-tests`.
They are not in-game results. `playable` stays false.

1. **High-entity packet + batch** — still needs the owner, on a new game process,
   in a room with 30–60 entities, window focused. Command is the `skip-packet`
   step in `authority/tools/live_acceptance.py` (`0x554cd0`, `--skip-ret 4`,
   `--packet-rva 0x2fadc0`). Do not treat it as done until `skip-probe.json`
   shows `packet_hook=true` and `normal_before.entities_max >= 30`. The last
   in-game timing is still the low-entity ~231 µs figure.
2. **Guest render inside the game** — not implemented. Offline
   `apply_guest_view()` writes position, velocity, and size through
   `GuestMemory` and is covered by `authority-state-tests`. It accepts only the
   measured exe hash `210cade2...3ea4831`. A null, out-of-range, or unmatched
   token is rejected, and a missing token is not replaced by another entity
   with the same triple. `Game*` and `Level*` field addresses go through
   `field_address()`; a sum that does not fit in 32 bits is `out_of_bounds`
   and writes nothing. `guest_exe_sha256_from_hex` stops at the terminator. Spawn and despawn plans are counted as not performed.
   There is no launcher switch. `probe.cpp` does not call it. No in-game
   command writes entity memory, and skipping `0x554cd0` (`ret 4`) while
   applying a snapshot has not been run.
3. **State model** — offline model is in `native/state_model.*`. Network ids
   follow Type `+0x28`, Variant `+0x2C`, and InitSeed `+0x3EC` (`+0x3DC` is a
   different field and is not an identity). The host pointer is a tie-break
   hint, not the identity. The same triple can miss `kIdentityGraceCaptures`
   (3) published captures and keep its id; the next miss is one despawn. A
   reused pointer with a different triple gets a new id. Two live entities
   with the same triple stay distinct: matching pointer hint, otherwise
   capture order paired with ascending id. A room change or a new run (the
   frame counter goes backwards) clears the map. An interval keyframe or
   `force_keyframe()` does not. Applying this to a running guest is not done.
   Animation, items, tiles, and stage are not in the snapshot. InitSeed
   stability across real frames is not verified.
4. **Networking** — loopback handshake, channels, pause, reconnect, and keyframe
   recovery are tested. Steam is not wired to `AuthorityLink`. Two machines
   have not exchanged packets.
5. **Per-player UI/save/unlock isolation** — still open. Do not hide or skip
   these gates.
6. **Dual-machine acceptance** — 30 min co-op, combat, room transitions, pickups,
   death/revive, menus/HUD, save/unlock, reconnect. Still open. The printed
   capture/preview commands only start the old JSON observer.

## 9. Multi-agent coordination

- One writer per file. Use the shared task board/`team_task*` tools if available;
  declare write scopes before editing.
- Engine/game runs are exclusive: only one agent may inject or run a probe at a time.
  Close the game before any rebuild; announce the run directory.
- Prefer small, reviewable commits. Do not commit generated evidence.
- If a claim is not reproducible from source + a run artifact, mark it unverified.
- Keep `playable=false` and the acceptance table honest. A passing dry run is not a
  playable co-op implementation.
- Update `authority/docs/AUTHORITY_P1.md` and `TOOLING_FIXES.md` when a probe result
  changes a contract.

## 10. Verification checklist for a new agent

1. Read `authority/docs/ENGINE_LAYOUT_P0.md`, `AUTHORITY_P1.md`, `TOOLING_FIXES.md`,
   `GOAL_STATUS.md`.
2. Build with the game closed; confirm `authority-tests` (38) and
   `authority-state-tests`, plus the 49 Python tests, pass. On a machine without
   the game, `cmake -S authority -B authority/build-host-tests -DIA_HOST_TESTS=ON`
   builds the portable tests only.
3. Run `--state-probe` in a seed run; confirm offsets and room index against Lua truth.
4. Run `--skip-probe -CandidateRva 0x554cd0 -SkipRet 4`; confirm displacement 0,
   frame delta 0, recovery, hook disabled. The high-entity batch adds
   `-PacketRva 0x2fadc0` and is a separate fresh process.
5. Only then start a new engine-facing change. Keep backups and a disposable save.
