# -*- coding: utf-8 -*-
"""
Telegram polling listener for on-demand stock analysis.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from src.config import get_config
from src.core.pipeline import StockAnalysisPipeline
from src.portfolio.google_sheets_reader import load_portfolio_from_config

logger = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"^(?:analyze|analyse)\s+([A-Za-z]{1,5}(?:\.[A-Za-z]{1,2})?)$", re.IGNORECASE)


def _state_path() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "bot_state.json"


def _load_state(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _save_state(path: Path, state: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _send_message(token: str, chat_id: str, text: str, parse_mode: Optional[str] = None) -> bool:
    if not text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram send failed: status=%s response=%s", resp.status_code, resp.text)
        return False
    except Exception as exc:
        logger.warning("Telegram send exception: %s", exc)
        return False


def _build_help() -> str:
    return "\n".join([
        "Available commands:",
        "- analyze TICKER  (or analyse TICKER)",
        "- portfolio",
        "- help",
    ])


def _build_portfolio_scorecard() -> str:
    state_path = Path(__file__).resolve().parent.parent.parent / "data" / "signal_history.json"
    if not state_path.exists():
        return "No portfolio history found yet."
    try:
        data = json.loads(state_path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return "Could not read portfolio history."

    lines = ["Portfolio scorecard:"]
    for ticker, info in sorted(data.items()):
        score = info.get("last_score", "N/A")
        decision = info.get("last_decision", "N/A")
        date = info.get("date", "N/A")
        lines.append(f"- {ticker}: {score} ({decision}) as of {date}")
    return "\n".join(lines)


def _build_evaluation_reply(ticker: str, payload: Dict[str, Any]) -> str:
    def esc(value: Optional[str]) -> str:
        if value is None:
            return ""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    buy_verdict = esc(payload.get("buy_verdict", ""))
    verdict_reason = esc(payload.get("verdict_reason", ""))
    quality_score = esc(payload.get("quality_score", ""))
    quality_summary = esc(payload.get("quality_summary", ""))
    growth_score = esc(payload.get("growth_score", ""))
    growth_summary = esc(payload.get("growth_summary", ""))
    macro_fit = esc(payload.get("macro_fit", ""))
    macro_summary = esc(payload.get("macro_summary", ""))
    portfolio_fit_comment = esc(payload.get("portfolio_fit_comment", ""))
    entry_zone = esc(payload.get("entry_zone", ""))
    stop_loss = esc(payload.get("stop_loss", ""))
    key_risks = esc(payload.get("key_risks", ""))
    watch_for = esc(payload.get("watch_for", ""))

    lines = [
        f"🔍 {esc(ticker)} — {buy_verdict}",
        "",
        f"📝 {verdict_reason}",
        "",
        f"<b>📊 Quality</b>: {quality_score}/100",
        f"{quality_summary}",
        "",
        f"<b>📈 Growth</b>: {growth_score}/100",
        f"{growth_summary}",
        "",
        f"<b>🌍 Macro</b>: {macro_fit}",
        f"{macro_summary}",
        "",
        "<b>🗂 Portfolio Fit</b>:",
        f"{portfolio_fit_comment}",
        "",
        f"<b>💰 Entry</b>: {entry_zone} | <b>Stop</b>: {stop_loss}",
        "",
        f"⚠️ Risks: {key_risks}",
        f"👀 Watch for: {watch_for}",
    ]
    return "\n".join([line for line in lines if line is not None])


def _handle_message(token: str, chat_id: str, text: str) -> None:
    if not text:
        return
    text = text.strip()
    if text.lower() == "help":
        _send_message(token, chat_id, _build_help())
        return
    if text.lower() == "portfolio":
        _send_message(token, chat_id, _build_portfolio_scorecard())
        return

    match = _TICKER_RE.match(text)
    if not match:
        if text.lower().startswith(("analyze", "analyse")):
            _send_message(token, chat_id, "Invalid format. Use: analyze TICKER (e.g. analyze AAPL)")
        return

    ticker = match.group(1).upper()
    if not re.match(r"^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$", ticker):
        _send_message(token, chat_id, f"Invalid ticker format: {ticker}")
        return

    done_flag = {"done": False}

    def _late_notice() -> None:
        time.sleep(30)
        if not done_flag["done"]:
            _send_message(token, chat_id, f"Analyzing {ticker}... this takes about 30 seconds ⏳")

    threading.Thread(target=_late_notice, daemon=True).start()

    config = get_config()
    portfolio = load_portfolio_from_config(config) or {}
    pipeline = StockAnalysisPipeline(config=config)
    portfolio_fit = pipeline._build_portfolio_fit_context(ticker, portfolio)

    stock_name = None
    realtime = None
    try:
        realtime = pipeline.fetcher_manager.get_realtime_quote(ticker)
        stock_name = getattr(realtime, "name", None) if realtime else None
    except Exception:
        realtime = None
    if not stock_name:
        try:
            stock_name = pipeline.fetcher_manager.get_stock_name(ticker)
        except Exception:
            stock_name = None

    context = {
        "code": ticker,
        "stock_name": stock_name or ticker,
        "date": pipeline._get_reference_date(ticker).isoformat(),
    }
    if realtime:
        context["realtime"] = {
            "name": getattr(realtime, "name", None),
            "price": getattr(realtime, "price", None),
            "change_pct": getattr(realtime, "change_pct", None),
            "volume_ratio": getattr(realtime, "volume_ratio", None),
            "turnover_rate": getattr(realtime, "turnover_rate", None),
            "pe_ratio": getattr(realtime, "pe_ratio", None),
            "pb_ratio": getattr(realtime, "pb_ratio", None),
            "total_mv": getattr(realtime, "total_mv", None),
            "circ_mv": getattr(realtime, "circ_mv", None),
            "high_52w": getattr(realtime, "high_52w", None),
            "low_52w": getattr(realtime, "low_52w", None),
        }

    try:
        fundamentals = pipeline.fetcher_manager.get_fundamentals(ticker) or {}
        if fundamentals:
            context["fundamentals"] = fundamentals
    except Exception:
        pass

    result = pipeline.analyzer.evaluate_for_purchase(context, portfolio_fit)
    done_flag["done"] = True
    if result is None:
        _send_message(token, chat_id, f"Could not evaluate {ticker}. Please try again.")
        return
    reply = _build_evaluation_reply(ticker, result)
    _send_message(token, chat_id, reply, parse_mode="HTML")


def _poll_loop() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.warning("BOT_LISTENER: Telegram token/chat_id not configured; listener disabled.")
        return

    poll_interval = int(os.getenv("BOT_LISTENER_POLL_INTERVAL", "5") or 5)
    state_path = _state_path()
    state = _load_state(state_path)
    offset = state.get("last_update_id", 0)

    logger.info("BOT_LISTENER: started polling every %ss", poll_interval)
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"timeout": 10, "offset": offset + 1}
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning("BOT_LISTENER: getUpdates failed: %s %s", resp.status_code, resp.text)
                time.sleep(poll_interval)
                continue
            payload = resp.json()
            updates = payload.get("result", []) if isinstance(payload, dict) else []
            for update in updates:
                update_id = update.get("update_id")
                message = update.get("message") or {}
                msg_chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text", "")
                if msg_chat_id != chat_id:
                    offset = max(offset, update_id or offset)
                    continue
                _handle_message(token, chat_id, text)
                if update_id is not None:
                    offset = max(offset, update_id)
            state["last_update_id"] = offset
            _save_state(state_path, state)
        except Exception as exc:
            logger.warning("BOT_LISTENER: polling error: %s", exc)
        time.sleep(poll_interval)


def start_listener() -> None:
    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()
