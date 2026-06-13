"use strict";
// HUB_DATA is injected by build_hub_page.py (the inlined manifest). All views
// build the DOM from data via textContent — never innerHTML — so artifact
// descriptions containing < > or quotes cannot break or inject markup.
(function () {
  const D = window.HUB_DATA;
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

  // Indexed by name; the clicked node's layer disambiguates a name shared across layers.
  const skillByName = {};
  D.skills.forEach((s) => { skillByName[s.name] = s; });
  const agentByName = {};
  D.agents.forEach((a) => { agentByName[a.name] = a; });
  // reverse edges: who preloads (agent skills:) or references (skill cross-ref) a skill
  const referencedBy = {};
  D.agents.forEach((a) => (a.skills || []).forEach((sk) => {
    (referencedBy[sk] || (referencedBy[sk] = [])).push({ name: a.name, layer: "agents" });
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
      dsec("preloads skills", (a.skills || []).map((sk) => linkChip(sk, "skills", sk))),
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

  function renderDev(root) {
    const ds = D.dev_state;
    if (!ds.active) {
      root.appendChild(el("div", { class: "notice" },
        "No telemetry recorded yet — either dev mode is not installed, or no "
        + "sessions have run since it was. Enable with ./install.sh --dev; "
        + "data appears here after a few sessions."));
      return;
    }
    root.appendChild(el("div", { class: "stat-row" }, [
      el("div", { class: "stat" }, [el("b", null, String(ds.telemetry.sessions)), " sessions"]),
      el("div", { class: "stat" }, [el("b", null, String(ds.feedback.length)), " feedback queued"]),
      el("div", { class: "stat" }, [el("b", null, String(ds.telemetry.events.length)), " event types"]),
    ]));
    const rows = ds.telemetry.events.map(([name, n]) => el("tr", null, [
      el("td", { class: "mono" }, name),
      el("td", { class: "num" }, String(n)),
    ]));
    root.appendChild(section("Telemetry events", "events", ds.telemetry.events.length,
      el("table", { class: "matrix" }, [
        el("thead", null, el("tr", null, [el("th", null, "event"), el("th", null, "count")])),
        el("tbody", null, rows)])));

    const t = ds.telemetry;
    if (t.by_day && t.by_day.length) {
      root.appendChild(section("Activity by day", "events", t.by_day.length, barList(t.by_day)));
    }
    if (t.by_agent && t.by_agent.length) {
      root.appendChild(section("Events by agent", "agents", t.by_agent.length, barList(t.by_agent)));
    }
    (t.breakdowns || []).forEach((b) => {
      const brows = b.items.map(([v, n]) => el("tr", null, [
        el("td", { class: "mono" }, v), el("td", { class: "num" }, String(n))]));
      if (b.unrecognized) {
        brows.push(el("tr", null, [
          el("td", { class: "mono dim" }, "(payload format unrecognized)"),
          el("td", { class: "num dim" }, String(b.unrecognized))]));
      }
      root.appendChild(section(b.event + " · by " + b.key, "dev", b.total,
        el("table", { class: "matrix" }, [el("tbody", null, brows)])));
    });

    if (ds.feedback.length) {
      root.appendChild(section("Feedback queue", "dev", ds.feedback.length,
        el("ul", { class: "files" }, ds.feedback.map((f) => el("li", { class: "mono" }, f)))));
    }
  }

  const LAYERS = ["events", "hooks", "agents", "skills", "dev"];

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
    function apply() { viewport.setAttribute("transform", "translate(" + tx + "," + ty + ") scale(" + scale + ")"); }
    board.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      scale = Math.min(4, Math.max(0.3, scale * (ev.deltaY < 0 ? 1.1 : 0.9)));
      apply();
    }, { passive: false });
    board.addEventListener("mousedown", (ev) => { drag = { x: ev.clientX - tx, y: ev.clientY - ty }; });
    window.addEventListener("mousemove", (ev) => { if (drag) { tx = ev.clientX - drag.x; ty = ev.clientY - drag.y; apply(); } });
    window.addEventListener("mouseup", () => { drag = null; });

    root.appendChild(graphLegend());
    root.appendChild(board);
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
      + (cfg.mode || "?") + ". Source: export/settings.json."));
    [["deny", "perm-deny"], ["ask", "perm-ask"], ["allow", "perm-allow"]].forEach(([key, cls]) => {
      const items = perms[key] || [];
      if (!items.length) return;
      const rows = items.map((p) => el("li", { class: "mono perm " + cls }, p));
      root.appendChild(section(key, cls, items.length, el("ul", { class: "permlist" }, rows)));
    });

    const flags = cfg.flags || {};
    const settingsRows = [
      kv("model", flags.model), kv("effortLevel", flags.effortLevel),
      kv("advisorModel", flags.advisorModel), kv("outputStyle", flags.outputStyle),
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
        el("div", { class: "kvgrid" }, envKeys.map((k) => kv(k, env[k])))));
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
      root.appendChild(el("div", { class: "notice" },
        "Reserved but empty layers: "
        + emptyLayers.map((e) => e.name + " (" + e.path + ")").join(", ")
        + ". They exist in the architecture but ship no artifacts yet."));
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

  const VIEWS = [
    { id: "catalog", label: "Catalog", render: renderCatalog },
    { id: "hooks", label: "Hooks", render: renderHooks },
    { id: "config", label: "Config", render: renderConfig },
    { id: "health", label: "Health", render: renderHealth },
    { id: "dev", label: "Dev state", render: renderDev },
    { id: "graph", label: "Graph", render: renderGraph },
  ];

  const panes = {};
  VIEWS.forEach((v) => {
    const btn = el("button", { type: "button" }, v.label);
    btn.addEventListener("click", () => show(v.id));
    v.btn = btn;
    tabsNav.appendChild(btn);
    const pane = el("div", { class: "view", id: "view-" + v.id });
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
  if (topbar) {
    const search = el("input", { class: "search", type: "search",
      placeholder: "filter skills, agents, hooks…", autocomplete: "off" });
    search.addEventListener("input", () => applyFilter(search.value));
    const stamp = topbar.querySelector(".stamp");
    topbar.insertBefore(search, stamp || null);
    // anchor the fixed drawer just under the (sticky) topbar, measured not guessed
    const top = topbar.offsetHeight || 49;
    detail.style.top = top + "px";
    detail.style.height = "calc(100vh - " + top + "px)";
  }

  function show(id) {
    VIEWS.forEach((v) => {
      const on = v.id === id;
      panes[v.id].pane.classList.toggle("active", on);
      panes[v.id].btn.classList.toggle("active", on);
    });
  }

  show("catalog");
})();
