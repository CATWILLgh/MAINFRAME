# Bundles, captures, and runtime artifacts

## First inspection for Electron

```sh
A=./app.asar
X=$(mktemp -d "${TMPDIR:-/tmp}/leanrea-asar.XXXXXX") || exit 1
asar extract "$A" "$X" || exit 1
jq '{name,version,main}' "$X/package.json"
find "$X" -path '*/node_modules' -prune -o -type f \( -name '*.js' -o -name '*.node' \) -print | head -60
ls "${A}.unpacked/node_modules" 2>/dev/null | head -60
rg -uu -l --glob '!node_modules' 'exposeInMainWorld' "$X" | head -60
```
Then slice the needle across the bundle: `rg -uu -o --glob '!node_modules' '.{0,250}NEEDLE.{0,250}' "$X" | head -20`.

Go: `go version -m T` alone usually answers the question.

| Target | Fastest path |
| --- | --- |
| Web bundle / minified JS | Find `sourceMappingURL`. List the map's source paths with `jq -r '.sources[]' MAP`. Read the corresponding entry with `jq -r '.sourcesContent[INDEX] // empty' MAP` when embedded source is available. For webpack, grep the module ids, then slice around the hit. For pretty-print: `prettier --parser babel F > F.pretty.js`, then read with line ranges. |
| Hermes / bytenode / V8 snapshot | Hermes magic is `c6 1f bc 03` (`index.android.bundle`): use `hermes-dec` / `hbc-decompiler`. `.jsc` (bytenode) cannot be decompiled: use strings and runtime hooks. |
| Android APK | `jadx -d X --show-bad-code a.apk` then `rg`. Resources/manifest only: `apktool d --no-src -o X a.apk`. Quick look: `unzip -l a.apk`. `lib/*/libflutter.so` means Flutter (Dart AOT: `blutter`); `libhermes.so` means React Native (Hermes row). |
| SQLite | Copy the db, plus the `-wal` file if present. `sqlite3 'file:C?mode=ro' '.schema'`, then `SELECT * FROM t LIMIT 20`. |
| plist / nib / car | `plutil -p F`. Info.plist holds the bundle id, URL schemes and privacy strings. Asset catalogs: `assetutil --info Assets.car`. |
| pcap / HAR | `tshark -r C -q -z conv,tcp`; `tshark -r C -T fields -e dns.qry.name -e tls.handshake.extensions_server_name -e http.request.full_uri \| sort -u`. HAR: `jq -r '.log.entries[].request \| .method+" "+.url'`. |
| Firmware | `binwalk -e F` or `unblob -e X F`. Then route each extracted binary through this table. |
| Website | `curl -sL URL` for the HTML and script srcs, then fetch the JS and slice it. For authorized runtime observation, use a headless browser with a network log (Playwright `page.on('request')`) or an isolated Chrome profile with `--remote-debugging-port` bound to loopback. |
| Running app / runtime | macOS: `lldb -p PID`, `dtrace`/`fs_usage`/`log stream --predicate 'process=="X"'`. Electron main: `--inspect` (only if the RunAsNode/inspect fuses allow it). Android: `adb logcat`, `frida -U -f pkg -l hook.js`. |

For JavaScript, trace the native/JS boundary to its caller, IPC registration,
then renderer or preload. Cap output and inspect a slice of a minified file.

For authorized tooling installation, select tools for the actual format.
Examples include `brew install jadx binwalk wireshark`
and `npm i -g @electron/asar @electron/fuses prettier`.
