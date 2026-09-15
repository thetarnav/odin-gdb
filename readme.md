# Odin GDB script

Python pretty-printers to visualize Odin slices, maps, strings, etc. in GDB.

Ported from [odin-lldb](https://github.com/thetarnav/odin-lldb) (original ideas by [harold-b](https://gist.github.com/harold-b/ef16a5c3ebcceccfc2bc7a5c5dd0058d) and [laytan](https://gist.github.com/laytan/a94c323a84cef7bcfbdf6d21987fd5a9)).

## Requirements

- Odin compiler (`odin build main.odin -file -debug -out:main.bin`)
- Modern GDB (tested on GDB 12+; developed against GDB 17).

## Usage

Manual load:

```gdb
(gdb) source odin.py
```

Or pass `gdb -x odin.py ./main.bin`.

Auto-load (recommended): `main.bin-gdb.py` next to `main.bin` imports `odin.py`
automatically. GDB must permit it:

```gdb
(gdb) add-auto-load-safe-path /path/to/project
```

## Commands

- `print <var>` — pretty summary; containers also show ` = {children}` (native GDB behavior).
- `odin-children <var> [MAX]` — one child per line (`name = summary`), e.g.
  `odin-children my_slice`, `odin-children big_array 3` (first 3 children).

## Development

```bash
./test.py            # build + run GDB test suite
./debug_session.sh   # interactive GDB stopped at breakpoint()
```

Map `len`/`cap` trailer status under `display_hint("map")`: falls back to no hint —
verified on GDB 17.2 (Omarchy/Arch) that trailers corrupt map-hint rendering
(empty map showed `map[0]{} = {[0] = 0}`, non-empty leaked `[1] = 8`), so
`MapPrinter.display_hint()` returns `None` and children render struct-style.

## Resources

- https://sourceware.org/gdb/current/onlinedocs/gdb/Pretty-Printing.html
