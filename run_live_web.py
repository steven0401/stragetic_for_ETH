from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import config
from live import monitoring


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_status() -> dict[str, Any]:
    signals = monitoring.read_csv_records(monitoring.DAILY_SIGNAL_CSV)
    equity = monitoring.read_csv_records(monitoring.EQUITY_CSV)
    ledger = monitoring.read_json(monitoring.TRADE_LEDGER_FILE, [])
    live_state = monitoring.read_json(monitoring.TRADE_STATE_FILE, {"positions": []})

    if equity:
        equity_curve = [
            {"timestamp": r.get("timestamp", ""), "equity": _float(r.get("equity"))}
            for r in equity
        ]
    else:
        equity_curve = [{"timestamp": "start", "equity": config.INITIAL_EQUITY}]

    latest_signal = signals[-1] if signals else {}
    latest_equity = equity_curve[-1]["equity"] if equity_curve else config.INITIAL_EQUITY
    positions = live_state.get("positions", [])

    return {
        "latest_signal": latest_signal,
        "latest_equity": latest_equity,
        "active_positions": positions,
        "position_count": len(positions),
        "signals": signals[-80:],
        "equity_curve": equity_curve[-300:],
        "ledger": ledger[-80:] if isinstance(ledger, list) else [],
        "settings": {
            "symbol": ",".join(config.LIVE_SYMBOLS),
            "threshold": config.LITERATURE_LONG_DAILY_THRESHOLD,
            "risk_pct": config.LITERATURE_LONG_DAILY_RISK_PCT,
            "max_active_per_symbol": config.LIVE_MAX_ACTIVE_PER_SYMBOL,
            "testnet": config.BYBIT_TESTNET,
        },
    }


