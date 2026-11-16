# Native binaries

## First inspection for Mach-O

```sh
T=./bin
D=$(mktemp -d "${TMPDIR:-/tmp}/leanrea.XXXXXX") || exit 1
file "$T"
lipo -info "$T"
otool -L "$T" | head -100
nm -gU "$T" | head -150
nm -u "$T" | rg -v '^__Z|napi_' | head -150 | tr '\n' ' '
strings -a -n 6 "$T" | rg -v '^[_$.]' | head -400
otool -tV "$T" > "$D/dis.txt"
rg '^[_a-zA-Z].*:$' "$D/dis.txt" | rg -v '^_?_?Z?N?St3' | head -150
```
Keep the scratch path for the targeted follow-up. Then read one function: `awk '/^FUNC_LABEL:$/{p=1;next} p&&/^[_a-zA-Z].*:$/{exit} p' "$D/dis.txt" | rg 'bl|b\.|cmp|literal|mov\s+w2'`.

| Target | Fastest path |
| --- | --- |
| Mach-O (`file`: Mach-O) | `lipo -info` (thin first: `lipo -thin arm64 -o T1 T`). Then: `otool -L` (libs); `xcrun dyld_info -exports -imports`; `nm -gU` (exports) / `nm -u` (imports = the capability map); `strings -a -n 6`; `otool -l \| rg -A3 'LC_(RPATH\|BUILD_VERSION)'`; `codesign -d --entitlements :- T`; `otool -ov` (ObjC classes/methods); `xcrun swift-demangle --compact`. |
| Native code logic | `otool -tV T > $D/dis.txt` (or `llvm-objdump -d --no-show-raw-insn -C`). Find the function: `rg -n '^_?.*Name.*:$'`. Read the call/string trail: `awk '/^FUNC:/{p=1} p&&/^[_a-zA-Z].*:$/&&!/FUNC/{exit} p' dis.txt \| rg 'bl\|call\|literal\|cmp'`. otool labels string literals and stubs inline, which is often enough. Only for real pseudocode: Ghidra `analyzeHeadless $D p -import T -postScript DecompileAll.java -deleteProject` or `r2 -qc 'aaa; pdc @ sym.X' T`. |
| ELF / PE | `readelf -hlSW`, `readelf -dW` (NEEDED), `nm -D --defined-only`, `objdump -d -M intel`. PE: `objdump -x`, `pefile`/`wrestool` for resources. checksec: `pwn checksec`. |
| Go (`__go_buildinfo`, `.go.buildinfo`) | `GOTOOLCHAIN=local go version -m T` reads available toolchain/module/build metadata without automatic toolchain downloads. Without Go, inspect strings around `Go buildinf`. Use `GOTOOLCHAIN=local go tool nm T` only when a symbol table exists: linker `-s` removes it. Build/runtime metadata may remain, but stripping or obfuscation limits what can be recovered. |
| Rust | Deps (cargo-auditable): `cargo audit bin T` with the advisory database available locally, or extract `.dep-v0` / `__DATA,.dep-v0` and zlib-inflate it. Compiler: `strings -a T \| rg -o '/rustc/[0-9a-f]{40}' \| sort -u`. Crates from paths: `strings -a T \| rg -o '[a-z0-9_-]+-[0-9]+\.[0-9]+\.[0-9]+/src' \| sort -u`. |
| .NET (`file`: Mono/.Net) | `ilspycmd -p -o X T.dll` (install: `dotnet tool install -g ilspycmd`), then `rg`. P/Invoke: `rg DllImport X`. NativeAOT/IL2CPP are native: use the native rows. |
| Flutter snapshot hash | In `libapp.so`, find magic `f5 f5 dc dc`; the 32 hex chars at +20 are the snapshot hash. Map it to a Dart version. |
| WASM | `wasm-objdump -x`, `wasm2wat`, `wasm-decompile` (WABT). |

On a small binary, try `nm -u`, exports and strings before disassembly. Find a
string's address in the `otool -tV` literal-pool comments, then find the nearest
enclosing function above the hit. C++ symbols such as `getpeereid` or
`std::hash` often identify the protocol before you read the call sequence.
See the official Go [linker flags](https://pkg.go.dev/cmd/link) and
[toolchain selection](https://go.dev/doc/toolchain#select) contracts.

For authorized tooling installation, select tools for the actual format.
Examples include `brew install ghidra radare2 wabt`,
`dotnet tool install -g ilspycmd`, and `cargo install cargo-audit`.
