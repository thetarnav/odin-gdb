#+feature dynamic-literals
package main

import "base:runtime"
import "core:io"

Enum     :: enum u8 {One, Two, Three}
Enum_Int :: enum int {One, Two, Three}

Bit_Set_Int :: bit_set[Enum_Int]

Foo :: struct {foo_name: string, value: int}
Bar :: struct {value: int, bar_name: string}

Struct_Empty :: struct {}
Struct_Long  :: struct {a, b, c, d, e, f: int}

Foo_Bar_Union            :: union {Foo, Bar, string}
Foo_Bar_Union_No_Nill    :: union #no_nil {Foo, Bar}
Foo_Bar_Union_Shared_Nil :: union #shared_nil {Enum, ^Foo, ^Bar}

Pair :: struct {a, b: int} // 16B — native by-value control case

add_ints :: proc (a, b: int) -> int {
	return a + b
}
dup_foo :: proc (f: ^Foo) -> Foo {
	return f^
}
foo_value :: proc (f: Foo) -> int {
	return f.value
}
long_value :: proc (l: Struct_Long) -> int {
	return l.a
}
pair_sum :: proc (p: Pair) -> int {
	return p.a + p.b
}
is_big_bar :: proc (b: ^Bar) -> bool {
	return b.value > 100
}
get_magic :: proc () -> int {
	return 42
}
add_ints_contextless :: proc "contextless" (a, b: int) -> int {
	return a + b
}
add_ints_c :: proc "c" (a, b: int) -> int {
	return a + b
}
make_foo :: proc (name: string, v: int) -> Foo {
	return Foo{name, v}
}

