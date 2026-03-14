# -*- coding: utf-8 -*-
"""
Hardcoded sector map for common US tickers.
"""

from __future__ import annotations

from typing import Dict, List, Optional

SECTOR_MAP = {

    # ---------------- TECH ----------------
    "AAPL": "tech",
    "MSFT": "tech",
    "NVDA": "tech",
    "GOOGL": "tech",
    "META": "tech",
    "AMZN": "tech",
    "TSLA": "tech",
    "ORCL": "tech",
    "CRM": "tech",
    "ADBE": "tech",
    "NOW": "tech",
    "UBER": "tech",
    "SNOW": "tech",
    "PLTR": "tech",
    "SHOP": "tech",

    # ---------------- SEMICONDUCTORS ----------------
    "AMD": "semiconductors",
    "INTC": "semiconductors",
    "AVGO": "semiconductors",
    "MU": "semiconductors",
    "TSM": "semiconductors",
    "ASML": "semiconductors",
    "LRCX": "semiconductors",
    "AMAT": "semiconductors",
    "KLAC": "semiconductors",
    "QCOM": "semiconductors",
    "TXN": "semiconductors",
    "ON": "semiconductors",
    "SNDK": "semiconductors",

    # ---------------- SEMICONDUCTOR ETF ----------------
    "SMH": "semiconductors_etf",
    "SOXX": "semiconductors_etf",

    # ---------------- BROAD MARKET ETF ----------------
    "SPY": "broad_market",
    "VTI": "broad_market",
    "VOO": "broad_market",
    "IWM": "broad_market",
    "DIA": "broad_market",

    # ---------------- TECH ETF ----------------
    "QQQ": "tech_etf",
    "XLK": "tech_etf",
    "VGT": "tech_etf",

    # ---------------- FINANCIALS ----------------
    "JPM": "financials",
    "BAC": "financials",
    "GS": "financials",
    "MS": "financials",
    "C": "financials",
    "WFC": "financials",
    "BRK.B": "financials",
    "AXP": "financials",
    "BLK": "financials",
    "SCHW": "financials",

    # ---------------- HEALTHCARE ----------------
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "LLY": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
    "TMO": "healthcare",
    "DHR": "healthcare",
    "ISRG": "healthcare",

    # ---------------- ENERGY ----------------
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "SLB": "energy",
    "EOG": "energy",
    "PSX": "energy",

    # ---------------- CONSUMER ----------------
    "WMT": "consumer",
    "COST": "consumer",
    "PG": "consumer",
    "KO": "consumer",
    "PEP": "consumer",
    "MCD": "consumer",
    "NKE": "consumer",
    "HD": "consumer",
    "LOW": "consumer",

    # ---------------- COMMUNICATION ----------------
    "NFLX": "communication",
    "DIS": "communication",
    "CMCSA": "communication",
    "T": "communication",
    "VZ": "communication",

    # ---------------- INDUSTRIAL ----------------
    "CAT": "industrial",
    "BA": "industrial",
    "GE": "industrial",
    "RTX": "industrial",
    "HON": "industrial",
    "UPS": "industrial",
    "FDX": "industrial",

    # ---------------- CRYPTO ETF ----------------
    "IBIT": "crypto_etf",
    "GBTC": "crypto_etf",
}

_SECTOR_CACHE: Dict[str, str] = {}


def get_sector(ticker: str) -> str:
    if not ticker:
        return "unknown"
    code = ticker.strip().upper()
    if code in SECTOR_MAP:
        return SECTOR_MAP[code]
    if code in _SECTOR_CACHE:
        return _SECTOR_CACHE[code]
    try:
        import yfinance as yf
        yf_ticker = yf.Ticker(code)
        info = getattr(yf_ticker, "info", {}) or {}
        sector = (info.get("sector") or "unknown").lower()
        _SECTOR_CACHE[code] = sector
        return sector
    except Exception:
        return "unknown"


def get_concentration_warning(
    watchlist: List[str],
    new_ticker: str,
    threshold: int,
) -> Optional[str]:
    if not new_ticker:
        return None
    clean_watchlist = [t.strip().upper() for t in watchlist if t and t.strip()]
    new_sector = get_sector(new_ticker)
    if new_sector == "unknown":
        return None

    matching = [t for t in clean_watchlist if get_sector(t) == new_sector]
    total = len(clean_watchlist)
    percentage = (len(matching) + 1) / (total + 1) * 100
    if percentage <= threshold:
        return None

    tickers = matching + [new_ticker.strip().upper()]
    tickers_text = ", ".join(tickers)
    return (
        f"⚠️ Adding {new_ticker.upper()} would make you {percentage:.0f}% concentrated in "
        f"{new_sector} ({tickers_text}). Consider diversifying."
    )
