"use strict";
// HUB_DATA is injected by build_hub_page.py (the inlined manifest). All views
// build the DOM from data via textContent — never innerHTML — so artifact
// descriptions containing < > or quotes cannot break or inject markup.
//
// Every user-facing string goes through t() or f(); nothing else is translated.
// That single rule is what tools/test_hub_page_i18n.py can check, so a new
// English literal cannot quietly ship as an untranslatable island.
(function () {
  let D = window.HUB_DATA;
  const LANGUAGES = ["en", "ru"];
  const RU = window.HUB_STRINGS_RU || {};
  let language = "en";
  try {
    const saved = window.localStorage.getItem("mainframe-language");
    language = LANGUAGES.includes(saved)
      ? saved
      : ((navigator.language || "").toLowerCase().startsWith("ru") ? "ru" : "en");
  } catch (_err) { /* private browsing keeps the default */ }

  const t = (text) => (language === "ru" && RU[text]) ? RU[text] : text;
  const f = (text, vars) => t(text).replace(/\{(\w+)\}/g,
    (whole, key) => (vars && key in vars) ? String(vars[key]) : whole);
  const LOCALE = () => (language === "ru" ? "ru-RU" : "en-US");

  const app = document.getElementById("app");
  const tabsNav = document.getElementById("tabs");
  if (!app) return;
  if (!D || !tabsNav) {
    // Never fail silently to a blank page: a visible message beats a white
    // screen with no devtools open.
    app.textContent = t("Failed to load hub data — regenerate with .venv/bin/python3 tools/build_hub_page.py");
    return;
  }

  function el(tag, props, kids) {
    const n = document.createElement(tag);
    if (props) {
      for (const k in props) {
        if (k === "class") n.className = props[k];
        else n.setAttribute(k, props[k]);
      }
    }
    if (kids != null) {
      (Array.isArray(kids) ? kids : [kids]).forEach((c) => {
        if (c == null || c === false) return;
        n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
      });
    }
    return n;
  }

  function badge(text, cls) {
    return el("span", { class: "badge " + (cls || "") }, text);
  }

  const SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, props, kids) {
    const n = document.createElementNS(SVGNS, tag);
    if (props) for (const k in props) n.setAttribute(k, props[k]);
    if (kids != null) (Array.isArray(kids) ? kids : [kids]).forEach((c) => {
      if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  // Number, duration and money formatting.
  function num(value) {
    return Number(value || 0).toLocaleString(LOCALE());
  }

  function fmtTok(n) {
    n = Number(n) || 0;
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
  }

  function fmtMs(ms) {
    ms = Number(ms) || 0;
    if (ms >= 60000) return (ms / 60000).toFixed(1) + " min";
    if (ms >= 1000) return (ms / 1000).toFixed(1) + " s";
    return ms + " ms";
  }

  function fmtUsd(microUsd) {
    const usd = (Number(microUsd) || 0) / 1e6;
    const digits = usd > 0 && usd < 1 ? 3 : 2;
    return "$" + usd.toLocaleString(LOCALE(), {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
  }

  function fmtStamp(value) {
    return String(value || "").replace("T", " ").replace("Z", "").slice(0, 16);
  }

  function fmtDay(value) {
    return String(value || "").slice(0, 10);
  }

  function fmtHour(h) {
    if (h == null) return "—";
    return String(h).padStart(2, "0") + ":00 UTC";
  }

  // Lookup tables built once from the manifest.
  const skillByName = {};
  D.skills.forEach((s) => { skillByName[s.name] = s; });
  const localSkillName = (name) => String(name || "").replace(/^mainframe:/, "");
  const agentByName = {};
  D.agents.forEach((a) => { agentByName[a.name] = a; });
  const referencedBy = {};
  D.agents.forEach((a) => (a.skills || []).forEach((sk) => {
    const local = localSkillName(sk);
    (referencedBy[local] || (referencedBy[local] = [])).push({ name: a.name, layer: "agents" });
  }));
  D.skills.forEach((s) => (s.crossrefs || []).forEach((ref) => {
    if (skillByName[ref]) {
      (referencedBy[ref] || (referencedBy[ref] = [])).push({ name: s.name, layer: "skills" });
    }
  }));
  const hooksByScript = {};
  const hooksByEvent = {};
  D.hooks.forEach((h) => {
    (hooksByScript[h.script] || (hooksByScript[h.script] = [])).push(h);
    (hooksByEvent[h.event] || (hooksByEvent[h.event] = [])).push(h);
  });

  // Module-level so applyFilter can reach items rendered by different views.
  let catalogCards = [];     // {el, text}
  let catalogSections = [];  // {el, cards:[{el,text}]}
  let graphNodes = [];       // {el, id, text}
  let graphEdges = [];       // {el, ends:[a,b]}
  // A re-render replaces the nodes the filter was applied to, so the query is
  // kept here and re-applied afterwards instead of silently resetting.
  let filterQuery = "";

  function applyFilter(raw) {
    filterQuery = (raw || "").trim().toLowerCase();
    const q = filterQuery;
    catalogCards.forEach((c) => c.el.classList.toggle("filtered", !!q && !c.text.includes(q)));
    catalogSections.forEach((s) => {
      const anyVisible = s.cards.some((c) => !q || c.text.includes(q));
      s.el.classList.toggle("filtered", !anyVisible);
    });
    const visibleNodes = new Set();
    graphNodes.forEach((n) => {
      const on = !q || n.text.includes(q);
      n.el.classList.toggle("filtered", !on);
      if (on) visibleNodes.add(n.id);
    });
    graphEdges.forEach((e) => {
      const on = !q || (visibleNodes.has(e.ends[0]) && visibleNodes.has(e.ends[1]));
      e.el.classList.toggle("filtered", !on);
    });
  }

  // Slide-in detail drawer.
  const detailBody = el("div", { class: "dbody" });
  const detailClose = el("button", { type: "button", class: "dclose", "aria-label": t("close") }, "×");
  const detail = el("aside", { class: "detail", id: "detail" }, [detailClose, detailBody]);
  detail.hidden = true;
  document.body.appendChild(detail);
  detailClose.addEventListener("click", closeDetail);
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });

  function closeDetail() { detail.hidden = true; detail.classList.remove("open"); }

  function openDetail(layer, id) {
    let body = null;
    if (layer === "skills" || layer === "dev") body = skillDetail(id);
    else if (layer === "agents") body = agentDetail(id);
    else if (layer === "hooks") body = hookDetail(id);
    else if (layer === "events") body = eventDetail(id);
    if (!body) return;
    while (detailBody.firstChild) detailBody.removeChild(detailBody.firstChild);
    detailBody.appendChild(body);
    detail.hidden = false;
    detail.classList.add("open");
  }

  function linkChip(label, layer, id) {
    const resolvable =
      ((layer === "skills" || layer === "dev") && skillByName[id]) ||
      (layer === "agents" && agentByName[id]) ||
      (layer === "hooks" && hooksByScript[id]) ||
      (layer === "events" && hooksByEvent[id]);
    const chip = el("span", { class: "chip" + (resolvable ? " link" : "") }, label);
    if (resolvable) chip.addEventListener("click", (e) => { e.stopPropagation(); openDetail(layer, id); });
    return chip;
  }

  function dhead(title, badgeText, cls) {
    return el("div", { class: "dhead" }, [el("span", { class: "dtitle" }, title), badge(badgeText, cls)]);
  }

  function dsec(title, items) {
    return items.length
      ? el("div", { class: "dsec" }, [el("h4", null, title), el("div", { class: "chips" }, items)])
      : null;
  }

  function skillDetail(id) {
    const s = skillByName[id];
    if (!s) return el("div", { class: "notice" }, f("Unknown skill: {name}", { name: id }));
    return el("div", null, [
      dhead(s.name, s.dev ? t("dev") : t("skill"), s.dev ? "dev" : "skills"),
      el("p", { class: "muted small" }, s.user_invocable
        ? f("user-invocable: /{name}", { name: s.name })
        : t("auto-triggered (not user-invocable)")),
      el("p", { class: "card-desc" }, s.description),
      s.when_to_use ? el("p", { class: "card-when" }, [el("b", null, t("when: ")), s.when_to_use]) : null,
      dsec(t("cross-refs"), (s.crossrefs || []).map((r) => linkChip(r, "skills", r))),
      dsec(t("referenced / preloaded by"),
        (referencedBy[s.name] || []).map((p) => linkChip(p.name, p.layer, p.name))),
    ]);
  }

  function agentDetail(id) {
    const a = agentByName[id];
    if (!a) return el("div", { class: "notice" }, f("Unknown agent: {name}", { name: id }));
    return el("div", null, [
      dhead(a.name, a.model || t("agent"), "agents"),
      el("p", { class: "card-desc" }, a.description),
      a.tools ? el("p", { class: "card-when" }, [el("b", null, t("tools: ")), String(a.tools)]) : null,
      dsec(t("preloads skills"), (a.skills || []).map((sk) => linkChip(sk, "skills", localSkillName(sk)))),
    ]);
  }

  function hookDetail(id) {
    const hs = hooksByScript[id] || [];
    const purpose = (hs[0] && hs[0].purpose) || "";
    const events = [];
    const seen = new Set();
    hs.forEach((h) => {
      if (!seen.has(h.event)) { seen.add(h.event); events.push(linkChip(h.event, "events", h.event)); }
    });
    return el("div", null, [
      dhead(id, t("hook event"), "hooks"),
      purpose ? el("p", { class: "card-desc" }, purpose)
        : el("p", { class: "muted small" }, t("(no docstring purpose)")),
      dsec(t("fires on"), events),
    ]);
  }

  function eventDetail(id) {
    const hs = hooksByEvent[id] || [];
    const rows = hs.map((h) => el("tr", null, [
      el("td", { class: "mono dim" }, h.matcher || "*"),
      el("td", null, linkChip(h.script, "hooks", h.script)),
    ]));
    return el("div", null, [
      dhead(id, t("event"), "events"),
      el("p", { class: "muted small" }, f("{count} hooks fire on this event.", { count: hs.length })),
      el("table", { class: "matrix" }, [el("tbody", null, rows)]),
    ]);
  }

  // Reusable layout primitives.
  function section(title, cls, count, body) {
    return el("section", null, [
      el("h2", { class: "layer-h " + cls }, title + (count == null ? "" : " (" + num(count) + ")")),
      body,
    ]);
  }

  function explain(text) {
    return el("p", { class: "explain" }, text);
  }

  function emptyState(text) {
    return el("p", { class: "empty-state" }, text);
  }

  function statRow(items) {
    return el("div", { class: "stat-row wrap" }, items.map(([value, label, tone]) =>
      el("div", { class: "stat " + (tone || "") }, [el("b", null, value), " " + label])));
  }

  function table(headers, rows) {
    return el("div", { class: "table-scroll" }, el("table", { class: "matrix" }, [
      el("thead", null, el("tr", null, headers.map(([label, numeric]) =>
        el("th", { class: numeric ? "num" : "" }, label)))),
      el("tbody", null, rows),
    ]));
  }

  function cells(values) {
    return el("tr", null, values.map(([value, kind]) =>
      el("td", { class: kind || "" }, value && value.nodeType ? value : String(value))));
  }

  function barList(rows) {
    const max = rows.reduce((m, r) => Math.max(m, r[1]), 0) || 1;
    return el("div", { class: "bars" }, rows.map(([label, n]) =>
      el("div", { class: "bar-row" }, [
        el("span", { class: "bar-label mono" }, String(label)),
        el("span", { class: "bar-track" },
          el("span", { class: "bar-fill", style: "width:" + Math.max(2, Math.round(100 * n / max)) + "%" })),
        el("span", { class: "bar-num" }, num(n)),
      ])));
  }

  function overviewMetric(label, value, note, tone) {
    return el("div", { class: "overview-metric " + (tone || "") }, [
      el("span", { class: "metric-label" }, label),
      el("strong", null, value),
      note ? el("span", { class: "metric-note" }, note) : null,
    ]);
  }

  function overviewPanel(kicker, title, body, cls) {
    return el("section", { class: "overview-panel " + (cls || "") }, [
      el("div", { class: "panel-heading" }, [
        el("span", { class: "panel-kicker" }, kicker),
        el("h2", null, title),
      ]),
      body,
    ]);
  }

  function signalChart(rows) {
    const shown = (rows || []).slice(-21);
    if (!shown.length) return emptyState(t("No activity is available yet."));
    const max = shown.reduce((m, row) => Math.max(m, row[1]), 0) || 1;
    return el("div", { class: "signal-chart", role: "img",
      "aria-label": t("Daily activity") }, shown.map((row) => {
      const pct = Math.max(4, Math.round(100 * row[1] / max));
      return el("div", { class: "signal-column", title: row[0] + " · " + num(row[1]) }, [
        el("span", { class: "signal-value", style: "height:" + pct + "%" }),
        el("span", { class: "signal-date" }, row[0].slice(5)),
      ]);
    }));
  }

  function shareRows(rows, total, tone) {
    if (!rows.length) return emptyState(t("No split is available yet."));
    const observed = rows.reduce((sum, row) => sum + row[1], 0);
    if (!observed) return emptyState(t("No split is available yet."));
    const base = total || observed;
    return el("div", { class: "share-list " + (tone || "") }, rows.map(([label, value, display]) => {
      // The printed share is the real one; only the bar gets a minimum width so
      // a rare value stays visible. Rounding both made 4-in-1618 read as 2%.
      const exact = 100 * value / base;
      const shown = exact > 0 && exact < 1 ? exact.toFixed(1) : String(Math.round(exact));
      return el("div", { class: "share-row" }, [
        el("div", { class: "share-copy" }, [
          el("span", { class: "mono" }, String(label)),
          el("span", null, (display || num(value)) + " · " + shown + "%"),
        ]),
        el("span", { class: "share-track" },
          el("span", { class: "share-fill",
            style: "width:" + Math.max(2, Math.round(exact)) + "%" })),
      ]);
    }));
  }

  function usageHeatmap(byDay) {
    // GitHub-style rolling year: 7 rows (Mon..Sun), one column per week, ending
    // today. by_day rows are [date, messages, tokens]; level scales on messages.
    const map = {};
    byDay.forEach(([d, msgs, tok]) => { map[d] = { msgs: msgs, tok: tok || 0 }; });
    const end = new Date();
    end.setUTCHours(0, 0, 0, 0);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 364);
    start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7)); // back to Monday
    // Quantile thresholds over active days, so a single huge day cannot wash out
    // a linear scale and low-activity days stay visible (n>0 => level>=1).
    const nz = byDay.map((r) => r[1]).filter((n) => n > 0).sort((a, b) => a - b);
    const q = (p) => (nz.length ? nz[Math.min(nz.length - 1, Math.floor(p * nz.length))] : 1);
    const t1 = q(0.25), t2 = q(0.5), t3 = q(0.75);
    const level = (n) => (!n ? 0 : n >= t3 ? 4 : n >= t2 ? 3 : n >= t1 ? 2 : 1);
    const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const cellEls = [], months = [];
    let i = 0, lastMonth = -1;
    for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
      const iso = d.toISOString().slice(0, 10);
      const e = map[iso] || { msgs: 0, tok: 0 };
      cellEls.push(el("div", { class: "hm-cell l" + level(e.msgs),
        title: f("{date} · {msgs} messages · {tok} tokens",
          { date: iso, msgs: num(e.msgs), tok: fmtTok(e.tok) }) }));
      if ((d.getUTCDay() + 6) % 7 === 0 && d.getUTCMonth() !== lastMonth) {
        lastMonth = d.getUTCMonth();
        months.push(el("span", { style: "grid-column-start:" + (Math.floor(i / 7) + 1) }, MON[lastMonth]));
      }
      i++;
    }
    return el("div", { class: "hm-wrap" }, [
      el("div", { class: "hm-months" }, months),
      el("div", { class: "heatmap" }, cellEls),
    ]);
  }

  // Accessors over the live manifest.
  function telemetry() {
    return (D.dev_state || {}).telemetry || {};
  }

  let periodPreset = "all";
  let customFrom = "";
  let customTo = "";
  try {
    periodPreset = window.localStorage.getItem("mainframe-period") || "all";
    customFrom = window.localStorage.getItem("mainframe-period-from") || "";
    customTo = window.localStorage.getItem("mainframe-period-to") || "";
  } catch (_err) { /* local state is optional */ }

  function periodBounds() {
    if (periodPreset === "all") return { from: "", to: "" };
    if (periodPreset === "custom") {
      return {
        from: customFrom ? customFrom + "T00:00:00Z" : "",
        to: customTo ? nextUtcDay(customTo) + "T00:00:00Z" : "",
      };
    }
    const days = Number(periodPreset);
    const end = new Date();
    const start = new Date(end.getTime() - days * 86400000);
    return { from: start.toISOString(), to: "" };
  }

  function nextUtcDay(day) {
    const value = new Date(day + "T00:00:00Z");
    value.setUTCDate(value.getUTCDate() + 1);
    return value.toISOString().slice(0, 10);
  }

  function periodQuery() {
    const bounds = periodBounds();
    const query = new URLSearchParams();
    if (bounds.from) query.set("from", bounds.from);
    if (bounds.to) query.set("to", bounds.to);
    return query.toString() ? "?" + query.toString() : "";
  }

  function ingestState() {
    return D.ingest || { evidence: "unknown", healthy: null };
  }

  function activeAdapters(report) {
    // Historical reporting must not disappear when an adapter's dev collector
    // is currently disabled. The control panel separately shows which inputs
    // are live now; analytics includes every adapter with a readable ledger.
    return (report.adapters || []).filter((item) => item.active);
  }

  function periodLine(report) {
    const selected = report.period || {};
    if (selected.preset && selected.preset !== "all") {
      const from = fmtDay(selected.from || report.first_timestamp);
      let to = fmtDay(report.last_timestamp);
      if (selected.to) {
        const exclusive = new Date(selected.to);
        to = Number.isNaN(exclusive.getTime()) ? fmtDay(selected.to)
          : fmtDay(new Date(exclusive.getTime() - 1).toISOString());
      }
      if (!from || !to) return el("p", { class: "muted" }, t("No events have been recorded yet."));
      return el("p", { class: "muted" },
        t("Selected period") + ": " + from + " — " + to);
    }
    const from = fmtDay(report.stored_first_timestamp || report.first_timestamp);
    const to = fmtDay(report.stored_last_timestamp || report.last_timestamp);
    if (!from || !to) return el("p", { class: "muted" }, t("No events have been recorded yet."));
    return el("p", { class: "muted" },
      f("Observation period: {from} — {to}", { from: from, to: to }) + " · "
        + t("All available history"));
  }

  function ingestSummary() {
    const ingest = ingestState();
    if (ingest.evidence === "unknown") {
      return { tone: "idle", text: t("The collector state is unknown because the observatory has not run in this workspace.") };
    }
    if (ingest.batches_failed) {
      return {
        tone: "warn",
        text: f("The collector is dropping batches — reason: {reason} ({kind}). Usage numbers are incomplete, not zero.",
          { reason: t(ingest.last_reason || "unknown"), kind: ingest.last_error_kind || t("unknown") }),
      };
    }
    if (!ingest.batches) {
      return { tone: "idle", text: t("The collector has not received anything yet. Start the observatory and run a session.") };
    }
    return { tone: "good", text: t("The collector is accepting every batch.") };
  }

  // Overview view.
  function renderOverview(root) {
    const ds = D.dev_state || { active: false, feedback: [] };
    const report = telemetry();
    const repo = D.health || { dangling: [], missing_scripts: [], unlinked_skills: [] };
    const adapters = activeAdapters(report);
    const reportingAdapters = adapters.filter((item) => (item.usable_records || 0) > 0);
    const cost = report.cost || {};
    const tokens = report.token_usage || {};
    const workload = report.workload || {};
    const ingest = ingestState();
    const ingestNote = ingestSummary();

    const uncounted = report.excluded_records || 0;
    const repoIssues = (repo.dangling || []).length + (repo.missing_scripts || []).length;
    const unmatched = (report.agent_lifecycle || []).reduce(
      (sum, row) => sum + (row.unmatched || 0), 0);
    const hookRows = report.hook_effectiveness || [];
    const hookGap = hookRows.reduce((sum, row) =>
      sum + Math.max(0, (row.blocked || 0) - (row.resolved || 0)), 0);
    const hookErrors = (report.hook_health || []).reduce(
      (sum, row) => sum + (row.errors || 0), 0);
    const toolCalls = (report.tool_reliability || []).reduce(
      (sum, row) => sum + (row.calls || 0), 0);
    const toolFailures = (report.tool_reliability || []).reduce(
      (sum, row) => sum + (row.failures || 0), 0);
    const feedback = (ds.feedback || []).length;
    const queue = report.telemetry_queue || {};

    const collectionBroken = ingest.evidence === "observed" && ingest.batches_failed > 0;
    const concerns = [];
    if (collectionBroken) {
      concerns.push([t("Data collection"),
        f("The collector rejected {failed} of {total} batches ({reason})", {
          failed: num(ingest.batches_failed), total: num(ingest.batches),
          reason: t(ingest.last_reason || "unknown"),
        }), "warn"]);
    }
    if ((queue.pending || 0) + (queue.claimed || 0) + (queue.invalid || 0)) {
      concerns.push([t("Telemetry queue"),
        f("{pending} pending, {claimed} being replayed, {invalid} invalid", {
          pending: num(queue.pending), claimed: num(queue.claimed), invalid: num(queue.invalid),
        }), "warn"]);
    }
    if (!ds.active) concerns.push([t("Telemetry"), t("No validated events yet"), "idle"]);
    if (uncounted) {
      concerns.push([t("Stored data"),
        f("{count} rows are stored but not counted", { count: num(uncounted) }), "idle"]);
    }
    if (repoIssues) {
      concerns.push([t("Delivery health"),
        f("{count} broken references or missing scripts", { count: num(repoIssues) }), "warn"]);
    }
    if (unmatched) {
      concerns.push([t("Subagent lifecycle"),
        f("{count} start/stop signals without a pair", { count: num(unmatched) }), "warn"]);
    }
    if (toolFailures) {
      concerns.push([t("Tool failures"),
        f("{failures} of {calls} tool calls failed",
          { failures: num(toolFailures), calls: num(toolCalls) }), "warn"]);
    }
    if (hookErrors) {
      concerns.push([t("Hook errors"),
        f("{count} hook executions reported an error", { count: num(hookErrors) }), "warn"]);
    }
    if (hookGap) {
      concerns.push([t("Quality hooks"),
        f("{count} more blocks than confirmed fixes", { count: num(hookGap) }), "warn"]);
    }
    if (feedback) {
      concerns.push([t("Feedback queue"), f("{count} items waiting", { count: num(feedback) }), "idle"]);
    }
    if (!concerns.length) {
      concerns.push([t("Current snapshot"), t("No actionable signal is visible"), "good"]);
    }
    // One row per thing a reader can act on; summing unrelated magnitudes
    // produced a headline number that matched nothing on screen.
    const attention = concerns.length && concerns[0][2] === "good" ? 0 : concerns.length;
    const healthy = ds.active && attention === 0;
    const statusLabel = collectionBroken ? t("Collection is broken")
      : !ds.active ? t("Waiting for telemetry")
        : healthy ? t("Signals are clean") : t("Review recommended");
    const statusTone = collectionBroken ? "warn"
      : !ds.active ? "idle" : healthy ? "good" : "warn";

    root.appendChild(el("header", { class: "overview-hero " + statusTone }, [
      el("div", { class: "overview-status " + statusTone }, [
        el("span", { class: "status-light", "aria-hidden": "true" }),
        el("div", null, [
          el("span", { class: "eyebrow" }, t("SYSTEM STATUS")),
          el("strong", null, statusLabel),
          el("span", null, ds.active && report.generated_at
            ? f("snapshot {stamp}", { stamp: fmtStamp(report.generated_at) })
            : t("no validated event snapshot yet")),
        ]),
      ]),
      el("div", { class: "overview-intro" }, [
        el("h1", null, t("Agent system overview")),
        el("p", null, t("What the harness actually did, what it cost, and what looks wrong. Start at the top; open the other tabs only when a number needs proof.")),
      ]),
      el("div", { class: "attention-total " + statusTone }, [
        el("span", null, t("OPEN SIGNALS")),
        el("strong", null, num(attention)),
        el("small", null, attention ? t("worth reviewing") : t("nothing actionable")),
      ]),
    ]));

    root.appendChild(periodLine(report));

    root.appendChild(el("div", { class: "overview-metrics" }, [
      overviewMetric(t("Observed sessions"), num(report.sessions), t("separate harness runs")),
      overviewMetric(t("Processed token volume"), fmtTok(tokens.processed_tokens),
        t("normalized context plus output"), "usage-tone"),
      overviewMetric(t("Model turns"), num(workload.model_turns), t("completed model responses"), "usage-tone"),
      // A partial cost figure covers only the requests that reported one, so the
      // note must say so; "billed by the provider" beside 3% coverage would read
      // as a full bill.
      overviewMetric(t("Spend"),
        cost.evidence === "unavailable" ? "—" : fmtUsd(cost.micro_usd),
        cost.evidence === "unavailable" ? t("cost not reported")
          : cost.evidence === "partial"
            ? f("only {reporting} of {total} requests report cost",
              { reporting: num(cost.reporting_requests), total: num(cost.total_requests) })
            : t("billed by the provider"),
        "usage-tone"),
      overviewMetric(t("Telemetry events"), num(report.usable_records), t("validated rows only"), "event-tone"),
      overviewMetric(t("Subagent instances"), num(report.agent_instances), t("distinct delegated runs"), "agent-tone"),
      overviewMetric(t("Observed days"), num((report.by_day || []).length), t("days with at least one event")),
      overviewMetric(t("Reporting adapters"), num(reportingAdapters.length),
        f("of {total} enabled", { total: adapters.length })),
    ]));

    const activityBody = el("div", null, [
      signalChart(report.by_day || []),
      el("div", { class: "panel-foot" }, [
        el("span", null, f("{days} days shown", { days: num(Math.min(21, (report.by_day || []).length)) })),
        el("span", null, f("{events} validated events", { events: num(report.usable_records) })),
      ]),
    ]);

    const attentionBody = el("div", { class: "attention-list" }, concerns.map((item) =>
      el("div", { class: "attention-row " + item[2] }, [
        el("span", { class: "attention-mark", "aria-hidden": "true" }),
        el("div", null, [el("strong", null, item[0]), el("span", null, item[1])]),
      ])));

    const costRows = (cost.by_model || []).filter((row) => row.micro_usd > 0).slice(0, 6);
    const costBody = costRows.length
      ? el("div", null, [
        shareRows(costRows.map((row) => [
          (row.adapter_id ? row.adapter_id + " · " : "") + row.model,
          row.micro_usd, fmtUsd(row.micro_usd),
        ]), cost.micro_usd, "usage-share"),
        el("p", { class: "panel-foot single" }, f("Cost is reported by {reporting} of {total} requests.",
          { reporting: num(cost.reporting_requests), total: num(cost.total_requests) })),
      ])
      : emptyState(t("No adapter reports cost, so spend cannot be shown. Token counts below are still exact."));

    const adapterActivity = adapters.map((item) => [
      item.adapter_label || item.adapter_id, item.usable_records || 0,
    ]);
    const agentBody = el("div", { class: "panel-stack" }, [
      el("div", null, [
        el("h3", null, t("Activity by adapter")),
        shareRows(adapterActivity, report.usable_records || 0, "agent-share"),
      ]),
      el("div", null, [
        el("h3", null, t("Execution split")),
        statRow([
          [num(workload.top_level_turns), t("main or unattributed turns")],
          [num(workload.subagent_starts), t("subagent calls")],
          [num(workload.subagent_attributed_turns), t("attributed subagent turns")],
        ]),
      ]),
    ]);

    const recent = (report.recent_events || []).slice(0, 8);
    const recentBody = recent.length ? el("ol", { class: "event-stream" }, recent.map((item) =>
      el("li", null, [
        el("span", { class: "event-time mono" }, fmtStamp(item.timestamp).slice(5)),
        el("span", { class: "event-name mono" }, item.event),
        el("span", { class: "event-owner" }, item.agent_type || t("(main context)")),
        el("span", { class: "event-project mono" }, item.project || "—"),
      ]))) : emptyState(t("No validated event stream is available yet."));

    root.appendChild(el("div", { class: "notice " + (ingestNote.tone === "good" ? "ok" : "") },
      ingestNote.text));

    root.appendChild(el("div", { class: "overview-grid" }, [
      overviewPanel(t("LATEST 21 DAYS"), t("Daily activity"), activityBody, "signal-panel"),
      overviewPanel(t("ATTENTION"), t("What deserves a look"), attentionBody, "attention-panel"),
      overviewPanel(t("SPEND"), t("Where the money goes"), costBody, "model-panel"),
      overviewPanel(t("ROUTING"), t("Where the work happens"), agentBody, "agent-panel"),
      overviewPanel(t("LATEST"), t("Recent validated events"), recentBody, "panel-full stream-panel"),
    ]));

    root.appendChild(el("p", { class: "overview-caveat" },
      t("This page measures what the harness did and what it cost. It does not claim the product it built is correct.")));
  }

  // Telemetry collection view.
  function renderCollection(root) {
    const ds = D.dev_state || { active: false, feedback: [] };
    const report = telemetry();
    if (!ds.active) {
      root.appendChild(el("div", { class: "notice" },
        t("No telemetry recorded yet — either dev mode is not installed, or no sessions have run since it was. Enable the intended adapter with ./install.sh --claude --dev, ./install.sh --codex --dev, or ./install.sh --pi --dev.")));
      if (report.error) {
        root.appendChild(el("div", { class: "notice" },
          f("Telemetry read error: {error}", { error: report.error })));
      }
      return;
    }

    root.appendChild(explain(t("Each adapter writes its own local database. The page reads them read-only and never merges their storage.")));
    root.appendChild(periodLine(report));

    // Collector.
    const ingest = ingestState();
    const ingestNote = ingestSummary();
    const collectorBody = el("div", { class: "panel-stack" }, [
      explain(t("The collector receives the harness's own usage stream over local OTLP. If it fails, the page would otherwise show a confident zero.")),
      ingest.evidence === "observed" ? statRow([
        [num(ingest.batches), t("batches received")],
        [num(ingest.batches_failed), t("batches rejected"), ingest.batches_failed ? "warn" : ""],
        [num(ingest.rows_written), t("rows stored")],
        [num(ingest.rows_deduplicated), t("duplicates dropped")],
        [fmtStamp(ingest.last_batch_at) || "—", t("last batch")],
      ]) : null,
      ingest.evidence === "observed" && ingest.started_at
        ? explain(f("Counted since the collector started at {stamp}.",
          { stamp: fmtStamp(ingest.started_at) }))
        : null,
      el("div", { class: "notice " + (ingestNote.tone === "good" ? "ok" : "") }, ingestNote.text),
    ]);
    root.appendChild(section(t("Collector"), "dev", null, collectorBody));

    const queue = report.telemetry_queue || {};
    root.appendChild(section(t("Telemetry queue"), "dev", queue.pending || 0,
      statRow([
        [num(queue.pending), t("pending")],
        [num(queue.claimed), t("being replayed")],
        [num(queue.invalid), t("invalid")],
      ])));

    const concurrency = report.session_concurrency || {};
    const concurrencyRows = concurrency.by_adapter || (concurrency.evidence
      ? [{ adapter_id: report.adapter_id, ...concurrency }] : []);
    root.appendChild(section(t("Parallel sessions"), "agents", concurrencyRows.length,
      el("div", { class: "panel-stack" }, [
        explain(t("Measured only from paired session start and end events. Partial means at least one boundary falls outside the selected period or was never observed; missing boundaries are not guessed.")),
        concurrencyRows.length ? table([
          [t("adapter")], [t("coverage")], [t("complete runs"), true],
          [t("peak active"), true], [t("sessions overlapping"), true],
          [t("overlap time"), true], [t("unpaired boundaries"), true],
        ], concurrencyRows.map((row) => cells([
          [row.adapter_id || "—", "mono"],
          [t(row.evidence || "unavailable"), row.evidence === "partial" ? "mono warn" : "mono"],
          [num(row.complete_runs), "num"],
          [num(row.peak_active), "num"],
          [num(row.overlap_sessions), "num"],
          [fmtMs(row.overlap_ms), "num"],
          [num((row.missing_start || 0) + (row.missing_end || 0)
            + (row.duplicate_start || 0) + (row.invalid_timestamp || 0)),
          (row.evidence === "partial") ? "num warn" : "num"],
        ]))) : emptyState(t("No paired session boundaries have been recorded.")),
      ])));

    // Adapters.
    const adapterRows = (report.adapters || []).map((item) => cells([
      [item.adapter_label || item.adapter_id, "mono"],
      [num(item.usable_records), "num"],
      [num(item.records), "num"],
      [num(item.excluded_records), "num"],
      [num(item.sessions), "num"],
      [item.active ? t("active") : t("inactive"), "num"],
    ]));
    if (adapterRows.length) {
      root.appendChild(section(t("Adapter coverage"), "dev", adapterRows.length, table([
        [t("adapter")], [t("usable"), true], [t("stored"), true],
        [t("not counted"), true], [t("sessions"), true], [t("state"), true],
      ], adapterRows)));
    }

    // Exclusions.
    const exclusions = report.exclusions || {};
    const exclusionRows = Object.keys(exclusions)
      .filter((key) => exclusions[key] > 0)
      .map((key) => cells([[t(key)], [num(exclusions[key]), "num"]]));
    root.appendChild(section(t("Why rows are not counted"), "dev",
      report.excluded_records || 0,
      el("div", { class: "panel-stack" }, [
        explain(t("A stored row is only counted when its format, contents and provenance all check out. Anything else stays visible here instead of quietly vanishing.")),
        exclusionRows.length
          ? table([[t("reason")], [t("rows"), true]], exclusionRows)
          : el("div", { class: "notice ok" }, t("Every stored row is counted.")),
      ])));

    // Hook health.
    const hookHealth = report.hook_health || [];
    root.appendChild(section(t("Hook health"), "hooks", hookHealth.length,
      el("div", { class: "panel-stack" }, [
        explain(t("How often the harness ran its hooks and how often one failed. An error here means a check did not run, so its guarantee did not hold for that turn.")),
        hookHealth.length ? table([
          [t("adapter")], [t("hook event")], [t("runs"), true], [t("errors"), true],
          [t("blocked"), true], [t("cancelled"), true],
          [t("median"), true], [t("p95"), true],
        ], hookHealth.map((row) => cells([
          [row.adapter_id || report.adapter_id || "—", "mono"],
          [row.hook_event, "mono"],
          [num(row.runs), "num"],
          [num(row.errors), row.errors ? "num warn" : "num"],
          [num(row.blocking), "num"],
          [num(row.cancelled), "num"],
          [fmtMs(row.median_ms), "num"],
          [fmtMs(row.p95_ms), "num"],
        ]))) : emptyState(t("No hook execution data has been recorded.")),
      ])));

    // Tool reliability.
    const tools = report.tool_reliability || [];
    root.appendChild(section(t("Tool reliability"), "events", tools.length,
      el("div", { class: "panel-stack" }, [
        explain(t("Every tool call the harness completed, with how long it took. p95 means 95% of calls finished faster than this.")),
        tools.length ? table([
          [t("adapter")], [t("tool")], [t("calls"), true], [t("failures"), true],
          [t("median"), true], [t("p95"), true], [t("max"), true],
        ], tools.map((row) => cells([
          [row.adapter_id || report.adapter_id || "—", "mono"],
          [row.tool_name, "mono"],
          [num(row.calls), "num"],
          [num(row.failures), row.failures ? "num warn" : "num"],
          [fmtMs(row.median_ms), "num"],
          [fmtMs(row.p95_ms), "num"],
          [fmtMs(row.max_ms), "num"],
        ]))) : emptyState(t("No tool result data has been recorded.")),
      ])));

    // Permission decisions.
    const decisions = report.tool_decisions || [];
    root.appendChild(section(t("Permission decisions"), "config", decisions.length,
      el("div", { class: "panel-stack" }, [
        explain(t("What the harness decided before running a tool, and what made the decision — configuration, a hook, or the user.")),
        decisions.length ? table([
          [t("adapter")], [t("tool")], [t("decision")], [t("source")], [t("count"), true],
        ], decisions.slice(0, 40).map((row) => cells([
          [row.adapter_id || report.adapter_id || "—", "mono"],
          [row.tool_name, "mono"],
          [row.decision, "mono"],
          [row.source || "—", "mono dim"],
          [num(row.count), "num"],
        ]))) : emptyState(t("No permission decision data has been recorded.")),
      ])));

    // Sensitive permission audit exists only in the live, local dev service.
    const permissionAudits = ds.permission_audit || [];
    if (permissionAudits.length) {
      const auditRows = permissionAudits.flatMap((audit) =>
        (audit.records || []).map((row) => {
          let input = row.tool_input || "{}";
          try { input = JSON.stringify(JSON.parse(input), null, 2); } catch (_err) { /* show raw */ }
          const detail = el("details", { class: "permission-input" }, [
            el("summary", null, t("view input")),
            el("pre", null, input),
          ]);
          return cells([
            [audit.adapter_id, "mono"],
            [fmtStamp(row.request_ts), "mono dim"],
            [row.permission_mode || "unknown", "mono"],
            [row.tool_name || "unknown", "mono"],
            [row.decision || t("waiting"), row.decision ? "mono" : "mono warn"],
            [row.decision_source || "—", "mono dim"],
            [row.wait_ms == null ? "—" : "≈ " + fmtMs(row.wait_ms), "num"],
            [t(row.correlation_evidence || "unresolved"), "mono dim"],
            [detail, "permission-input-cell"],
          ]);
        }));
      const requests = permissionAudits.reduce((n, item) => n + (item.requests || 0), 0);
      const accepted = permissionAudits.reduce((n, item) => n + (item.accepted || 0), 0);
      const rejected = permissionAudits.reduce((n, item) => n + (item.rejected || 0), 0);
      const unresolved = permissionAudits.reduce((n, item) => n + (item.unresolved || 0), 0);
      root.appendChild(section(t("Permission request audit"), "config", requests,
        el("div", { class: "panel-stack" }, [
          el("div", { class: "notice warn" },
            t("Sensitive local data: exact tool input is stored only in the live dev database and is never included in static snapshots or model analysis.")),
          explain(t("The runtime reports the final decision and its source, but not the exact matching rule. Request-to-decision links and wait time are marked as inferred when no shared ID exists.")),
          statRow([
            [num(requests), t("requests")], [num(accepted), t("accepted")],
            [num(rejected), t("rejected")], [num(unresolved), t("waiting")],
          ]),
          auditRows.length ? table([
            [t("adapter")], [t("time")], [t("mode")], [t("tool")],
            [t("decision")], [t("source")], [t("wait"), true],
            [t("link evidence")], [t("input")],
          ], auditRows) : emptyState(t("No permission requests have been recorded.")),
        ])));
    }

    // Mainframe's own quality hooks.
    const effectiveness = report.hook_effectiveness || [];
    if (effectiveness.length) {
      root.appendChild(section(t("Quality hook outcomes"), "hooks", effectiveness.length,
        el("div", { class: "panel-stack" }, [
          explain(t("MAINFRAME's own checks. When a collection start is shown, outcomes and recorded runs cover that same window; older findings are separated instead of being divided by a newer denominator. A linked fix only confirms that the technical finding disappeared in the same session, hook, and rule.")),
          table([
            [t("adapter")], [t("script")], [t("rule")], [t("noted"), true],
            [t("asked"), true], [t("blocked"), true], [t("resolved"), true],
            [t("linked fixes"), true], [t("unlinked fixes"), true],
            [t("median to fix"), true], [t("sessions"), true],
            [t("recorded runs"), true], [t("since")], [t("older findings"), true],
          ], effectiveness.map((row) => cells([
            [row.adapter_id || report.adapter_id || "—", "mono"],
            [row.hook, "mono"],
            [row.rule_id, "mono"],
            [num(row.noted), "num"],
            [num(row.asked), "num"],
            [num(row.blocked), "num"],
            [num(row.resolved), "num"],
            [num(row.linked_resolutions), "num"],
            [num(row.unlinked_resolutions), row.unlinked_resolutions ? "num warn" : "num"],
            [row.resolution_latency?.median_ms == null ? "—" : fmtMs(row.resolution_latency.median_ms), "num"],
            [num(row.sessions), "num"],
            [row.denominator_from ? num(row.invocations) : "—", "num"],
            [row.denominator_from ? fmtStamp(row.denominator_from) : "—", "mono"],
            [row.denominator_from
              ? num(row.historical_before_denominator?.count || 0) : "—", "num dim"],
          ]))),
        ])));
    }

    const injected = report.harness_context_cost || {};
    if (injected.characters) {
      root.appendChild(section(t("Injected context"), "usage", null,
        explain(f("Hook messages added {chars} characters to the model's context. At 2–6 characters per token that is roughly {low}–{high} tokens — an estimate, not a measurement, and it does not prove the harness slowed anything down.", {
          chars: num(injected.characters),
          low: fmtTok(injected.estimated_tokens_low),
          high: fmtTok(injected.estimated_tokens_high),
        }))));
    }

    // Lifecycle.
    const lifecycle = report.agent_lifecycle || [];
    if (lifecycle.length) {
      root.appendChild(section(t("Subagent lifecycle"), "agents", lifecycle.length, table([
        [t("adapter")], [t("agent")], [t("instances"), true], [t("started"), true],
        [t("stopped"), true], [t("duplicate stops"), true],
        [t("missing start"), true], [t("missing stop"), true],
      ], lifecycle.map((row) => cells([
        [row.adapter_id || report.adapter_id || "—", "mono"],
        [row.agent === "(main context)" ? t("(main context)") : row.agent, "mono"],
        [num(row.instances), "num"],
        [num(row.started), "num"],
        [num(row.stopped), "num"],
        [num(row.duplicate_stops), row.duplicate_stops ? "num warn" : "num"],
        [num(row.missing_start), row.missing_start ? "num warn" : "num"],
        [num(row.missing_stop), row.missing_stop ? "num warn" : "num"],
      ])))));
    }

    const engineer = report.engineer_runs || {};
    if (engineer.runs) {
      root.appendChild(section(t("Pi engineer runs"), "agents", engineer.runs,
        el("div", { class: "panel-stack" }, [
          explain(t("Bounded implementation blocks run by Pi. Ready means the internal verifier passed; the primary agent still owns final review and commit.")),
          statRow([
            [num(engineer.runs), t("runs")],
            [num(engineer.ready), t("ready")],
            [num(engineer.blocked), t("not ready")],
            [num(engineer.correction_rounds), t("corrections")],
            [num(engineer.checks_passed) + " / " + num(engineer.checks_total), t("checks passed")],
            [num(engineer.compactions), t("compactions")],
            [num(engineer.tool_calls), t("tool calls")],
            [fmtMs(engineer.duration_ms), t("total duration")],
          ]),
          (report.engineer_tools || []).length ? table([
            [t("adapter")], [t("stage")], [t("tool")], [t("calls"), true],
          ], report.engineer_tools.map((row) => cells([
            [row.adapter_id || "pi", "mono"],
            [row.stage, "mono"],
            [row.tool_name, "mono"],
            [num(row.calls), "num"],
          ]))) : null,
        ])));
    }

    // Raw counts.
    if ((report.event_counts || []).length) {
      root.appendChild(section(t("Event counts"), "events", report.event_counts.length,
        barList(report.event_counts)));
    }
    const breakdowns = (report.breakdowns || []).filter((item) => item.items.length > 1);
    if (breakdowns.length) {
      root.appendChild(section(t("Breakdowns"), "dev", breakdowns.length,
        el("div", { class: "breakdown-grid" }, breakdowns.map((item) =>
          el("div", { class: "breakdown-card" }, [
            // Two adapters produce the same event/field pair; without the owner
            // the two cards look like an accidental duplicate.
            el("h3", { class: "mono" },
              (item.adapter_id ? item.adapter_id + " · " : "") + item.event + " · " + item.key),
            shareRows(item.items, item.total),
          ])))));
    }

    if ((report.recent_events || []).length) {
      root.appendChild(section(t("Recent validated rows"), "dev", report.recent_events.length, table([
        [t("adapter")], [t("event")], [t("agent")], [t("project")],
      ], report.recent_events.map((item) => cells([
        [item.adapter_id || report.adapter_id || "—", "mono"],
        [fmtStamp(item.timestamp) + "  " + item.event, "mono"],
        [item.agent_type || t("(main context)"), "mono"],
        [item.project || "—", "mono dim"],
      ])))));
    }

    if ((ds.feedback || []).length) {
      root.appendChild(section(t("Feedback queue"), "dev", ds.feedback.length,
        el("div", null, [
          explain(t("Files waiting in the local feedback queue.")),
          el("ul", { class: "files" }, ds.feedback.map((name) => el("li", { class: "mono" }, name))),
        ])));
    }
  }

  // Spend and token view.
  function renderUsage(root) {
    const ds = D.dev_state || { active: false };
    const report = telemetry();
    const usage = report.token_usage || {};
    const cost = report.cost || {};
    const workload = report.workload || {};
    const adapters = activeAdapters(report);

    root.appendChild(explain(t("Only exact native counters are used. Cached input is normalized per adapter so it is counted once; an adapter that reports nothing stays visible and is never treated as zero.")));

    if (!ds.active) {
      root.appendChild(el("div", { class: "notice" },
        t("No adapter telemetry is active yet. Install Claude Code, Codex, or Pi in dev mode and start a fresh session.")));
      return;
    }
    root.appendChild(periodLine(report));

    // Spend.
    root.appendChild(section(t("Total spend"), "usage", null,
      el("div", { class: "panel-stack" }, [
        cost.evidence === "unavailable"
          ? emptyState(t("No adapter reports cost, so spend cannot be shown. Token counts below are still exact."))
          : statRow([
            [fmtUsd(cost.micro_usd), t("cost")],
            [num(cost.reporting_requests), t("priced requests")],
            [t(cost.evidence), t("coverage"), cost.evidence === "partial" ? "warn" : ""],
          ]),
        cost.evidence !== "unavailable"
          ? explain(f("Cost is reported by {reporting} of {total} requests.",
            { reporting: num(cost.reporting_requests), total: num(cost.total_requests) }))
          : null,
      ])));

    const costRows = (cost.by_model || []).filter((row) => row.micro_usd > 0);
    if (costRows.length) {
      root.appendChild(section(t("Cost by model"), "usage", costRows.length, table([
        [t("adapter")], [t("model")], [t("requests"), true], [t("cost"), true],
      ], costRows.map((row) => cells([
        [row.adapter_id || "—", "mono"],
        [row.model || t("(unknown)"), "mono"],
        [num(row.requests), "num"],
        [fmtUsd(row.micro_usd), "num"],
      ])))));
    }

    // Tokens.
    root.appendChild(section(t("Token volume"), "usage", null,
      el("div", { class: "panel-stack" }, [
        statRow([
          [num(usage.requests), t("requests")],
          [fmtTok(usage.fresh_input_tokens), t("fresh input")],
          [fmtTok(usage.cached_input_tokens), t("cached input detail")],
          [fmtTok(usage.cache_write_tokens), t("cache write")],
          [fmtTok(usage.request_context_tokens), t("request context")],
          [fmtTok(usage.output_tokens), t("output")],
          [fmtTok(usage.reasoning_output_tokens), t("reasoning detail")],
          [fmtTok(usage.processed_tokens), t("processed volume")],
        ]),
        explain(t("Fresh input excludes cache hits. Request context is the full input seen by the model for the recorded requests, with cached input counted once. Reasoning is a detail of output, not an extra amount. Processed volume is request context plus output. None of these counters is a price; only the separately reported cost is money.")),
      ])));

    // Latency.
    const latency = report.latency || {};
    const latencyRows = latency.by_adapter || (latency.samples
      ? [{ adapter_id: report.adapter_id, ...latency }] : []);
    root.appendChild(section(t("Response time"), "dev", latencyRows.length,
      el("div", { class: "panel-stack" }, [
        explain(t("Measured from request to completed response, as the harness reports it.")),
        latencyRows.length ? table([
          [t("adapter")], [t("requests"), true], [t("median"), true],
          [t("p95"), true], [t("max"), true],
        ], latencyRows.map((row) => cells([
          [row.adapter_id || "—", "mono"],
          [num(row.samples), "num"],
          [fmtMs(row.median_ms), "num"],
          [fmtMs(row.p95_ms), "num"],
          [fmtMs(row.max_ms), "num"],
        ]))) : emptyState(t("No response-time data has been recorded.")),
      ])));

    // Adapter coverage.
    const coverageRows = adapters.map((item) => {
      const value = item.token_usage || {};
      return cells([
        [item.adapter_label || item.adapter_id, "mono"],
        [t(value.evidence || "unavailable"), "num"],
        [num(value.requests), "num"],
        [fmtTok(value.fresh_input_tokens), "num"],
        [fmtTok(value.cached_input_tokens), "num"],
        [fmtTok(value.request_context_tokens), "num"],
        [fmtTok(value.output_tokens), "num"],
        [fmtTok(value.processed_tokens), "num"],
      ]);
    });
    if (coverageRows.length) {
      root.appendChild(section(t("Adapter coverage"), "dev", coverageRows.length, table([
        [t("adapter")], [t("source"), true], [t("requests"), true], [t("fresh input"), true],
        [t("cached input detail"), true], [t("request context"), true],
        [t("output"), true], [t("processed volume"), true],
      ], coverageRows)));
      const adapterTokenRows = adapters
        .map((item) => [
          item.adapter_label || item.adapter_id,
          ((item.token_usage || {}).processed_tokens || 0),
          fmtTok((item.token_usage || {}).processed_tokens || 0),
        ])
        .filter((row) => row[1] > 0);
      if (adapterTokenRows.length) {
        root.appendChild(section(t("Token share by adapter"), "usage", adapterTokenRows.length,
          shareRows(adapterTokenRows, usage.processed_tokens || 0, "usage-share")));
      }
    }

    root.appendChild(section(t("Agent workload"), "agents", null,
      el("div", { class: "panel-stack" }, [
        statRow([
          [num(workload.top_level_turns), t("main or unattributed turns")],
          [fmtTok(workload.top_level_tokens), t("main or unattributed processed tokens")],
          [num(workload.subagent_starts), t("subagent calls")],
          [num(workload.subagent_stops), t("subagent completions")],
          [num(workload.subagent_attributed_turns), t("attributed subagent turns")],
          [fmtTok(workload.subagent_attributed_tokens), t("attributed subagent processed tokens")],
        ]),
        explain(workload.subagent_token_evidence === "observed-correlation"
          ? t("Subagent tokens are shown only when the native model session identifier matches a recorded subagent identifier. Unmatched usage stays at the top level instead of being guessed.")
          : t("The native telemetry does not currently expose a verified link between model usage and individual subagents. Calls are exact; per-subagent tokens remain unavailable.")),
        workload.top_level_evidence === "partial" || workload.top_level_evidence === "unavailable"
          ? explain(t("Main-agent usage and unattributed usage are combined because at least one adapter does not expose enough identifiers to separate them safely."))
          : null,
      ])));

    const agentRows = workload.by_subagent || [];
    if (agentRows.length) {
      root.appendChild(section(t("Subagents"), "agents", agentRows.length, table([
        [t("adapter")], [t("agent")], [t("calls"), true], [t("completed"), true],
        [t("turns"), true], [t("processed volume"), true],
      ], agentRows.map((row) => cells([
        [row.adapter_id || report.adapter_id || "—", "mono"],
        [row.agent || t("(unknown)"), "mono"],
        [num(row.starts), "num"], [num(row.stops), "num"],
        [row.turns ? num(row.turns) : "—", "num"],
        [row.processed_tokens ? fmtTok(row.processed_tokens) : "—", "num"],
      ])))));
    }

    const skillRows = workload.skills || [];
    root.appendChild(section(t("Skill invocations"), "skills", skillRows.length,
      skillRows.length ? table([
        [t("adapter")], [t("skill")], [t("invoker")], [t("calls"), true],
      ], skillRows.map((row) => cells([
        [row.adapter_id || report.adapter_id || "—", "mono"],
        [row.skill, "mono"], [t(row.invoker), "mono"], [num(row.calls), "num"],
      ]))) : emptyState(t("No verified skill-invocation events were collected in this period. This is unknown coverage, not proof that no skill ran."))));

    const modelRows = (usage.by_model || []).filter((row) => row.processed_tokens > 0);
    if (modelRows.length) {
      const modelTokenRows = modelRows.slice(0, 16).map((row) => [
        (row.adapter_id ? row.adapter_id + " · " : "") + (row.model || t("(unknown)")),
        row.processed_tokens,
        fmtTok(row.processed_tokens),
      ]);
      root.appendChild(section(t("Token share by model"), "usage", modelTokenRows.length,
        shareRows(modelTokenRows, usage.processed_tokens || 0, "usage-share")));
      root.appendChild(section(t("Usage by model"), "usage", modelRows.length, table([
        [t("adapter")], [t("model")], [t("requests"), true], [t("fresh input"), true],
        [t("cached input detail"), true], [t("request context"), true],
        [t("output"), true], [t("processed volume"), true],
      ], modelRows.map((row) => cells([
        [row.adapter_id || "—", "mono"],
        [row.model || t("(unknown)"), "mono"],
        [num(row.requests), "num"],
        [fmtTok(row.fresh_input_tokens), "num"],
        [fmtTok(row.cached_input_tokens), "num"],
        [fmtTok(row.request_context_tokens), "num"],
        [fmtTok(row.output_tokens), "num"],
        [fmtTok(row.processed_tokens), "num"],
      ])))));
    }

    const sourceRows = (usage.by_source || []).map((row) => cells([
      [row.adapter_id || "—", "mono"],
      [row.source, "mono"],
      [num(row.requests), "num"],
      [fmtTok(row.processed_tokens), "num"],
    ]));
    if (sourceRows.length) {
      root.appendChild(section(t("Usage by source"), "usage", sourceRows.length, table([
        [t("adapter")], [t("source")], [t("requests"), true], [t("processed volume"), true],
      ], sourceRows)));
    }

    if ((report.by_day || []).length) {
      root.appendChild(section(t("Activity calendar"), "events", report.by_day.length,
        usageHeatmap(report.by_day)));
    }

    renderTranscriptHistory(root);
  }

  function renderTranscriptHistory(root) {
    const u = D.usage;
    if (!u || !u.active || !u.messages) return;
    root.appendChild(section(t("Claude transcript history"), "usage", u.sessions || 0,
      el("div", { class: "panel-stack" }, [
        explain(t("Claude-only history read from local session transcripts. It is useful for long-term trends but is kept out of the exact cross-adapter totals above, because Codex has no equivalent transcript contract.")),
        explain(t("This legacy section always shows its full available transcript history and does not follow the period selector.")),
        explain(f("Read from {files} local session transcripts. Counts only — no prompt text is read.",
          { files: num(u.files) })),
        statRow([
          [num(u.sessions), t("sessions")],
          [num(u.messages), t("assistant replies")],
          [fmtTok(u.tokens.total), t("input plus output")],
          [num(u.active_days), t("active days")],
          [f("{n}d", { n: u.current_streak }), t("current streak")],
          [f("{n}d", { n: u.longest_streak }), t("longest streak")],
          [fmtHour(u.peak_hour), t("peak hour")],
          [u.favorite_model || "—", t("top model")],
        ]),
        explain(f("This legacy input-plus-output counter excludes cache and is not a price: {read} cache-read tokens + {write} cache-write tokens are shown separately.",
          { read: fmtTok(u.tokens.cache_read), write: fmtTok(u.tokens.cache_creation) })),
      ])));

    const sp = u.split || { main: {}, sub: {} };
    const splitRow = (label, s) => cells([
      [label],
      [num(s.messages), "num"],
      [fmtTok(s["in"]), "num"],
      [fmtTok(s.out), "num"],
      [fmtTok(s.total), "num"],
    ]);
    root.appendChild(section(t("Main window vs subagents"), "usage", 2, table([
      [t("scope")], [t("messages"), true], [t("input"), true],
      [t("output"), true], [t("input plus output"), true],
    ], [splitRow(t("main window"), sp.main), splitRow(t("subagents"), sp.sub)])));

    const grand = u.tokens.total || 1;
    const shown = u.models.filter((m) => m.total > 0);
    root.appendChild(section(t("Tokens by model"), "usage", shown.length, table([
      [t("model")], [t("input"), true], [t("output"), true],
      [t("input plus output"), true], [t("share")],
    ], shown.map((m) => el("tr", null, [
      el("td", { class: "mono" }, m.model),
      el("td", { class: "num" }, fmtTok(m["in"])),
      el("td", { class: "num" }, fmtTok(m.out)),
      el("td", { class: "num" }, fmtTok(m.total)),
      el("td", null, el("div", { class: "share" }, [
        el("span", { class: "bar-track" }, el("span", { class: "bar-fill",
          style: "width:" + Math.max(2, Math.round(100 * m.total / grand)) + "%" })),
        el("span", { class: "share-pct" }, (m.share * 100).toFixed(1) + "%"),
      ])),
    ])))));

    if (u.by_hour && u.by_hour.some((r) => r[1])) {
      root.appendChild(section(t("By hour of day (UTC)"), "usage", 24,
        barList(u.by_hour.map(([h, n]) => [String(h).padStart(2, "0") + ":00", n]))));
    }
    if (u.no_usage) {
      root.appendChild(el("p", { class: "muted small" },
        f("{count} replies had no usage record (counted, no token data).", { count: num(u.no_usage) })));
    }
  }

  // Component catalogue view.
  function skillCard(s) {
    const badges = el("div", { class: "badges" }, [
      badge(s.dev ? t("dev") : t("skill"), s.dev ? "dev" : "skills"),
      badge(s.user_invocable ? "/" + s.name : t("auto"), s.user_invocable ? "user" : "muted"),
    ]);
    return el("article", { class: "card clickable" }, [
      el("div", { class: "card-head" }, [el("span", { class: "card-name" }, s.name), badges]),
      el("p", { class: "card-desc" }, s.description),
      s.when_to_use && el("p", { class: "card-when" }, [el("b", null, t("when: ")), s.when_to_use]),
    ]);
  }

  function agentCard(a) {
    const chips = el("div", { class: "chips" },
      (a.skills || []).map((sk) => el("span", { class: "chip" }, sk)));
    return el("article", { class: "card clickable" }, [
      el("div", { class: "card-head" }, [
        el("span", { class: "card-name" }, a.name),
        el("div", { class: "badges" }, [badge(a.model || "?", "agents")]),
      ]),
      el("p", { class: "card-desc" }, a.description),
      (a.skills || []).length ? el("div", { class: "card-when" },
        [el("b", null, t("preloads: ")), chips]) : null,
    ]);
  }

  function cardText(it) {
    return (it.name + " " + (it.description || "") + " " + (it.when_to_use || "")
            + " " + ((it.skills || []).join(" "))).toLowerCase();
  }

  function renderCatalog(root) {
    catalogCards = [];
    catalogSections = [];
    const skills = D.skills.filter((s) => !s.dev);
    const devSkills = D.skills.filter((s) => s.dev);
    const groups = [
      [t("Skills"), "skills", skills, skillCard, "skills"],
      [t("Agents"), "agents", D.agents, agentCard, "agents"],
      [t("Dev skills"), "dev", devSkills, skillCard, "dev"],
    ];
    groups.forEach(([title, cls, items, mk, layer]) => {
      if (!items.length) return;
      const grid = el("div", { class: "grid" });
      const sec = section(title, cls, items.length, grid);
      const cards = [];
      items.forEach((it) => {
        const card = mk(it);
        const text = cardText(it);
        card.addEventListener("click", () => openDetail(layer, it.name));
        grid.appendChild(card);
        const entry = { el: card, text };
        catalogCards.push(entry);
        cards.push(entry);
      });
      catalogSections.push({ el: sec, cards });
      root.appendChild(sec);
    });
    applyFilter(filterQuery);
  }

  function renderHooks(root) {
    const byEvent = {};
    D.hooks.forEach((h) => (byEvent[h.event] || (byEvent[h.event] = [])).push(h));
    root.appendChild(explain(t("Every hook the plugin registers, grouped by the event that fires it.")));
    Object.keys(byEvent).sort().forEach((ev) => {
      const rows = byEvent[ev].map((h) => cells([
        [h.matcher || "*", "mono dim"], [h.script, "mono"], [h.purpose || ""],
      ]));
      root.appendChild(section(ev, "hooks", byEvent[ev].length,
        table([[t("matcher")], [t("script")], [t("purpose")]], rows)));
    });
  }

  // Configuration view.
  function kv(k, v) {
    return el("div", { class: "kv" }, [
      el("span", { class: "kvk" }, k),
      el("span", { class: "kvv mono" }, v == null || v === "" ? "—" : String(v)),
    ]);
  }

  function renderConfig(root) {
    const cfg = D.settings || {};
    const misc = D.misc || {};
    const perms = cfg.permissions || { allow: [], deny: [], ask: [] };

    const installed = D.installation || [];
    if (installed.length) {
      const rows = [];
      installed.forEach((adapter) => (adapter.items || []).forEach((item) => {
        rows.push(cells([
          [adapter.adapter_id, "mono"], [item.name, "mono"],
          [t(item.status), item.status === "present" ? "good" : "warn"],
        ]));
      }));
      root.appendChild(section(t("Installed MAINFRAME layers"), "config", rows.length,
        el("div", { class: "panel-stack" }, [
          explain(t("This is a local presence check of MAINFRAME-managed delivery records and targets. It does not claim unchanged content; installer checks remain the authority for drift.")),
          table([[t("adapter")], [t("component")], [t("status")]], rows),
        ])));
    }

    root.appendChild(el("h2", { class: "layer-h config" }, t("Permissions")));
    root.appendChild(explain(f("What the hub lets an agent do silently, ask about, or refuse. Default mode: {mode}.",
      { mode: cfg.mode || "?" })));
    [["deny", "perm-deny"], ["ask", "perm-ask"], ["allow", "perm-allow"]].forEach(([key, cls]) => {
      const items = perms[key] || [];
      if (!items.length) return;
      const rows = items.map((p) => el("li", { class: "mono perm " + cls }, p));
      root.appendChild(section(t(key), cls, items.length, el("ul", { class: "permlist" }, rows)));
    });

    const flags = cfg.flags || {};
    const settingsRows = [
      kv("model", flags.model), kv("effortLevel", flags.effortLevel),
      kv("outputStyle", flags.outputStyle),
      kv("language", flags.language), kv("defaultMode", cfg.mode),
      kv("autoCompact", flags.autoCompactEnabled), kv("autoMemory", flags.autoMemoryEnabled),
      kv("teammateMode", flags.teammateMode),
    ];
    root.appendChild(section(t("Settings"), "config", settingsRows.length,
      el("div", { class: "kvgrid" }, settingsRows)));

    const env = cfg.env || {};
    const envKeys = Object.keys(env);
    if (envKeys.length) {
      root.appendChild(section(t("Environment"), "config", envKeys.length,
        el("div", { class: "kvgrid wide" }, envKeys.map((k) => kv(k, env[k])))));
    }

    const plugins = cfg.plugins || {};
    const pkeys = Object.keys(plugins);
    if (pkeys.length) {
      root.appendChild(section(t("Plugins"), "config", pkeys.length,
        el("div", { class: "badges wrap" }, pkeys.map((p) =>
          badge(p + " · " + (plugins[p] ? t("on") : t("off")), plugins[p] ? "user" : "muted")))));
    }

    [[t("Output styles"), misc.output_styles || []], [t("Templates"), misc.templates || []]]
      .forEach(([title, items]) => {
        if (!items.length) return;
        const grid = el("div", { class: "grid" }, items.map((it) =>
          el("article", { class: "card" }, [
            el("div", { class: "card-head" }, [el("span", { class: "card-name" }, it.name)]),
            el("p", { class: "card-desc" }, it.summary || ""),
          ])));
        root.appendChild(section(title, "config", items.length, grid));
      });

    const emptyLayers = misc.empty_layers || [];
    if (emptyLayers.length) {
      root.appendChild(el("div", { class: "notice" }, [
        el("p", { class: "small" }, t("Reserved but empty layers — they exist in the architecture but ship no artifacts yet:")),
        el("div", { class: "chips" }, emptyLayers.map((e) =>
          el("span", { class: "chip" }, e.name + " · " + e.path))),
      ]));
    }
  }

  function renderHealth(root) {
    const h = D.health || { dangling: [], unlinked_skills: [], missing_scripts: [] };
    const issues = h.dangling.length + h.missing_scripts.length;
    root.appendChild(statRow([
      [num(h.missing_scripts.length), t("missing scripts")],
      [num(h.dangling.length), t("broken refs")],
      [num(h.unlinked_skills.length), t("skills without static links")],
    ]));
    if (issues === 0) {
      root.appendChild(el("div", { class: "notice ok" },
        t("Every cross-ref and preload resolves, and every registered hook script exists on disk.")));
    }
    if (h.missing_scripts.length) {
      root.appendChild(section(t("Missing hook scripts"), "perm-deny", h.missing_scripts.length,
        el("ul", { class: "hlist" }, h.missing_scripts.map((s) =>
          el("li", { class: "hitem err mono" }, f("{name} — registered in hooks.json but not on disk", { name: s }))))));
    }
    if (h.dangling.length) {
      root.appendChild(section(t("Broken references"), "perm-ask", h.dangling.length,
        el("ul", { class: "hlist" }, h.dangling.map((d) =>
          el("li", { class: "hitem" }, [
            linkChip(d.source, d.kind === "agent-skill" ? "agents" : "skills", d.source),
            el("span", { class: "harrow" }, " → "),
            el("span", { class: "mono missing" }, d.target),
            el("span", { class: "muted small" }, "  " + f("({kind}, dropped from the graph)", { kind: d.kind })),
          ])))));
    }
    if (h.unlinked_skills.length) {
      root.appendChild(section(t("Skills without static links"), "config", h.unlinked_skills.length,
        el("div", null, [
          explain(t("No static preload or cross-reference is known. These skills may still be reached through description routing, explicit invocation, init, or native commands; this is inventory, not a health failure.")),
          el("div", { class: "chips" }, h.unlinked_skills.map((o) => linkChip(o, "skills", o))),
        ])));
    }
  }

  // Relationship map view.
  const LAYERS = ["events", "hooks", "agents", "skills", "dev"];

  function ctrlBtn(label, title, onClick) {
    const b = el("button", { type: "button", title: title }, label);
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return b;
  }

  function renderGraph(root) {
    graphNodes = [];
    graphEdges = [];
    const pos = D.layout;
    const placed = D.nodes.filter((n) => pos[n.id]);
    let maxX = 0, maxY = 0;
    placed.forEach((n) => { maxX = Math.max(maxX, pos[n.id].x); maxY = Math.max(maxY, pos[n.id].y); });
    const w = maxX + 240, h = maxY + 120;

    const adj = {};
    D.edges.forEach((e) => {
      (adj[e.source] || (adj[e.source] = new Set())).add(e.target);
      (adj[e.target] || (adj[e.target] = new Set())).add(e.source);
    });

    const viewport = svg("g", { class: "viewport" });
    const edgeLayer = svg("g", { class: "edges" });
    const nodeLayer = svg("g", { class: "nodes" });
    viewport.appendChild(edgeLayer);
    viewport.appendChild(nodeLayer);

    const edgeEls = [];
    D.edges.forEach((e) => {
      const a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      const line = svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "edge " + e.kind });
      line._ends = [e.source, e.target];
      edgeLayer.appendChild(line);
      edgeEls.push(line);
      graphEdges.push({ el: line, ends: [e.source, e.target] });
    });

    const nodeEls = {};
    placed.forEach((n) => {
      const p = pos[n.id];
      const g = svg("g", { class: "gnode " + n.layer, transform: "translate(" + p.x + "," + p.y + ")" });
      g.appendChild(svg("circle", { r: 6, class: "dot" }));
      g.appendChild(svg("text", { x: 11, y: 4 }, n.label));
      g.addEventListener("mouseenter", () => focus(n.id));
      g.addEventListener("mouseleave", reset);
      let downXY = null;
      g.addEventListener("mousedown", (e) => { downXY = [e.clientX, e.clientY]; });
      g.addEventListener("click", (e) => {
        // a click that moved is a pan, not a select — don't open the panel
        if (downXY && Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]) > 4) return;
        openDetail(n.layer, n.id);
      });
      nodeLayer.appendChild(g);
      nodeEls[n.id] = g;
      graphNodes.push({ el: g, id: n.id, text: (n.label || n.id).toLowerCase() });
    });

    const board = svg("svg", { class: "graph", viewBox: "0 0 " + w + " " + h,
      preserveAspectRatio: "xMidYMin meet" }, viewport);

    function focus(id) {
      const keep = adj[id] || new Set();
      board.classList.add("dimmed");
      for (const k in nodeEls) nodeEls[k].classList.toggle("hot", k === id || keep.has(k));
      edgeEls.forEach((l) => l.classList.toggle("hot", l._ends[0] === id || l._ends[1] === id));
    }
    function reset() {
      board.classList.remove("dimmed");
      for (const k in nodeEls) nodeEls[k].classList.remove("hot");
      edgeEls.forEach((l) => l.classList.remove("hot"));
    }

    let scale = 1, tx = 0, ty = 0, drag = null;
    const Z_MIN = 0.3, Z_MAX = 6;
    function apply() { viewport.setAttribute("transform", "translate(" + tx + "," + ty + ") scale(" + scale + ")"); }
    function zoomBy(factor) { scale = Math.min(Z_MAX, Math.max(Z_MIN, scale * factor)); apply(); }
    function resetView() { scale = 1; tx = 0; ty = 0; apply(); }
    board.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      zoomBy(ev.deltaY < 0 ? 1.1 : 0.9);
    }, { passive: false });
    board.addEventListener("mousedown", (ev) => { drag = { x: ev.clientX - tx, y: ev.clientY - ty }; });
    window.addEventListener("mousemove", (ev) => { if (drag) { tx = ev.clientX - drag.x; ty = ev.clientY - drag.y; apply(); } });
    window.addEventListener("mouseup", () => { drag = null; });

    const ctrls = el("div", { class: "graph-ctrls" }, [
      ctrlBtn("+", t("zoom in"), () => zoomBy(1.25)),
      ctrlBtn("−", t("zoom out"), () => zoomBy(0.8)),
      ctrlBtn("⤢", t("reset view"), resetView),
    ]);
    root.appendChild(graphLegend());
    root.appendChild(el("div", { class: "graph-wrap" }, [board, ctrls]));
    applyFilter(filterQuery);
  }

  function graphLegend() {
    const items = LAYERS.map((L) =>
      el("span", { class: "leg" }, [el("i", { class: "swatch " + L }), L]));
    return el("div", { class: "legend" },
      [el("span", { class: "muted" }, t("drag to pan · scroll to zoom · hover to trace links · click a node for details")), ...items]);
  }

  // Analysis queue view.
  async function controlPost(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Mainframe-Token": window.HUB_CONTROL_TOKEN || "" },
      body: JSON.stringify(payload || {}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "request failed");
    await refreshData(true);
  }

  function actionButton(label, action, tone) {
    const button = el("button", { type: "button", class: "control-button " + (tone || "") }, label);
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await action(); }
      catch (error) { button.title = String(error); }
      finally { if (button.isConnected) button.disabled = false; }
    });
    return button;
  }

  function renderControl(root) {
    const control = D.control || { providers: {}, jobs: [] };
    const jobs = control.jobs || [];
    const countStatus = (name) => (control.counts || {})[name]
      || jobs.filter((job) => job.status === name).length;
    root.appendChild(explain(t("Queue operations are local, bounded, and review-only.")));
    root.appendChild(statRow([
      [num(countStatus("queued")), t("Queued")],
      [num(countStatus("running")), t("Running")],
      [num(countStatus("completed")), t("Completed")],
      [num(countStatus("retryable")), t("Needs retry")],
    ]));
    const subagent = control.subagent_analysis || {};
    root.appendChild(section(t("Codex subagent reviews"), "dev",
      Object.values(subagent).reduce((sum, value) => sum + Number(value || 0), 0),
      statRow([
        [num(subagent.pending || 0), t("Waiting")],
        [num(subagent.processing || 0), t("Processing")],
        [num(subagent.completed || 0), t("Reviewed")],
        [num(subagent.blocked || 0), t("Blocked after retries")],
      ])));
    const launch = el("div", { class: "control-launch" }, [
      actionButton(t("Run Spark"), () => controlPost("/api/jobs", { provider: "spark", adapter: "claude-code" })),
      actionButton(t("Run Spark"), () => controlPost("/api/jobs", { provider: "spark", adapter: "codex" })),
      actionButton(t("Run Antigravity"), () => controlPost("/api/jobs", { provider: "antigravity", adapter: "claude-code" }), "accent"),
    ]);
    launch.children[0].appendChild(el("span", { class: "button-detail" }, "Claude Code"));
    launch.children[1].appendChild(el("span", { class: "button-detail" }, "Codex"));
    launch.children[2].appendChild(el("span", { class: "button-detail" }, "Claude Code"));
    root.appendChild(section(t("Analysis queue"), "dev", 3, launch));

    const providerStatus = control.provider_status || {};
    const providerCards = Object.entries(control.providers || {}).map(([provider, enabled]) => {
      const readiness = providerStatus[provider] || { state: "checking", detail: "" };
      return el("article", { class: "provider-card" }, [
        el("div", { class: "provider-copy" }, [
          el("div", { class: "provider-title" }, [
            el("strong", { class: "mono" }, provider),
            badge(enabled ? t("Enabled") : t("Paused"), enabled ? "user" : "muted"),
            badge(t(readiness.state), readiness.state),
          ]),
          el("span", { class: "provider-detail" }, t(readiness.detail || "")),
        ]),
        actionButton(enabled ? t("Pause") : t("Resume"),
          () => controlPost("/api/providers/" + provider, { enabled: !enabled })),
      ]);
    });
    root.appendChild(section(t("Providers"), "config", providerCards.length,
      el("div", { class: "provider-grid" }, providerCards)));

    const analyses = D.analyses || [];
    if (analyses.length) {
      root.appendChild(section(t("Analysis reports"), "dev", analyses.length,
        el("div", { class: "report-list" }, analyses.map((report) =>
          el("article", { class: "report-card" }, [
            el("div", { class: "card-head" }, [
              el("strong", { class: "mono" }, report.producer),
              badge(report.adapter_id, "dev"),
              report.finding_count ? badge(num(report.finding_count) + " " + t("findings"), "muted") : null,
            ]),
            el("div", { class: "report-meta mono" }, [
              report.model + " · " + report.effort + " · " + fmtStamp(report.generated_at),
            ]),
            report.summary
              ? el("p", { class: "card-desc" }, report.summary)
              : el("p", { class: "card-desc muted" }, t("No plain-language summary was stored.")),
            report.findings && report.findings.length
              ? el("ul", { class: "report-findings" }, report.findings.map((finding) =>
                  el("li", null, finding)))
              : null,
            el("div", { class: "report-path mono dim" }, report.artifact),
          ])))));
    } else {
      root.appendChild(emptyState(t("No Spark or Gemini reports have been stored yet.")));
    }

    if (!jobs.length) {
      root.appendChild(el("div", { class: "notice" }, t("No analysis jobs yet.")));
      return;
    }
    const rows = jobs.map((job) => {
      const actions = [];
      if (["retryable", "failed", "cancelled"].includes(job.status)) {
        actions.push(actionButton(t("Retry"), () => controlPost("/api/jobs/" + job.id + "/retry", {})));
      } else if (job.status === "queued") {
        actions.push(actionButton(t("Cancel"), () => controlPost("/api/jobs/" + job.id + "/cancel", {}), "danger"));
      }
      return el("tr", null, [
        el("td", { class: "mono" }, job.provider),
        el("td", null, job.adapter),
        el("td", null, badge(t(job.status), job.status)),
        el("td", { class: "num" }, num(job.attempts)),
        el("td", { class: "mono dim" }, fmtStamp(job.updated_at)),
        el("td", { class: "job-detail" }, job.detail || ""),
        el("td", { class: "job-actions" }, actions),
      ]);
    });
    root.appendChild(section(t("Recent jobs"), "dev", jobs.length, table([
      [t("Provider")], [t("Adapter")], [t("Status")], [t("Attempts"), true],
      [t("Updated")], [t("Detail")], [t("Actions")],
    ], rows)));
  }

  // Tab shell, language and background refresh.
  const VIEWS = [
    { id: "overview", label: "Overview", short: "OV", render: renderOverview },
    { id: "dev", label: "Telemetry", short: "TL", render: renderCollection },
    { id: "usage", label: "Usage", short: "US", render: renderUsage },
    { id: "analysis", label: "Analysis", short: "AN", render: renderControl },
    { id: "catalog", label: "Components", short: "CP", render: renderCatalog, divider: true },
    { id: "hooks", label: "Hooks", short: "HK", render: renderHooks },
    { id: "config", label: "Configuration", short: "CF", render: renderConfig },
    { id: "health", label: "Health", short: "HL", render: renderHealth },
    { id: "graph", label: "Map", short: "MP", render: renderGraph },
  ];

  const panes = {};
  const dynamicViewIds = new Set(["overview", "dev", "usage", "analysis"]);
  const dirtyViews = new Set();
  let currentViewId = null;
  let refreshInFlight = false;
  let lastInteractionAt = 0;

  function renderPane(view) {
    const pane = panes[view.id] && panes[view.id].pane;
    if (!pane) return;
    pane.replaceChildren();
    try {
      view.render(pane);
    } catch (err) {
      pane.appendChild(el("div", { class: "notice" }, f("This view failed to render: {error}", { error: err })));
    }
  }

  VIEWS.forEach((v) => {
    if (v.divider) tabsNav.appendChild(el("div", { class: "nav-label nav-label-inline" }, t("System")));
    const btn = el("button", { type: "button", role: "tab", "aria-controls": "view-" + v.id,
      "aria-selected": "false", class: v.divider ? "tab-divider" : "",
      "data-short": v.short }, [el("span", { class: "tab-code", "aria-hidden": "true" }, v.short),
      el("span", { class: "tab-label" }, t(v.label))]);
    btn.addEventListener("click", () => show(v.id));
    btn.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const current = VIEWS.indexOf(v);
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = VIEWS[(current + delta + VIEWS.length) % VIEWS.length];
      show(next.id);
      next.btn.focus();
    });
    v.btn = btn;
    tabsNav.appendChild(btn);
    const pane = el("div", { class: "view", id: "view-" + v.id, role: "tabpanel" });
    app.appendChild(pane);
    panes[v.id] = { pane, btn };
    renderPane(v);
  });

  const topbar = document.querySelector(".topbar");
  let search = null;
  if (topbar) {
    search = el("input", { class: "search", type: "search",
      placeholder: t("filter skills, agents, hooks…"), autocomplete: "off" });
    search.addEventListener("input", () => applyFilter(search.value));
    const tools = topbar.querySelector(".toptools") || topbar;
    const languageSelect = el("select", { class: "language-select", "aria-label": t("Language") }, [
      el("option", { value: "en" }, "English"), el("option", { value: "ru" }, "Русский"),
    ]);
    languageSelect.value = language;
    languageSelect.addEventListener("change", () => {
      try { window.localStorage.setItem("mainframe-language", languageSelect.value); } catch (_err) { /* optional */ }
      window.location.reload();
    });
    tools.appendChild(languageSelect);
    const periodSelect = el("select", { class: "period-select", "aria-label": t("Period") }, [
      el("option", { value: "all" }, t("All time")),
      el("option", { value: "1" }, t("Last 24 hours")),
      el("option", { value: "7" }, t("Last 7 days")),
      el("option", { value: "30" }, t("Last 30 days")),
      el("option", { value: "custom" }, t("Custom range")),
    ]);
    periodSelect.value = ["all", "1", "7", "30", "custom"].includes(periodPreset)
      ? periodPreset : "all";
    const fromInput = el("input", { class: "period-date", type: "date", "aria-label": t("From") });
    const toInput = el("input", { class: "period-date", type: "date", "aria-label": t("To") });
    fromInput.value = customFrom;
    toInput.value = customTo;
    const syncPeriodInputs = () => {
      const custom = periodSelect.value === "custom";
      fromInput.hidden = !custom;
      toInput.hidden = !custom;
    };
    const applyPeriod = () => {
      periodPreset = periodSelect.value;
      customFrom = fromInput.value;
      customTo = toInput.value;
      const invalid = periodPreset === "custom" && customFrom && customTo
        && customFrom > customTo;
      toInput.setCustomValidity(invalid ? t("Start date must not be after end date.") : "");
      if (invalid) {
        toInput.reportValidity();
        return;
      }
      try {
        window.localStorage.setItem("mainframe-period", periodPreset);
        window.localStorage.setItem("mainframe-period-from", customFrom);
        window.localStorage.setItem("mainframe-period-to", customTo);
      } catch (_err) { /* local state is optional */ }
      syncPeriodInputs();
      refreshData(true);
    };
    periodSelect.addEventListener("change", applyPeriod);
    fromInput.addEventListener("change", applyPeriod);
    toInput.addEventListener("change", applyPeriod);
    syncPeriodInputs();
    tools.appendChild(periodSelect);
    tools.appendChild(fromInput);
    tools.appendChild(toInput);
    const stamp = tools.querySelector(".stamp");
    tools.insertBefore(search, stamp || null);
    // anchor the fixed drawer just under the (sticky) topbar, measured not guessed
    const top = topbar.offsetHeight || 49;
    detail.style.top = top + "px";
    detail.style.height = "calc(100vh - " + top + "px)";
  }

  function show(id) {
    const activeView = VIEWS.find((v) => v.id === id);
    if (activeView && dirtyViews.has(id)) {
      renderPane(activeView);
      dirtyViews.delete(id);
    }
    currentViewId = id;
    VIEWS.forEach((v) => {
      const on = v.id === id;
      panes[v.id].pane.classList.toggle("active", on);
      panes[v.id].btn.classList.toggle("active", on);
      panes[v.id].btn.setAttribute("aria-selected", on ? "true" : "false");
      panes[v.id].btn.tabIndex = on ? 0 : -1;
    });
    const activeName = document.getElementById("active-view-name");
    if (activeName && activeView) activeName.textContent = t(activeView.label);
    if (activeView) document.title = t(activeView.label) + " · " + t("MAINFRAME hub");
    if (search) search.hidden = id !== "catalog" && id !== "graph";
    try { window.sessionStorage.setItem("mainframe-hub-view", id); } catch (_err) { /* file:// origins */ }
  }

  let initialView = "overview";
  try {
    const saved = window.sessionStorage.getItem("mainframe-hub-view");
    if (VIEWS.some((view) => view.id === saved)) initialView = saved;
  } catch (_err) { /* session state is optional */ }
  show(initialView);

  document.documentElement.lang = language;
  const navLabel = document.querySelector(".sidebar > .nav-label");
  const brandSub = document.querySelector(".brand-sub");
  const privacy = document.querySelector(".privacy-note");
  if (navLabel) navLabel.textContent = t("Observe");
  if (brandSub) brandSub.textContent = t("local observatory");
  if (privacy) privacy.textContent = t("Local data only");

  // A background refresh must never move the ground under the reader. It waits
  // while a control has focus, the drawer is open, a filter is active, or the
  // pointer/keyboard was used a moment ago — but scroll position alone no longer
  // blocks it forever; the position is restored around the re-render instead.
  function userIsBusy() {
    const active = document.activeElement;
    const editing = active && ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(active.tagName);
    return Boolean(editing) || !detail.hidden || Boolean(filterQuery)
      || Date.now() - lastInteractionAt < 1500;
  }

  function applyCurrentData(force) {
    if (!currentViewId || !dirtyViews.has(currentViewId)) return;
    if (!force && userIsBusy()) return;
    const view = VIEWS.find((item) => item.id === currentViewId);
    if (!view) return;
    const scrollTop = window.scrollY;
    renderPane(view);
    dirtyViews.delete(currentViewId);
    if (scrollTop > 0) window.requestAnimationFrame(() => window.scrollTo(0, scrollTop));
  }

  async function refreshData(forceApply) {
    if (!window.HUB_LIVE || refreshInFlight) return;
    refreshInFlight = true;
    try {
      const response = await fetch("/api/live" + periodQuery(), { cache: "no-store" });
      if (!response.ok) throw new Error("live refresh failed");
      const update = await response.json();
      D = Object.assign({}, D, update);
      dynamicViewIds.forEach((id) => dirtyViews.add(id));
      applyCurrentData(Boolean(forceApply));
    } catch (_error) {
      // The current snapshot stays usable. A later poll retries without
      // injecting errors into the page or interrupting navigation.
    } finally {
      refreshInFlight = false;
    }
  }

  ["pointerdown", "keydown", "input"].forEach((eventName) => {
    window.addEventListener(eventName, () => { lastInteractionAt = Date.now(); }, { passive: true });
  });

  if (window.HUB_AUTO_REFRESH_MS >= 2000 && window.HUB_LIVE) {
    window.setInterval(() => { refreshData(false); }, window.HUB_AUTO_REFRESH_MS);
  }
  if (window.HUB_LIVE && periodPreset !== "all") refreshData(true);
})();
