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

  function skillCard(s) {
    const badges = el("div", { class: "badges" }, [
      badge(s.dev ? "dev" : "skill", s.dev ? "dev" : "skills"),
      badge(s.user_invocable ? "/" + s.name : "auto",
            s.user_invocable ? "user" : "muted"),
    ]);
    return el("article", { class: "card" }, [
      el("div", { class: "card-head" }, [el("span", { class: "card-name" }, s.name), badges]),
      el("p", { class: "card-desc" }, s.description),
      s.when_to_use && el("p", { class: "card-when" }, [el("b", null, "when: "), s.when_to_use]),
    ]);
  }

  function agentCard(a) {
    const chips = el("div", { class: "chips" },
      (a.skills || []).map((sk) => el("span", { class: "chip" }, sk)));
    return el("article", { class: "card" }, [
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

  function renderCatalog(root) {
    const skills = D.skills.filter((s) => !s.dev);
    const devSkills = D.skills.filter((s) => s.dev);
    const groups = [
      ["Skills", "skills", skills, skillCard],
      ["Agents", "agents", D.agents, agentCard],
      ["Dev skills", "dev", devSkills, skillCard],
    ];
    groups.forEach(([title, cls, items, mk]) => {
      if (!items.length) return;
      const grid = el("div", { class: "grid" }, items.map(mk));
      root.appendChild(section(title, cls, items.length, grid));
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
    });

    const nodeEls = {};
    placed.forEach((n) => {
      const p = pos[n.id];
      const g = svg("g", { class: "gnode " + n.layer, transform: "translate(" + p.x + "," + p.y + ")" });
      g.appendChild(svg("circle", { r: 6, class: "dot" }));
      g.appendChild(svg("text", { x: 11, y: 4 }, n.label));
      g.addEventListener("mouseenter", () => focus(n.id));
      g.addEventListener("mouseleave", reset);
      nodeLayer.appendChild(g);
      nodeEls[n.id] = g;
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
      [el("span", { class: "muted" }, "drag to pan · scroll to zoom · hover a node to trace its links"), ...items]);
  }

  const VIEWS = [
    { id: "catalog", label: "Catalog", render: renderCatalog },
    { id: "hooks", label: "Hooks", render: renderHooks },
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

  function show(id) {
    VIEWS.forEach((v) => {
      const on = v.id === id;
      panes[v.id].pane.classList.toggle("active", on);
      panes[v.id].btn.classList.toggle("active", on);
    });
  }

  show("catalog");
})();
