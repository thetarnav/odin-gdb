"""
Python script to visualize Odin slices, maps, strings, etc. in GDB.

Based on harold-b's script: https://gist.github.com/harold-b/ef16a5c3ebcceccfc2bc7a5c5dd0058d
and laytan's script: https://gist.github.com/laytan/a94c323a84cef7bcfbdf6d21987fd5a9

Ported from odin-lldb (LLDB pretty-printers) to native GDB pretty-printers.
Reference: https://github.com/thetarnav/odin-lldb
Repository: https://github.com/thetarnav/odin-gdb
"""

import gdb
import dataclasses
import enum
from collections.abc import Callable


# ------------------------------------------------------------------------------
# Odin type dispatch

class Odin_Type(enum.Enum):
    Slice               = "slice"
    Array               = "array"
    String              = "string"
    Map                 = "map"
    Struct              = "struct"
    Ptr                 = "pointer"
    Enum                = "enum"
    Bitset              = "bitset"
    SOA_Slice           = "soa_dynamic_array"
    Fixed_Dynamic_Array = "fixed_dynamic_array"
    Other               = "other"
    Union               = "union"

def get_odin_type(t) -> Odin_Type:

    if t.code == gdb.TYPE_CODE_STRUCT:
        name = t.tag or str(t)

        if name == "string":
            return Odin_Type.String

        if name.startswith("[dynamic;") and not name.endswith(']'):
            return Odin_Type.Fixed_Dynamic_Array

        if (
            (name.startswith("[]") or name.startswith("[dynamic]")) and
            not name.endswith(']')
        ):
            return Odin_Type.Slice

        if (
            (name.startswith("#soa[]") or name.startswith("#soa[dynamic]")) and
            not name.endswith(']')
        ):
            return Odin_Type.SOA_Slice

        if name.startswith("map["):
            return Odin_Type.Map

        return Odin_Type.Struct

    if t.code == gdb.TYPE_CODE_ARRAY:
        return Odin_Type.Array

    if t.code == gdb.TYPE_CODE_ENUM:
        return Odin_Type.Enum

    if t.code == gdb.TYPE_CODE_UNION:
        if (t.tag or "").startswith("bit_set["):
            return Odin_Type.Bitset

        try:
            fields = t.fields()
        except Exception:
            return Odin_Type.Other
        if fields and fields[0].name == "tag":
            return Odin_Type.Union

        return Odin_Type.Other

    if t.code == gdb.TYPE_CODE_PTR:
        return Odin_Type.Ptr

    return Odin_Type.Other

def value_summary(v, _depth: int = 0) -> str:
    # Depth guard—prevent RecursionError.
    if _depth > 5:
        return "..."
    try:
        printer = lookup_odin(v)
    except Exception:
        printer = None
    if printer is not None:
        try:
            s = printer.to_string()
        except Exception as e:
            return f"<error: {e}>"
        if isinstance(printer, Printer_String):
            return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')
        try:
            return str(s)
        except Exception:
            return "<no value>"
    try:
        return str(v)
    except Exception:
        return "<no value>"

AGGREGATE_SUMMARY_MAX_LEN = 60

def aggregate_value_summary(
    prefix:    str,
    suffix:    str,
    get_value: Callable[[int], str],
    length:    int,
) -> str:
    summary = prefix

    for i in range(length):
        item = get_value(i)

        separator = ", " if i > 0 else ""
        new_length = len(summary) + len(separator) + len(item) + len(suffix)

        if new_length > AGGREGATE_SUMMARY_MAX_LEN and i > 0:
            summary += "..."
            break

        summary += separator + item

    return summary + suffix

def get_len(v) -> int:
    return int(v["len"])

def get_cap(v) -> int:
    return int(v["cap"])

def get_data(v):
    return v["data"]


# ------------------------------------------------------------------------------
# String Values
#
# Same layout as a slice,
#    Raw_String :: struct {
#        data: [^]u8,
#        len:  int,
#    }
#
# Odin strings are UTF-8 encoded.
#
# NOTE: to_string() returns the RAW text (no quotes).
# GDB adds quoting and escaping natively because display_hint() is "string".

class Printer_String:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        try:
            length = int(self.val["len"])
        except gdb.error:
            return "<no value>"
        if length == 0:
            return ""
        try:
            data_addr = int(self.val["data"])
        except gdb.error:
            return "<no value>"
        if data_addr == 0:
            return "{nil, %d}" % length
        try:
            raw = bytes(gdb.selected_inferior().read_memory(data_addr, length))
        except gdb.MemoryError:
            return "<error reading string>"
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return "<error decoding string>"

    def children(self):
        return iter(())

    def display_hint(self):
        try:
            if int(self.val["len"]) != 0 and int(self.val["data"]) == 0:
                return None
        except gdb.error:
            return None
        return "string"


# ------------------------------------------------------------------------------
# Slice Values
#
# handles both slices and dynamic arrays
# since the layout is the same:
#
#    Raw_Slice :: struct($T: typeid) {
#        data: [^]T,
#        len:  int,
#    }
#
#    Raw_Dynamic_Array :: struct($T: typeid) {
#        data:      [^]T,
#        len:       int,
#        cap:       int,
#        allocator: ^runtime.Allocator,
#    }

