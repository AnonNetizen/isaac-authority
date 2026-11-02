# Compact read handles before boundary expressions

Keep the verified read-set runtime, its fixed single-evaluation tag barrier, source, binaries and reports unchanged. Build a separate x86 `ia-lua533-compact-reads-1` candidate using the same preserved Lua static library. No game, old full tracer, resource copy or ZIP.

1. Assign each watched field a monotonically increasing lifetime handle. Keep its typed key only in the live field map. Consumers store numeric dependency keys and handles rather than two string copies. A direct live-handle index resolves versions without rescanning a table.
2. Use transparent borrowed-key lookups for repeated reads and writes. Copy bytes only when installing a new field. On owner removal or table collection, retire the handle before freeing its key; never dereference a retired handle or reuse it for another field.
3. Keep legacy expanded diagnostics for regression. Add compact status and a separately requested live-key dictionary so large keys need not repeat per consumer. Expose logical retained-key byte counters and record-layout sizes; distinguish those from measured process memory.
4. Verify the original 50 read cases and 56 write/handoff cases unchanged. Add long keys, many consumers, A→B→A, siblings, embedded-NUL/typed keys, retirement/recreation, rollback and repeated replacement. Compare against the preserved read-set candidate and stock Lua. Every process has a 5-second timeout, a 10,000,000 work limit and a 1-GiB cap; stop batches after 60 seconds.

After handles are verified, attach actual API consumption locations and bounded backwards bytecode recipes for drawing arguments. A recipe is not a value/version proof: source observations, operand order, control flow, helper results and cross-frame stores still need proof before projection or reuse. Unknown paths must remain unresolved, never receive invented values. The goal remains unchanged mod source, independent personal settings and authoritative rewards.
