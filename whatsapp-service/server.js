// WhatsApp Web link for NZ Job Autopilot.
// Shows a QR code to link your WhatsApp, then sends the app's updates to your own number only.
// Listens on 127.0.0.1 only. Uses Baileys (an unofficial WhatsApp Web client): keep volume low.

import { rm } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import makeWASocket, { DisconnectReason, useMultiFileAuthState } from "@whiskeysockets/baileys";
import pino from "pino";
import QRCode from "qrcode";

const HOST = "127.0.0.1";
const PORT = Number(process.env.WA_PORT || 3010);
const TOKEN = process.env.WA_TOKEN || "";
// Numbers this service may message. Empty means only the linked account's own number.
const ALLOWED_TO = (process.env.WA_ALLOWED_TO || "")
  .split(",")
  .map((n) => n.replace(/\D/g, ""))
  .filter(Boolean);
const AUTH_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "auth");
const MAX_BODY_BYTES = 20_000;

const status = { state: "starting", qr: null, me: null, error: null };
let sock = null;
let restartTimer = null;

function restart(delayMs) {
  clearTimeout(restartTimer);
  restartTimer = setTimeout(() => start().catch(fail), delayMs);
}

function fail(error) {
  status.state = "error";
  status.error = String(error?.message || error);
  console.error("WhatsApp link failed:", status.error);
  restart(10_000);
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  sock = makeWASocket({ auth: state, logger: pino({ level: "silent" }) });
  sock.ev.on("creds.update", saveCreds);
  sock.ev.on("connection.update", async (update) => {
    if (update.qr) {
      status.state = "qr";
      status.qr = await QRCode.toDataURL(update.qr, { margin: 1, width: 264 });
    }
    if (update.connection === "open") {
      status.state = "connected";
      status.qr = null;
      status.error = null;
      status.me = (sock.user?.id || "").split(":")[0].split("@")[0] || null;
      console.log("WhatsApp linked.");
    }
    if (update.connection === "close") {
      const code = update.lastDisconnect?.error?.output?.statusCode;
      status.qr = null;
      if (code === DisconnectReason.loggedOut) {
        // Unlinked from the phone or logged out here: forget the session and show a new QR.
        status.state = "logged_out";
        status.me = null;
        await rm(AUTH_DIR, { recursive: true, force: true });
        restart(1_000);
      } else {
        status.state = "reconnecting";
        restart(2_000);
      }
    }
  });
}

function send(response, code, body) {
  const data = JSON.stringify(body);
  response.writeHead(code, { "Content-Type": "application/json" });
  response.end(data);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("too large"));
        request.destroy();
      } else {
        chunks.push(chunk);
      }
    });
    request.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"));
      } catch {
        reject(new Error("not JSON"));
      }
    });
  });
}

async function handleSend(request, response) {
  let body;
  try {
    body = await readJson(request);
  } catch (error) {
    return send(response, 400, { error: `Bad request: ${error.message}` });
  }
  const to = String(body.to || "").replace(/\D/g, "");
  const text = String(body.message || "").trim();
  if (!to || !text) return send(response, 400, { error: "Send JSON with 'to' and 'message'." });
  if (status.state !== "connected") {
    return send(response, 503, {
      error: "WhatsApp is not linked. Scan the QR code on the app's Settings page.",
    });
  }
  const allowed = ALLOWED_TO.length ? ALLOWED_TO : [status.me];
  if (!allowed.includes(to)) {
    return send(response, 403, {
      error: "This service only messages your own number. Set WA_ALLOWED_TO to allow another.",
    });
  }
  try {
    await sock.sendMessage(`${to}@s.whatsapp.net`, { text });
    return send(response, 200, { ok: true });
  } catch (error) {
    return send(response, 502, { error: `WhatsApp did not accept the message: ${error.message}` });
  }
}

const server = http.createServer(async (request, response) => {
  if (TOKEN && request.headers.authorization !== `Bearer ${TOKEN}`) {
    return send(response, 401, { error: "Wrong or missing token." });
  }
  const url = new URL(request.url, `http://${HOST}`);
  if (request.method === "GET" && url.pathname === "/status") {
    return send(response, 200, status);
  }
  if (request.method === "POST" && url.pathname === "/send") {
    return handleSend(request, response);
  }
  if (request.method === "POST" && url.pathname === "/logout") {
    try {
      await sock?.logout();
    } catch {
      await rm(AUTH_DIR, { recursive: true, force: true });
      restart(1_000);
    }
    return send(response, 200, { ok: true });
  }
  return send(response, 404, { error: "Not found." });
});

server.listen(PORT, HOST, () => {
  console.log(`WhatsApp service on http://${HOST}:${PORT} (status, send, logout)`);
  start().catch(fail);
});
