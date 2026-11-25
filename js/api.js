/* =========================================================
   API layer — the ONLY file that talks to the backend.

   MODE = "mock": data lives in this browser's localStorage, seeded with
                  the same rows/field names as backend/schema.sql + seed.sql.
   MODE = "live": the same calls go to the Flask API (backend/app.py).

   Pages never call fetch() directly; they call API.list("cars") etc.
   The mode is picked automatically (see MODE below); pages never change.
   ========================================================= */
(function () {
  // Automatic: the preview server (tools/dev-server.js, port 5500) and file:// use mock data;
  // Flask / Docker (any other origin) uses the real API. Force one for testing with
  // localStorage.setItem("g9rac_mode", "mock" | "live").
  const FORCED = (() => { try { return localStorage.getItem("g9rac_mode"); } catch (e) { return null; } })();
  const MODE = FORCED === "mock" || FORCED === "live" ? FORCED
    : (location.protocol === "file:" || location.port === "5500" ? "mock" : "live");
  const BASE = "/api";          // Flask serves pages + API on the same origin
  const DB_KEY = "g9rac_db_v2";

  const RESOURCES = ["cars", "customers", "rentals", "payments"];
  const SINGULAR = { cars: "car", customers: "customer", rentals: "rental", payments: "payment" };
  const ACTIVE_RENTAL = ["Pending", "Active"]; // statuses that block a car

  /* ---------- Shared helpers ---------- */
  const today = () => new Date().toISOString().slice(0, 10);

  // Inclusive day count, same rule as the backend (2026-12-01..03 = 3 days)
  function dayCount(start, end) {
    const ms = Date.parse(end) - Date.parse(start);
    if (!Number.isFinite(ms) || ms < 0) return 0;
    return Math.round(ms / 86400000) + 1;
  }

  function overlaps(aStart, aEnd, bStart, bEnd) {
    return aStart <= bEnd && bStart <= aEnd;
  }

  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status || 400; }
  }

  /* =======================================================
     MOCK backend (localStorage)
     ======================================================= */
  const SEED = {
    // Demo-only plaintext passwords. The real DB stores scrypt hashes (seed.sql).
    users: [
      { id: 1, username: "admin", password: "Admin123!", role: "admin" },
      { id: 2, username: "demo1", password: "Customer123!", role: "customer" },
      { id: 3, username: "demo2", password: "Customer123!", role: "customer" }
    ],
    cars: [
      { id: 1, brand: "BMW", model: "320i", license_plate: "06 DEMO 101", year: 2023, price_per_day: 5000, status: "Available" },
      { id: 2, brand: "Mercedes-Benz", model: "C200", license_plate: "06 DEMO 102", year: 2024, price_per_day: 6500, status: "Available" },
      { id: 3, brand: "Toyota", model: "Corolla", license_plate: "06 DEMO 103", year: 2022, price_per_day: 2500, status: "Maintenance" },
      { id: 4, brand: "Renault", model: "Clio", license_plate: "06 DEMO 104", year: 2023, price_per_day: 1800, status: "Available" },
      { id: 5, brand: "Fiat", model: "Egea", license_plate: "06 DEMO 105", year: 2024, price_per_day: 1900, status: "Available" },
      { id: 6, brand: "Volkswagen", model: "Passat", license_plate: "06 DEMO 106", year: 2023, price_per_day: 4200, status: "Available" },
      { id: 7, brand: "Hyundai", model: "i20", license_plate: "06 DEMO 107", year: 2022, price_per_day: 1700, status: "Available" },
      { id: 8, brand: "Audi", model: "A4", license_plate: "06 DEMO 108", year: 2024, price_per_day: 5800, status: "Available" },
      { id: 9, brand: "Peugeot", model: "3008", license_plate: "06 DEMO 109", year: 2023, price_per_day: 3900, status: "Rented" }
    ],
    customers: [
      { id: 1, user_id: 2, name: "Demo Customer One", email: "demo1@example.com", phone: "05000000001", driver_license_no: "DL-100001" },
      { id: 2, user_id: 3, name: "Demo Customer Two", email: "demo2@example.com", phone: "05000000002", driver_license_no: "DL-100002" },
      { id: 3, user_id: null, name: "Demo Customer Three", email: "demo3@example.com", phone: "05000000003", driver_license_no: "DL-100003" }
    ],
    // Same rows as backend/seed.sql
    rentals: [
      { id: 1, customer_id: 3, car_id: 3, start_date: "2026-10-05", end_date: "2026-10-08", total_price: 10000, status: "Completed" },
      { id: 2, customer_id: 1, car_id: 5, start_date: "2026-11-10", end_date: "2026-11-12", total_price: 5700, status: "Completed" },
      { id: 3, customer_id: 2, car_id: 9, start_date: "2026-11-24", end_date: "2026-11-28", total_price: 19500, status: "Active" },
      { id: 4, customer_id: 1, car_id: 1, start_date: "2026-12-01", end_date: "2026-12-03", total_price: 15000, status: "Pending" },
      { id: 5, customer_id: 2, car_id: 2, start_date: "2026-12-05", end_date: "2026-12-06", total_price: 13000, status: "Pending" },
      { id: 6, customer_id: 3, car_id: 6, start_date: "2026-11-15", end_date: "2026-11-16", total_price: 8400, status: "Cancelled" }
    ],
    payments: [
      { id: 1, rental_id: 1, payment_date: "2026-10-08", amount: 10000, payment_method: "Cash", payment_status: "Paid" },
      { id: 2, rental_id: 2, payment_date: "2026-11-12", amount: 5700, payment_method: "Card", payment_status: "Paid" },
      { id: 3, rental_id: 3, payment_date: "2026-11-24", amount: 10000, payment_method: "Card", payment_status: "Paid" },
      { id: 4, rental_id: 4, payment_date: "2026-11-25", amount: 5000, payment_method: "Card", payment_status: "Pending" }
    ]
  };

  function load() {
    try {
      const raw = localStorage.getItem(DB_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* fall through to seed */ }
    const fresh = JSON.parse(JSON.stringify(SEED));
    save(fresh);
    return fresh;
  }
  function save(db) {
    try { localStorage.setItem(DB_KEY, JSON.stringify(db)); } catch (e) { /* private mode */ }
  }
  const nextId = rows => rows.reduce((m, r) => Math.max(m, r.id), 0) + 1;
  const clone = x => JSON.parse(JSON.stringify(x));
  const delay = v => new Promise(res => setTimeout(() => res(clone(v)), 120));

  function checkRental(db, r, excludeId) {
    if (!db.customers.some(c => c.id === r.customer_id)) throw new ApiError("Customer not found.", 404);
    const car = db.cars.find(c => c.id === r.car_id);
    if (!car) throw new ApiError("Car not found.", 404);
    if (!r.start_date || !r.end_date || r.end_date < r.start_date) throw new ApiError("End date must be on or after start date.");
    if (!ACTIVE_RENTAL.includes(r.status)) return;
    if (car.status === "Maintenance") throw new ApiError("This car is under maintenance.", 409);
    const clash = db.rentals.some(x => x.id !== excludeId && x.car_id === r.car_id &&
      ACTIVE_RENTAL.includes(x.status) && overlaps(r.start_date, r.end_date, x.start_date, x.end_date));
    if (clash) throw new ApiError("This car is already booked for those dates.", 409);
  }

  // Same rules as backend/app.py
  const STATUS_FLOW = { Pending: ["Active", "Cancelled"], Active: ["Completed"], Completed: [], Cancelled: [] };

  function checkPayment(db, p, excludeId) {
    const rental = db.rentals.find(r => r.id === p.rental_id);
    if (!rental) throw new ApiError("Rental not found.", 404);
    if (p.payment_status !== "Paid") return;
    const paid = db.payments.filter(x => x.id !== excludeId && x.rental_id === p.rental_id && x.payment_status === "Paid")
      .reduce((s, x) => s + Number(x.amount), 0);
    if (paid + Number(p.amount) > rental.total_price) throw new ApiError("Payment exceeds the remaining balance of this rental.");
  }

  // Mirror UNIQUE constraints from schema.sql
  function checkUnique(db, res, row, excludeId) {
    const taken = (key, msg) => {
      if (row[key] != null && db[res].some(x => x.id !== excludeId && x[key] === row[key])) throw new ApiError(msg, 409);
    };
    if (res === "cars") taken("license_plate", "License plate already exists.");
    if (res === "customers") {
      taken("email", "E-mail already registered.");
      taken("driver_license_no", "Driver license number already registered.");
      taken("user_id", "This user account is already linked to a customer.");
    }
  }

  const mock = {
    async list(res) { return delay(load()[res]); },

    async get(res, id) {
      const row = load()[res].find(r => r.id === Number(id));
      if (!row) throw new ApiError("Not found.", 404);
      return delay(row);
    },

    async create(res, data) {
      const db = load();
      const row = { ...data, id: nextId(db[res]) };
      checkUnique(db, res, row);
      if (res === "cars") row.status = row.status || "Available";
      if (res === "customers") row.user_id = row.user_id ?? null;
      if (res === "rentals") {
        row.status = row.status || "Pending";
        checkRental(db, row);
        if (row.total_price == null) {
          const car = db.cars.find(c => c.id === row.car_id);
          row.total_price = dayCount(row.start_date, row.end_date) * car.price_per_day;
        }
      }
      if (res === "payments") {
        checkPayment(db, row);
        row.payment_date = row.payment_date || today();
      }
      db[res].push(row);
      save(db);
      return delay(row);
    },

    async update(res, id, data) {
      const db = load();
      const row = db[res].find(r => r.id === Number(id));
      if (!row) throw new ApiError("Not found.", 404);
      const next = { ...row, ...data, id: row.id };
      checkUnique(db, res, next, row.id);
      if (res === "rentals" && next.status !== row.status && !(STATUS_FLOW[row.status] || []).includes(next.status)) {
        throw new ApiError(`Status can't change from ${row.status} to ${next.status}.`);
      }
      if (res === "payments") checkPayment(db, next, row.id);
      if (res === "rentals") {
        checkRental(db, next, row.id);
        const moved = next.car_id !== row.car_id || next.start_date !== row.start_date || next.end_date !== row.end_date;
        if (moved && data.total_price == null) {
          const car = db.cars.find(c => c.id === next.car_id);
          next.total_price = dayCount(next.start_date, next.end_date) * car.price_per_day;
        }
      }
      if (res === "payments" && !db.rentals.some(r => r.id === next.rental_id)) throw new ApiError("Rental not found.", 404);
      Object.assign(row, next);
      save(db);
      return delay(row);
    },

    async remove(res, id) {
      const db = load();
      id = Number(id);
      // Mirror ON DELETE RESTRICT foreign keys
      if (res === "cars" && db.rentals.some(r => r.car_id === id)) throw new ApiError("Car has rentals and cannot be deleted.", 409);
      if (res === "customers" && db.rentals.some(r => r.customer_id === id)) throw new ApiError("Customer has rentals and cannot be deleted.", 409);
      if (res === "rentals" && db.payments.some(p => p.rental_id === id)) throw new ApiError("Rental has payments and cannot be deleted.", 409);
      const before = db[res].length;
      db[res] = db[res].filter(r => r.id !== id);
      if (db[res].length === before) throw new ApiError("Not found.", 404);
      save(db);
      return delay({ deleted_id: id });
    },

    async availableCars(start, end) {
      const db = load();
      return delay(db.cars.filter(car => car.status !== "Maintenance" && !db.rentals.some(r =>
        r.car_id === car.id && ACTIVE_RENTAL.includes(r.status) && overlaps(start, end, r.start_date, r.end_date))));
    },

    async bookedRanges(carId) {
      const db = load();
      return delay(db.rentals
        .filter(r => r.car_id === Number(carId) && ACTIVE_RENTAL.includes(r.status))
        .map(r => ({ start_date: r.start_date, end_date: r.end_date })));
    },

    // ---- auth (mock) ----
    async login(username, password) {
      const db = load();
      const u = db.users.find(x => x.username === username && x.password === password);
      if (!u) throw new ApiError("Wrong username or password.", 401);
      const c = db.customers.find(x => x.user_id === u.id);
      return delay({ id: u.id, username: u.username, role: u.role, customer_id: c ? c.id : null, name: c ? c.name : u.username });
    },

    async register(data) {
      const db = load();
      if (db.users.some(u => u.username === data.username)) throw new ApiError("Username is taken.", 409);
      if (db.customers.some(c => c.email === data.email)) throw new ApiError("E-mail already registered.", 409);
      if (db.customers.some(c => c.driver_license_no === data.driver_license_no)) throw new ApiError("Driver license number already registered.", 409);
      const user = { id: nextId(db.users), username: data.username, password: data.password, role: "customer" };
      const cust = { id: nextId(db.customers), user_id: user.id, name: data.name, email: data.email, phone: data.phone, driver_license_no: data.driver_license_no };
      db.users.push(user);
      db.customers.push(cust);
      save(db);
      return delay({ id: user.id, username: user.username, role: "customer", customer_id: cust.id, name: cust.name });
    },

    async logout() { return delay({}); }
  };

  /* =======================================================
     LIVE backend (Flask). Response shapes follow README_BACKEND.md.
     Auth + /cars/available + /cars/<id>/booked are still TO BUILD in app.py.
     ======================================================= */
  async function http(method, path, body) {
    const res = await fetch(BASE + path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    });
    let json = {};
    try { json = await res.json(); } catch (e) { /* empty body */ }
    // Flask currently returns {"error": "..."}; accept {"message": "..."} too
    if (!res.ok || json.status === "error") throw new ApiError(json.error || json.message || res.statusText, res.status);
    return json;
  }

  const live = {
    async list(res) { return (await http("GET", `/${res}`))[res]; },
    async get(res, id) { return (await http("GET", `/${res}/${id}`))[SINGULAR[res]]; },
    async create(res, data) { return (await http("POST", `/${res}`, data)).record; },
    async update(res, id, data) { return (await http("PATCH", `/${res}/${id}`, data)).record; },
    async remove(res, id) { return http("DELETE", `/${res}/${id}`); },
    async availableCars(start, end) {
      return (await http("GET", `/cars/available?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)).cars;
    },
    async bookedRanges(carId) { return (await http("GET", `/cars/${carId}/booked`)).ranges; },
    async login(username, password) { return (await http("POST", "/auth/login", { username, password })).user; },
    async register(data) { return (await http("POST", "/auth/register", data)).user; },
    async logout() { return http("POST", "/auth/logout"); },
    // Server-side session check; null when not logged in
    async me() {
      try { return (await http("GET", "/auth/me")).user; }
      catch (e) { if (e.status === 401) return null; throw e; }
    }
  };
  mock.me = async () => undefined;   // mock keeps the session only in the browser

  const impl = MODE === "live" ? live : mock;

  window.API = {
    MODE,
    RESOURCES,
    ApiError,
    dayCount,
    today,
    list: impl.list,
    get: impl.get,
    create: impl.create,
    update: impl.update,
    remove: impl.remove,
    availableCars: impl.availableCars,
    bookedRanges: impl.bookedRanges,
    login: impl.login,
    register: impl.register,
    logout: impl.logout,
    me: impl.me,
    resetMock() { localStorage.removeItem(DB_KEY); }
  };
})();
