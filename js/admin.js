/* =========================================================
   Admin panel helpers. Load after api.js and app.js.

   AdminCrud({...}) builds a full list + add/edit/delete page
   for one resource from a small config (see admin/cars.html).
   ========================================================= */
(function () {
  const TABS = [
    ["dashboard", "Dashboard"], ["cars", "Cars"], ["customers", "Customers"],
    ["rentals", "Rentals"], ["payments", "Payments"]
  ];

  function adminNav(current) {
    return `<nav class="admin-nav" aria-label="Admin">${TABS.map(([key, label]) =>
      `<a href="${UI.url("admin/" + key + ".html")}"${key === current ? ' aria-current="page"' : ""}>${label}</a>`).join("")}</nav>`;
  }

  // Loads every resource the page needs and returns lookup helpers
  async function loadRefs(names) {
    const lists = await Promise.all(names.map(n => API.list(n)));
    const refs = {};
    names.forEach((n, i) => { refs[n] = lists[i]; refs[n + "ById"] = new Map(lists[i].map(r => [r.id, r])); });
    return refs;
  }

  const carName = c => c ? `${c.brand} ${c.model}` : "—";

  /* ---------- Generic CRUD page ----------
     cfg = {
       resource: "cars", title: "Cars", singular: "car",
       refs: ["customers"],                  // other lists to load
       columns: [{ label, value(row, refs) -> html string }],
       fields:  [{ key, label, type: text|number|date|select|ref,
                   options: [...], ref: "cars", refLabel(row),
                   required, optional, min, max, step, hint, maxlength,
                   onlyOnCreate, readOnlyOnEdit }],
       defaults: { status: "Available" },
       canDelete: true
     }                                        */
  window.AdminCrud = async function (cfg) {
    if (!Auth.require("admin")) return;
    const root = document.getElementById("admin");
    root.innerHTML = `${adminNav(cfg.resource)}
      <div class="toolbar">
        <h1>${cfg.title}</h1>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <input class="input" type="search" id="search" placeholder="Search…" aria-label="Search">
          <button class="btn btn-accent" id="addBtn" type="button">+ Add ${cfg.singular}</button>
        </div>
      </div>
      <div class="card" style="overflow:hidden"><div class="table-wrap" id="tableBox"><p class="muted" style="padding:20px">Loading…</p></div></div>
      <dialog class="modal" id="modal">
        <form id="form" novalidate>
          <div class="modal-head"><h2 id="formTitle"></h2><button class="btn btn-ghost btn-sm" type="button" data-close aria-label="Close">✕</button></div>
          <div class="modal-body"><div id="formError" class="form-error hidden" role="alert"></div><div id="fields"></div></div>
          <div class="modal-foot"><button class="btn btn-ghost" type="button" data-close>Cancel</button><button class="btn btn-accent" id="saveBtn" type="submit">Save</button></div>
        </form>
      </dialog>`;

    const $ = id => document.getElementById(id);
    const modal = $("modal");
    let rows = [], refs = {}, editing = null;

    async function load() {
      try {
        [rows, refs] = await Promise.all([API.list(cfg.resource), loadRefs(cfg.refs || [])]);
        rows.sort((a, b) => b.id - a.id);
        render();
      } catch (e) {
        $("tableBox").innerHTML = `<div class="empty" style="border:0"><h3>Could not load data</h3><p>${UI.esc(e.message)}</p></div>`;
      }
    }

    function render() {
      const q = $("search").value.trim().toLowerCase();
      const cells = rows.map(r => ({ row: r, html: cfg.columns.map(c => c.value(r, refs)) }));
      const shown = q ? cells.filter(c => c.html.join(" ").replace(/<[^>]+>/g, "").toLowerCase().includes(q)) : cells;
      if (!shown.length) {
        $("tableBox").innerHTML = `<div class="empty" style="border:0"><h3>${q ? "No matches" : "Nothing here yet"}</h3><p>${q ? "Try another search." : `Add the first ${cfg.singular}.`}</p></div>`;
        return;
      }
      $("tableBox").innerHTML = `<table class="table">
        <thead><tr>${cfg.columns.map(c => `<th>${c.label}</th>`).join("")}<th></th></tr></thead>
        <tbody>${shown.map(({ row, html }) => `<tr>${html.map(h => `<td>${h}</td>`).join("")}
          <td><div class="row-actions">
            <button class="btn btn-ghost btn-sm" data-edit="${row.id}">Edit</button>
            ${cfg.canDelete === false ? "" : `<button class="btn btn-ghost btn-sm" data-del="${row.id}" style="color:var(--bad)">Delete</button>`}
          </div></td></tr>`).join("")}</tbody></table>`;
    }

    function fieldHtml(f, value) {
      const v = value ?? "";
      const disabled = editing && f.readOnlyOnEdit ? " disabled" : "";
      const req = f.required ? " required" : "";
      let input;
      if (f.type === "select" || f.type === "ref") {
        const opts = f.type === "ref"
          ? refs[f.ref].map(r => [r.id, f.refLabel(r, refs)])
          : f.options.map(o => [o, o]);
        input = `<select class="select" id="f_${f.key}"${req}${disabled}>
          ${f.required ? "" : `<option value="">—</option>`}
          ${f.type === "ref" && f.required ? `<option value="" disabled${v === "" ? " selected" : ""}>Choose…</option>` : ""}
          ${opts.map(([val, label]) => `<option value="${UI.esc(val)}"${String(val) === String(v) ? " selected" : ""}>${UI.esc(label)}</option>`).join("")}
        </select>`;
      } else {
        const attrs = ["min", "max", "step", "maxlength"].filter(a => f[a] != null).map(a => ` ${a}="${f[a]}"`).join("");
        input = `<input class="input" id="f_${f.key}" type="${f.type || "text"}" value="${UI.esc(v)}"${attrs}${req}${disabled}>`;
      }
      return `<div class="field"><label for="f_${f.key}">${f.label}${f.required ? "" : ' <span class="muted">(optional)</span>'}</label>${input}${f.hint ? `<span class="hint">${f.hint}</span>` : ""}</div>`;
    }

    function openForm(row) {
      editing = row || null;
      $("formTitle").textContent = row ? `Edit ${cfg.singular} #${row.id}` : `Add ${cfg.singular}`;
      $("formError").classList.add("hidden");
      const fields = cfg.fields.filter(f => !(row && f.onlyOnCreate));
      $("fields").innerHTML = fields.map(f => fieldHtml(f, row ? row[f.key] : (cfg.defaults || {})[f.key])).join("");
      modal.showModal();
      const first = $("fields").querySelector("input:not([disabled]),select:not([disabled])");
      if (first) first.focus();
    }

    function readForm() {
      const data = {};
      for (const f of cfg.fields) {
        if (editing && (f.onlyOnCreate || f.readOnlyOnEdit)) continue;
        const el = $("f_" + f.key);
        if (!el) continue;
        let v = el.value.trim();
        if (v === "") {
          if (f.required) throw new Error(`${f.label} is required.`);
          continue;                       // optional & empty: let the server decide
        }
        if (f.type === "number" || f.type === "ref") {
          v = Number(v);
          if (!Number.isFinite(v)) throw new Error(`${f.label} must be a number.`);
          if (f.min != null && v < f.min) throw new Error(`${f.label} must be at least ${f.min}.`);
          if (f.max != null && v > f.max) throw new Error(`${f.label} must be at most ${f.max}.`);
        }
        if (f.transform) v = f.transform(v);
        data[f.key] = v;
      }
      if (cfg.validate) cfg.validate(data, editing);
      return data;
    }

    $("addBtn").addEventListener("click", () => openForm(null));
    $("search").addEventListener("input", render);
    modal.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => modal.close()));

    $("form").addEventListener("submit", async ev => {
      ev.preventDefault();
      $("formError").classList.add("hidden");
      let data;
      try { data = readForm(); }
      catch (e) { $("formError").textContent = e.message; $("formError").classList.remove("hidden"); return; }
      $("saveBtn").disabled = true;
      try {
        if (editing) await API.update(cfg.resource, editing.id, data);
        else await API.create(cfg.resource, data);
        modal.close();
        UI.toast(editing ? "Changes saved." : `${cfg.singular[0].toUpperCase() + cfg.singular.slice(1)} added.`, "ok");
        await load();
      } catch (e) {
        $("formError").textContent = e.message;
        $("formError").classList.remove("hidden");
      }
      $("saveBtn").disabled = false;
    });

    $("tableBox").addEventListener("click", async ev => {
      const edit = ev.target.closest("[data-edit]");
      const del = ev.target.closest("[data-del]");
      if (edit) openForm(rows.find(r => r.id === Number(edit.dataset.edit)));
      if (del) {
        const id = Number(del.dataset.del);
        if (!confirm(`Delete ${cfg.singular} #${id}? This cannot be undone.`)) return;
        try {
          await API.remove(cfg.resource, id);
          UI.toast(`Deleted #${id}.`, "ok");
          await load();
        } catch (e) { UI.toast(e.message, "bad"); }
      }
    });

    load();
  };

  window.Admin = { adminNav, loadRefs, carName };
})();
