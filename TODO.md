# odin-gdb TODO (deferred from v1)

- [ ] **Full SOA slice/dynamic-array children** — v1 ships summary-only
  (`SoaSlicePrinter` has empty `children()`). Blocked on Odin debug-info shape;
  see [odin-lang/Odin#5611](https://github.com/odin-lang/Odin/issues/5611).
  When DWARF is fixed, add per-element `children()` mirroring `SlicePrinter`
  (flat `[i]` yields, no chunking).
  - 2026-09-15 probe (Odin dev-2026-09, GDB 17.2): `&soa_dyn_array[1]` has the
    same address value as `&soa_dyn_array` — the element index is unknowable
    from DWARF, so SOA pointers degrade to `&` + whole-array summary, e.g.
    `&[3]{{"SOA1", 1}, {"SOA2", 2}, {"SOA3", 3}}`. Same limitation, same issue.
- [x] **Map `len`/`cap` trailer vs `display_hint("map")`** — experiment run on
  GDB 17.2 (Omarchy/Arch): trailers corrupt map-hint rendering (empty map
  showed `map[0]{} = {[0] = 0}`, non-empty map leaked `[1] = 8` as a phantom
  entry). Fell back to `display_hint() -> None` (keeps trailers, loses native
  map formatting); children render struct-style. If a future GDB tolerates
  trailers under the map hint, re-enable `return "map"`.
- [ ] **`set print elements` tuning** — v1 leaves the default (200). Revisit if
  large values render slowly in interactive use.
- [ ] **Proc display polish** — v1 hardcodes `proc "c"` (matches odin-lldb).
  Calling-convention fidelity (`"contextless"` etc.) is future work.
