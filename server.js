const http = require("node:http");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");

const ROOT = __dirname;
const WEB_ROOT = path.join(ROOT, "web");
const BRIDGE_PATH = path.join(ROOT, "node_bridge.py");
const MAX_BODY_SIZE = 64 * 1024;

const MIME_TYPES = {
  ".css": "text/css",
  ".html": "text/html",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

function parseArgs(argv) {
  const args = {
    host: process.env.HOST || "127.0.0.1",
    port: Number(process.env.PORT || 8000),
  };

  for (let index = 2; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];

    if (current === "--host" && next) {
      args.host = next;
      index += 1;
    } else if (current === "--port" && next) {
      args.port = Number(next);
      index += 1;
    }
  }

  return args;
}

function pythonExecutable() {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }

  const localPython = path.join(ROOT, "myaibot", "Scripts", "python.exe");
  if (fs.existsSync(localPython)) {
    return localPython;
  }

  return "python";
}

function sendJson(response, body, status = 200) {
  const content = JSON.stringify(body);
  response.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(content),
    "Cache-Control": "no-store",
  });
  response.end(content);
}

function sendError(response, status, message) {
  sendJson(response, { error: message }, status);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let totalSize = 0;
    let rejected = false;

    request.on("data", (chunk) => {
      totalSize += chunk.length;
      if (totalSize > MAX_BODY_SIZE) {
        rejected = true;
        reject(new Error("Request is too large."));
        request.destroy();
        return;
      }

      chunks.push(chunk);
    });

    request.on("end", () => {
      if (rejected) {
        return;
      }

      const rawBody = Buffer.concat(chunks).toString("utf8");
      try {
        resolve(rawBody ? JSON.parse(rawBody) : {});
      } catch (error) {
        reject(new Error("Request body must be valid JSON."));
      }
    });

    request.on("error", () => {
      if (!rejected) {
        reject(new Error("Could not read request body."));
      }
    });
  });
}

function runBridge(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable(), [BRIDGE_PATH, action], {
      cwd: ROOT,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (error) => {
      reject(error);
    });

    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `Python bridge exited with code ${code}.`));
        return;
      }

      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(new Error(stderr.trim() || "Python bridge returned invalid JSON."));
      }
    });

    child.stdin.end(JSON.stringify(payload));
  });
}

async function renderIndex(filePath) {
  let content = await fsp.readFile(filePath, "utf8");

  for (const assetName of ["styles.css", "app.js"]) {
    const assetPath = path.join(WEB_ROOT, assetName);
    let version = 0;

    try {
      const stats = await fsp.stat(assetPath);
      version = Math.floor(stats.mtimeMs / 1000);
    } catch (error) {
      version = 0;
    }

    content = content.replaceAll(`"/${assetName}"`, `"/${assetName}?v=${version}"`);
  }

  return Buffer.from(content, "utf8");
}

async function serveFile(request, response) {
  const requestUrl = new URL(request.url, "http://localhost");
  const pathname = decodeURIComponent(requestUrl.pathname);
  const filePath = pathname === "/"
    ? path.join(WEB_ROOT, "index.html")
    : path.resolve(WEB_ROOT, `.${pathname}`);

  const relativePath = path.relative(WEB_ROOT, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    sendError(response, 404, "Not found.");
    return;
  }

  let stats;
  try {
    stats = await fsp.stat(filePath);
  } catch (error) {
    sendError(response, 404, "Not found.");
    return;
  }

  if (!stats.isFile()) {
    sendError(response, 404, "Not found.");
    return;
  }

  const extension = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[extension] || "application/octet-stream";
  const content = path.basename(filePath) === "index.html"
    ? await renderIndex(filePath)
    : await fsp.readFile(filePath);

  response.writeHead(200, {
    "Content-Type": contentType,
    "Content-Length": content.length,
    "Cache-Control": "no-store",
  });
  response.end(content);
}

async function handleApi(request, response, requestUrl) {
  if (request.method === "GET" && requestUrl.pathname === "/api/status") {
    const result = await runBridge("status");
    sendJson(response, result.body, result.status);
    return true;
  }

  if (request.method === "POST" && requestUrl.pathname === "/api/chat") {
    const payload = await readJson(request);
    const result = await runBridge("chat", payload);
    sendJson(response, result.body, result.status);
    return true;
  }

  return false;
}

async function handleRequest(request, response) {
  const requestUrl = new URL(request.url, "http://localhost");

  try {
    if (requestUrl.pathname.startsWith("/api/")) {
      const handled = await handleApi(request, response, requestUrl);
      if (!handled) {
        sendError(response, 404, "Not found.");
      }
      return;
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      sendError(response, 405, "Method not allowed.");
      return;
    }

    await serveFile(request, response);
  } catch (error) {
    const message = error.message || "Request failed.";
    const status = message === "Request is too large." || message === "Request body must be valid JSON."
      ? 400
      : 500;
    sendError(response, status, status === 500 ? "Local server failed." : message);
  }
}

const args = parseArgs(process.argv);

function listen(port, attempts = 0) {
  const server = http.createServer(handleRequest);

  function onError(error) {
    if (error.code === "EADDRINUSE" && attempts < 10) {
      const nextPort = port + 1;
      console.log(`Port ${port} is busy; trying ${nextPort}.`);
      listen(nextPort, attempts + 1);
      return;
    }

    console.error(error);
    process.exit(1);
  }

  server.once("error", onError);
  server.listen(port, args.host, () => {
    server.off("error", onError);
    console.log(`AI Bot UI running with Node at http://${args.host}:${port}`);
  });
}

listen(args.port);
