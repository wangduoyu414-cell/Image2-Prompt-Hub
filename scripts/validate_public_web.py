"""Fresh synthetic-API, production-Next, and real-browser evidence for TASK-0015."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "apps" / "web"
RUNTIME_ENV = "IMAGE2_WEB_RUNTIME_ROOT"
EVIDENCE_ENV = "IMAGE2_WEB_EVIDENCE_DIR"
PROMPT = "Create a precise glass sculpture under soft studio light.\nKeep the original line break exactly."
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+PqW1YQAAAABJRU5ErkJggg=="
)
GOOD_HASH = hashlib.sha256(PNG_BYTES).hexdigest()
INPUT_HASH = hashlib.sha256(b"synthetic-input-image").hexdigest()
LINK_HASH = hashlib.sha256(b"link-only-private-image").hexdigest()
BROKEN_HASH = hashlib.sha256(b"broken-image-route").hexdigest()
GOOD_KEY = "a" * 64
LINK_KEY = "b" * 64
BROKEN_KEY = "c" * 64


class ValidationFailure(RuntimeError):
    """A fail-closed result for the task-owned browser integration harness."""


def _must_be_external(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    workspace = REPO_ROOT.resolve()
    if resolved == workspace or workspace in resolved.parents:
        raise ValidationFailure(f"{label} must be outside the workspace")
    return resolved


def _runtime_root() -> Path:
    raw = os.environ.get(RUNTIME_ENV)
    if not raw:
        raise ValidationFailure(f"{RUNTIME_ENV} is required")
    root = _must_be_external(Path(raw), RUNTIME_ENV)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _evidence_root(runtime_root: Path) -> Path:
    raw = os.environ.get(EVIDENCE_ENV)
    root = _must_be_external(Path(raw), EVIDENCE_ENV) if raw else runtime_root / "browser-evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _asset(content_sha256: str, *, role: str, ordinal: int) -> dict[str, object]:
    return {
        "content_sha256": content_sha256,
        "media_type": "image/png",
        "byte_size": len(PNG_BYTES),
        "ordinal": ordinal,
        "role": role,
        "source_path": f"synthetic/{content_sha256[:12]}.png",
        "source_url": f"https://source.example.invalid/assets/{content_sha256}",
        "source_location": {"path": f"synthetic/{content_sha256[:12]}.png"},
    }


def _member(*, policy: str, source_id: str, output_hash: str, with_input: bool) -> dict[str, object]:
    return {
        "prompt": {
            "raw_text": PROMPT,
            "provenance": {
                "source_path": "synthetic/prompt.md",
                "source_url": "https://source.example.invalid/prompt.md",
            },
        },
        "inputs": [_asset(INPUT_HASH, role="input_reference", ordinal=0)] if with_input else [],
        "outputs": [_asset(output_hash, role="output_primary", ordinal=0)],
        "source": {
            "source_id": source_id,
            "repository_id": f"synthetic/{source_id}",
            "revision_sha": "1" * 40,
            "source_path": "synthetic/prompt.md",
            "source_url": "https://source.example.invalid/prompt.md",
        },
        "rights": {
            "repository_license": "CC-BY-4.0",
            "prompt_rights": "approved",
            "asset_rights": "approved",
            "author": "Synthetic Author",
            "original_url": "https://source.example.invalid/original",
            "evidence_url": "https://source.example.invalid/rights",
            "reviewer": "synthetic-reviewer",
            "reviewed_at": "2026-08-08T00:00:00+00:00",
            "display_policy": policy,
        },
        "model": {
            "source_claim": {
                "evidence_status": "source_claimed",
                "model_raw": "gpt-image-2",
                "parameters_raw": {"size": "1024x1024"},
            },
            "warning": "source_claimed_not_officially_verified",
        },
        "taxonomy": [
            {
                "taxonomy_version": "taxonomy-v1",
                "classifier_version": "synthetic-v1",
                "tag_value": "studio",
                "tag_source": "synthetic",
                "confidence": 1.0,
            }
        ],
    }


def _publication(case_count: int) -> dict[str, object]:
    return {
        "state": "active",
        "publication": {
            "content_digest": "d" * 64,
            "included_count": case_count,
            "excluded_count": 0,
            "reason_counts": {},
            "completed_at": "2026-08-08T00:00:00+00:00",
        },
        "case_count": case_count,
    }


def _summary(
    canonical_key: str,
    *,
    prompt_preview: str,
    source_id: str,
    policy: str,
    tag: str = "studio",
    reference: bool = True,
) -> dict[str, object]:
    return {
        "canonical_key": canonical_key,
        "prompt_preview": prompt_preview,
        "source_ids": [source_id],
        "display_policies": [policy],
        "tags": [tag],
        "has_reference": reference,
        "member_count": 1,
    }


class SyntheticApi:
    def __init__(self) -> None:
        self.asset_requests: list[str] = []
        self.list_queries: list[dict[str, list[str]]] = []
        self.lock = threading.Lock()
        self.good_member = _member(policy="mirror_allowed", source_id="source-a", output_hash=GOOD_HASH, with_input=True)
        self.link_member = _member(policy="link_only", source_id="source-link", output_hash=LINK_HASH, with_input=False)
        self.broken_member = _member(policy="mirror_allowed", source_id="source-broken", output_hash=BROKEN_HASH, with_input=True)

    def list_payload(self, query: dict[str, list[str]]) -> tuple[int, dict[str, object]]:
        with self.lock:
            self.list_queries.append({key: list(values) for key, values in query.items()})
        requested_q = query.get("q", [""])[0]
        if requested_q == "__api_error__":
            return 503, {"error": {"code": "publication_unavailable", "message": "synthetic unavailable"}}
        if requested_q == "__invalid__":
            return 200, {"publication": _publication(0), "total": "not-a-number"}
        if requested_q == "__empty__":
            return 200, {
                "publication": _publication(0),
                "total": 0,
                "page": 1,
                "page_size": 12,
                "cases": [],
                "facets": {"sources": [], "display_policies": [], "tags": [], "has_reference": []},
            }
        if requested_q == "__broken__":
            cases = [_summary(BROKEN_KEY, prompt_preview="Broken image fallback case", source_id="source-broken", policy="mirror_allowed")]
        elif query.get("source", [""])[0] == "source-a" or requested_q.lower() == "glass":
            cases = [_summary(GOOD_KEY, prompt_preview="Create a precise glass sculpture under soft studio light.", source_id="source-a", policy="mirror_allowed")]
        else:
            cases = [
                _summary(GOOD_KEY, prompt_preview="Create a precise glass sculpture under soft studio light.", source_id="source-a", policy="mirror_allowed"),
                _summary(LINK_KEY, prompt_preview="Link-only historic artwork.", source_id="source-link", policy="link_only", tag="history", reference=False),
            ]
        return 200, {
            "publication": _publication(len(cases)),
            "total": len(cases),
            "page": int(query.get("page", ["1"])[0]),
            "page_size": int(query.get("page_size", ["12"])[0]),
            "cases": cases,
            "facets": {
                "sources": [{"value": "source-a", "count": 1}, {"value": "source-link", "count": 1}],
                "display_policies": [{"value": "mirror_allowed", "count": 1}, {"value": "link_only", "count": 1}],
                "tags": [{"value": "studio", "count": 1}, {"value": "history", "count": 1}],
                "has_reference": [{"value": True, "count": 1}, {"value": False, "count": 1}],
            },
        }

    def detail_payload(self, key: str) -> tuple[int, dict[str, object]]:
        members = {GOOD_KEY: [self.good_member], LINK_KEY: [self.link_member], BROKEN_KEY: [self.broken_member]}.get(key)
        if members is None:
            return 404, {"error": {"code": "case_not_found", "message": "synthetic missing"}}
        return 200, {
            "publication": _publication(len(members)),
            "canonical_key": key,
            "member_count": len(members),
            "representative": members[0],
            "members": members,
        }


def _handler(api: SyntheticApi) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def _json(self, status: int, payload: Mapping[str, object]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/v1/cases":
                status, payload = api.list_payload(parse_qs(parsed.query, keep_blank_values=True))
                self._json(status, payload)
                return
            if parsed.path.startswith("/api/v1/cases/"):
                status, payload = api.detail_payload(parsed.path.rsplit("/", 1)[-1])
                self._json(status, payload)
                return
            if parsed.path.startswith("/api/v1/assets/"):
                content_sha256 = parsed.path.rsplit("/", 1)[-1]
                with api.lock:
                    api.asset_requests.append(content_sha256)
                if content_sha256 in {GOOD_HASH, INPUT_HASH}:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(PNG_BYTES)))
                    self.end_headers()
                    self.wfile.write(PNG_BYTES)
                    return
                if content_sha256 == BROKEN_HASH:
                    self._json(404, {"error": {"code": "asset_not_found", "message": "synthetic unavailable"}})
                    return
                self._json(404, {"error": {"code": "asset_not_found", "message": "synthetic missing"}})
                return
            self._json(404, {"error": {"code": "not_found", "message": "synthetic missing"}})

    return Handler


def _serve_synthetic() -> tuple[ThreadingHTTPServer, threading.Thread, SyntheticApi, str]:
    api = SyntheticApi()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(api))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, api, f"http://{host}:{port}"


def _node_command() -> tuple[str, Path]:
    node = shutil.which("node")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not node or not npm:
        raise ValidationFailure("Node and npm are required for public-web validation")
    npm_cli = Path(npm).resolve().parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not npm_cli.is_file():
        raise ValidationFailure("npm CLI path is unavailable")
    return node, npm_cli


def _run(command: list[str], *, cwd: Path, env: Mapping[str, str], timeout: int, label: str) -> None:
    try:
        completed = subprocess.run(command, cwd=str(cwd), env=dict(env), capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationFailure(f"{label} did not complete") from exc
    if completed.returncode != 0:
        raise ValidationFailure(f"{label} failed")


def _copy_web_workspace(target: Path) -> None:
    ignored = {"node_modules", ".next", "screenshots", "logs"}

    def ignore(_: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(WEB_ROOT, target, ignore=ignore)


def _browser_executable() -> Path:
    configured = os.environ.get("IMAGE2_WEB_BROWSER_EXECUTABLE")
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return _must_be_external(candidate, "browser executable")
    raise ValidationFailure("a local Chromium-family browser is required")


def _wait_for_http(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValidationFailure("Next production server exited before becoming ready")
        try:
            with urlopen(url, timeout=3) as response:  # nosec B310 -- fixed local loopback URL.
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise ValidationFailure("Next production server did not become ready")


def _stop_process(process: subprocess.Popen[str] | None) -> bool:
    if process is None or process.poll() is not None:
        return True
    try:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, text=True, timeout=30, check=False)
        process.wait(timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return process.poll() is not None


BROWSER_SMOKE = r'''
const fs = require("node:fs");
const { chromium } = require("playwright-core");

const [baseUrl, browserPath, evidenceDir, prompt, goodHash, linkHash, brokenHash] = process.argv.slice(2);
const fail = (message) => { throw new Error(message); };
const expect = (condition, message) => { if (!condition) fail(message); };

(async () => {
  fs.mkdirSync(evidenceDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseUrl });
  await context.addInitScript(() => {
    window.__image2CopiedPrompt = null;
    window.__image2ForceClipboardFailure = false;
    try {
      const clipboard = navigator.clipboard;
      const original = clipboard && clipboard.writeText && clipboard.writeText.bind(clipboard);
      if (original) {
        Object.defineProperty(clipboard, "writeText", {
          configurable: true,
          value: async (text) => {
            if (window.__image2ForceClipboardFailure) {
              throw new Error("synthetic clipboard denial");
            }
            window.__image2CopiedPrompt = text;
            return original(text);
          },
        });
      }
    } catch (_) {
      // The browser still exercises the native write path; the assertion below will fail closed if it is not observed.
    }
  });
  const page = await context.newPage();
  const unexpectedConsole = [];
  const assetRequests = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes(brokenHash)) return;
    if (text === "Failed to load resource: the server responded with a status of 404 (Not Found)") {
      return;
    }
    unexpectedConsole.push(text);
  });
  page.on("pageerror", (error) => unexpectedConsole.push(String(error)));
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/backend/assets/")) assetRequests.push(url);
  });
  try {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    expect((await page.getByRole("heading", { name: "可浏览的原始 Prompt 案例" }).count()) === 1, "catalog heading is missing");
    expect((await page.locator(".case-card").count()) === 2, "canonical cards are missing");
    expect((await page.locator("img").count()) === 1, "link_only card constructed an image request");
    expect(!assetRequests.some((url) => url.includes(linkHash)), "link_only requested a private asset route");
    await page.screenshot({ path: `${evidenceDir}/catalog-desktop.png`, fullPage: true });

    await page.locator('input[name="q"]').fill("glass");
    await page.locator('select[name="source"]').selectOption("source-a");
    await page.locator('select[name="display_policy"]').selectOption("mirror_allowed");
    await page.locator('select[name="tag"]').selectOption("studio");
    await page.locator('select[name="has_reference_input"]').selectOption("true");
    await Promise.all([
      page.waitForURL(/q=glass/),
      page.getByRole("button", { name: "应用筛选" }).click(),
    ]);
    await page.waitForLoadState("networkidle");
    const filtered = new URL(page.url());
    expect(filtered.searchParams.get("q") === "glass", "search URL state was not preserved");
    expect(filtered.searchParams.get("source") === "source-a", "source URL state was not preserved");
    expect(filtered.searchParams.get("has_reference_input") === "true", "reference URL state was not preserved");
    expect((await page.locator(".case-card").count()) === 1, "filtered canonical list was not rendered");

    await Promise.all([
      page.waitForURL(/\/cases\/[0-9a-f]{64}$/),
      page.locator('.case-card a[href^="/cases/"]').first().click(),
    ]);
    await page.waitForLoadState("networkidle");
    expect((await page.locator("#raw-prompt-title").count()) === 1, "detail prompt heading is missing");
    const renderedPrompt = await page.locator('pre[aria-label="原始 Prompt"]').textContent();
    expect(renderedPrompt === prompt, "detail changed the raw prompt text");
    await page.getByRole("button", { name: "复制原始 Prompt" }).click();
    await page.getByRole("status").filter({ hasText: "已复制原始 Prompt。" }).waitFor();
    const clipboardArgument = await page.evaluate(() => window.__image2CopiedPrompt);
    expect(clipboardArgument === prompt, "clipboard content differs from raw prompt");
    await page.evaluate(() => { window.__image2ForceClipboardFailure = true; });
    await page.getByRole("button", { name: "复制原始 Prompt" }).click();
    await page.getByRole("status").filter({ hasText: "无法复制原始 Prompt。请手动选择并复制。" }).waitFor();
    await page.evaluate(() => { window.__image2ForceClipboardFailure = false; });
    const imageReady = await page.locator("img").first().evaluate((image) => image.complete && image.naturalWidth > 0);
    expect(imageReady, "authorized image did not load through the same-origin rewrite");
    await page.screenshot({ path: `${evidenceDir}/detail-copy.png`, fullPage: true });

    await page.goto(`${baseUrl}/?q=__broken__`, { waitUntil: "networkidle" });
    await page.getByTestId("asset-placeholder").filter({ hasText: "图片暂不可用" }).waitFor();
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${evidenceDir}/image-fallback.png`, fullPage: true });

    await page.goto(`${baseUrl}/?q=__empty__`, { waitUntil: "networkidle" });
    expect((await page.getByRole("heading", { name: "尚无可公开案例" }).count()) === 1, "empty state is missing");
    await page.screenshot({ path: `${evidenceDir}/empty.png`, fullPage: true });

    await page.goto(`${baseUrl}/?q=__api_error__`, { waitUntil: "networkidle" });
    expect((await page.getByRole("heading", { name: "目录暂时不可用" }).count()) === 1, "safe API error state is missing");
    expect(!(await page.locator("body").innerText()).includes("127.0.0.1"), "API error exposed an internal endpoint");

    await page.goto(`${baseUrl}/?q=__invalid__`, { waitUntil: "networkidle" });
    expect((await page.getByRole("heading", { name: "目录暂时不可用" }).count()) === 1, "safe invalid response state is missing");
    expect(!(await page.locator("body").innerText()).includes("127.0.0.1"), "invalid response exposed an internal endpoint");

    await page.goto(`${baseUrl}/cases/${"f".repeat(64)}`, { waitUntil: "networkidle" });
    expect((await page.getByRole("heading", { name: "找不到该案例" }).count()) === 1, "missing-detail state is missing");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.keyboard.press("Tab");
    const skipFocused = await page.locator(".skip-link").evaluate((node) => document.activeElement === node);
    expect(skipFocused, "skip link is not keyboard reachable");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(!overflow, "mobile layout overflows horizontally");
    await page.screenshot({ path: `${evidenceDir}/catalog-mobile.png`, fullPage: true });

    expect(assetRequests.some((url) => url.includes(goodHash)), "authorized asset route was not requested");
    expect(!assetRequests.some((url) => url.includes(linkHash)), "link_only asset route was requested");
    expect(unexpectedConsole.length === 0, "unexpected browser console errors");
    console.log(JSON.stringify({
      status: "passed",
      screenshots: 5,
      authorized_asset_request: true,
      link_only_asset_request: false,
      copy_exact: true,
      copy_denial_safe: true,
      invalid_response_safe: true,
      mobile_keyboard: true,
    }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  const known = new Set([
    "catalog heading is missing", "canonical cards are missing", "link_only card constructed an image request",
    "link_only requested a private asset route", "search URL state was not preserved", "source URL state was not preserved",
    "reference URL state was not preserved", "filtered canonical list was not rendered", "detail prompt heading is missing",
    "detail changed the raw prompt text", "clipboard content differs from raw prompt", "authorized image did not load through the same-origin rewrite",
    "empty state is missing", "safe API error state is missing", "API error exposed an internal endpoint",
    "safe invalid response state is missing", "invalid response exposed an internal endpoint",
    "missing-detail state is missing", "skip link is not keyboard reachable", "mobile layout overflows horizontally",
    "authorized asset route was not requested", "link_only asset route was requested", "unexpected browser console errors"
  ]);
  const errorCode = error && known.has(String(error.message)) ? String(error.message) : "browser smoke did not complete";
  console.log(JSON.stringify({ status: "failed", error_code: errorCode }));
  process.exitCode = 1;
});
'''


def _run_browser(*, target: Path, web_url: str, browser: Path, evidence: Path, env: Mapping[str, str]) -> dict[str, object]:
    script = target / "browser-smoke.cjs"
    script.write_text(BROWSER_SMOKE, encoding="utf-8")
    node, _ = _node_command()
    completed = subprocess.run(
        [node, str(script), web_url, str(browser), str(evidence), PROMPT, GOOD_HASH, LINK_HASH, BROKEN_HASH],
        cwd=str(target),
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValidationFailure("real browser smoke did not produce structured evidence") from exc
    if completed.returncode != 0:
        reason = payload.get("error_code") if isinstance(payload, dict) else None
        if not isinstance(reason, str):
            reason = "browser smoke did not complete"
        raise ValidationFailure(f"real browser smoke failed: {reason}")
    if not isinstance(payload, dict) or payload.get("status") != "passed":
        raise ValidationFailure("real browser smoke did not pass")
    return payload


def run() -> dict[str, object]:
    if not WEB_ROOT.is_dir():
        raise ValidationFailure("apps/web is required")
    runtime = _runtime_root()
    evidence = _evidence_root(runtime) / f"live-{uuid.uuid4().hex}"
    evidence.mkdir(parents=True, exist_ok=False)
    work_root = Path(tempfile.mkdtemp(prefix="public-web-", dir=runtime))
    web_target = work_root / "web"
    server: ThreadingHTTPServer | None = None
    server_thread: threading.Thread | None = None
    next_process: subprocess.Popen[str] | None = None
    cleanup_ok = False
    try:
        _copy_web_workspace(web_target)
        server, server_thread, api, api_url = _serve_synthetic()
        node, npm_cli = _node_command()
        command_env = {
            **os.environ,
            "IMAGE2_API_INTERNAL_BASE_URL": api_url,
            "NPM_CONFIG_CACHE": str(runtime / "npm-cache"),
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        _run([node, str(npm_cli), "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=web_target, env=command_env, timeout=300, label="external web dependency install")
        _run([node, str(npm_cli), "run", "build"], cwd=web_target, env=command_env, timeout=300, label="production Next build")
        port = _free_port()
        next_process = subprocess.Popen(
            [node, str(npm_cli), "run", "start", "--", "--hostname", "127.0.0.1", "--port", str(port)],
            cwd=str(web_target),
            env=command_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        web_url = f"http://127.0.0.1:{port}"
        _wait_for_http(web_url, next_process)
        browser_result = _run_browser(target=web_target, web_url=web_url, browser=_browser_executable(), evidence=evidence, env=command_env)
        with api.lock:
            asset_requests = list(api.asset_requests)
            list_queries = list(api.list_queries)
        if LINK_HASH in asset_requests:
            raise ValidationFailure("link_only requested a synthetic private asset route")
        if GOOD_HASH not in asset_requests:
            raise ValidationFailure("authorized asset did not reach the API rewrite")
        if not any(query.get("q") == ["glass"] and query.get("source") == ["source-a"] for query in list_queries):
            raise ValidationFailure("URL filter state did not reach the server API request")
        return {
            "status": "passed",
            "topology": "synthetic API -> production Next -> local Chromium",
            "browser": browser_result,
            "api": {
                "canonical_cases": 2,
                "authorized_asset_request": True,
                "link_only_asset_request": False,
                "filter_query_forwarded": True,
            },
            "evidence": {"screenshots": 5, "directory": str(evidence)},
        }
    finally:
        next_clean = _stop_process(next_process)
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=15)
        if work_root.exists():
            shutil.rmtree(work_root)
        cleanup_ok = next_clean and not work_root.exists()
        if not cleanup_ok:
            raise ValidationFailure("temporary Next runtime cleanup did not complete")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the production public Next.js catalog against a synthetic API.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run()
    except Exception:
        payload = {"status": "failed", "error_type": "ValidationFailure", "error": "public web validator did not complete"}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
