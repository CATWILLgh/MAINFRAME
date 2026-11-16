# Third-party material

## Modern Web Guidance

The frontend method was informed by
[GoogleChrome Modern Web Guidance](https://github.com/GoogleChrome/modern-web-guidance)
and its linked primary documentation. MAINFRAME does not vendor the upstream
skill or source tree.

The web hook uses AST/DOM/CSS parsers from the separately prepared
[`modern-web-guidance` npm package](https://www.npmjs.com/package/modern-web-guidance).
Its [Apache-2.0 license](https://github.com/GoogleChrome/modern-web-guidance-src/blob/main/LICENSE)
and bundled `THIRD_PARTY_NOTICES` remain intact in that package, including notices
for its embedded dependencies. Runtime preparation installs the official package
without modifying its files. Temporary research copies are removed after use.

The adapted rule program in `_WEB_RULES_PROGRAM` in
[`hooks/mainframe-code-quality.py`](hooks/mainframe-code-quality.py) is derived
from the upstream rule definitions and remains under
[Apache-2.0](LICENSES/Apache-2.0.txt). Its header identifies the source and
MAINFRAME modifications. The prepared upstream package supplies the same full
license and its bundled dependency notices alongside the installed hook runtime.

Svelte template parsing uses the separately prepared official
[`svelte/compiler`](https://svelte.dev/docs/svelte/svelte-compiler), retaining
Svelte's MIT license and dependency notices in the unmodified npm package.

Other MAINFRAME code and instructions retain the repository's [MIT license](LICENSE).
