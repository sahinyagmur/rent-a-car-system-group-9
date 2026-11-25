// Frontend preview server (no backend needed; js/api.js must be in "mock" mode).
// Usage, from the repository root:   node tools/dev-server.js   ->  http://localhost:5500
//
// Routing rules (the Flask backend should behave the same way):
//   /            -> index.html
//   /admin       -> redirect to /admin/
//   /admin/      -> admin/index.html (which opens the dashboard)
//   /cars        -> cars.html          (".html" may be left out)
//   anything else that doesn't exist -> 404.html with status 404
const http = require("http");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = Number(process.env.PORT || process.argv[2] || 5500);
const types = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon"
};

const isFile = p => { try { return fs.statSync(p).isFile(); } catch (e) { return false; } };
const isDir = p => { try { return fs.statSync(p).isDirectory(); } catch (e) { return false; } };

function send(res, status, file) {
  res.writeHead(status, { "Content-Type": types[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}

http.createServer((req, res) => {
  let urlPath;
  try { urlPath = decodeURIComponent(new URL(req.url, "http://x").pathname); }
  catch (e) { res.writeHead(400); return res.end("Bad request"); }

  const target = path.normalize(path.join(root, urlPath));
  if (!target.startsWith(root)) { res.writeHead(403); return res.end("Forbidden"); }

  // Never serve backend code, git data or dotfiles
  const rel = path.relative(root, target).split(path.sep);
  if (rel[0] === "backend" || rel[0] === "tools" || rel.some(part => part.startsWith("."))) {
    return send(res, 404, path.join(root, "404.html"));
  }

  if (isDir(target)) {
    if (!urlPath.endsWith("/")) { res.writeHead(301, { Location: urlPath + "/" }); return res.end(); }
    const index = path.join(target, "index.html");
    if (isFile(index)) return send(res, 200, index);
  } else if (isFile(target)) {
    return send(res, 200, target);
  } else if (isFile(target + ".html")) {
    return send(res, 200, target + ".html");
  }
  send(res, 404, path.join(root, "404.html"));
}).listen(port, () => console.log(`Frontend preview on http://localhost:${port}`));