class Printer_Slice:
    def __init__(self, val) -> None:
        self.val = val

    def _len_data(self):
        try:
            return int(self.val["len"]), self.val["data"]
        except gdb.error:
            return None, None

    def _elem_summary(self, data, i: int) -> str:
        try:
            return value_summary((data + i).dereference())
        except Exception:
            return "<error>"

    def to_string(self):
        length, data = self._len_data()
        if length is None:
            return "<no value>"
        if length == 0:
            return "[0]{}"
        try:
            data_null = int(data) == 0
        except Exception:
            data_null = True
        if data_null:
            return "[%d]{<nil data>}" % length
        return aggregate_value_summary("[%d]{" % length, "}",
            get_value=lambda i: self._elem_summary(data, i),
            length=length,
        )

    def children(self):
        length, data = self._len_data()
        if not length:
            return iter(())
        try:
            if int(data) == 0:
                return iter(())
        except Exception:
            return iter(())
        def gen():
            try:
                for i in range(length):
                    yield ("[%d]" % i, (data + i).dereference())
            except Exception:
                return
        return gen()

    def display_hint(self):
        return "array"


# ------------------------------------------------------------------------------
# Fixed-Capacity Dynamic Array Values
#
# Layout:
#    struct {
#        data: [N]T,
#        len:  int,
#    }
#
# DWARF tag: [dynamic;N]pkg::T (e.g. [dynamic;100]main::Foo).
# Unlike slices/dynamic arrays, data is an inline array, not a pointer,
# so there is no nullable address and no null-data branch.

class Printer_Fixed_Capacity_Dynamic_Array:
    def __init__(self, val) -> None:
        self.val = val

    def _len_data(self):
        try:
            length = int(self.val["len"])
            data = self.val["data"]
        except gdb.error:
            return None, None
        if length < 0:
            length = 0
        try:
            lo, hi = data.type.strip_typedefs().range()
            capacity = hi - lo + 1
        except Exception:
            capacity = length
        if length > capacity:
            length = capacity
        return length, data

    def _elem_summary(self, data, i: int) -> str:
        try:
            return value_summary(data[i])
        except Exception:
            return "<error>"

    def to_string(self):
        length, data = self._len_data()
        if length is None:
            return "<no value>"
        if length == 0:
            return "[0]{}"
        return aggregate_value_summary("[%d]{" % length, "}",
            get_value=lambda i: self._elem_summary(data, i),
            length=length,
        )

    def children(self):
        length, data = self._len_data()
        if not length:
            return iter(())
        def gen():
            try:
                for i in range(length):
                    yield ("[%d]" % i, data[i])
            except Exception:
                return
        return gen()

    def display_hint(self):
        return "array"


# ------------------------------------------------------------------------------
# SOA Slice / Dynamic Array
#
# Layout:
#   struct {
#       field_1:   [^]Field_1,
#       field_2:   [^]Field_2,
#       field_3:   [^]Field_3,
#       ...                     ...or for slices:  ...
#       __$len:    int,                     |      __$len:    int,
#       __$cap:    int,                     |      <no more fields>
#       allocator: ^runtime.Allocator,      |
#   }

class Printer_SOA_Slice:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        try:
            length = int(self.val["__$len"])
        except gdb.error:
            return "<no value>"
        if length == 0:
            return "[0]{}"
        try:
            all_fields = self.val.type.strip_typedefs().fields()
            len_idx = [f.name for f in all_fields].index("__$len")
            user_fields = [f for f in all_fields[:len_idx] if f.name]
        except Exception:
            return "<error reading soa>"
        def get_soa_value(i: int) -> str:
            parts = []
            for f in user_fields:
                try:
                    ptr = self.val[f.name]
                    elem_type = ptr.type.strip_typedefs().target()
                    addr = int(ptr) + i * elem_type.sizeof
                    elem = gdb.Value(addr).cast(elem_type.pointer()).dereference()
                    parts.append(value_summary(elem))
                except Exception:
                    parts.append("<error>")
            return "{" + ", ".join(parts) + "}"
        return aggregate_value_summary("[%d]{" % length, "}", get_soa_value, length)

    def children(self):
        return iter(())

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Array Values

class Printer_Array:
    def __init__(self, val) -> None:
        self.val = val

    def _length(self) -> int:
        try:
            lo, hi = self.val.type.strip_typedefs().range()
            return hi - lo + 1
        except Exception:
            return 0

    def _elem_summary(self, i: int) -> str:
        try:
            return value_summary(self.val[i])
        except Exception:
            return "<error>"

    def to_string(self):
        length = self._length()
        if length == 0:
            return "[0]{}"
        return aggregate_value_summary("[%d]{" % length, "}",
            get_value=self._elem_summary,
            length=length,
        )

    def children(self):
        length = self._length()
        if length == 0:
            return iter(())
        def gen():
            try:
                for i in range(length):
                    yield ("[%d]" % i, self.val[i])
            except Exception:
                return
        return gen()

    def display_hint(self):
        return "array"


# ------------------------------------------------------------------------------
# Struct Values
#
# Default for any struct type that is not a built-in type.

class Printer_Struct:
    def __init__(self, val) -> None:
        self.val = val

    def _fields(self):
        try:
            return [f for f in self.val.type.strip_typedefs().fields() if f.name]
        except Exception:
            return []

    def to_string(self):
        fields = self._fields()
        def get_value(i: int) -> str:
            try:
                return value_summary(self.val[fields[i].name])
            except Exception:
                return "<no value>"
        return aggregate_value_summary("{", "}", get_value, len(fields))

    def children(self):
        fields = self._fields()
        if not fields:
            return iter(())
        def gen():
            for f in fields:
                try:
                    yield (f.name, self.val[f.name])
                except Exception:
                    continue
        return gen()

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Enum Values

