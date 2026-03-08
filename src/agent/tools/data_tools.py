# -*- coding: utf-8 -*-
"""Agent-callable wrappers around the retained market-data APIs."""

from src.agent.tools.registry import ToolParameter, ToolDefinition


def _get_fetcher_manager():
    """Lazy import to avoid circular dependencies."""
    from data_provider import DataFetcherManager

    return DataFetcherManager()


def _get_db():
    """Lazy import for database access."""
    from src.storage import get_db

    return get_db()


def _handle_get_realtime_quote(stock_code: str) -> dict:
    """Get a realtime quote for a stock or supported US index."""
    manager = _get_fetcher_manager()
    quote = manager.get_realtime_quote(stock_code)
    if quote is None:
        return {"error": f"No realtime quote available for {stock_code}"}

    return {
        "code": quote.code,
        "name": quote.name,
        "price": quote.price,
        "change_pct": quote.change_pct,
        "change_amount": quote.change_amount,
        "volume": quote.volume,
        "amount": quote.amount,
        "volume_ratio": quote.volume_ratio,
        "turnover_rate": quote.turnover_rate,
        "amplitude": quote.amplitude,
        "open": quote.open_price,
        "high": quote.high,
        "low": quote.low,
        "pre_close": quote.pre_close,
        "pe_ratio": quote.pe_ratio,
        "pb_ratio": quote.pb_ratio,
        "total_mv": quote.total_mv,
        "circ_mv": quote.circ_mv,
        "change_60d": quote.change_60d,
        "source": quote.source.value if hasattr(quote.source, "value") else str(quote.source),
    }


get_realtime_quote_tool = ToolDefinition(
    name="get_realtime_quote",
    description=(
        "Get real-time stock quote including price, change, volume, valuation, and market-cap fields."
    ),
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="US stock or supported US index code, e.g. 'AAPL' or 'SPX'",
        ),
    ],
    handler=_handle_get_realtime_quote,
    category="data",
)


def _handle_get_daily_history(stock_code: str, days: int = 60) -> dict:
    """Get daily OHLCV history data."""
    manager = _get_fetcher_manager()
    df, source = manager.get_daily_data(stock_code, days=days)

    if df is None or df.empty:
        return {"error": f"No historical data available for {stock_code}"}

    records = df.tail(min(days, len(df))).to_dict(orient="records")
    for record in records:
        if "date" in record:
            record["date"] = str(record["date"])

    return {
        "code": stock_code,
        "source": source,
        "total_records": len(records),
        "data": records,
    }


get_daily_history_tool = ToolDefinition(
    name="get_daily_history",
    description="Get daily OHLCV history with MA5, MA10, and MA20 indicators.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="US stock or supported US index code, e.g. 'AAPL' or 'QQQ'",
        ),
        ToolParameter(
            name="days",
            type="integer",
            description="Number of trading days to fetch",
            required=False,
            default=60,
        ),
    ],
    handler=_handle_get_daily_history,
    category="data",
)


def _handle_get_chip_distribution(stock_code: str) -> dict:
    """Return chip-distribution data when available."""
    manager = _get_fetcher_manager()
    chip = manager.get_chip_distribution(stock_code)

    if chip is None:
        return {"error": f"No chip distribution data available for {stock_code}"}

    return {
        "code": chip.code,
        "date": chip.date,
        "source": chip.source,
        "profit_ratio": chip.profit_ratio,
        "avg_cost": chip.avg_cost,
        "cost_90_low": chip.cost_90_low,
        "cost_90_high": chip.cost_90_high,
        "concentration_90": chip.concentration_90,
        "cost_70_low": chip.cost_70_low,
        "cost_70_high": chip.cost_70_high,
        "concentration_70": chip.concentration_70,
    }


get_chip_distribution_tool = ToolDefinition(
    name="get_chip_distribution",
    description="Get chip-distribution analysis if the configured provider stack supports it.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code",
        ),
    ],
    handler=_handle_get_chip_distribution,
    category="data",
)


def _handle_get_analysis_context(stock_code: str) -> dict:
    """Get stored analysis context from the database."""
    db = _get_db()
    context = db.get_analysis_context(stock_code)

    if context is None:
        return {"error": f"No analysis context in DB for {stock_code}"}

    safe_context = {}
    for key, value in context.items():
        if key == "raw_data":
            safe_context["has_raw_data"] = True
            safe_context["raw_data_count"] = len(value) if isinstance(value, list) else 0
        else:
            safe_context[key] = value

    return safe_context


get_analysis_context_tool = ToolDefinition(
    name="get_analysis_context",
    description="Get the stored technical analysis context from the local database.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code",
        ),
    ],
    handler=_handle_get_analysis_context,
    category="data",
)


def _handle_get_stock_info(stock_code: str) -> dict:
    """Get the basic stock fields available in the retained provider stack."""
    manager = _get_fetcher_manager()
    quote = manager.get_realtime_quote(stock_code)
    if quote:
        return {
            "code": quote.code,
            "name": quote.name,
            "pe_ratio": quote.pe_ratio,
            "pb_ratio": quote.pb_ratio,
            "total_mv": quote.total_mv,
            "circ_mv": quote.circ_mv,
            "note": "Basic info only from the retained US-only provider stack",
        }
    return {"error": f"Unable to fetch stock info for {stock_code}"}


get_stock_info_tool = ToolDefinition(
    name="get_stock_info",
    description="Get the basic stock information available from the retained provider stack.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="US stock code, e.g. 'AAPL'",
        ),
    ],
    handler=_handle_get_stock_info,
    category="data",
)


ALL_DATA_TOOLS = [
    get_realtime_quote_tool,
    get_daily_history_tool,
    get_chip_distribution_tool,
    get_analysis_context_tool,
    get_stock_info_tool,
]
