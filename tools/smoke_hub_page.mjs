// Interaction smoke for the generated hub.html.
//
// The Python suite (tools/test_build_hub_page.py) covers the data layer; this
// covers the browser layer the Python tests cannot reach — search filtering,
// the click-to-detail drawer, and the analytics charts. It runs the real
// page in jsdom and asserts POST-EVENT DOM state (a syntax check never executes
// the JS, which is how the v1 page once shipped blank).
//
// The hub stays python-only: jsdom is NOT a repo dependency, so it is resolved
// from a throwaway dir via createRequire (no node_modules / package.json enters
// the tree). Run it by hand against a freshly regenerated page:
//   .venv/bin/python3 tools/build_hub_page.py
//   mkdir -p /tmp/hubcheck && cd /tmp/hubcheck && npm install jsdom
//   node tools/smoke_hub_page.mjs        # default base /tmp/hubcheck, default page workspace/runtime/hub.html
// Override with HUB_SMOKE_JSDOM_BASE=<dir-with-jsdom> and argv[2]=<hub.html>.
// Exit 0 = all assertions passed and the console was clean.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = path.dirname(fileURLToPath(import.meta.url));
const jsdomBase = process.env.HUB_SMOKE_JSDOM_BASE || "/tmp/hubcheck/";
const { JSDOM, VirtualConsole } = createRequire(path.join(jsdomBase, "_resolve.cjs"))("jsdom");
const htmlPath = process.argv[2] || path.join(here, "..", "workspace", "runtime", "hub.html");
const html = fs.readFileSync(htmlPath, "utf8");

const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(String(e)));
vc.on("error", (m) => errors.push("console.error: " + m));

const dom = new JSDOM(html, { runScripts: "dangerously", virtualConsole: vc });
const { window } = dom;
const doc = window.document;

let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) { pass++; console.log("  ok  " + msg); }
  else { fail++; console.log("FAIL  " + msg); } };

const q = (sel) => Array.from(doc.querySelectorAll(sel));
const visibleCards = () => q("#view-catalog .card").filter((c) => !c.classList.contains("filtered"));
const visibleNodes = () => q(".gnode").filter((n) => !n.classList.contains("filtered"));
const fire = (elm, type, init) => elm.dispatchEvent(new window.Event(type, { bubbles: true, ...init }));
const esc = () => window.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape" }));

ok(q("#tabs button").length === 8, "8 tabs rendered");
ok(doc.querySelector("#view-overview").classList.contains("active"), "overview is the default view");
ok(q("#view-overview .overview-metric").length >= 10, "overview metrics rendered");
ok(q("#view-overview .overview-panel").length >= 6, "overview evidence panels rendered");
ok(/whole agent system|What deserves a look/.test(doc.querySelector("#view-overview").textContent),
  "overview explains the system in plain language");
ok(q("#view-overview .signal-chart").length === 1, "overview telemetry signal rendered");
ok(q("#view-overview .event-stream li").length >= 1, "overview recent event stream rendered");
const totalCards = q("#view-catalog .card").length;
ok(totalCards > 20, "catalog cards rendered (" + totalCards + ")");
const totalNodes = q(".gnode").length;
ok(totalNodes > 40, "graph nodes rendered (" + totalNodes + ")");
const search = doc.querySelector(".search");
ok(!!search, "search box present in topbar");
ok(search.hidden, "catalog search stays hidden on the analytics overview");
const detail = doc.querySelector("#detail");
ok(!!detail && detail.hidden, "detail drawer present and hidden at start");

search.value = "shadcn";
fire(search, "input");
const vc1 = visibleCards();
ok(vc1.length >= 1 && vc1.length < totalCards, "query narrows cards (" + vc1.length + "/" + totalCards + ")");
ok(vc1.some((c) => c.textContent.toLowerCase().includes("shadcn")), "the matching card stays visible");
const vn1 = visibleNodes();
ok(vn1.length >= 1 && vn1.length < totalNodes, "query narrows graph nodes (" + vn1.length + "/" + totalNodes + ")");

search.value = "zzzznomatch";
fire(search, "input");
ok(visibleCards().length === 0, "no-match query hides every card");
ok(visibleNodes().length === 0, "no-match query hides every graph node");
ok(q("#view-catalog section").every((s) => s.classList.contains("filtered") || !s.querySelector(".card")),
  "catalog sections with no visible card are hidden");