# Width (bytes) -> unsigned GDB type name for bit-preserving reads.
_ENUM_UNSIGNED_BY_WIDTH = {1: "unsigned char", 2: "unsigned short", 4: "unsigned int", 8: "unsigned long long"}
# Odin backing-type spellings that are unambiguous without parsing.
_ENUM_SIGNED_NAMES = frozenset({"int", "i8", "i16", "i32", "i64"})
_ENUM_UNSIGNED_NAMES = frozenset({"uint", "u8", "u16", "u32", "u64"})

def _enum_backing_is_signed(name: str) -> bool:
    n = (name or "").strip().lower()
    if n in _ENUM_SIGNED_NAMES:
        return True
    if n in _ENUM_UNSIGNED_NAMES:
        return False
    if "unsigned" in n:
        return False
    return True

def _signed_enum_discriminant(val) -> int:
    t = val.type.strip_typedefs()
    backing = None
    try:
        backing = t.target()
    except Exception:
        backing = None
    if backing is None:
        try:
            f0 = t.fields()[0]
            if getattr(f0, "type", None) is not None:
                backing = f0.type.strip_typedefs()
        except Exception:
            pass
    if backing is not None:
        try:
            backing_name = str(backing.strip_typedefs())
        except Exception:
            backing_name = str(backing)
        try:
            width = int(backing.sizeof)
        except Exception:
            width = 8
    else:
        try:
            backing_name = str(t)
        except Exception:
            backing_name = ""
        width = 8
    signed = _enum_backing_is_signed(backing_name)
    unsigned_t = gdb.lookup_type(_ENUM_UNSIGNED_BY_WIDTH.get(width, "unsigned long long"))
    raw = int(val.cast(unsigned_t))
    bits = width * 8
    if signed and raw >= (1 << (bits - 1)):
        raw -= (1 << bits)
    return raw

class Printer_Enum:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        try:
            num = _signed_enum_discriminant(self.val)
        except Exception:
            try:
                num = int(self.val)
            except Exception:
                return "<no value>"
        try:
            for f in self.val.type.strip_typedefs().fields():
                if f.name and f.enumval is not None and f.enumval == num:
                    return ".%s" % f.name
        except Exception:
            pass
        return str(num)

    def children(self):
        return iter(())

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Bit Set Values

class Printer_Bitset:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        set_flags = []
        try:
            fields = self.val.type.strip_typedefs().fields()
        except Exception:
            return "{}"
        for f in fields:
            if not f.name or f.name == "tag":
                continue
            try:
                child = self.val[f.name]
            except Exception:
                continue
            try:
                if int(child) != 0:
                    set_flags.append(".%s" % f.name)
            except Exception:
                continue
        return "{" + ", ".join(set_flags) + "}"

    def children(self):
        return iter(())

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Map Values

class Cell_Info:
    def __init__(self, size_of_type: int, size_of_cell: int, elements_per_cell: int) -> None:
        self.size_of_type      = size_of_type
        self.size_of_cell      = size_of_cell
        self.elements_per_cell = elements_per_cell

def cell_info(type_size: int, cell_size: int, cell_type) -> 'Cell_Info':
    elements_per_cell = 1

    if type_size != cell_size:
        try:
            child_type = cell_type.strip_typedefs().fields()[0].type
            if child_type.sizeof > 0 and type_size > 0:
                elements_per_cell = child_type.sizeof // type_size
        except Exception:
            pass

    if elements_per_cell == 0:
        elements_per_cell = 1

    return Cell_Info(type_size, cell_size, elements_per_cell)

def cell_index(base: int, info: "Cell_Info", index: int) -> int:
    cell_index = 0
    data_index = 0
    if info.elements_per_cell == 1:
        return base + (index * info.size_of_cell)
    elif info.elements_per_cell == 2:
        cell_index = index >> 1;
        data_index = index & 1;
    elif info.elements_per_cell == 4:
        cell_index = index >> 2;
        data_index = index & 3;
    elif info.elements_per_cell == 8:
        cell_index = index >> 3;
        data_index = index & 7;
    elif info.elements_per_cell == 16:
        cell_index = index >> 4;
        data_index = index & 15;
    elif info.elements_per_cell == 32:
        cell_index = index >> 5;
        data_index = index & 31;
    else:
        cell_index = index // info.elements_per_cell;
        data_index = index % info.elements_per_cell;

    return base + (cell_index * info.size_of_cell) + (data_index * info.size_of_type);

