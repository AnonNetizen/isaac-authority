# Boundary write barrier candidate 1

Preserve the accepted boundary-handoff runtime and the pristine Lua 5.3.3 tree. Build an independent Windows x86 candidate with ABI `ia-lua533-boundary-writes-1`, plus a stock-Lua reference using the same model backend. No game process, mod edits, full value graph, audit stream, or world projection.

## Sequence

1. Selective table barriers: watch explicitly requested string/integer fields. Count every logical assignment, including same-value and A→B→A, from watch registration. Cover VM stores, raw API stores, table-library stores, metamethod destinations and weak GC clears. Rehash/resize copies are not assignments. Retire watches on table free or last owner removal.
2. Selective upvalue barriers: watch actual captured cells, including open stack slots. Count value stores, preserve identity/revision across stack relocation and closure closing, and retire on last callback owner removal. Shared closures use the same cell. Unsupported native rebinding fails explicitly.
3. Run bounded, repeatable CLI comparisons against stock Lua: ordinary results/bytes/errors, exact write deltas, unrelated-field stability, typed keys, native API writes, weak GC, closure sharing/closing/stack growth, lifetime churn, rollback and work limits. Consumer read sets remain a subsequent gate.

## Representation and limits

Only current counters and selected keys are retained, with at most 1,024 selected fields and 1,024 captured cells per context. No historical per-write record. A fixed native slot index tests whether a store targets a watched open/closed cell. Table lookup occurs once per logical store; unselected writes do not allocate field records. Shape revisions describe membership changes, separately from selected-field writes and metatable changes.

The existing 10,000,000 ledger limit remains. Watched writes, key processing and lifecycle events are charged; VM execution remains prepaid in 64-instruction blocks. All child tests have a 5-second timeout and 1-GiB process cap. The new work unit is not comparable to the retired full-trace unit. Unknown capabilities and capacity exhaustion reject, never silently establish purity.

## Boundary

These barriers establish exact mutation versions after registration, not dependency provenance, consumer read sets, menu isolation or reward projection. Personal stores remain separate; only host authority callbacks submit world changes. Personal draw queues remain unpublished until projection is proved. The compatibility rule remains `personal-settings-authority-hud-v1`.
