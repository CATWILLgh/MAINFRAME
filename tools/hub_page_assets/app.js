"use strict";
// HUB_DATA is injected by build_hub_page.py (the inlined manifest). All views
// build the DOM from data via textContent — never innerHTML — so artifact
// descriptions containing < > or quotes cannot break or inject markup.
(function () {
  const D = window.HUB_DATA;
  const LANGUAGES = ["en", "ru"];
  const RU = {
    "Overview": "Обзор", "Telemetry": "Телеметрия", "Usage": "Расход",
    "Analysis": "Анализ", "Components": "Компоненты", "Hooks": "Хуки",
    "Configuration": "Настройки", "Health": "Состояние", "Map": "Карта",
    "Observe": "Наблюдение", "System": "Система", "local observatory": "локальная обсерватория",
    "Local data only": "Только локальные данные", "Analysis queue": "Очередь анализа",
    "Providers": "Провайдеры", "Recent jobs": "Последние задания",
    "Provider": "Провайдер", "Adapter": "Адаптор", "Status": "Статус",
    "Attempts": "Попытки", "Updated": "Обновлено", "Detail": "Детали", "Actions": "Действия",
    "Run Spark": "Запустить Spark", "Run Antigravity": "Запустить Antigravity",
    "Enabled": "Включён", "Paused": "На паузе", "Pause": "Пауза",
    "Resume": "Продолжить", "Retry": "Повторить", "Cancel": "Отменить",
    "Queued": "В очереди", "Running": "В работе", "Completed": "Обработано",
    "Needs retry": "Нужен повтор", "queued": "в очереди", "running": "в работе",
    "completed": "обработано", "retryable": "нужен повтор", "failed": "ошибка",
    "cancelled": "отменено",
    "No analysis jobs yet.": "Заданий анализа пока нет.",
    "Queue operations are local, bounded, and review-only.": "Операции очереди локальны, ограничены и требуют проверки.",
    "English": "English", "Русский": "Русский",
  };
  let language = "en";
  try {
    const saved = window.localStorage.getItem("mainframe-language");
    language = LANGUAGES.includes(saved)
      ? saved
      : ((navigator.language || "").toLowerCase().startsWith("ru") ? "ru" : "en");
  } catch (_err) { /* optional browser storage */ }
  const tr = (text) => language === "ru" ? (RU[text] || text) : text;
  const app = document.getElementById("app");
  const tabsNav = document.getElementById("tabs");
  if (!app) return;
  if (!D || !tabsNav) {
    // Never fail silently to a blank page: a visible message beats a white screen
    // with no devtools open (this is exactly how the const-not-on-window bug hid).
    app.textContent = "Failed to load hub data — regenerate with "
      + ".venv/bin/python3 tools/build_hub_page.py";
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
        n.appendChild(typeof c === "string" ? document.createTextNode(tr(c)) : c);
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

  // Indexed by name; the clicked node's layer disambiguates a name shared across layers.
  const skillByName = {};
  D.skills.forEach((s) => { skillByName[s.name] = s; });
  const localSkillName = (name) => String(name || "").replace(/^mainframe:/, "");
  const agentByName = {};
  D.agents.forEach((a) => { agentByName[a.name] = a; });
  // reverse edges: who preloads (agent skills:) or references (skill cross-ref) a skill
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
  const catalogCards = [];     // {el, text}
  const catalogSections = [];  // {el, cards:[{el,text}]}
  const graphNodes = [];       // {el, id, text}
  const graphEdges = [];       // {el, ends:[a,b]}

  function applyFilter(raw) {
    const q = (raw || "").trim().toLowerCase();
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

  const detailBody = el("div", { class: "dbody" });
  const detailClose = el("button", { type: "button", class: "dclose", "aria-label": "close" }, "×");
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
    if (!s) return el("div", { class: "notice" }, "Unknown skill: " + id);
    return el("div", null, [
      dhead(s.name, s.dev ? "dev" : "skill", s.dev ? "dev" : "skills"),
      el("p", { class: "muted small" }, s.user_invocable ? "user-invocable: /" + s.name : "auto-triggered (not user-invocable)"),
      el("p", { class: "card-desc" }, s.description),
      s.when_to_use ? el("p", { class: "card-when" }, [el("b", null, "when: "), s.when_to_use]) : null,
      dsec("cross-refs", (s.crossrefs || []).map((r) => linkChip(r, "skills", r))),
      dsec("referenced / preloaded by", (referencedBy[s.name] || []).map((p) => linkChip(p.name, p.layer, p.name))),
    ]);
  }

  function agentDetail(id) {
    const a = agentByName[id];
    if (!a) return el("div", { class: "notice" }, "Unknown agent: " + id);
    return el("div", null, [
      dhead(a.name, a.model || "agent", "agents"),
      el("p", { class: "card-desc" }, a.description),
      a.tools ? el("p", { class: "card-when" }, [el("b", null, "tools: "), String(a.tools)]) : null,
      dsec("preloads skills", (a.skills || []).map((sk) => linkChip(sk, "skills", localSkillName(sk)))),
    ]);
  }

  function hookDetail(id) {
    const hs = hooksByScript[id] || [];
    const purpose = (hs[0] && hs[0].purpose) || "";
    const events = [];
    const seen = new Set();
    hs.forEach((h) => { if (!seen.has(h.event)) { seen.add(h.event); events.push(linkChip(h.event, "events", h.event)); } });
    return el("div", null, [
      dhead(id, "hook", "hooks"),
      purpose ? el("p", { class: "card-desc" }, purpose) : el("p", { class: "muted small" }, "(no docstring purpose)"),
      dsec("fires on", events),
    ]);
  }

  function eventDetail(id) {
    const hs = hooksByEvent[id] || [];
    const rows = hs.map((h) => el("tr", null, [
      el("td", { class: "mono dim" }, h.matcher || "*"),
      el("td", null, linkChip(h.script, "hooks", h.script)),
    ]));
    return el("div", null, [
      dhead(id, "event", "events"),
      el("p", { class: "muted small" }, hs.length + " hook" + (hs.length === 1 ? "" : "s") + " fire on this event."),
      el("table", { class: "matrix" }, [el("tbody", null, rows)]),
    ]);
  }

  function skillCard(s) {
    const badges = el("div", { class: "badges" }, [
      badge(s.dev ? "dev" : "skill", s.dev ? "dev" : "skills"),
      badge(s.user_invocable ? "/" + s.name : "auto",
            s.user_invocable ? "user" : "muted"),
    ]);
    return el("article", { class: "card clickable" }, [
      el("div", { class: "card-head" }, [el("span", { class: "card-name" }, s.name), badges]),
      el("p", { class: "card-desc" }, s.description),
      s.when_to_use && el("p", { class: "card-when" }, [el("b", null, "when: "), s.when_to_use]),
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
        [el("b", null, "preloads: "), chips]) : null,
    ]);
  }

  function section(title, cls, count, body) {
    return el("section", null, [
      el("h2", { class: "layer-h " + cls }, title + " (" + count + ")"),
      body,
    ]);
  }

  function cardText(it) {
    return (it.name + " " + (it.description || "") + " " + (it.when_to_use || "")
            + " " + ((it.skills || []).join(" "))).toLowerCase();
  }

  function renderCatalog(root) {
    const skills = D.skills.filter((s) => !s.dev);
    const devSkills = D.skills.filter((s) => s.dev);
    const groups = [
      ["Skills", "skills", skills, skillCard, "skills"],
      ["Agents", "agents", D.agents, agentCard, "agents"],
      ["Dev skills", "dev", devSkills, skillCard, "dev"],
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
  }

  function renderHooks(root) {
    const byEvent = {};
    D.hooks.forEach((h) => (byEvent[h.event] || (byEvent[h.event] = [])).push(h));
    root.appendChild(el("p", { class: "muted" },
      "Every hook the plugin registers, grouped by the event that fires it."));
    Object.keys(byEvent).sort().forEach((ev) => {
      const rows = byEvent[ev].map((h) => el("tr", null, [
        el("td", { class: "mono dim" }, h.matcher || "*"),
        el("td", { class: "mono" }, h.script),
        el("td", null, h.purpose || ""),
      ]));
      const table = el("table", { class: "matrix" }, [
        el("thead", null, el("tr", null, [
          el("th", null, "matcher"), el("th", null, "script"), el("th", null, "purpose")])),
        el("tbody", null, rows),
      ]);
      root.appendChild(section(ev, "hooks", byEvent[ev].length, table));
    });
  }

  function barList(rows) {
    const max = rows.reduce((m, r) => Math.max(m, r[1]), 0) || 1;
    return el("div", { class: "bars" }, rows.map(([label, n]) =>
      el("div", { class: "bar-row" }, [
        el("span", { class: "bar-label mono" }, String(label)),
        el("span", { class: "bar-track" },
          el("span", { class: "bar-fill", style: "width:" + Math.max(2, Math.round(100 * n / max)) + "%" })),
        el("span", { class: "bar-num" }, String(n)),
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

  function emptyState(text) {
    return el("p", { class: "empty-state" }, text);
  }

  function signalChart(rows, unit) {
    const shown = (rows || []).slice(-21);
    if (!shown.length) return emptyState("No activity is available yet.");
    const max = shown.reduce((m, row) => Math.max(m, row[1]), 0) || 1;
    return el("div", { class: "signal-chart", role: "img",
      "aria-label": (unit || "Activity") + " over the latest recorded days" }, shown.map((row) => {
      const pct = Math.max(4, Math.round(100 * row[1] / max));
      return el("div", { class: "signal-column", title: row[0] + " · " + row[1] + " " + (unit || "events") }, [
        el("span", { class: "signal-value", style: "height:" + pct + "%" }),
        el("span", { class: "signal-date" }, row[0].slice(5)),
      ]);
    }));
  }

  function shareRows(rows, total, tone) {
    if (!rows.length) return emptyState("No split is available yet.");
    const observed = rows.reduce((sum, row) => sum + row[1], 0);
    if (!observed) return emptyState("No split is available yet.");
    const base = total || observed;
    return el("div", { class: "share-list " + (tone || "") }, rows.map(([label, value]) => {
      const pct = Math.max(2, Math.round(100 * value / base));
      return el("div", { class: "share-row" }, [
        el("div", { class: "share-copy" }, [
          el("span", { class: "mono" }, String(label)),
          el("span", null, value.toLocaleString() + " · " + pct + "%"),
        ]),
        el("span", { class: "share-track" },
          el("span", { class: "share-fill", style: "width:" + pct + "%" })),
      ]);
    }));
  }

  function renderOverview(root) {
    const ds = D.dev_state || { active: false, feedback: [] };
    const t = ds.telemetry || {};
    const u = D.usage || {};
    const h = D.health || { dangling: [], missing_scripts: [], orphans: [] };
    const unknownKinds = (t.unknown_events || []).length;
    const unknownRecords = (t.unknown_events || []).reduce(
      (sum, row) => sum + Number(row[1] || 0), 0);
    const dataIssueRecords = (t.invalid_rows || 0) + (t.legacy_rows || 0)
      + (t.excluded_records || 0) + unknownRecords;
    const dataIssueKinds = Number(Boolean(t.invalid_rows))
      + Number(Boolean(t.legacy_rows)) + Number(Boolean(t.excluded_records))
      + Number(Boolean(unknownKinds));
    const repoIssues = (h.dangling || []).length + (h.missing_scripts || []).length;
    const unmatched = (t.agent_lifecycle || []).reduce((sum, row) => sum + (row.unmatched || 0), 0);
    const hookRows = t.hook_effectiveness || [];
    const hookGap = hookRows.reduce((sum, row) =>
      sum + Math.max(0, (row.blocked || 0) - (row.resolved || 0)), 0);
    const feedback = (ds.feedback || []).length;
    const attentionCount = dataIssueKinds + repoIssues + unmatched + hookGap + feedback;
    const healthy = ds.active && attentionCount === 0;
    const statusLabel = !ds.active ? "Waiting for telemetry" : healthy ? "Signals are clean" : "Review recommended";
    const statusTone = !ds.active ? "idle" : healthy ? "good" : "warn";

    root.appendChild(el("header", { class: "overview-hero " + statusTone }, [
      el("div", { class: "overview-status " + statusTone }, [
        el("span", { class: "status-light", "aria-hidden": "true" }),
        el("div", null, [
          el("span", { class: "eyebrow" }, "SYSTEM STATUS"),
          el("strong", null, statusLabel),
          el("span", null, ds.active && t.generated_at
            ? "snapshot " + t.generated_at : "no validated event snapshot yet"),
        ]),
      ]),
      el("div", { class: "overview-intro" }, [
        el("h1", null, "Agent system overview"),
        el("p", null, "Activity, cost, routing and quality signals. Start with attention; drill into evidence only when needed."),
      ]),
      el("div", { class: "attention-total " + statusTone }, [
        el("span", null, "OPEN SIGNALS"),
        el("strong", null, attentionCount.toLocaleString()),
        el("small", null, attentionCount ? "worth reviewing" : "nothing actionable"),
      ]),
    ]));

    root.appendChild(el("div", { class: "overview-metrics" }, [
      overviewMetric("Claude sessions", (u.sessions || 0).toLocaleString(), "from local transcripts"),
      overviewMetric("Assistant replies", (u.messages || 0).toLocaleString(), "deduplicated turns"),
      overviewMetric("Tokens", fmtTok(u.tokens && u.tokens.total), "input + output", "usage-tone"),
      overviewMetric("Telemetry events", (t.usable_records || 0).toLocaleString(), "validated only", "event-tone"),
      overviewMetric("Agent instances", (t.agent_instances || 0).toLocaleString(), "observed subagents", "agent-tone"),
      overviewMetric("Active days", (u.active_days || 0).toLocaleString(), (u.current_streak || 0) + " day current streak"),
    ]));

    const telemetryDays = t.by_day || [];
    const usageDays = u.by_day || [];
    const activityRows = telemetryDays.length > 1 ? telemetryDays : usageDays;
    const activityUnit = telemetryDays.length > 1 ? "events" : "assistant replies";
    const activityTitle = telemetryDays.length > 1 ? "Telemetry signal" : "Work rhythm";
    const activityBody = el("div", null, [
      signalChart(activityRows, activityUnit),
      el("div", { class: "panel-foot" }, [
        el("span", null, activityRows.length.toLocaleString() + " active days in view"),
        el("span", null, telemetryDays.length > 1
          ? (t.usable_records || 0).toLocaleString() + " validated events"
          : (u.messages || 0).toLocaleString() + " total replies"),
      ]),
    ]);

    const concerns = [];
    if (!ds.active) concerns.push(["Telemetry", "No validated events yet", "idle"]);
    if (dataIssueRecords) concerns.push(["Data quality", dataIssueRecords + " excluded, invalid, legacy or unknown records", "warn"]);
    if (repoIssues) concerns.push(["Delivery health", repoIssues + " broken references or missing scripts", "warn"]);
    if (unmatched) concerns.push(["Agent lifecycle", unmatched + " unmatched start/stop signals", "warn"]);
    if (hookGap) {
      concerns.push(["Quality hooks", hookGap + " more block signals than confirmed resolutions", "warn"]);
      hookRows.map((row) => ({
        name: row.rule_id || row.hook || "unknown hook",
        gap: Math.max(0, (row.blocked || 0) - (row.resolved || 0)),
        blocked: row.blocked || 0,
        resolved: row.resolved || 0,
      })).filter((row) => row.gap > 0).sort((a, b) => b.gap - a.gap).slice(0, 3)
        .forEach((row) => {
          const plainRule = String(row.name).replace(/\.py$/, "").replace(/[-_]+/g, " ");
          concerns.push([
            plainRule.charAt(0).toUpperCase() + plainRule.slice(1),
            row.blocked + " blocked · " + row.resolved + " confirmed resolved",
            "warn",
          ]);
        });
    }
    if (feedback) concerns.push(["Feedback queue", feedback + " item" + (feedback === 1 ? "" : "s") + " waiting", "idle"]);
    if (!concerns.length) concerns.push(["Current snapshot", "No actionable signal is visible", "good"]);
    const attentionBody = el("div", { class: "attention-list" }, concerns.map((item) =>
      el("div", { class: "attention-row " + item[2] }, [
        el("span", { class: "attention-mark", "aria-hidden": "true" }),
        el("div", null, [el("strong", null, item[0]), el("span", null, item[1])]),
      ])));

    const integrityBody = el("div", { class: "integrity-grid" }, [
      overviewMetric("Skills", D.skills.length.toLocaleString(), "delivered knowledge"),
      overviewMetric("Agents", D.agents.length.toLocaleString(), "specialized profiles", "agent-tone"),
      overviewMetric("Hooks", D.hooks.length.toLocaleString(), "registered checks", "event-tone"),
      overviewMetric("Broken links", repoIssues.toLocaleString(), repoIssues ? "needs attention" : "delivery resolves",
        repoIssues ? "warn" : "good"),
      overviewMetric("Connections", (D.edges || []).length.toLocaleString(), "mapped relationships"),
      overviewMetric("Dev skills", D.skills.filter((skill) => skill.dev).length.toLocaleString(), "development only", "usage-tone"),
    ]);

    const sp = u.split || { main: {}, sub: {} };
    const scopeRows = [
      ["main window", (sp.main && sp.main.messages) || 0],
      ["subagents", (sp.sub && sp.sub.messages) || 0],
    ];
    const agentRows = (t.by_agent || []).slice(0, 7);
    const agentBody = el("div", { class: "panel-stack" }, [
      el("div", null, [
        el("h3", null, "Reply split"),
        shareRows(scopeRows, (u.messages || 0), "agent-share"),
      ]),
      el("div", null, [
        el("h3", null, "Telemetry by agent"),
        shareRows(agentRows, null, "agent-share"),
      ]),
    ]);

    const models = (u.models || []).filter((m) => m.total > 0).slice(0, 6);
    const modelBody = shareRows(models.map((m) => [m.model, m.total]),
      u.tokens && u.tokens.total, "usage-share");

    const hookTotals = hookRows.reduce((sum, row) => {
      ["noted", "asked", "blocked", "resolved", "context_chars"].forEach((key) => {
        sum[key] += row[key] || 0;
      });
      return sum;
    }, { noted: 0, asked: 0, blocked: 0, resolved: 0, context_chars: 0 });
    const hookBody = el("div", null, [
      el("div", { class: "outcome-strip" }, [
        overviewMetric("Noted", hookTotals.noted.toLocaleString(), "soft signal"),
        overviewMetric("Asked", hookTotals.asked.toLocaleString(), "permission gate"),
        overviewMetric("Blocked", hookTotals.blocked.toLocaleString(), "hard stop", "warn"),
        overviewMetric("Resolved", hookTotals.resolved.toLocaleString(), "confirmed fix", "good"),
      ]),
      el("p", { class: "panel-foot single" }, fmtTok(hookTotals.context_chars) + " characters added to model context"),
    ]);

    const recent = (t.recent_events || []).slice(0, 8);
    const recentBody = recent.length ? el("ol", { class: "event-stream" }, recent.map((item) =>
      el("li", null, [
        el("span", { class: "event-time mono" }, (item.timestamp || "").replace("T", " ").slice(5, 16)),
        el("span", { class: "event-name mono" }, item.event),
        el("span", { class: "event-owner" }, item.agent_type || "main context"),
        el("span", { class: "event-project mono" }, item.project || "—"),
      ]))) : emptyState("No validated event stream is available yet.");

    root.appendChild(el("div", { class: "overview-grid" }, [
      overviewPanel("LATEST 21 DAYS", activityTitle, activityBody, "signal-panel"),
      overviewPanel("ATTENTION", "What deserves a look", attentionBody, "attention-panel"),
      overviewPanel("SYSTEM", "Delivered shape", integrityBody, "integrity-panel"),
      overviewPanel("ROUTING", "Where the work happens", agentBody, "agent-panel"),
      overviewPanel("MODELS", "Token distribution", modelBody, "model-panel"),
      overviewPanel("QUALITY HOOKS", "Outcomes, not just triggers", hookBody, "hook-panel"),
      overviewPanel("LATEST", "Recent validated events", recentBody, "panel-full stream-panel"),
    ]));

    if (u.active && u.by_day && u.by_day.length) {
      root.appendChild(overviewPanel("365 DAY CONTEXT", "Work rhythm", usageHeatmap(u.by_day), "calendar-panel"));
    }
    root.appendChild(el("p", { class: "overview-caveat" },
      "This page measures coverage, activity and context cost. It does not claim that the product itself is correct."));
  }

  function renderDev(root) {
    const ds = D.dev_state;
    const t = ds.telemetry;
    if (!ds.active) {
      root.appendChild(el("div", { class: "notice" },
        "No telemetry recorded yet — either dev mode is not installed, or no "
        + "sessions have run since it was. Enable the intended adapter with "
        + "./install.sh --claude --dev or ./install.sh --codex --dev; "
        + "data appears here after a few sessions."));
      if (t && t.error) root.appendChild(el("div", { class: "notice" }, "Telemetry read error: " + t.error));
      return;
    }
    root.appendChild(el("p", { class: "muted" },
      "Validated telemetry snapshot generated " + t.generated_at + ". Rebuild hub.html to refresh it; "
      + "machine readers use tools/telemetry_data.py over the same event stream."));
    root.appendChild(el("div", { class: "stat-row wrap" }, [
      el("div", { class: "stat" }, [el("b", null, String(t.usable_records)), " usable events"]),
      el("div", { class: "stat" }, [el("b", null, String(t.records)), " stored rows"]),
      el("div", { class: "stat" }, [el("b", null, String(t.sessions)), " sessions"]),
      el("div", { class: "stat" }, [el("b", null, String(t.agent_instances)), " agent instances"]),
      el("div", { class: "stat" }, [el("b", null, String(t.invalid_rows)), " invalid rows"]),
      el("div", { class: "stat" }, [el("b", null, String(ds.feedback.length)), " feedback queued"]),
    ]));

    const usage = t.token_usage || {};
    const harnessCost = t.harness_context_cost || {};
    root.appendChild(section("Context cost ledger", "usage", 2,
      el("div", { class: "panel-stack" }, [
        el("div", { class: "stat-row wrap" }, [
          el("div", { class: "stat" }, [
            el("b", null, fmtTok(usage.total_tokens || 0)), " exact runtime tokens",
          ]),
          el("div", { class: "stat" }, [
            el("b", null, fmtTok(usage.cached_input_tokens || 0)), " cached input tokens",
          ]),
          el("div", { class: "stat" }, [
            el("b", null, fmtTok(harnessCost.characters || 0)), " injected characters",
          ]),
          el("div", { class: "stat" }, [
            el("b", null,
              fmtTok(harnessCost.estimated_tokens_low || 0) + "–"
              + fmtTok(harnessCost.estimated_tokens_high || 0)),
            " estimated injected tokens",
          ]),
        ]),
        el("div", { class: "notice small" },
          "Runtime counters are exact when native usage is available. Injection tokens are a broad "
          + "2–6 characters-per-token estimate. Causal overhead remains unproven until a comparable A/B run."),
      ])));

    if (usage.by_source && usage.by_source.length) {
      const usageRows = usage.by_source.map((item) => el("tr", null, [
        el("td", { class: "mono" }, item.adapter_id || t.adapter_id || "—"),
        el("td", { class: "mono" }, item.source),
        el("td", { class: "num" }, fmtTok(item.input_tokens)),
        el("td", { class: "num" }, fmtTok(item.cached_input_tokens)),
        el("td", { class: "num" }, fmtTok(item.output_tokens)),
        el("td", { class: "num" }, fmtTok(item.reasoning_output_tokens)),
        el("td", { class: "num" }, fmtTok(item.total_tokens)),
      ]));
      root.appendChild(section("Exact usage by source", "usage", usageRows.length,
        el("table", { class: "matrix" }, [
          el("thead", null, el("tr", null, [
            el("th", null, "adapter"), el("th", null, "source"),
            el("th", { class: "num" }, "input"),
            el("th", { class: "num" }, "cached"),
            el("th", { class: "num" }, "output"),
            el("th", { class: "num" }, "reasoning"),
            el("th", { class: "num" }, "total"),
          ])),
          el("tbody", null, usageRows),
        ])));
    }

    if (t.adapters && t.adapters.length) {
      const adapterRows = t.adapters.map((item) => el("tr", null, [
        el("td", { class: "mono" }, item.adapter_label || item.adapter_id),
        el("td", { class: "num" }, String(item.usable_records || 0)),
        el("td", { class: "num" }, String(item.excluded_records || 0)),
        el("td", { class: "num" }, String(item.sessions || 0)),
        el("td", { class: "num" }, item.active ? "active" : "inactive"),
      ]));
      root.appendChild(section("Adapter telemetry", "dev", adapterRows.length,
        el("table", { class: "matrix" }, [
          el("thead", null, el("tr", null, [el("th", null, "adapter"),
            el("th", { class: "num" }, "usable"),
            el("th", { class: "num" }, "excluded"),
            el("th", { class: "num" }, "sessions"),
            el("th", { class: "num" }, "state")])),
          el("tbody", null, adapterRows)])));
    }

    if (t.invalid_rows || t.legacy_rows || t.excluded_records
        || (t.unknown_events && t.unknown_events.length)) {
      const details = [];
      if (t.invalid_rows) details.push(t.invalid_rows + " invalid");
      if (t.legacy_rows) details.push(t.legacy_rows + " legacy");
      if (t.excluded_records) details.push(t.excluded_records + " excluded");
      if (t.unknown_events && t.unknown_events.length) details.push(t.unknown_events.length + " unknown event types");
      root.appendChild(el("div", { class: "notice" },
        "Data health needs attention: " + details.join(", ") + ". New-format rows are validated before display."));
    } else {
      root.appendChild(el("div", { class: "notice ok" },
        "Data health is clean: every current-format row matches the canonical event contract."));
    }

    const rows = t.event_counts.map(([name, n]) => el("tr", null, [
      el("td", { class: "mono" }, name),
      el("td", { class: "num" }, String(n)),
    ]));
    root.appendChild(section("Telemetry events", "events", t.event_counts.length,
      el("table", { class: "matrix" }, [
        el("thead", null, el("tr", null, [el("th", null, "event"), el("th", null, "count")])),
        el("tbody", null, rows)])));

    if (t.by_day && t.by_day.length) {
      root.appendChild(section("Activity by day", "events", t.by_day.length, barList(t.by_day)));
    }
    if (t.by_agent && t.by_agent.length) {
      root.appendChild(section("Events by agent", "agents", t.by_agent.length, barList(t.by_agent)));
    }
    if (t.by_model && t.by_model.length) {
      root.appendChild(section("Runtime model signals", "dev", t.by_model.length, barList(t.by_model)));
    }
    if (t.agent_lifecycle && t.agent_lifecycle.length) {
      const arows = t.agent_lifecycle.map((item) => el("tr", null, [
        el("td", { class: "mono" }, item.adapter_id || t.adapter_id || "—"),
        el("td", { class: "mono" }, item.agent),
        el("td", { class: "num" }, String(item.instances)),
        el("td", { class: "num" }, String(item.started)),
        el("td", { class: "num" }, String(item.stopped)),
        el("td", { class: "num" }, String(item.missing_start || 0)),
        el("td", { class: "num" }, String(item.missing_stop || 0)),
      ]));
      root.appendChild(section("Subagent lifecycle", "agents", arows.length,
        el("table", { class: "matrix" }, [
          el("thead", null, el("tr", null, [el("th", null, "adapter"),
            el("th", null, "agent"),
            el("th", { class: "num" }, "instances"), el("th", { class: "num" }, "started"),
            el("th", { class: "num" }, "stopped"),
            el("th", { class: "num" }, "missing start"),
            el("th", { class: "num" }, "missing stop")])),
          el("tbody", null, arows)])));
    }
    if (t.hook_effectiveness && t.hook_effectiveness.length) {
      const hrows = t.hook_effectiveness.map((item) => el("tr", null, [
        el("td", { class: "mono" }, item.adapter_id || t.adapter_id || "—"),
        el("td", { class: "mono" }, item.hook),
        el("td", { class: "mono" }, item.rule_id),
        el("td", { class: "num" }, String(item.noted)),
        el("td", { class: "num" }, String(item.asked)),
        el("td", { class: "num" }, String(item.blocked)),
        el("td", { class: "num" }, String(item.resolved)),
        el("td", { class: "num" }, String(item.context_chars)),
        el("td", { class: "num" }, String(item.sessions)),
      ]));
      root.appendChild(section("Hook effectiveness", "hooks", hrows.length,
        el("table", { class: "matrix" }, [
          el("thead", null, el("tr", null, [
            el("th", null, "adapter"), el("th", null, "hook"), el("th", null, "rule"),
            el("th", null, "noted"), el("th", null, "asked"),
            el("th", null, "blocked"), el("th", null, "resolved"),
            el("th", null, "context chars"), el("th", null, "sessions"),
          ])),
          el("tbody", null, hrows),
        ])));
    }
    (t.breakdowns || []).forEach((b) => {
      const brows = b.items.map(([v, n]) => el("tr", null, [
        el("td", { class: "mono" }, v), el("td", { class: "num" }, String(n))]));
      root.appendChild(section(b.event + " · by " + b.key, "dev", b.total,
        el("table", { class: "matrix" }, [el("tbody", null, brows)])));
    });

    if (t.recent_events && t.recent_events.length) {
      const rrows = t.recent_events.map((item) => el("tr", null, [
        el("td", { class: "mono" }, item.adapter_id || t.adapter_id || "—"),
        el("td", { class: "mono dim" }, String(item.id)),
        el("td", { class: "mono dim" }, item.timestamp),
        el("td", { class: "mono" }, item.event),
        el("td", { class: "mono" }, item.agent_type || "(main context)"),
        el("td", { class: "mono dim" }, item.project || "—"),
      ]));
      root.appendChild(section("Recent usable event stream", "dev", rrows.length,
        el("table", { class: "matrix" }, [
          el("thead", null, el("tr", null, [el("th", null, "adapter"),
            el("th", null, "id"), el("th", null, "UTC"),
            el("th", null, "event"), el("th", null, "agent"), el("th", null, "project")])),
          el("tbody", null, rrows)])));
    }

    if (ds.feedback.length) {
      root.appendChild(section("Feedback queue", "dev", ds.feedback.length,
        el("ul", { class: "files" }, ds.feedback.map((f) => el("li", { class: "mono" }, f)))));
    }
  }

  function fmtTok(n) {
    n = n || 0;
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
  }

  function fmtHour(h) {
    if (h == null) return "—";
    const ap = h < 12 ? "AM" : "PM";
    return (h % 12 === 0 ? 12 : h % 12) + " " + ap + " UTC";
  }

  function usageHeatmap(byDay) {
    // GitHub-style rolling year: 7 rows (Mon..Sun), one column per week, ending
    // today. by_day rows are [date, messages, tokens]; level scales on messages.
    const map = {};
    byDay.forEach(([d, msgs, tok]) => { map[d] = { msgs: msgs, tok: tok }; });
    const end = new Date();
    end.setUTCHours(0, 0, 0, 0);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 364);
    start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7)); // back to Monday
    // Quantile thresholds over active days, so a single huge day can't wash out
    // a linear scale and low-activity days stay visibly green (n>0 => level>=1).
    const nz = byDay.map((r) => r[1]).filter((n) => n > 0).sort((a, b) => a - b);
    const q = (p) => (nz.length ? nz[Math.min(nz.length - 1, Math.floor(p * nz.length))] : 1);
    const t1 = q(0.25), t2 = q(0.5), t3 = q(0.75);
    const level = (n) => (!n ? 0 : n >= t3 ? 4 : n >= t2 ? 3 : n >= t1 ? 2 : 1);
    const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const cells = [], months = [];
    let i = 0, lastMonth = -1;
    for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
      const iso = d.toISOString().slice(0, 10);
      const e = map[iso] || { msgs: 0, tok: 0 };
      cells.push(el("div", { class: "hm-cell l" + level(e.msgs),
        title: iso + " · " + e.msgs + " msg · " + fmtTok(e.tok) + " tok" }));
      // a month label sits at the column where that month's first Monday lands
      if ((d.getUTCDay() + 6) % 7 === 0 && d.getUTCMonth() !== lastMonth) {
        lastMonth = d.getUTCMonth();
        months.push(el("span", { style: "grid-column-start:" + (Math.floor(i / 7) + 1) }, MON[lastMonth]));
      }
      i++;
    }
    return el("div", { class: "hm-wrap" }, [
      el("div", { class: "hm-months" }, months),
      el("div", { class: "heatmap" }, cells),
    ]);
  }

  function renderUsage(root) {
    const u = D.usage;
    if (!u || !u.active) {
      root.appendChild(el("div", { class: "notice" },
        "No local session transcripts found at ~/.claude/projects — usage stats "
        + "are computed from those (independent of --dev telemetry)."));
      return;
    }
    if (!u.messages) {
      root.appendChild(el("div", { class: "notice" },
        "Transcripts found, but no assistant messages with token usage yet."));
      return;
    }
    root.appendChild(el("p", { class: "muted" },
      "Aggregated from " + u.files + " local session transcripts (~/.claude/projects). "
      + "Counts only — no prompt content is read. Streaming snapshots are de-duplicated "
      + "by message id; main and subagent turns are combined (same runs, same limits) "
      + "— a main/subagent split is below."));

    root.appendChild(el("div", { class: "stat-row wrap" }, [
      el("div", { class: "stat" }, [el("b", null, String(u.sessions)), " sessions"]),
      el("div", { class: "stat" }, [el("b", null, u.messages.toLocaleString()), " assistant replies"]),
      el("div", { class: "stat" }, [el("b", null, fmtTok(u.tokens.total)), " tokens (in+out)"]),
      el("div", { class: "stat" }, [el("b", null, String(u.active_days)), " active days"]),
      el("div", { class: "stat" }, [el("b", null, u.current_streak + "d"), " current streak"]),
      el("div", { class: "stat" }, [el("b", null, u.longest_streak + "d"), " longest streak"]),
      el("div", { class: "stat" }, [el("b", null, fmtHour(u.peak_hour)), " peak hour"]),
      el("div", { class: "stat" }, [el("b", { class: "mono" }, u.favorite_model || "—"), " top model"]),
    ]));

    const tk = u.tokens;
    root.appendChild(el("div", { class: "notice ok small" }, [
      el("b", null, fmtTok(tk["in"])), " in · ", el("b", null, fmtTok(tk.out)), " out · ",
      el("b", null, fmtTok(tk.total)), " total. ",
      el("span", { class: "muted" }, "Cache (excluded from total — the real cost driver): "
        + fmtTok(tk.cache_read) + " read + " + fmtTok(tk.cache_creation) + " write."),
    ]));

    const sp = u.split || { main: {}, sub: {} };
    const splitRow = (label, s) => el("tr", null, [
      el("td", null, label),
      el("td", { class: "num" }, (s.messages || 0).toLocaleString()),
      el("td", { class: "num" }, fmtTok(s["in"])),
      el("td", { class: "num" }, fmtTok(s.out)),
      el("td", { class: "num" }, fmtTok(s.total)),
    ]);
    root.appendChild(section("Main window vs subagents", "usage", 2,
      el("table", { class: "matrix" }, [
        el("thead", null, el("tr", null, [el("th", null, "scope"),
          el("th", { class: "num" }, "messages"), el("th", { class: "num" }, "in"),
          el("th", { class: "num" }, "out"), el("th", { class: "num" }, "total")])),
        el("tbody", null, [splitRow("main window", sp.main), splitRow("subagents", sp.sub)])])));

    const grand = u.tokens.total || 1;
    const shown = u.models.filter((m) => m.total > 0);
    const rows = shown.map((m) => el("tr", null, [
      el("td", { class: "mono" }, m.model),
      el("td", { class: "num" }, fmtTok(m["in"])),
      el("td", { class: "num" }, fmtTok(m.out)),
      el("td", { class: "num" }, fmtTok(m.total)),
      el("td", null, el("div", { class: "share" }, [
        el("span", { class: "bar-track" }, el("span", { class: "bar-fill",
          style: "width:" + Math.max(2, Math.round(100 * m.total / grand)) + "%" })),
        el("span", { class: "share-pct" }, (m.share * 100).toFixed(1) + "%"),
      ])),
    ]));
    root.appendChild(section("Tokens by model", "usage", shown.length,
      el("table", { class: "matrix" }, [
        el("thead", null, el("tr", null, [el("th", null, "model"),
          el("th", { class: "num" }, "in"), el("th", { class: "num" }, "out"),
          el("th", { class: "num" }, "total"), el("th", null, "share")])),
        el("tbody", null, rows)])));

    root.appendChild(section("Activity calendar", "usage", u.active_days,
      usageHeatmap(u.by_day)));

    if (u.by_hour && u.by_hour.some((r) => r[1])) {
      root.appendChild(section("By hour of day (UTC)", "usage", 24,
        barList(u.by_hour.map(([h, n]) => [String(h).padStart(2, "0") + ":00", n]))));
    }

    if (u.no_usage) {
      root.appendChild(el("p", { class: "muted small" },
        u.no_usage.toLocaleString() + " replies had no usage record (counted, no token data)."));
    }
  }

  const LAYERS = ["events", "hooks", "agents", "skills", "dev"];

  function ctrlBtn(label, title, onClick) {
    const b = el("button", { type: "button", title: title }, label);
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return b;
  }

  function renderGraph(root) {
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
    function zoomBy(f) { scale = Math.min(Z_MAX, Math.max(Z_MIN, scale * f)); apply(); }
    function resetView() { scale = 1; tx = 0; ty = 0; apply(); }
    board.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      zoomBy(ev.deltaY < 0 ? 1.1 : 0.9);
    }, { passive: false });
    board.addEventListener("mousedown", (ev) => { drag = { x: ev.clientX - tx, y: ev.clientY - ty }; });
    window.addEventListener("mousemove", (ev) => { if (drag) { tx = ev.clientX - drag.x; ty = ev.clientY - drag.y; apply(); } });
    window.addEventListener("mouseup", () => { drag = null; });

    const ctrls = el("div", { class: "graph-ctrls" }, [
      ctrlBtn("+", "zoom in", () => zoomBy(1.25)),
      ctrlBtn("−", "zoom out", () => zoomBy(0.8)),
      ctrlBtn("⤢", "reset view", resetView),
    ]);
    root.appendChild(graphLegend());
    root.appendChild(el("div", { class: "graph-wrap" }, [board, ctrls]));
  }

  function graphLegend() {
    const items = LAYERS.map((L) =>
      el("span", { class: "leg" }, [el("i", { class: "swatch " + L }), L]));
    return el("div", { class: "legend" },
      [el("span", { class: "muted" }, "drag to pan · scroll to zoom · hover to trace links · click a node for details"), ...items]);
  }

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

    root.appendChild(el("h2", { class: "layer-h config" }, "Permissions"));
    root.appendChild(el("p", { class: "muted" },
      "What the hub lets an agent do silently, ask about, or refuse — default mode: "
      + (cfg.mode || "?") + ". Source: adapters/claude-code/export/settings.json."));
    [["deny", "perm-deny"], ["ask", "perm-ask"], ["allow", "perm-allow"]].forEach(([key, cls]) => {
      const items = perms[key] || [];
      if (!items.length) return;
      const rows = items.map((p) => el("li", { class: "mono perm " + cls }, p));
      root.appendChild(section(key, cls, items.length, el("ul", { class: "permlist" }, rows)));
    });

    const flags = cfg.flags || {};
    const settingsRows = [
      kv("model", flags.model), kv("effortLevel", flags.effortLevel),
      kv("outputStyle", flags.outputStyle),
      kv("language", flags.language), kv("defaultMode", cfg.mode),
      kv("autoCompact", flags.autoCompactEnabled), kv("autoMemory", flags.autoMemoryEnabled),
      kv("teammateMode", flags.teammateMode),
    ];
    root.appendChild(section("Settings", "config", settingsRows.length,
      el("div", { class: "kvgrid" }, settingsRows)));

    const env = cfg.env || {};
    const envKeys = Object.keys(env);
    if (envKeys.length) {
      root.appendChild(section("Environment", "config", envKeys.length,
        el("div", { class: "kvgrid wide" }, envKeys.map((k) => kv(k, env[k])))));
    }

    const plugins = cfg.plugins || {};
    const pkeys = Object.keys(plugins);
    if (pkeys.length) {
      root.appendChild(section("Plugins", "config", pkeys.length,
        el("div", { class: "badges wrap" }, pkeys.map((p) =>
          badge(p + " · " + (plugins[p] ? "on" : "off"), plugins[p] ? "user" : "muted")))));
    }

    [["Output styles", misc.output_styles || []], ["Templates", misc.templates || []]]
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
        el("p", { class: "small" },
          "Reserved but empty layers — they exist in the architecture but ship no artifacts yet:"),
        el("div", { class: "chips" }, emptyLayers.map((e) =>
          el("span", { class: "chip" }, e.name + " · " + e.path))),
      ]));
    }
  }

  function renderHealth(root) {
    const h = D.health || { dangling: [], orphans: [], missing_scripts: [] };
    const issues = h.dangling.length + h.missing_scripts.length;
    root.appendChild(el("div", { class: "stat-row" }, [
      el("div", { class: "stat" }, [el("b", null, String(h.missing_scripts.length)), " missing scripts"]),
      el("div", { class: "stat" }, [el("b", null, String(h.dangling.length)), " broken refs"]),
      el("div", { class: "stat" }, [el("b", null, String(h.orphans.length)), " orphan skills"]),
    ]));
    if (issues === 0) {
      root.appendChild(el("div", { class: "notice ok" },
        "Every cross-ref and preload resolves, and every registered hook script exists on disk."));
    }

    if (h.missing_scripts.length) {
      root.appendChild(section("Missing hook scripts", "perm-deny", h.missing_scripts.length,
        el("ul", { class: "hlist" }, h.missing_scripts.map((s) =>
          el("li", { class: "hitem err mono" }, s + " — registered in hooks.json but not on disk")))));
    }
    if (h.dangling.length) {
      root.appendChild(section("Broken references", "perm-ask", h.dangling.length,
        el("ul", { class: "hlist" }, h.dangling.map((d) =>
          el("li", { class: "hitem" }, [
            linkChip(d.source, d.kind === "agent-skill" ? "agents" : "skills", d.source),
            el("span", { class: "harrow" }, " → "),
            el("span", { class: "mono missing" }, d.target),
            el("span", { class: "muted small" }, "  (" + d.kind + ", dropped from the graph)"),
          ])))));
    }
    if (h.orphans.length) {
      root.appendChild(section("Orphan skills", "config", h.orphans.length,
        el("div", null, [
          el("p", { class: "muted small" },
            "No preload or cross-ref edge in or out. Expected for user-invocable skills "
            + "(triggered directly) and description-auto-triggered ones — not necessarily a problem."),
          el("div", { class: "chips" }, h.orphans.map((o) => linkChip(o, "skills", o))),
        ])));
    }
  }

  async function controlPost(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Mainframe-Token": window.HUB_CONTROL_TOKEN || "" },
      body: JSON.stringify(payload || {}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "request failed");
    window.location.reload();
  }

  function actionButton(label, action, tone) {
    const button = el("button", { type: "button", class: "control-button " + (tone || "") }, label);
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await action(); }
      catch (error) { button.disabled = false; button.title = String(error); }
    });
    return button;
  }

  function renderControl(root) {
    const control = D.control || { providers: {}, jobs: [] };
    const jobs = control.jobs || [];
    const countStatus = (name) => (control.counts || {})[name]
      || jobs.filter((job) => job.status === name).length;
    root.appendChild(el("p", { class: "muted" }, "Queue operations are local, bounded, and review-only."));
    root.appendChild(el("div", { class: "stat-row wrap" }, [
      el("div", { class: "stat" }, [el("b", null, String(countStatus("queued"))), "Queued"]),
      el("div", { class: "stat" }, [el("b", null, String(countStatus("running"))), "Running"]),
      el("div", { class: "stat" }, [el("b", null, String(countStatus("completed"))), "Completed"]),
      el("div", { class: "stat" }, [el("b", null, String(countStatus("retryable"))), "Needs retry"]),
    ]));
    const launch = el("div", { class: "control-launch" }, [
      actionButton("Run Spark", () => controlPost("/api/jobs", { provider: "spark", adapter: "claude-code" })),
      actionButton("Run Spark", () => controlPost("/api/jobs", { provider: "spark", adapter: "codex" })),
      actionButton("Run Antigravity", () => controlPost("/api/jobs", { provider: "antigravity", adapter: "claude-code" }), "accent"),
    ]);
    launch.children[0].appendChild(el("span", { class: "button-detail" }, "Claude Code"));
    launch.children[1].appendChild(el("span", { class: "button-detail" }, "Codex"));
    launch.children[2].appendChild(el("span", { class: "button-detail" }, "Claude Code"));
    root.appendChild(section("Analysis queue", "dev", 3, launch));

    const providerCards = Object.entries(control.providers || {}).map(([provider, enabled]) =>
      el("article", { class: "provider-card" }, [
        el("div", null, [el("strong", { class: "mono" }, provider), badge(enabled ? "Enabled" : "Paused", enabled ? "user" : "muted")]),
        actionButton(enabled ? "Pause" : "Resume", () => controlPost("/api/providers/" + provider, { enabled: !enabled })),
      ]));
    root.appendChild(section("Providers", "config", providerCards.length, el("div", { class: "provider-grid" }, providerCards)));

    if (!jobs.length) {
      root.appendChild(el("div", { class: "notice" }, "No analysis jobs yet."));
      return;
    }
    const rows = jobs.map((job) => {
      const actions = [];
      if (["retryable", "failed", "cancelled"].includes(job.status)) {
        actions.push(actionButton("Retry", () => controlPost("/api/jobs/" + job.id + "/retry", {})));
      } else if (job.status === "queued") {
        actions.push(actionButton("Cancel", () => controlPost("/api/jobs/" + job.id + "/cancel", {}), "danger"));
      }
      return el("tr", null, [
        el("td", { class: "mono" }, job.provider), el("td", null, job.adapter),
        el("td", null, badge(job.status, job.status)), el("td", { class: "num" }, String(job.attempts)),
        el("td", { class: "mono dim" }, job.updated_at || ""),
        el("td", { class: "job-detail" }, job.detail || ""), el("td", { class: "job-actions" }, actions),
      ]);
    });
    root.appendChild(section("Recent jobs", "dev", jobs.length, el("div", { class: "table-scroll" }, el("table", { class: "matrix" }, [
      el("thead", null, el("tr", null, ["Provider", "Adapter", "Status", "Attempts", "Updated", "Detail", "Actions"].map((name) => el("th", null, name)))),
      el("tbody", null, rows),
    ]))));
  }

  const VIEWS = [
    { id: "overview", label: "Overview", short: "OV", render: renderOverview },
    { id: "dev", label: "Telemetry", short: "TL", render: renderDev },
    { id: "usage", label: "Usage", short: "US", render: renderUsage },
    { id: "analysis", label: "Analysis", short: "AN", render: renderControl },
    { id: "catalog", label: "Components", short: "CP", render: renderCatalog, divider: true },
    { id: "hooks", label: "Hooks", short: "HK", render: renderHooks },
    { id: "config", label: "Configuration", short: "CF", render: renderConfig },
    { id: "health", label: "Health", short: "HL", render: renderHealth },
    { id: "graph", label: "Map", short: "MP", render: renderGraph },
  ];

  const panes = {};
  VIEWS.forEach((v) => {
    if (v.divider) tabsNav.appendChild(el("div", { class: "nav-label nav-label-inline" }, "System"));
    const btn = el("button", { type: "button", role: "tab", "aria-controls": "view-" + v.id,
      "aria-selected": "false", class: v.divider ? "tab-divider" : "",
      "data-short": v.short }, [el("span", { class: "tab-code", "aria-hidden": "true" }, v.short),
      el("span", { class: "tab-label" }, v.label)]);
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
    // Isolate each view: a throw in one render degrades to one empty tab with a
    // notice, never a blank page (this opens with no devtools to debug a crash).
    try {
      v.render(pane);
    } catch (err) {
      pane.appendChild(el("div", { class: "notice" }, "This view failed to render: " + err));
    }
    app.appendChild(pane);
    panes[v.id] = { pane, btn };
  });

  // Search box lives in the topbar; it filters the catalog and the graph in place
  // (kept out of the per-view render so the graph keeps its pan/zoom on a keystroke).
  const topbar = document.querySelector(".topbar");
  let search = null;
  if (topbar) {
    search = el("input", { class: "search", type: "search",
      placeholder: language === "ru" ? "фильтр skills, агентов, hooks…" : "filter skills, agents, hooks…",
      autocomplete: "off" });
    search.addEventListener("input", () => applyFilter(search.value));
    const tools = topbar.querySelector(".toptools") || topbar;
    const languageSelect = el("select", { class: "language-select", "aria-label": "Language" }, [
      el("option", { value: "en" }, "English"), el("option", { value: "ru" }, "Русский"),
    ]);
    languageSelect.value = language;
    languageSelect.addEventListener("change", () => {
      try { window.localStorage.setItem("mainframe-language", languageSelect.value); } catch (_err) { /* optional */ }
      window.location.reload();
    });
    tools.appendChild(languageSelect);
    const stamp = tools.querySelector(".stamp");
    tools.insertBefore(search, stamp || null);
    // anchor the fixed drawer just under the (sticky) topbar, measured not guessed
    const top = topbar.offsetHeight || 49;
    detail.style.top = top + "px";
    detail.style.height = "calc(100vh - " + top + "px)";
  }

  function show(id) {
    const activeView = VIEWS.find((v) => v.id === id);
    VIEWS.forEach((v) => {
      const on = v.id === id;
      panes[v.id].pane.classList.toggle("active", on);
      panes[v.id].btn.classList.toggle("active", on);
      panes[v.id].btn.setAttribute("aria-selected", on ? "true" : "false");
      panes[v.id].btn.tabIndex = on ? 0 : -1;
    });
    const activeName = document.getElementById("active-view-name");
    if (activeName && activeView) activeName.textContent = tr(activeView.label);
    if (activeView) document.title = tr(activeView.label) + " · MAINFRAME hub";
    if (search) search.hidden = id !== "catalog" && id !== "graph";
    try { window.sessionStorage.setItem("mainframe-hub-view", id); } catch (_err) { /* unavailable over some file origins */ }
  }

  let initialView = "overview";
  try {
    const saved = window.sessionStorage.getItem("mainframe-hub-view");
    if (VIEWS.some((view) => view.id === saved)) initialView = saved;
    const savedScroll = Number(window.sessionStorage.getItem("mainframe-hub-scroll"));
    if (savedScroll > 0) window.requestAnimationFrame(() => window.scrollTo(0, savedScroll));
  } catch (_err) { /* session state is optional */ }
  show(initialView);

  document.documentElement.lang = language;
  const navLabel = document.querySelector(".sidebar > .nav-label");
  const brandSub = document.querySelector(".brand-sub");
  const privacy = document.querySelector(".privacy-note");
  if (navLabel) navLabel.textContent = tr("Observe");
  if (brandSub) brandSub.textContent = tr("local observatory");
  if (privacy) privacy.textContent = tr("Local data only");

  if (window.HUB_AUTO_REFRESH_MS >= 2000) {
    window.setInterval(() => {
      try { window.sessionStorage.setItem("mainframe-hub-scroll", String(window.scrollY)); } catch (_err) { /* optional */ }
      window.location.reload();
    }, window.HUB_AUTO_REFRESH_MS);
  }
})();