class Printer_Map:
    def __init__(self, val) -> None:
        self.val = val

    def _decode(self) -> dict:
        data          = self.val["data"]
        tagged        = int(data)
        cap_log2      = tagged & 63
        cap           = (1 << cap_log2) if cap_log2 > 0 else 0
        key_ptr       = tagged & ~63
        entries       = data.dereference()
        key_type      = entries["key"].type
        val_type      = entries["value"].type
        key_cell      = entries["key_cell"]
        value_cell    = entries["value_cell"]
        key_cell_info = cell_info(key_type.sizeof, key_cell.type.sizeof, key_cell.type)
        val_cell_info = cell_info(val_type.sizeof, value_cell.type.sizeof, value_cell.type)
        val_ptr       = cell_index(key_ptr, key_cell_info, cap)
        hash_ptr      = cell_index(val_ptr, val_cell_info, cap)
        return {
            "length":   int(self.val["len"]),
            "cap":      cap,
            "key_ptr":  key_ptr,
            "key_type": key_type,
            "val_type": val_type,
            "key_info": key_cell_info,
            "val_info": val_cell_info,
            "val_ptr":  val_ptr,
            "hash_ptr": hash_ptr,
        }

    def _entries(self):
        try:
            info = self._decode()
        except Exception:
            return
        if info["cap"] == 0 or info["length"] == 0:
            return
        found = 0
        for i in range(info["cap"]):
            try:
                raw = bytes(gdb.selected_inferior().read_memory(info["hash_ptr"] + i * 8, 8))
            except gdb.MemoryError:
                return
            hash_val = int.from_bytes(raw, "little")
            if hash_val == 0 or (hash_val & (1 << 63)) != 0:
                continue
            try:
                key_addr = cell_index(info["key_ptr"], info["key_info"], i)
                val_addr = cell_index(info["val_ptr"], info["val_info"], i)
                k = gdb.Value(key_addr).cast(info["key_type"].pointer()).dereference()
                v = gdb.Value(val_addr).cast(info["val_type"].pointer()).dereference()
            except Exception:
                continue
            yield (k, v)
            found += 1
            if found >= info["length"]:
                break

    def to_string(self):
        try:
            length = int(self.val["len"])
        except gdb.error:
            return "<no value>"
        if length == 0:
            return "map[0]{}"
        def get_value(i: int) -> str:
            # _entries() is a fresh scan per call; to_string() consumes it
            # lazily via islice-style manual advance.
            for idx, (k, v) in enumerate(self._entries()):
                if idx == i:
                    return "%s = %s" % (value_summary(k), value_summary(v))
            return "<missing>"
        return aggregate_value_summary("map[%d]{" % length, "}", get_value, length)

    def children(self):
        try:
            length = int(self.val["len"])
        except gdb.error:
            return iter(())
        def gen():
            try:
                cap = self._decode()["cap"]
            except Exception:
                return
            try:
                for idx, (k, v) in enumerate(self._entries()):
                    yield ("key%d" % idx, k)
                    try:
                        key_summary = value_summary(k)
                    except Exception:
                        key_summary = "?"
                    yield ("[%s]" % key_summary, v)
            except Exception:
                return
            yield ("len", gdb.Value(length))
            yield ("cap", gdb.Value(cap))
        return gen()

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Union Values

# Layout:
#    normal & #shared_nil union type:
#        tag: u64
#        v1:  T0
#        v2:  T1
#        ...
#    #no_nil union type:
#        tag: u64
#        v0:  T0
#        v1:  T1
#        ...

def union_is_no_nil(t) -> bool:
    try:
        fields = t.strip_typedefs().fields()
        return len(fields) > 1 and fields[1].name == "v0"
    except Exception:
        return False

def union_variant(v):
    try:
        tag_value = int(v["tag"])
    except Exception:
        return None
    if not union_is_no_nil(v.type) and tag_value == 0:
        return None
    try:
        return v["v%d" % tag_value]
    except Exception:
        return None

class Printer_Union:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        variant = union_variant(self.val)
        if variant is None:
            return "nil"
        try:
            return "%s(%s)" % (type_display(variant.type), value_summary(variant))
        except Exception:
            return "<error>"

    def children(self):
        variant = union_variant(self.val)
        if variant is None:
            return iter(())
        try:
            vtype = variant.type.strip_typedefs()
        except Exception:
            return iter(())
        # String variants render bare (their chars are not useful children).
        try:
            from_string = get_odin_type(variant.type.strip_typedefs()) == Odin_Type.String
        except Exception:
            from_string = False
        if from_string:
            return iter(())
        def gen():
            try:
                vt = variant.type.strip_typedefs()
                if vt.code == gdb.TYPE_CODE_PTR:
                    try:
                        deref = variant.dereference()
                    except Exception:
                        return
                    target = deref.type.strip_typedefs()
                    if target.code == gdb.TYPE_CODE_STRUCT:
                        for f in target.fields():
                            if f.name:
                                try:
                                    yield (f.name, deref[f.name])
                                except Exception:
                                    continue
                        return
                    yield ("value", deref)
                    return
                if vt.code == gdb.TYPE_CODE_STRUCT:
                    for f in vt.fields():
                        if f.name:
                            try:
                                yield (f.name, variant[f.name])
                            except Exception:
                                continue
                    return
                yield ("value", variant)
            except Exception:
                return
        return gen()

    def display_hint(self):
        return None


def type_display(t) -> str:
    try:
        t = t.strip_typedefs()
    except Exception:
        return "<unknown>"
    try:
        name = (t.tag or str(t)).replace("::", ".")
    except Exception:
        name = "<unknown>"
    if t.code == gdb.TYPE_CODE_PTR:
        try:
            pointee = t.target()
        except Exception:
            return "^%s" % name
        if pointee.code == gdb.TYPE_CODE_VOID:
            return "rawptr"
        if pointee.code == gdb.TYPE_CODE_FUNC:
            return "proc"
        return "^" + type_display(pointee)
    if t.code == gdb.TYPE_CODE_REF:
        return "&%s" % name
    return name