main :: proc () {

	struct_empty := Struct_Empty{}
	// (gdb) print struct_empty
	// {}

	struct_long := Struct_Long{100000001, 100000002, 100000003, 100000004, 100000005, 100000006}
	// (gdb) print struct_long
	// {100000001, 100000002, 100000003, 100000004, 100000005...} = {a = 100000001, b = 100000002, c = 100000003, d = 100000004, e = 100000005, f = 100000006}

	str_empty := ""
	// (gdb) print str_empty
	// ""

	str_foo := "foo"
	// (gdb) print str_foo
	// "foo"

	str_nil: string
	// (gdb) print str_nil
	// ""

	str_raw: runtime.Raw_String = {len = 10}
	// (gdb) print str_raw
	// {nil, 10} = {data = nil, len = 10}

	str_nil_with_len := transmute(string)str_raw
	// (gdb) print str_nil_with_len
	// {nil, 10}

	foo := Foo{"Hello", 42}
	// (gdb) print foo
	// {"Hello", 42} = {foo_name = "Hello", value = 42}

	// (gdb) print foo.foo_name
	// "Hello"

	foo_ptr := &foo
	// (gdb) print foo_ptr
	// &{"Hello", 42}

	foo_raw_ptr := rawptr(foo_ptr)
	// (gdb) print foo_raw_ptr
	// rawptr(%PTR%)

	bar := Bar{84, "World"}
	// (gdb) print bar
	// {84, "World"} = {value = 84, bar_name = "World"}

	pair := Pair{3, 4}
	// (gdb) print pair
	// {3, 4} = {a = 3, b = 4}

	enum_two := Enum.Two
	// (gdb) print enum_two
	// .Two

	enum_three := Enum.Three
	// (gdb) print enum_three
	// .Three

	enum_out_of_bounds := Enum(100)
	// (gdb) print enum_out_of_bounds
	// 100

	enum_int_two := Enum_Int.Two
	// (gdb) print enum_int_two
	// .Two

	enum_int_three := Enum_Int.Three
	// (gdb) print enum_int_three
	// .Three

	enum_int_out_of_bounds := Enum_Int(-100)
	// (gdb) print enum_int_out_of_bounds
	// -100

	foo_bar_union: Foo_Bar_Union = "hello world"
	// (gdb) print foo_bar_union
	// string("hello world")

	foo_bar_union_nil: Foo_Bar_Union
	// (gdb) print foo_bar_union_nil
	// nil

	foo_bar_union_no_nil: Foo_Bar_Union_No_Nill = foo
	// (gdb) print foo_bar_union_no_nil
	// main.Foo({"Hello", 42}) = {foo_name = "Hello", value = 42}

	// (gdb) odin-children foo_bar_union_no_nil
	// foo_name = "Hello"
	// value = 42

	foo_bar_union_shared_nil: Foo_Bar_Union_Shared_Nil = &bar
	// (gdb) print foo_bar_union_shared_nil
	// ^main.Bar(&{84, "World"}) = {value = 84, bar_name = "World"}

	// (gdb) odin-children foo_bar_union_shared_nil
	// value = 84
	// bar_name = "World"

	foo_bar_union_shared_nil_nil: Foo_Bar_Union_Shared_Nil
	// (gdb) print foo_bar_union_shared_nil_nil
	// nil

	writer := io.Writer{}
	// (gdb) print writer
	// {nil, nil} = {procedure = nil, data = nil}

	// (gdb) print writer.procedure
	// nil

	// (gdb) print writer.data
	// nil

	foo_proc := proc (f: ^Foo, b: Bar) {return}
	// (gdb) print foo_proc
	// proc (^main.Foo, main.Bar)

	foo_proc_ok := proc (f: ^Foo, b: Bar) -> (ok: bool) {return}
	// (gdb) print foo_proc_ok
	// proc (^main.Foo, main.Bar) -> bool

	foo_proc_multi_res := proc (f: Foo, b: Bar) -> (idx: int, ok: bool) {return}
	// (gdb) print foo_proc_multi_res
	// proc (main.Foo, main.Bar) -> (int, bool)

	foo_bar_contextless := proc "contextless" (f: Foo, b: Bar) -> (idx: int, ok: bool) {return}
	// (gdb) print foo_bar_contextless
	// proc "contextless" (main.Foo, main.Bar) -> (int, bool)

	foo_proc_tri_res := proc (f: Foo, b: Bar) -> (idx: int, n: f32, ok: bool) {return}
	// (gdb) print foo_proc_tri_res
	// proc (main.Foo, main.Bar) -> (int, f32, bool)

	foo_proc_c := proc "c" (f: ^Foo, b: Bar) {return}
	// (gdb) print foo_proc_c
	// proc "c" (^main.Foo, main.Bar)

	foo_proc_noargs := proc () {return}
	// (gdb) print foo_proc_noargs
	// proc ()

	foo_proc_ctxless_noargs := proc "contextless" () {return}
	// (gdb) print foo_proc_ctxless_noargs
	// proc "contextless" ()

	foo_proc_nil: proc (f: ^Foo, b: Bar) = nil
	// (gdb) print foo_proc_nil
	// nil

	foo_proc_c_nil: proc "c" (f: ^Foo, b: Bar) = nil
	// (gdb) print foo_proc_c_nil
	// nil

	foo_proc_ctxless_nil: proc "contextless" (f: Foo, b: Bar) -> (idx: int, ok: bool) = nil
	// (gdb) print foo_proc_ctxless_nil
	// nil

	Holder :: struct {cb: proc (f: ^Foo) -> bool}
	holder := Holder{cb = proc (f: ^Foo) -> bool {return true}}
	// (gdb) print holder.cb
	// proc (^main.Foo) -> bool

	slice := []Foo{{"Slice1", 1}, {"Slice2", 2}}
	// (gdb) print slice
	// [2]{{"Slice1", 1}, {"Slice2", 2}} = {{"Slice1", 1} = {foo_name = "Slice1", value = 1}, {"Slice2", 2} = {foo_name = "Slice2", value = 2}}

	// (gdb) odin-children slice
	// [0] = {"Slice1", 1}
	// [1] = {"Slice2", 2}

	slice_long := []Foo{{"Slice1", 1}, {"Slice2", 2}, {"Slice3", 3}, {"Slice4", 4}, {"Slice5", 5}}
	// (gdb) print slice_long
	// [5]{{"Slice1", 1}, {"Slice2", 2}, {"Slice3", 3}...} = {{"Slice1", 1} = {foo_name = "Slice1", value = 1}, {"Slice2", 2} = {foo_name = "Slice2", value = 2}, {"Slice3", 3} = {foo_name = "Slice3", value = 3}, {"Slice4", 4} = {foo_name = "Slice4", value = 4}, {"Slice5", 5} = {foo_name = "Slice5", value = 5}}

	slice_empty := []Foo{}
	// (gdb) print slice_empty
	// [0]{}

	array := [2]Foo{{"Array1", 1}, {"Array2", 2}}
	// (gdb) print array
	// [2]{{"Array1", 1}, {"Array2", 2}} = {{"Array1", 1} = {foo_name = "Array1", value = 1}, {"Array2", 2} = {foo_name = "Array2", value = 2}}

	// (gdb) odin-children array
	// [0] = {"Array1", 1}
	// [1] = {"Array2", 2}

	array_long := [5]Foo{{"Array1", 1}, {"Array2", 2}, {"Array3", 3}, {"Array4", 4}, {"Array5", 5}}
	// (gdb) print array_long
	// [5]{{"Array1", 1}, {"Array2", 2}, {"Array3", 3}...} = {{"Array1", 1} = {foo_name = "Array1", value = 1}, {"Array2", 2} = {foo_name = "Array2", value = 2}, {"Array3", 3} = {foo_name = "Array3", value = 3}, {"Array4", 4} = {foo_name = "Array4", value = 4}, {"Array5", 5} = {foo_name = "Array5", value = 5}}

	array_empty := [0]Foo{}
	// (gdb) print array_empty
	// [0]{}

	dynamic_array := [dynamic]Foo{Foo{"Dynamic1", 1}, Foo{"Dynamic2", 2}}
	// (gdb) print dynamic_array
	// [2]{{"Dynamic1", 1}, {"Dynamic2", 2}} = {{"Dynamic1", 1} = {foo_name = "Dynamic1", value = 1}, {"Dynamic2", 2} = {foo_name = "Dynamic2", value = 2}}

	// (gdb) odin-children dynamic_array
	// [0] = {"Dynamic1", 1}
	// [1] = {"Dynamic2", 2}

	dynamic_array_long := [dynamic]Foo{Foo{"Dynamic1", 1}, Foo{"Dynamic2", 2}, Foo{"Dynamic3", 3}, Foo{"Dynamic4", 4}, Foo{"Dynamic5", 5}}
	// (gdb) print dynamic_array_long
	// [5]{{"Dynamic1", 1}, {"Dynamic2", 2}, {"Dynamic3", 3}...} = {{"Dynamic1", 1} = {foo_name = "Dynamic1", value = 1}, {"Dynamic2", 2} = {foo_name = "Dynamic2", value = 2}, {"Dynamic3", 3} = {foo_name = "Dynamic3", value = 3}, {"Dynamic4", 4} = {foo_name = "Dynamic4", value = 4}, {"Dynamic5", 5} = {foo_name = "Dynamic5", value = 5}}

	dynamic_array_chunked: [dynamic]Foo
	for i in 0..<10_000 {
		append(&dynamic_array_chunked, Foo{"DynamicChunked", i})
	}

	// (gdb) odin-children dynamic_array_chunked 3
	// [0] = {"DynamicChunked", 0}
	// [1] = {"DynamicChunked", 1}
	// [2] = {"DynamicChunked", 2}

	fcda := [dynamic; 100]Foo{{"Dynamic1", 1}, {"Dynamic2", 2}}
	// (gdb) print fcda
	// [2]{{"Dynamic1", 1}, {"Dynamic2", 2}} = {{"Dynamic1", 1} = {foo_name = "Dynamic1", value = 1}, {"Dynamic2", 2} = {foo_name = "Dynamic2", value = 2}}

	// (gdb) odin-children fcda
	// [0] = {"Dynamic1", 1}
	// [1] = {"Dynamic2", 2}

	str_map: map[string]Foo = {"key1" = {"Value1", 1}}
	// (gdb) print str_map
	// map[1]{"key1" = {"Value1", 1}} = {key0 = "key1", ["key1"] = {"Value1", 1} = {foo_name = "Value1", value = 1}, len = 1, cap = 8}

	// (gdb) odin-children str_map
	// key0 = "key1"
	// ["key1"] = {"Value1", 1}
	// len = 1
	// cap = 8

	str_map_empty: map[string]Foo = {}
	// (gdb) print str_map_empty
	// map[0]{} = {len = 0, cap = 0}

	flags: bit_set[Enum] = {.One, .Two}
	// (gdb) print flags
	// {.One, .Two}

	flags_empty: bit_set[Enum] = {}
	// (gdb) print flags_empty
	// {}

	flags_max := transmute(bit_set[Enum])max(u8)
	// (gdb) print flags_max
	// {.One, .Two, .Three}

	flags_int: Bit_Set_Int = {.One, .Two}
	// (gdb) print flags_int
	// {.One, .Two}

	enum_array := [Enum]string{
		.One   = "one",
		.Two   = "two",
		.Three = "three",
	}
	// Can't detect enum array unfortunately

	// (gdb) print enum_array
	// [3]{"one", "two", "three"} = {"one", "two", "three"}

	// (gdb) odin-children enum_array
	// [0] = "one"
	// [1] = "two"
	// [2] = "three"

	soa_dyn_array: #soa[dynamic]Foo
	append(&soa_dyn_array, Foo{"SOA1", 1}, Foo{"SOA2", 2}, Foo{"SOA3", 3})

	// (gdb) print soa_dyn_array
	// [3]{{"SOA1", 1}, {"SOA2", 2}, {"SOA3", 3}}

	soa_dyn_array_ptr := &soa_dyn_array[1]
	// (gdb) print soa_dyn_array_ptr
	// &[3]{{"SOA1", 1}, {"SOA2", 2}, {"SOA3", 3}}

	soa_slice := soa_dyn_array[:]
	// (gdb) print soa_slice
	// [3]{{"SOA1", 1}, {"SOA2", 2}, {"SOA3", 3}}

	soa_slice_ptr := &soa_slice[1]
	// (gdb) print soa_slice_ptr
	// &[3]{{"SOA1", 1}, {"SOA2", 2}, {"SOA3", 3}}

	// Keep odin-call fixtures alive (prevent dead-code elimination).
	_ = add_ints
	_ = dup_foo
	_ = foo_value
	_ = long_value
	_ = pair_sum
	_ = is_big_bar
	_ = get_magic
	_ = add_ints_contextless
	_ = add_ints_c
	_ = make_foo

	// (gdb) odin-call add_ints(2, 3)
	// 5

	// (gdb) odin-call get_magic()
	// 42

	// (gdb) odin-call add_ints_contextless(2, 3)
	// 5

	// (gdb) odin-call add_ints_c(2, 3)
	// 5

	// (gdb) odin-call is_big_bar(&bar)
	// false

	// (gdb) odin-call foo_value(foo)
	// 42

	// (gdb) odin-call long_value(struct_long)
	// 100000001

	// (gdb) odin-call pair_sum(pair)
	// 7

	// (gdb) odin-call dup_foo(&foo)
	// {"Hello", 42} = {foo_name = "Hello", value = 42}

	// (gdb) odin-call foo_proc_nil(&foo, bar)
	// error: proc is nil, refusing to call

	breakpoint() // for gdb to breakpoint here
	return
}

@(link_name="breakpoint")
breakpoint :: proc () {}