search.value = "";
fire(search, "input");
ok(visibleCards().length === totalCards, "clearing the query restores all cards");
ok(visibleNodes().length === totalNodes, "clearing the query restores all graph nodes");

const componentTab = q("#tabs button").find((b) => b.textContent === "Components");
fire(componentTab, "click");
ok(doc.querySelector("#view-catalog").classList.contains("active"), "component tab activates its view");
ok(!search.hidden, "search appears only where it can filter content");

const nodeFor = (id) => q(".gnode").find((g) => g.querySelector("text") && g.querySelector("text").textContent === id);
const stNode = nodeFor("ticket");
ok(!!stNode, "found the ticket graph node");
fire(stNode, "click");
ok(!detail.hidden, "clicking a node opens the detail drawer");
ok(detail.textContent.includes("ticket"), "detail shows the clicked artifact name");
ok(/referenced|preloaded|cross-refs/i.test(detail.textContent), "detail shows a reverse-lookup section");

const link = detail.querySelector(".chip.link");
ok(!!link, "detail has at least one clickable cross-link");
const linkName = link.textContent;
fire(link, "click");
ok(detail.querySelector(".dtitle").textContent === linkName, "cross-link navigates the panel to '" + linkName + "'");

esc();
ok(detail.hidden, "Escape closes the detail drawer");

const evNode = nodeFor("Stop");
if (evNode) {
  fire(evNode, "click");
  ok(!detail.hidden && /fire on this event/i.test(detail.textContent), "event-node detail lists its hooks");
  esc();
}

const firstCard = doc.querySelector("#view-catalog .card");
fire(firstCard, "click");
ok(!detail.hidden, "clicking a catalog card opens the detail drawer");

const cfg = doc.querySelector("#view-config");
ok(!!cfg, "config pane rendered");
ok(q("#view-config .permlist").length === 3, "deny/ask/allow permission lists present");
ok(q("#view-config .perm").length > 150, "permission rows rendered (" + q("#view-config .perm").length + ")");
ok(q("#view-config .kvgrid").length >= 1, "settings key/value grid present");
ok(/rules/.test(cfg.textContent) && /commands/.test(cfg.textContent), "empty-layer markers shown");
ok(/Output styles|Templates/.test(cfg.textContent), "output-styles / templates section present");

const health = doc.querySelector("#view-health");
ok(!!health, "health pane rendered");
ok(q("#view-health .stat").length === 3, "health shows 3 stat tiles");
ok(!!health.querySelector(".notice.ok"), "clean repo shows the all-resolved notice");
ok(/Orphan skills/.test(health.textContent), "orphan section present with its caveat");

const dev = doc.querySelector("#view-dev");
ok(!!dev, "dev pane rendered");
ok(q("#view-dev .bars").length >= 2, "activity-by-day and by-agent bar charts present");
ok(q("#view-dev .bar-row").length >= 2, "bar rows rendered (" + q("#view-dev .bar-row").length + ")");
ok(/by skill|by hook/.test(dev.textContent), "payload breakdowns rendered");

const usage = doc.querySelector("#view-usage");
ok(!!usage, "usage pane rendered");
ok(q("#view-usage .stat").length >= 6, "usage stat tiles present (" + q("#view-usage .stat").length + ")");
ok(q("#view-usage table.matrix").length >= 1, "per-model token table present");
ok(q("#view-usage .heatmap").length === 1, "activity-calendar heatmap present");
ok(q("#view-usage .hm-cell").length > 300, "rolling-year heatmap cells rendered (" + q("#view-usage .hm-cell").length + ")");
ok(q("#view-usage .hm-months span").length >= 1, "heatmap month labels present");
ok(/Main window vs subagents/.test(usage.textContent), "main/subagent split section present");

ok(q("#view-config .kvgrid.wide").length >= 1, "environment uses the full-width key/value grid");
ok(q("#view-graph .graph-ctrls button").length === 3, "graph has on-canvas zoom/reset controls");

console.log("\nconsole/jsdom errors: " + errors.length);
errors.slice(0, 5).forEach((e) => console.log("  ! " + e.slice(0, 200)));
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail || errors.length ? 1 : 0);