def _proc_convention(typedef_name: str) -> str | None:
    """Parse the calling convention from an unstripped proc typedef name.

    Returns None for bare `proc(` (odin default), else the quoted label
    (canonical `cdecl` mapped to `c`). Raises ValueError when unparseable
    so the caller can fall back to legacy output.
    """
    try:
        s = typedef_name.strip()
    except Exception:
        raise ValueError("unparseable proc typedef name")
    if s.startswith("proc("):
        return None
    if s.startswith('proc"'):
        end = s.find('"', len('proc"'))
        if end != -1 and s[end + 1:].lstrip().startswith("("):
            label = s[len('proc"'):end]
            if label == "cdecl":
                return "c"
            if label:
                return label
    raise ValueError("unparseable proc typedef name: %r" % (typedef_name,))


def _split_top_level(s: str) -> list:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts

def _clean_ret_elem(elem: str) -> str:
    e = elem.strip()
    tmp = e.replace("::", "\x00")
    if ":" in tmp:
        tmp = tmp.split(":", 1)[-1]
    return tmp.replace("\x00", ".").strip().replace("::", ".")

def _norm_type(s: str) -> str:
    try:
        return s.replace("::", ".").replace(" ", "").replace("\t", "")
    except Exception:
        return s

def _proc_returns(typedef_name: str):
    try:
        s = typedef_name.strip()
    except Exception:
        return None
    depth, arrow = 0, -1
    i = 0
    while i < len(s) - 1:
        ch = s[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "-" and s[i + 1] == ">" and depth == 0:
            arrow = i
            i += 1
        i += 1
    if arrow == -1:
        return None
    ret = s[arrow + 2:].strip()
    if not ret:
        return None
    if ret.startswith("(") and ret.endswith(")"):
        inner = ret[1:-1].strip()
        if not inner:
            return []
        return [_clean_ret_elem(p) for p in _split_top_level(inner)]
    return [_clean_ret_elem(ret)]


# ------------------------------------------------------------------------------
# Pure proc core (no GDB I/O)
#
# Single model for procedure signatures. Both the display path
# (format_proc) and the eval path (call_plan) consume ProcSignature;
# neither parses typedef strings itself.

import dataclasses


@dataclasses.dataclass
class ProcSignature:
    # None = odin default convention, else label string ("c", "contextless", ...)
    convention: object
    # Written (user-visible) params as display type strings.
    written_params: list
    # Hidden params in C-ABI order: list of (kind, type_str),
    # kind in ("sret", "ctx").
    hidden_params: list
    # None = void | ("single", type_str) | ("tuple", [type_strs]) |
    # ("lowered", type_str) = sret cross-check failed, render lowered form.
    returns: object
    # Source typedef string, for debugging only (never re-parsed).
    typedef_name: str


@dataclasses.dataclass
class CCall:
    expr_string: str
    temp_allocs: list
    cleanup: list


class ProcCallError(Exception):
    pass


def _strip_hidden_context(convention, params: list) -> tuple:
    """Pop trailing ^Context for the odin default convention.

    Mirrors the historical printer rule on display strings: the last
    param whose normalized form is pointer-typed and mentions "Context".
    Returns (written, hidden) without mutating the input.
    """
    written = list(params)
    hidden = []
    if convention is None and written:
        try:
            n = _norm_type(written[-1])
        except Exception:
            n = ""
        if n.startswith("^") and "Context" in n:
            hidden.append(("ctx", written.pop()))
    return written, hidden


def parse_proc_signature(typedef_name: str, lowered_params: list,
                         lowered_ret: str):
    """The single place proc typedef parsing + ctx-strip + sret lives.

    Returns a ProcSignature, or None when the convention is unparseable
    (caller falls back to the legacy lowered display / refuses the call).
    """
    try:
        conv = _proc_convention(typedef_name)
    except Exception:
        return None
    try:
        ret_tuple = _proc_returns(typedef_name)
    except Exception:
        return None

    written, hidden = _strip_hidden_context(conv, list(lowered_params))
    returns = None

    if ret_tuple is not None and len(ret_tuple) >= 2:
        n_extra = len(ret_tuple) - 1
        if n_extra > len(written):
            return None
        cands = written[len(written) - n_extra:] if n_extra else []
        try:
            target_norm = _norm_type(lowered_ret)
        except Exception:
            target_norm = lowered_ret
        ok = target_norm == _norm_type(ret_tuple[-1])
        if ok:
            for slot_disp, want in zip(cands, ret_tuple[:-1]):
                wl = want.lstrip()
                if wl.startswith("^") or wl.startswith("&"):
                    ok = False
                    break
                if _norm_type(slot_disp) != _norm_type(want):
                    ok = False
                    break
        if not ok:
            # Cross-check failed: keep slots visible, render lowered
            # return. call_plan refuses to build a sugared call for this.
            return ProcSignature(
                convention=conv,
                written_params=written,
                hidden_params=hidden,
                returns=("lowered", lowered_ret),
                typedef_name=typedef_name,
            )
        for s in cands:
            hidden.append(("sret", s))
        if n_extra:
            del written[len(written) - n_extra:]
        returns = ("tuple", list(ret_tuple))
    elif ret_tuple is not None and len(ret_tuple) == 1:
        # 1-tuple renders as single return, no parens (Odin style).
        returns = ("single", ret_tuple[0])
    elif lowered_ret and lowered_ret != "void":
        returns = ("single", lowered_ret)
    else:
        returns = None

    return ProcSignature(
        convention=conv,
        written_params=written,
        hidden_params=hidden,
        returns=returns,
        typedef_name=typedef_name,
    )


def format_proc(sig: ProcSignature) -> str:
    """Render `proc [...] (...) [-> ...]` from a signature (types only)."""
    if sig.convention is None:
        label = "proc"
    else:
        label = 'proc "%s"' % sig.convention
    result = "%s (%s)" % (label, ", ".join(sig.written_params))
    if sig.returns is None:
        return result
    kind, payload = sig.returns
    if kind == "tuple":
        result += " -> (" + ", ".join(payload) + ")"
    else:
        # "single" and "lowered" both render bare.
        result += " -> " + payload
    return result


def _proc_legacy_display(lowered_params: list, lowered_ret: str) -> str:
    """Byte-identical fallback for convention-unparseable typedefs."""
    result = 'proc "c" (%s)' % ", ".join(lowered_params)
    if lowered_ret and lowered_ret != "void":
        result += " -> " + lowered_ret
    return result


def call_plan(sig: ProcSignature, fn_expr: str, fn_addr: int,
              user_args: list) -> CCall:
    """Build the C call expression from a signature. Never parses strings.

    fn_expr names the callee verbatim in the expression; fn_addr is only
    used for the nil refusal. Hidden ^Context is auto-appended as
    `&context`; hidden sret slots must be supplied by the caller as
    trailing args (Phase 1 explicit; Phase 2 automates allocation).
    """
    if not fn_addr:
        raise ProcCallError("error: proc is nil, refusing to call")
    if sig.returns is not None and sig.returns[0] == "lowered":
        raise ProcCallError(
            "error: cannot build sugared call for '%s' "
            "(signature mismatch); inspect with ptype and call the "
            "lowered form" % fn_expr)
    sret_count = sum(1 for k, _ in sig.hidden_params if k == "sret")
    has_ctx = any(k == "ctx" for k, _ in sig.hidden_params)
    n_written = len(sig.written_params)
    if sret_count and len(user_args) == n_written + sret_count:
        # Caller supplied sret slot addresses explicitly.
        args = list(user_args)
    elif len(user_args) != n_written:
        msg = ["error: arity mismatch for '%s': proc takes %d%s, got %d"
               % (fn_expr, n_written,
                  " (+ %d sret slot(s))" % sret_count if sret_count else "",
                  len(user_args))]
        if sret_count:
            slots = ", ".join(t for k, t in sig.hidden_params if k == "sret")
            msg.append("hidden sret slot(s): %s "
                       "(pass slot addresses as trailing args)" % slots)
        raise ProcCallError(" ".join(msg))
    else:
        if sret_count:
            slots = ", ".join(t for k, t in sig.hidden_params if k == "sret")
            raise ProcCallError(
                "error: proc '%s' has %d hidden sret slot(s) (%s); "
                "pass slot addresses as trailing args" % (fn_expr, sret_count, slots))
        args = list(user_args)
    if has_ctx:
        args.append("&context")
    return CCall(expr_string="%s(%s)" % (fn_expr, ", ".join(args)),
                 temp_allocs=[], cleanup=[])


# ------------------------------------------------------------------------------
# Pointer Values

class Printer_Pointer:
    def __init__(self, val) -> None:
        self.val = val

    def to_string(self):
        try:
            addr = int(self.val)
        except Exception:
            return "<no value>"

        # nil pointer
        if addr == 0:
            return "nil"

        try:
            target = self.val.type.strip_typedefs().target()
        except Exception:
            return type_display(self.val.type)

        # raw pointer
        try:
            void_name = str(target.strip_typedefs()) == "void"
        except Exception:
            void_name = False
        if target.code == gdb.TYPE_CODE_VOID or void_name:
            return "rawptr(%s)" % hex(addr)

        # proc pointer
        if target.code == gdb.TYPE_CODE_FUNC:
            try:
                typedef_name = str(self.val.type)
            except Exception:
                typedef_name = ""
            return self._proc_display(target, typedef_name)

        # SOA slice pointer (e.g. &soa_slice[1])
        try:
            tag = target.tag or ""
        except Exception:
            tag = ""
        if tag.startswith("#soa"):
            return self._soa_ptr_display(addr)

        # Regular pointer
        try:
            pointee = self.val.dereference()
        except Exception:
            return type_display(self.val.type)
        try:
            return "&" + value_summary(pointee)
        except Exception:
            return type_display(self.val.type)

    def _proc_display(self, func_type, typedef_name: str = "") -> str:
        lowered_params = []
        try:
            for f in func_type.fields():
                try:
                    lowered_params.append(type_display(f.type))
                except Exception:
                    continue
        except Exception:
            pass
        try:
            lowered_ret = type_display(func_type.target())
        except Exception:
            lowered_ret = ""
        sig = parse_proc_signature(typedef_name, lowered_params, lowered_ret)
        if sig is None:
            return _proc_legacy_display(lowered_params, lowered_ret)
        return format_proc(sig)

    def _soa_ptr_display(self, addr: int) -> str:
        # Current Odin DWARF does not encode the element index:
        # &soa[i] has the same value as &soa (points at an unadjusted struct copy),
        # so the index is unknowable (see TODO.md / Odin#5611).
        # Render honestly as a pointer to the whole SOA array instead of guessing an element.
        try:
            v = self.val.dereference()
        except Exception:
            return type_display(self.val.type)
        try:
            return "&" + value_summary(v)
        except Exception:
            return type_display(self.val.type)

    def children(self):
        return iter(())

    def display_hint(self):
        return None


# ------------------------------------------------------------------------------
# Lookup + registration
#
# GDB calls lookup_odin(val) for every value printed.
# Returning None falls through to GDB defaults—`Other` type.

def lookup_odin(val):
    try:
        kind = get_odin_type(val.type.strip_typedefs())
    except Exception:
        return None
    cls = {
        Odin_Type.String:              Printer_String,
        Odin_Type.Slice:               Printer_Slice,
        Odin_Type.SOA_Slice:           Printer_SOA_Slice,
        Odin_Type.Fixed_Dynamic_Array: Printer_Fixed_Capacity_Dynamic_Array,
        Odin_Type.Array:               Printer_Array,
        Odin_Type.Struct:              Printer_Struct,
        Odin_Type.Enum:                Printer_Enum,
        Odin_Type.Bitset:              Printer_Bitset,
        Odin_Type.Map:                 Printer_Map,
        Odin_Type.Union:               Printer_Union,
        Odin_Type.Ptr:                 Printer_Pointer,
    }.get(kind)
    if cls is None:
        return None
    try:
        return cls(val)
    except Exception:
        return None


if lookup_odin not in gdb.pretty_printers:
    gdb.pretty_printers.append(lookup_odin)
try:
    _odin_objfile = gdb.current_objfile()
except Exception:
    _odin_objfile = None
if _odin_objfile is not None:
    try:
        if lookup_odin not in _odin_objfile.pretty_printers:
            _odin_objfile.pretty_printers.append(lookup_odin)
    except Exception:
        pass


# ------------------------------------------------------------------------------
# odin-children command
#
# Usage: odin-children VARIABLE [MAX]

class Odin_Children_Command(gdb.Command):
    """Print pretty-printer children of a variable, one per line."""

    def __init__(self) -> None:
        super().__init__("odin-children", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def invoke(self, arg, from_tty) -> None:
        argv = gdb.string_to_argv(arg)
        if not argv:
            print("Usage: odin-children VARIABLE [MAX]")
            return
        try:
            val = gdb.parse_and_eval(argv[0])
        except gdb.error as e:
            print("Variable '%s' not found: %s" % (argv[0], e))
            return
        max_children = None
        if len(argv) > 1:
            try:
                max_children = int(argv[1])
            except ValueError:
                print("MAX must be an integer")
                return
        printer = lookup_odin(val)
        children = None
        if printer is not None:
            try:
                children = printer.children()
            except Exception as e:
                print("<error reading children: %s>" % e)
                return
        if children is None:
            children = _default_children(val)
        count = 0
        try:
            for name, child in children:
                if max_children is not None and count >= max_children:
                    break
                try:
                    print("%s = %s" % (name, value_summary(child)))
                except Exception as e:
                    print("%s = <error: %s>" % (name, e))
                count += 1
            if count == 0:
                print("  No children")
        except Exception as e:
            print("<error reading children: %s>" % e)


def _default_children(val):
    """Fallback children for non-Odin types (old print_children.py behavior)."""
    try:
        t = val.type.strip_typedefs()
    except Exception:
        return iter(())
    def gen():
        try:
            if t.code == gdb.TYPE_CODE_ARRAY:
                lo, hi = t.range()
                for i in range(lo, hi + 1):
                    yield ("[%d]" % (i - lo), val[i - lo])
            elif t.code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
                for f in t.fields():
                    if f.name and not f.is_base_class:
                        try:
                            yield (f.name, val[f.name])
                        except Exception:
                            continue
        except Exception:
            return
    return gen()


try:
    Odin_Children_Command()
except Exception:
    pass  # already registered (re-source safe)


# ------------------------------------------------------------------------------
# odin-call command
#
# Usage: odin-call PROC_NAME(ARG, ...)
#   odin-call add_ints(2, 3)
#   odin-call foo_value(foo)
#   odin-call 'main::add_ints'(2, 3)   (imported proc: quote the :: name)
#
# Stopped-inferior only; pure procs preferred. Single-return and void
# procs are fully automatic (hidden &context appended). Multi-return
# procs need explicit sret slot addresses as trailing args (Phase 1).

import re as _re


class Odin_Call_Command(gdb.Command):
    """Call an Odin procedure with hidden args supplied."""

    def __init__(self) -> None:
        super().__init__("odin-call", gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL)

    def invoke(self, arg, from_tty) -> None:
        text = (arg or "").strip()
        m = _re.match(r"^([^\s(]+)\s*\((.*)\)\s*$", text, _re.S)
        if not m:
            print("Usage: odin-call PROC_NAME(ARG, ...)  e.g. odin-call add_ints(2, 3)")
            return
        fn_token, argstr = m.group(1), m.group(2).strip()
        user_args = (_split_top_level(argstr) if argstr else [])
        user_args = [a.strip() for a in user_args if a.strip() or len(user_args) == 1]
        if len(user_args) == 1 and not user_args[0]:
            user_args = []

        # --- resolve function value + address (both kinds) ---
        fn_val = None
        resolved_expr = fn_token
        try:
            fn_val = gdb.parse_and_eval(fn_token)
        except gdb.error:
            fn_val = None
        fn_addr = 0
        if fn_val is not None:
            try:
                fn_addr = int(fn_val)
            except Exception:
                fn_addr = 0
            if not fn_addr:
                # Function designators have no integer value but are still
                # callable by name; nil proc *variables* (pointer-typed)
                # keep 0 so the nil refusal still fires.
                try:
                    is_func = (fn_val.type.strip_typedefs().code
                               == gdb.TYPE_CODE_FUNC)
                except Exception:
                    is_func = False
                if is_func:
                    fn_addr = -1  # resolved-but-addressless marker
        else:
            # constant / imported proc: resolve via symbol table
            # ('pkg::proc' quoting guidance in the usage string above).
            sym = None
            for probe in (fn_token, fn_token.strip("'\"")):
                try:
                    found = gdb.lookup_symbol(probe)
                except Exception:
                    found = None
                cand = found[0] if isinstance(found, tuple) else found
                if cand is not None:
                    sym = cand
                    break
            if sym is None:
                # Resolution discovery (fallback only): this binary emits
                # DW_AT_name as `<pkg>::<bare>` (e.g. main::add_ints), so a
                # bare token resolves to nothing above. Probe
                # `info functions` for the qualified spelling.
                if "::" not in fn_token:
                    bare = fn_token.strip("'\"").strip()
                    if bare:
                        try:
                            info = gdb.execute("info functions %s$" % bare,
                                               to_string=True)
                        except Exception:
                            info = ""
                        m2 = _re.search(r"([\w.]+)::" + _re.escape(bare)
                                        + r"\s*\(", info or "")
                        if m2:
                            qual = m2.group(1)
                            try:
                                fn_val = gdb.parse_and_eval("'%s::%s'" % (qual, bare))
                            except gdb.error:
                                fn_val = None
                            if fn_val is not None:
                                resolved_expr = "'%s::%s'" % (qual, bare)
                                try:
                                    fn_addr = int(fn_val)
                                except Exception:
                                    fn_addr = 0
                                if not fn_addr:
                                    fn_addr = -1  # resolved-but-addressless marker
                if fn_val is None:
                    print("error: could not resolve '%s' "
                          "(for imported procs quote the name: 'pkg::proc')" % fn_token)
                    return
            else:
                try:
                    fn_val = sym.value()
                except Exception as e:
                    print("error: could not read symbol '%s': %s" % (fn_token, e))
                    return
                try:
                    addr_val = fn_val.address
                    fn_addr = int(addr_val) if addr_val is not None else 0
                except Exception:
                    fn_addr = 0
                if not fn_addr:
                    # function symbols report no address; still callable by name
                    fn_addr = -1  # resolved-but-addressless marker

        # --- build signature via the shared parser (no second parser) ---
        try:
            ftype = fn_val.type.strip_typedefs()
        except Exception:
            print("error: could not read type of '%s'" % fn_token)
            return
        try:
            typedef_name = str(fn_val.type)
        except Exception:
            typedef_name = ""
        if ftype.code == gdb.TYPE_CODE_PTR:
            try:
                func_type = ftype.target()
            except Exception:
                print("error: '%s' is not a procedure" % fn_token)
                return
        elif ftype.code == gdb.TYPE_CODE_FUNC:
            func_type = ftype
        else:
            print("error: '%s' is not a procedure" % fn_token)
            return
        try:
            lowered_params = [type_display(f.type) for f in func_type.fields()]
        except Exception:
            lowered_params = []
        try:
            lowered_ret = type_display(func_type.target())
        except Exception:
            lowered_ret = ""
        sig = parse_proc_signature(typedef_name, lowered_params, lowered_ret)
        if sig is None:
            if typedef_name.lstrip().startswith("proc"):
                print("error: cannot parse signature of '%s' "
                      "(inspect with ptype and call the lowered form)" % fn_token)
                return
            # C-symbol fallback (fallback only): plain C types carry no proc
            # typedef, so call the already-lowered form directly (no hidden
            # context; hidden args still come from sig.hidden_params).
            written = list(lowered_params)
            if len(written) == 1 and written[0].strip() == "void":
                written = []
            ret_stripped = lowered_ret.strip() if lowered_ret else ""
            if ret_stripped in ("", "void"):
                returns = None
            else:
                returns = ("single", lowered_ret)
            sig = ProcSignature(convention="c", written_params=written,
                                hidden_params=[], returns=returns,
                                typedef_name=typedef_name)

        # --- plan (nil / arity / lowered refusals are deterministic) ---
        try:
            plan = call_plan(sig, resolved_expr, fn_addr, user_args)
        except ProcCallError as e:
            print(e)
            return

        # --- scheduler-locking guard + eval + cleanup ---
        try:
            prev_out = gdb.execute("show scheduler-locking", to_string=True)
        except Exception:
            prev_out = ""
        prev_m = _re.search(r"\b(on|off|step)\b", prev_out)
        prev_mode = prev_m.group(1) if prev_m else "off"
        try:
            gdb.execute("set scheduler-locking on")
        except Exception as e:
            print("error: cannot set scheduler-locking: %s" % e)
            return
        try:
            try:
                gdb.execute("print " + plan.expr_string)
            except gdb.error as e:
                print("error: call failed: %s" % e)
                print("hint: lowered signature is: %s"
                      % _proc_legacy_display(lowered_params, lowered_ret))
        finally:
            for thunk in plan.cleanup:
                try:
                    thunk()
                except Exception:
                    pass
            try:
                gdb.execute("set scheduler-locking %s" % prev_mode)
            except Exception:
                pass


try:
    Odin_Call_Command()
except Exception:
    pass  # already registered (re-source safe)
