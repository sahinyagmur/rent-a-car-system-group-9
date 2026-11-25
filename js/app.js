/* =========================================================
   Shared page code: session (Auth), header/footer (layout),
   small UI helpers (UI). Load AFTER js/api.js on every page:

     <script src="js/api.js"></script>
     <script src="js/app.js"></script>

   <body data-page="cars">  -> highlights the "Cars" nav link
   <body data-layout="bare"> -> no footer (auth pages)
   ========================================================= */
(function () {
  const BRAND = "G9 Rent a Car";
  const SESSION_KEY = "g9rac_session";

  // Site root derived from this script's URL, so pages in /admin/ work too.
  const ROOT = document.currentScript.src.replace(/js\/app\.js(\?.*)?$/, "");
  const url = path => ROOT + path;

  /* ---------- Auth ---------- */
  const Auth = {
    user() {
      try { return JSON.parse(localStorage.getItem(SESSION_KEY)); } catch (e) { return null; }
    },
    isAdmin() { const u = Auth.user(); return !!u && u.role === "admin"; },
    async login(username, password) {
      const user = await API.login(username, password);
      localStorage.setItem(SESSION_KEY, JSON.stringify(user));
      return user;
    },
    async register(data) {
      const user = await API.register(data);
      localStorage.setItem(SESSION_KEY, JSON.stringify(user));
      return user;
    },
    async logout() {
      try { await API.logout(); } catch (e) { /* ignore */ }
      localStorage.removeItem(SESSION_KEY);
      location.href = url("index.html");
    },
    // Call at the top of a protected page: Auth.require("admin")
    require(role) {
      const u = Auth.user();
      if (!u) {
        const next = encodeURIComponent(location.pathname + location.search);
        location.replace(url("login.html?next=" + next));
        return null;
      }
      if (role && u.role !== role) { location.replace(url("index.html")); return null; }
      return u;
    },
    homeFor(user) {
      return user && user.role === "admin" ? url("admin/dashboard.html") : url("cars.html");
    }
  };

  /* ---------- UI helpers ---------- */
  const moneyFmt = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 });
  const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

  const BADGE = {
    Available: "ok", Rented: "info", Maintenance: "warn",
    Pending: "warn", Active: "info", Completed: "ok", Cancelled: "bad",
    Paid: "ok"
  };

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function hash(str) {
    let h = 0;
    for (const ch of str) h = (h * 31 + ch.charCodeAt(0)) | 0;
    return Math.abs(h);
  }

  const PAINT = ["#c8341b", "#1f3b70", "#2a2d33", "#e6e3dc", "#3d6b4f", "#8a8f98", "#b5832a", "#5b3a7a", "#0f6b78"];

  const SHAPES = {
    sedan: {
      body: "M18 96 Q16 76 40 70 L96 62 Q122 38 160 34 L210 34 Q238 36 262 62 L292 68 Q308 72 306 92 L306 98 Q306 104 298 104 L22 104 Q18 104 18 96 Z",
      win: ["M108 62 Q128 44 160 42 L182 42 L182 62 Z", "M190 42 L208 42 Q232 44 250 62 L190 62 Z"]
    },
    hatch: {
      body: "M22 96 Q18 70 34 56 Q52 38 120 34 L196 34 Q228 36 256 62 L290 68 Q306 72 306 92 L306 98 Q306 104 298 104 L26 104 Q22 104 22 96 Z",
      win: ["M44 62 Q56 44 120 42 L176 42 L176 62 Z", "M184 42 L196 42 Q224 44 246 62 L184 62 Z"]
    },
    suv: {
      body: "M18 94 Q16 70 36 64 L78 58 Q96 28 136 26 L232 26 Q258 28 272 56 L294 62 Q308 66 306 90 L306 98 Q306 104 298 104 L22 104 Q18 104 18 94 Z",
      win: ["M90 58 Q106 34 136 34 L176 34 L176 58 Z", "M184 34 L228 34 Q250 36 262 58 L184 58 Z"]
    }
  };

  function shapeFor(car) {
    const m = `${car.brand} ${car.model}`.toLowerCase();
    if (/3008|5008|2008|tucson|tiguan|t-roc|qashqai|duster|rav4|kuga|sportage|x[1-7]\b|q[2-8]\b|gl[abce]/.test(m)) return "suv";
    if (/clio|i10|i20|polo|golf|corsa|208|yaris|fiesta|micra|sandero|fabia|ibiza|a1\b|mini/.test(m)) return "hatch";
    return "sedan";
  }

  // Inline SVG illustration (the schema has no image column)
  function carArt(car) {
    const s = SHAPES[shapeFor(car)];
    const paint = PAINT[hash(car.brand + car.model) % PAINT.length];
    const light = paint === "#e6e3dc";
    const wheel = cx => `<circle cx="${cx}" cy="104" r="22" fill="#15171b"/><circle cx="${cx}" cy="104" r="12" fill="#9aa0a8"/><circle cx="${cx}" cy="104" r="4" fill="#15171b"/>`;
    return `<svg viewBox="0 0 324 132" role="img" aria-label="${esc(car.brand + " " + car.model)}">
      <ellipse cx="162" cy="126" rx="142" ry="5" fill="rgba(0,0,0,.16)"/>
      <path d="${s.body}" fill="${paint}" ${light ? 'stroke="#bdb9af" stroke-width="1.5"' : ""}/>
      ${s.win.map(d => `<path d="${d}" fill="#27303c"/>`).join("")}
      <path d="M40 84 L298 84" stroke="${light ? "#bdb9af" : "rgba(255,255,255,.22)"}" stroke-width="2"/>
      <rect x="290" y="74" width="12" height="6" rx="3" fill="#fff4c2"/>
      <rect x="20" y="76" width="9" height="6" rx="3" fill="#ff5a3c"/>
      ${wheel(80)}${wheel(246)}
    </svg>`;
  }

  function badge(status, label) {
    return `<span class="badge badge-${BADGE[status] || "info"}">${esc(label || status)}</span>`;
  }

  function toast(message, kind) {
    let host = document.querySelector(".toast-host");
    if (!host) { host = document.createElement("div"); host.className = "toast-host"; document.body.appendChild(host); }
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " " + kind : "");
    el.setAttribute("role", "status");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => el.remove(), 3800);
  }

  function qs(name) { return new URLSearchParams(location.search).get(name); }

  function addDays(iso, n) {
    const d = new Date(iso + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  const UI = {
    url, esc, badge, toast, carArt, qs, addDays,
    money: n => moneyFmt.format(Number(n) || 0),
    date: iso => iso ? dateFmt.format(new Date(iso + "T00:00:00")) : "—"
  };

  /* ---------- Layout ---------- */
  const ICON_MENU = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';

  function renderHeader() {
    const user = Auth.user();
    const page = document.body.dataset.page || "";
    const links = [["home", "Home", "index.html"], ["cars", "Cars", "cars.html"]];
    if (user && user.role === "customer") links.push(["my-rentals", "My rentals", "my-rentals.html"]);
    if (user && user.role === "admin") links.push(["admin", "Admin panel", "admin/dashboard.html"]);

    const nav = links.map(([key, label, href]) =>
      `<a href="${url(href)}"${page === key ? ' aria-current="page"' : ""}>${label}</a>`).join("");

    const initials = user ? (user.name || user.username).split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase() : "";
    const actions = user
      ? `<span class="user-chip"><span class="avatar">${esc(initials)}</span>${esc(user.name || user.username)}</span>
         ${user.role === "customer" ? `<a class="btn btn-ghost btn-sm" href="${url("profile.html")}">Profile</a>` : ""}
         <button class="btn btn-ghost btn-sm" type="button" data-logout>Log out</button>`
      : `<a class="btn btn-ghost btn-sm" href="${url("login.html")}">Log in</a>
         <a class="btn btn-accent btn-sm" href="${url("register.html")}">Sign up</a>`;

    const header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML = `
      <div class="container">
        <a class="brand" href="${url("index.html")}"><span class="brand-mark">G<b>9</b></span>${BRAND}</a>
        <nav class="nav" aria-label="Main">${nav}</nav>
        <div class="header-actions">${actions}</div>
        <button class="btn btn-ghost btn-sm menu-toggle" type="button" aria-label="Menu" aria-expanded="false">${ICON_MENU}</button>
      </div>`;
    document.body.prepend(header);

    if (API.MODE === "mock") {
      const banner = document.createElement("div");
      banner.className = "mode-banner";
      banner.textContent = "Demo mode — data is stored in this browser only. ";
      const reset = document.createElement("button");
      reset.className = "link-btn"; reset.type = "button"; reset.textContent = "Reset demo data";
      reset.style.color = "inherit";
      reset.addEventListener("click", () => { API.resetMock(); localStorage.removeItem(SESSION_KEY); location.reload(); });
      banner.appendChild(reset);
      document.body.prepend(banner);
    }

    const toggle = header.querySelector(".menu-toggle");
    toggle.addEventListener("click", () => {
      const open = header.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    const out = header.querySelector("[data-logout]");
    if (out) out.addEventListener("click", Auth.logout);
  }

  function renderFooter() {
    if (document.body.dataset.layout === "bare") return;
    const footer = document.createElement("footer");
    footer.className = "site-footer";
    footer.innerHTML = `
      <div class="container">
        <div>
          <a class="brand" href="${url("index.html")}"><span class="brand-mark">G<b>9</b></span>${BRAND}</a>
          <p style="margin-top:14px;max-width:38ch">Pick a car, choose your dates, drive away. Transparent daily prices, no hidden fees.</p>
        </div>
        <div>
          <h4>Rent</h4>
          <a href="${url("cars.html")}">All cars</a>
          <a href="${url("index.html#how")}">How it works</a>
          <a href="${url("my-rentals.html")}">My rentals</a>
        </div>
        <div>
          <h4>Account</h4>
          <a href="${url("login.html")}">Log in</a>
          <a href="${url("register.html")}">Create account</a>
        </div>
        <div class="copy">© 2026 ${BRAND} · CMPE341 Group 9 project</div>
      </div>`;
    document.body.appendChild(footer);
  }

  window.Auth = Auth;
  window.UI = UI;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { renderHeader(); renderFooter(); });
  } else { renderHeader(); renderFooter(); }
})();