def _html() -> bytes:
    return """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ETH 策略監控</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f1217;
      --panel: #171b22;
      --panel-2: #1f2530;
      --text: #eef2f7;
      --muted: #8c98a8;
      --line: #2b3340;
      --green: #41d18d;
      --red: #ff6b6b;
      --amber: #ffbc42;
      --blue: #65a9ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      border-bottom: 1px solid var(--line);
      background: #12161d;
    }
    h1 { font-size: 18px; margin: 0; font-weight: 650; }
    main { max-width: 1320px; margin: 0 auto; padding: 24px; }
    .status { color: var(--muted); font-size: 13px; }
    .grid { display: grid; gap: 14px; }
    .metrics { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .two { grid-template-columns: minmax(0, 1.5fr) minmax(360px, .8fr); margin-top: 16px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .metric { padding: 16px; min-height: 92px; }
    .label { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .value { font-size: 26px; line-height: 1.1; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .sub { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .panel h2 { font-size: 14px; font-weight: 650; margin: 0; padding: 14px 16px; border-bottom: 1px solid var(--line); }
    .chart-wrap { padding: 14px; height: 360px; }
    svg { width: 100%; height: 100%; display: block; }
    .table-wrap { overflow: auto; max-height: 360px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
    th { color: var(--muted); font-weight: 600; background: var(--panel-2); position: sticky; top: 0; }
    .pill { display: inline-flex; min-width: 64px; justify-content: center; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 650; }
    .ok { background: rgba(65, 209, 141, .12); color: var(--green); }
    .bad { background: rgba(255, 107, 107, .12); color: var(--red); }
    .warn { background: rgba(255, 188, 66, .14); color: var(--amber); }
    .empty { padding: 28px 16px; color: var(--muted); }
    .section { margin-top: 16px; }
    @media (max-width: 980px) {
      header { padding: 0 18px; }
      main { padding: 16px; }
      .metrics, .two { grid-template-columns: 1fr; }
      .value { font-size: 22px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ETH 策略監控</h1>
    <div class="status" id="refreshStatus">loading...</div>
  </header>
  <main>
    <section class="grid metrics">
      <div class="panel metric"><div class="label">帳戶權益</div><div class="value" id="equity">-</div><div class="sub" id="env">-</div></div>
      <div class="panel metric"><div class="label">最新模型機率</div><div class="value" id="prob">-</div><div class="sub" id="threshold">-</div></div>
      <div class="panel metric"><div class="label">策略訊號</div><div class="value" id="signal">-</div><div class="sub" id="signalTime">-</div></div>
      <div class="panel metric"><div class="label">目前持倉</div><div class="value" id="positions">-</div><div class="sub" id="maxActive">-</div></div>
      <div class="panel metric"><div class="label">最新收盤價</div><div class="value" id="close">-</div><div class="sub" id="scores">-</div></div>
    </section>

    <section class="grid two">
      <div class="panel">
        <h2>資金曲線</h2>
        <div class="chart-wrap"><svg id="equityChart" role="img" aria-label="資金曲線"></svg></div>
      </div>
      <div class="panel">
        <h2>目前持倉</h2>
        <div class="table-wrap"><table id="positionTable"></table></div>
      </div>
    </section>

    <section class="grid two section">
      <div class="panel">
        <h2>日K訊號紀錄</h2>
        <div class="table-wrap"><table id="signalTable"></table></div>
      </div>
      <div class="panel">
        <h2>交易紀錄</h2>
        <div class="table-wrap"><table id="ledgerTable"></table></div>
      </div>
    </section>
  </main>
  <script>
    const money = n => Number(n || 0).toLocaleString(undefined, {maximumFractionDigits: 2});
    const num = n => Number(n || 0).toFixed(4);
    const text = v => (v === undefined || v === null || v === "") ? "-" : String(v);

    function drawLine(svg, points, color) {
      svg.innerHTML = "";
      const width = svg.clientWidth || 800;
      const height = svg.clientHeight || 320;
      const pad = 36;
      if (!points.length) return;
      const ys = points.map(p => Number(p.equity || 0));
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const span = Math.max(maxY - minY, 1);
      const stepX = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;
      const coords = points.map((p, i) => {
        const x = pad + i * stepX;
        const y = height - pad - ((Number(p.equity || 0) - minY) / span) * (height - pad * 2);
        return [x, y];
      });
      const path = coords.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
      svg.insertAdjacentHTML("beforeend", `<line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}" stroke="#2b3340"/>`);
      svg.insertAdjacentHTML("beforeend", `<line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height-pad}" stroke="#2b3340"/>`);
      svg.insertAdjacentHTML("beforeend", `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.5"/>`);
      svg.insertAdjacentHTML("beforeend", `<text x="${pad}" y="${pad-10}" fill="#8c98a8" font-size="12">${money(maxY)}</text>`);
      svg.insertAdjacentHTML("beforeend", `<text x="${pad}" y="${height-10}" fill="#8c98a8" font-size="12">${money(minY)}</text>`);
    }

    function table(el, cols, rows, emptyText) {
      if (!rows.length) {
        el.innerHTML = `<tr><td class="empty">${emptyText}</td></tr>`;
        return;
      }
      el.innerHTML = "<thead><tr>" + cols.map(c => `<th>${c.label}</th>`).join("") + "</tr></thead>" +
        "<tbody>" + rows.map(r => "<tr>" + cols.map(c => `<td>${c.render ? c.render(r) : text(r[c.key])}</td>`).join("") + "</tr>").join("") + "</tbody>";
    }

    async function load() {
      const res = await fetch("/api/status", {cache: "no-store"});
      const data = await res.json();
      const s = data.latest_signal || {};
      const settings = data.settings || {};

      document.getElementById("equity").textContent = "$" + money(data.latest_equity);
      document.getElementById("env").textContent = settings.testnet ? "Testnet" : "Mainnet";
      document.getElementById("prob").textContent = s.probability !== undefined ? num(s.probability) : "-";
      document.getElementById("threshold").textContent = "進場門檻 " + text(settings.threshold);
      document.getElementById("signal").innerHTML = s.signal === true || s.signal === "True" ? '<span class="pill ok">進場</span>' : '<span class="pill warn">等待</span>';
      document.getElementById("signalTime").textContent = text(s.timestamp);
      document.getElementById("positions").textContent = data.position_count || 0;
      document.getElementById("maxActive").textContent = "單幣最多持倉 " + text(settings.max_active_per_symbol);
      document.getElementById("close").textContent = s.close !== undefined ? money(s.close) : "-";
      document.getElementById("scores").textContent = "多頭分數 " + text(s.bull_score) + " / 風險分數 " + text(s.risk_score);
      document.getElementById("refreshStatus").textContent = "更新時間 " + new Date().toLocaleTimeString();

      drawLine(document.getElementById("equityChart"), data.equity_curve || [], "#65a9ff");

      table(document.getElementById("positionTable"), [
        {label:"幣種", key:"symbol"},
        {label:"數量", key:"qty"},
        {label:"進場價", key:"entry_price"},
        {label:"停損", key:"sl_price"},
        {label:"止盈", key:"tp_price"},
        {label:"最晚出場", key:"exit_time"}
      ], data.active_positions || [], "目前沒有持倉");

      const signals = (data.signals || []).slice().reverse();
      table(document.getElementById("signalTable"), [
        {label:"時間", key:"timestamp"},
        {label:"幣種", key:"symbol"},
        {label:"機率", render:r=>num(r.probability)},
        {label:"訊號", render:r=>String(r.signal).toLowerCase()==="true" ? '<span class="pill ok">進場</span>' : '<span class="pill warn">等待</span>'},
        {label:"收盤價", render:r=>money(r.close)},
        {label:"多頭分數", key:"bull_score"},
        {label:"風險分數", key:"risk_score"}
      ], signals, "還沒有訊號紀錄");

      const ledger = (data.ledger || []).slice().reverse();
      table(document.getElementById("ledgerTable"), [
        {label:"狀態", key:"status"},
        {label:"幣種", key:"symbol"},
        {label:"進場價", key:"entry_price"},
        {label:"數量", key:"qty"},
        {label:"時間", render:r=>text(r.entry_time || r.exit_time_actual)}
      ], ledger, "還沒有交易紀錄");
    }

    load();
    setInterval(load, 60000);
  </script>
</body>
</html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        if not config.DASHBOARD_PASSWORD:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        except Exception:
            return False
        return decoded == f"{config.DASHBOARD_USERNAME}:{config.DASHBOARD_PASSWORD}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="ETH Strategy Monitor"')
        self.end_headers()
        return False

    def do_GET(self) -> None:
        if not self._require_auth():
            return

        path = urlparse(self.path).path
        if path == "/":
            body = _html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/status":
            body = json.dumps(_load_status(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((config.DASHBOARD_HOST, config.DASHBOARD_PORT), Handler)
    print(f"Dashboard running on http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
