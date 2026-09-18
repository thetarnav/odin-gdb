# Odin GDB script

Python pretty-printers to visualize Odin slices, maps, arrays, etc. in GDB.

Ported from [odin-lldb](https://github.com/thetarnav/odin-lldb) (original ideas by [harold-b](https://gist.github.com/harold-b/ef16a5c3ebcceccfc2bc7a5c5dd0058d) and [laytan](https://gist.github.com/laytan/a94c323a84cef7bcfbdf6d21987fd5a9)).

## Usage

Manual load:

```gdb
(gdb) source odin.py
```

Or pass `gdb -x odin.py ./main.bin`.

Or auto-load: `main.bin-gdb.py` next to `main.bin` imports `odin.py`
automatically. GDB must permit it:

```gdb
(gdb) add-auto-load-safe-path /path/to/project
```

Or add to global config:

```sh
echo "source path/to/odin.py" >> "~/.gdbinit"
```

## Commands

- `print <var>` — pretty summary.
- `odin-children <var> [MAX]` — one child per line (`name = summary`), e.g.
  `odin-children my_slice`, `odin-children big_array 3` (first 3 children).
- `odin-call PROC(ARG, ...)` — call a procedure with hidden args supplied,
  e.g. `odin-call add_ints(2, 3)`, `odin-call foo_value(foo)`.
  For imported procs quote the symbol: `odin-call 'main::add_ints'(2, 3)`.

## Calling Odin procs

`odin-call` evaluates a call in the stopped inferior and prints the result:

```gdb
(gdb) odin-call add_ints(2, 3)
$1 = 5
```

Rules:

- Inferior must be stopped (e.g. at `breakpoint()`); pure procs preferred —
  calling a proc with side effects mutates program state.
- Hidden args are handled: `&context` is appended automatically for
  `odin`-default procs (`contextless`/`"c"` procs take none).
- Multi-return procs need explicit sret slot addresses as trailing args
  (automatic slot allocation is planned).
- GDB must be allowed to call: `set may-call-functions on` (default on);
  a breakpoint hit inside the callee or a stopped thread aborts the call —
  locking is restored, temps may leak on that failure path only.
- Dummy-frame notes: results live in `$N` history like `print`; `ptype`
  shows the lowered signature when the sugared call is refused.
- Package-level procs resolve by bare name with automatic `main::`-style
  discovery — quote only if ambiguous: `'pkg::proc'`.
- LIMIT: by-value struct args over 16 bytes may misdeliver (hidden-pointer
  codegen vs by-value DWARF) — pass pointers (`&foo`) instead.

## Development

```bash
./test.py          # build + run GDB test suite
./build.sh         # build main.odin with debug symbols
./debug_session.sh # interactive GDB stopped at breakpoint()
```

## Resources

- https://sourceware.org/gdb/current/onlinedocs/gdb/Pretty-Printing.html
