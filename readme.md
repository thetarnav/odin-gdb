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

## Development

```bash
./test.py          # build + run GDB test suite
./build.sh         # build main.odin with debug symbols
./debug_session.sh # interactive GDB stopped at breakpoint()
```

## Resources

- https://sourceware.org/gdb/current/onlinedocs/gdb/Pretty-Printing.html
