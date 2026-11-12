---
name: mainframe-leanrea
description: Analyze authorized shipped apps, binaries, web bundles, APKs, SQLite, and captures. Trace behavior, versions, dependencies, or build differences.
---

# Inspect shipped software

Adapted from [AICodeKing's LeanREA](https://github.com/aicodeking/leanrea/blob/09ba4aa0217f82cd880f855a60b877f59f39b22b/leanrea/SKILL.md). The [MIT license](LICENSE) accompanies this copy. Upstream credits the REA team for informing its tool guidance.

- Work on an authorized copy in a fresh scratch directory. Reuse a matching
  extraction. On APFS, a clone copy with `cp -c` can avoid duplicating data.
  Start with static inspection and trace runtime only on an authorized process
  or device. Keep collected output local and redact sensitive evidence.
- Start with `file -b` and magic bytes. Inventory before decompiling. Search
  extracted trees with `rg -uu` so hidden bundle paths are included. Read
  bounded slices of large files and reuse a disassembly instead of dumping it
  repeatedly. Batch independent probes and keep their outputs attributable.
- Use installed tools or the listed fallback. Get authority for installation
  or network-dependent alternatives. For build comparisons, diff inventories
  before code. Verify any minimal reimplementation with the same inputs and
  outputs as the original.

| Target | Read |
| --- | --- |
| Mach-O, ELF, PE, Go, Rust, .NET, Flutter snapshots, or WASM | [Native binaries](references/native.md) |
| Electron, web or Hermes bundles, APKs, SQLite, plist, pcap/HAR, firmware, or runtime tracing | [Bundles and data](references/bundles-and-data.md) |

Tie observations to a file, offset, symbol, or string. Label inferences and
unknowns. Use runtime evidence when the claim depends on actual execution.
Finish when the requested conclusions have evidence.
