"""
dMoERA Creator Studio — MCP Server

Exposes the dMoERA Creator API as Model Context Protocol tools so any
AI agent (Claude, Cursor, Windsurf, Devin, Copilot, etc.) can:
  - Discover available trading domains and data feeds
  - List and inspect bots/strategies and their performance
  - Sandbox-backtest strategy code before submission
  - Submit strategies for full validation and live deployment
  - Read market regime and feature data for strategy logic

This is AI-agnostic: any MCP-compatible client can connect and use it.
No dMoERA-specific knowledge is required by the client — the tool
descriptions and the companion CREATOR_API.md document provide all
necessary context.

Run standalone:
    python mcp_creator_server.py

Or configure in your AI client's MCP settings:
    {
      "mcpServers": {
        "dmoera-creator": {
          "command": "python",
          "args": ["mcp_creator_server.py"],
          "cwd": "/path/to/dmoen-core"
        }
      }
    }
"""
import os
import sys
import json
import asyncio
from typing import Optional, List, Dict, Any

# Ensure we can import dMoERA modules when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "dmoera-creator",
    instructions=(
        "dMoERA Creator Studio — build, test, deploy, and manage crypto trading strategies and funds. "
        "Creator tools: list_domains, list_bots, get_bot_profile, get_feature_catalog, "
        "get_market_regime, get_current_prices, sandbox_backtest, submit_strategy, list_strategies, "
        "get_strategy_report, get_marketplace_bots, get_tournament_status. "
        "Fund management tools: list_funds, get_fund, get_active_fund, create_fund, "
        "add_bot_to_fund, remove_bot_from_fund, swap_bot_in_fund, update_fund_weights, "
        "update_fund_caps, activate_fund, deactivate_fund, close_fund, estimate_swap_cost, "
        "browse_fund_marketplace. "
        "Read CREATOR_API.md for the full strategy contract, data model, and examples."
    ),
)


# ── Helpers ──────────────────────────────────────────────

def _get_engine():
    """Get the running engine instance (if available)."""
    try:
        import engine_pro
        return getattr(engine_pro, "engine", None)
    except Exception:
        return None


def _get_creator_service():
    """Get a CreatorService instance."""
    from validation.upload_service import CreatorService
    return CreatorService()


def _get_marketplace_manager():
    """Get the marketplace manager."""
    from marketplace.manager import MarketplaceManager
    return MarketplaceManager()


def _get_tournament_manager():
    """Get the tournament manager."""
    from tournaments.manager import TournamentManager
    return TournamentManager()


# ── Discovery Tools ──────────────────────────────────────

@mcp.tool()
def list_domains() -> str:
    """List all available trading domains on dMoERA.

    Domains define what asset pair a strategy trades, what time horizon
    it uses (scalp=5m, swing=1h, crisis=2m), and what data is available.
    Strategies must declare which domain they belong to.

    Returns a JSON array of domain objects with: key, name, type,
    base_asset, quote_asset, grading_seconds, and feed_symbols.
    """
    from domains.registry import get_all_domains
    domains = []
    for d in get_all_domains():
        domains.append({
            "key": d.key,
            "name": d.name,
            "type": d.domain_type.value if hasattr(d.domain_type, "value") else str(d.domain_type),
            "base_asset": d.base_asset,
            "quote_asset": d.quote_asset,
            "grading_seconds": d.grading_seconds,
            "feed_symbols": d.feed_symbols,
        })
    return json.dumps(domains, indent=2)


@mcp.tool()
def list_bots(domain: Optional[str] = None, limit: int = 20) -> str:
    """List trading bots ranked by performance.

    Args:
        domain: Filter by domain key (e.g. "eth_usdc", "btc_usdc", "sol_usdc").
               If omitted, returns top bots across all domains.
        limit: Maximum number of bots to return (default 20, max 100).

    Returns JSON array of bots with: bot_id, domain, strategy_name, sharpe,
    win_rate, total_trades, return_bps, and validation_score.
    """
    eng = _get_engine()
    if not eng:
        return json.dumps({"error": "Engine not running. Start the dMoERA engine first."})
    limit = max(1, min(limit, 100))
    if domain:
        ranked = eng.leaderboard.get_ranked(domain)
    else:
        # Aggregate across all domains
        ranked = []
        from domains.registry import get_all_domains
        for d in get_all_domains():
            ranked.extend(eng.leaderboard.get_ranked(d.key)[:limit])
        # Sort by validation_score as proxy
        ranked.sort(key=lambda b: getattr(b, "validation_score", 0), reverse=True)
        ranked = ranked[:limit]
    bots = []
    for b in ranked:
        perf = b.performance
        bots.append({
            "bot_id": b.bot_id,
            "domain": b.domain.key if hasattr(b.domain, "key") else str(b.domain),
            "strategy_name": getattr(b, "strategy_name", "unknown"),
            "sharpe": round(getattr(perf, "sharpe", 0), 3),
            "win_rate": round(getattr(perf, "win_rate", 0), 3),
            "total_trades": getattr(perf, "total_trades", 0),
            "return_bps": round(getattr(perf, "total_return_bps", 0), 1),
            "validation_score": round(getattr(b, "validation_score", 0), 1),
        })
    return json.dumps(bots, indent=2)


@mcp.tool()
def get_bot_profile(bot_id: str) -> str:
    """Get detailed profile and performance stats for a specific bot.

    Args:
        bot_id: The bot identifier (e.g. "Eth_Full_Ensemble").

    Returns JSON with: bot_id, domain, strategy type, full performance
    metrics (Sharpe, Sortino, Calmar, profit factor, regime breakdown),
    current position if any, and recent trade history.
    """
    eng = _get_engine()
    if not eng:
        return json.dumps({"error": "Engine not running."})
    bot = eng.bot_by_id.get(bot_id)
    if not bot:
        return json.dumps({"error": f"Bot '{bot_id}' not found"})
    perf = bot.performance
    profile = {
        "bot_id": bot.bot_id,
        "domain": bot.domain.key if hasattr(bot.domain, "key") else str(bot.domain),
        "strategy_name": getattr(bot, "strategy_name", "unknown"),
        "validation_score": getattr(bot, "validation_score", 0),
        "performance": {
            "sharpe": getattr(perf, "sharpe", 0),
            "sortino": getattr(perf, "sortino", 0),
            "calmar": getattr(perf, "calmar", 0),
            "profit_factor": getattr(perf, "profit_factor", 0),
            "win_rate": getattr(perf, "win_rate", 0),
            "total_trades": getattr(perf, "total_trades", 0),
            "total_return_bps": getattr(perf, "total_return_bps", 0),
            "max_drawdown_bps": getattr(perf, "max_drawdown_bps", 0),
            "avg_trade_bps": getattr(perf, "avg_trade_bps", 0),
        },
    }
    # Add regime breakdown if available
    regime_stats = getattr(perf, "regime_stats", {})
    if regime_stats:
        profile["regime_breakdown"] = {
            k: {"trades": v.get("trades", 0), "avg_bps": v.get("avg_bps", 0)}
            for k, v in regime_stats.items()
        }
    return json.dumps(profile, indent=2)


@mcp.tool()
def get_feature_catalog() -> str:
    """List all data feeds available to strategies via ctx.features.

    Features are external data that strategies can read during on_bar().
    Each feature has a status: "live" (available now, requirable) or
    "planned" (roadmap, not yet available). Only live features can be
    used in required_features.

    Returns JSON array of features with: key, label, description, unit,
    example, cadence, source, status, and backtest_mode.
    """
    from features.catalog import FEATURE_CATALOG
    features = []
    for f in FEATURE_CATALOG:
        features.append({
            "key": f.key,
            "label": f.label,
            "description": f.description,
            "unit": f.unit,
            "example": f.example,
            "cadence": f.cadence,
            "source": f.source,
            "status": f.status,
            "backtest_mode": f.backtest_mode,
        })
    return json.dumps(features, indent=2)


# ── Market Data Tools ────────────────────────────────────

@mcp.tool()
def get_market_regime() -> str:
    """Get current market regime classification.

    Returns the aggregate regime (e.g. "bull_calm", "bear_volatile"),
    per-symbol regimes, crisis score, and the derivatives data driving
    the classification (funding rates, open interest, long/short ratios,
    taker buy/sell ratios).

    Regime determines which trade directions are allowed:
    - bull_* → longs only
    - bear_* → shorts only
    - neutral_* → both longs and shorts
    - crisis/meltdown → no new positions
    """
    eng = _get_engine()
    if not eng:
        return json.dumps({"error": "Engine not running."})
    status = eng.get_regime_status()
    # Remove non-serializable items
    clean = {}
    for k, v in status.items():
        try:
            json.dumps(v)
            clean[k] = v
        except (TypeError, ValueError):
            clean[k] = str(v)
    return json.dumps(clean, indent=2)


@mcp.tool()
def get_current_prices() -> str:
    """Get current live prices for all tracked symbols.

    Returns JSON with symbol → {price, bid, ask, source, change_24h_pct,
    volume_24h} for ETHUSDT, BTCUSDT, SOLUSDT from Binance/Coinbase/Kraken.
    """
    eng = _get_engine()
    if not eng:
        return json.dumps({"error": "Engine not running."})
    prices = {}
    for sym, tick in eng.latest_prices.items():
        if hasattr(tick, "price"):
            prices[sym] = {
                "price": tick.price,
                "bid": getattr(tick, "bid", 0),
                "ask": getattr(tick, "ask", 0),
                "source": tick.source,
                "change_24h_pct": getattr(tick, "change_24h_pct", 0),
                "volume_24h": getattr(tick, "volume_24h", 0),
            }
        elif isinstance(tick, (int, float)):
            prices[sym] = {"price": tick}
    return json.dumps(prices, indent=2)


# ── Strategy Development Tools ───────────────────────────

@mcp.tool()
def sandbox_backtest(
    code: str,
    domain: str = "eth_usdc",
    symbol: str = "ETHUSDT",
    user_id: str = "mcp_sandbox",
) -> str:
    """Run a sandbox backtest of strategy code without persisting anything.

    This is the fastest way to test a strategy. The code is run through
    static checks and a full backtest on historical data, but no Strategy
    or StrategyVersion rows are created. Use this for rapid iteration.

    Args:
        code: Python source code implementing the Strategy contract.
              Must define a METADATA dict and a class extending Strategy
              with an on_bar(ctx) -> Signal method. See CREATOR_API.md.
        domain: Trading domain (e.g. "eth_usdc", "btc_usdc", "sol_usdc").
        symbol: Price symbol for historical data (e.g. "ETHUSDT").
        user_id: Identifier for trial tracking (used for DSR correction).

    Returns JSON with: success, metrics (sharpe, sortino, win_rate,
    total_trades, return_bps, max_drawdown, regime_breakdown,
    exit_reason_breakdown), or error details if validation failed.
    """
    try:
        service = _get_creator_service()
        # Fetch candles from the engine's historical data
        eng = _get_engine()
        candles = []
        if eng:
            hist = eng.price_history.get(symbol, [])
            candles = [{"timestamp": h.get("timestamp"), "open": h.get("open", h.get("price")),
                        "high": h.get("high", h.get("price")), "low": h.get("low", h.get("price")),
                        "close": h.get("close", h.get("price")), "volume": h.get("volume", 0)}
                       for h in hist]
        if not candles:
            return json.dumps({"error": f"No historical data available for {symbol}. Engine may not be running."})
        result = service.sandbox_backtest(
            code=code, candles=candles, symbol=symbol,
            user_id=user_id, domain=domain,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def submit_strategy(
    name: str,
    domain: str,
    code: str,
    user_id: str,
    symbol: str = "ETHUSDT",
) -> str:
    """Submit a strategy for full validation and live deployment.

    Runs the complete 7-stage validation pipeline:
    1. static_check — code safety (banned imports, syntax)
    2. in_sample — sanity check on training data
    3. out_of_sample — test on unseen data (70/30 split)
    4. walk_forward — rolling window validation
    5. randomized_start — different random start points
    6. perturbation — market stress test
    7. holdout — server-side reserved data (pass/fail only)

    If all stages pass, the strategy is registered for isolated live
    paper trading with status="incubating". Promotion to "live" requires
    a proven track record.

    Args:
        name: Human-readable strategy name (e.g. "ETH Momentum v2").
        domain: Trading domain key (e.g. "eth_usdc").
        code: Python source code implementing the Strategy contract.
        user_id: The creator's user ID.
        symbol: Price symbol for historical data.

    Returns JSON with: success, strategy_id, bot_id, validation results
    per stage, or error details.
    """
    try:
        service = _get_creator_service()
        eng = _get_engine()
        candles = []
        if eng:
            hist = eng.price_history.get(symbol, [])
            candles = [{"timestamp": h.get("timestamp"), "open": h.get("open", h.get("price")),
                        "high": h.get("high", h.get("price")), "low": h.get("low", h.get("price")),
                        "close": h.get("close", h.get("price")), "volume": h.get("volume", 0)}
                       for h in hist]
        if not candles:
            return json.dumps({"error": f"No historical data available for {symbol}."})
        result = service.submit(
            user_id=user_id, name=name, domain=domain, code=code,
            candles=candles, symbol=symbol,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def list_strategies(user_id: str) -> str:
    """List all strategies created by a user.

    Args:
        user_id: The creator's user ID.

    Returns JSON array of strategies with: id, bot_id, name, domain,
    status, declared_sl_bps, declared_tp_bps, and created_at.
    """
    try:
        service = _get_creator_service()
        strategies = service.list_strategies(user_id)
        return json.dumps(strategies, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_strategy_report(strategy_id: int) -> str:
    """Get a detailed report card for a strategy.

    Includes validation run results for all 7 stages, performance metrics,
    and the integrity block (code hash, AST hash, parameter fingerprint).

    Args:
        strategy_id: The strategy's database ID.

    Returns JSON with: strategy details, latest validation runs, metrics.
    """
    try:
        service = _get_creator_service()
        report = service.get_report_card(strategy_id)
        if not report:
            return json.dumps({"error": f"Strategy {strategy_id} not found"})
        return json.dumps(report, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── Marketplace Tools ────────────────────────────────────

@mcp.tool()
def get_marketplace_bots(domain: Optional[str] = None, sort: str = "rating", limit: int = 20) -> str:
    """List bots published to the marketplace.

    Args:
        domain: Filter by domain (e.g. "eth_usdc"). Omit for all domains.
        sort: Sort order — "rating", "return", "subscribers", or "newest".
        limit: Max results (default 20, max 100).

    Returns JSON array of marketplace listings with: listing_id, bot_id,
    title, description, domain, creator, monthly_price_usd, cached stats
    (win_rate, return_bps, sharpe), subscriber_count, and avg_rating.
    """
    try:
        mgr = _get_marketplace_manager()
        listings = mgr.list_bots(domain=domain, sort=sort, limit=limit)
        return json.dumps(listings, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── Tournament Tools ─────────────────────────────────────

@mcp.tool()
def get_tournament_status() -> str:
    """Get current tournament round status and leaderboard.

    Tournaments run every 3 days. Top 3 bots per domain win prizes
    from the reward pool. Scoring is weighted: 50% risk-adjusted return,
    30% total PnL, 20% consistency.

    Returns JSON with: current round info (round_id, start/end time,
    reward_pool_usd, total_participants), and leaderboard entries.
    """
    try:
        mgr = _get_tournament_manager()
        round_info = mgr.get_or_create_current_round()
        entries = mgr.get_leaderboard()
        return json.dumps({
            "current_round": {
                "round_id": round_info.round_id,
                "start_time": round_info.start_time.isoformat() if round_info.start_time else None,
                "end_time": round_info.end_time.isoformat() if round_info.end_time else None,
                "reward_pool_usd": round_info.reward_pool_usd,
                "total_participants": round_info.total_participants,
                "status": round_info.status,
            },
            "leaderboard": entries[:20] if entries else [],
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── Fund Management Tools ────────────────────────────────

def _get_fund_manager():
    """Get a FundManager instance."""
    from engine.fund_manager import FundManager
    return FundManager()


@mcp.tool()
def list_funds(user_id: str) -> str:
    """List all hedge funds for a user (active + closed).

    Args:
        user_id: The user's ID.

    Returns a JSON array of fund objects with: id, fund_name, is_active,
    inception_date, initial_capital, current_aum, router_preset,
    aggression_mode, total_pnl_usd, total_pnl_bps, and roster summary.
    """
    try:
        fm = _get_fund_manager()
        funds = fm.list_funds(user_id)
        return json.dumps({"success": True, "funds": funds}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_fund(fund_id: int) -> str:
    """Get detailed info for a specific hedge fund, including its roster.

    Args:
        fund_id: The fund's ID.

    Returns a JSON object with fund details and active roster entries
    (bot_id, bot_name, weight, domain, current_pnl).
    """
    try:
        fm = _get_fund_manager()
        fund = fm.get_fund(fund_id)
        if not fund:
            return json.dumps({"error": "Fund not found"}, indent=2)
        return json.dumps({"success": True, "fund": fund}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_active_fund(user_id: str) -> str:
    """Get the user's currently active (Manager Mode) fund.

    Args:
        user_id: The user's ID.

    Returns the active fund object or null if Manager Mode is not active.
    """
    try:
        fm = _get_fund_manager()
        fund = fm.get_active_fund(user_id)
        return json.dumps({"success": True, "fund": fund}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def create_fund(
    user_id: str,
    fund_name: str = "My Hedge Fund",
    router_preset: str = "standard",
    aggression_mode: str = "normal",
    philosophy: str = "",
) -> str:
    """Create a new hedge fund for the user.

    The fund starts inactive — call activate_fund to start Manager Mode.
    Initial capital is taken from the user's wallet_cash at creation time.

    Args:
        user_id: The user's ID.
        fund_name: Display name for the fund.
        router_preset: Risk profile — one of "prudent", "standard",
                      "opportunistic", "unrestricted".
        aggression_mode: "normal" or "yolo".
        philosophy: Optional text describing the fund's investment thesis
                   (max 2000 chars).

    Returns the created fund object.
    """
    try:
        fm = _get_fund_manager()
        ok, fund, err = fm.create_fund(
            user_id=user_id,
            fund_name=fund_name,
            router_preset=router_preset,
            aggression_mode=aggression_mode,
            philosophy=philosophy,
        )
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "fund": fund}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def add_bot_to_fund(user_id: str, fund_id: int, bot_id: str, bot_domain: str, weight: float = 20.0) -> str:
    """Add a bot to a fund's roster.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.
        bot_id: The bot to add (e.g. "momentum_eth_v3").
        bot_domain: The bot's domain (e.g. "eth_usdc", "btc_usdc").
        weight: Initial allocation weight in percent (default 20.0).

    Returns the updated roster entry.
    """
    try:
        fm = _get_fund_manager()
        ok, entry, err = fm.add_bot_to_roster(user_id, fund_id, bot_id, bot_domain, weight)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "entry": entry}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def remove_bot_from_fund(user_id: str, fund_id: int, bot_id: str, reason: str = "") -> str:
    """Remove a bot from a fund's roster (triggers wind-down of its positions).

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.
        bot_id: The bot to remove.
        reason: Optional reason for removal.

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.remove_bot_from_roster(user_id, fund_id, bot_id, reason)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def swap_bot_in_fund(
    user_id: str,
    fund_id: int,
    old_bot_id: str,
    new_bot_id: str,
    new_bot_domain: str,
    weight: Optional[float] = None,
    reason: str = "",
) -> str:
    """Swap one bot for another in a fund's roster.

    Closes the old bot's positions and opens new ones for the replacement.
    Incurs friction cost — use estimate_swap_cost first.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.
        old_bot_id: The bot to remove.
        new_bot_id: The bot to add in its place.
        new_bot_domain: The new bot's domain (e.g. "eth_usdc").
        weight: Allocation weight for the new bot (defaults to old bot's weight).
        reason: Optional reason for the swap.

    Returns the updated roster entry and friction estimate.
    """
    try:
        fm = _get_fund_manager()
        ok, result, err = fm.swap_bot(user_id, fund_id, old_bot_id, new_bot_id, new_bot_domain, weight, reason)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "result": result}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def update_fund_weights(user_id: str, fund_id: int, weights: Dict[str, float]) -> str:
    """Update allocation weights for bots in a fund's roster.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.
        weights: A dict mapping bot_id to new weight percentage (e.g.
                {"momentum_eth_v3": 15.0, "scalper_btc_v2": 20.0}).

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.update_weights(user_id, fund_id, weights)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def update_fund_caps(
    user_id: str,
    fund_id: int,
    max_per_bot_pct: Optional[float] = None,
    max_per_domain_pct: Optional[float] = None,
    regime_veto_enabled: Optional[bool] = None,
) -> str:
    """Update a fund's risk caps and settings.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.
        max_per_bot_pct: Max allocation per single bot (e.g. 40.0 = 40%).
        max_per_domain_pct: Max allocation per domain (e.g. 60.0 = 60%).
        regime_veto_enabled: Whether the regime detector can veto trades.

    Only provided fields are updated; others remain unchanged.

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.update_caps(
            user_id, fund_id,
            max_per_bot_pct=max_per_bot_pct,
            max_per_domain_pct=max_per_domain_pct,
            regime_veto_enabled=regime_veto_enabled,
        )
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def activate_fund(user_id: str, fund_id: int) -> str:
    """Activate Manager Mode for a fund — starts the personal router.

    This deploys capital across the fund's roster bots according to their
    weights and the fund's risk caps. The main platform router is paused
    while Manager Mode is active.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.activate_manager_mode(user_id, fund_id)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "message": "Manager Mode activated"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def deactivate_fund(user_id: str, fund_id: int) -> str:
    """Deactivate Manager Mode — returns to the main platform router.

    Closes all roster bot positions and returns capital to the wallet.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.deactivate_manager_mode(user_id, fund_id)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "message": "Manager Mode deactivated"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def close_fund(user_id: str, fund_id: int) -> str:
    """Permanently close a hedge fund. Returns all capital to the wallet.

    This is irreversible. The fund's performance record is preserved for
    reporting and copy-trader settlement.

    Args:
        user_id: The user's ID (must own the fund).
        fund_id: The fund's ID.

    Returns success or error.
    """
    try:
        fm = _get_fund_manager()
        ok, err = fm.close_fund(user_id, fund_id)
        if not ok:
            return json.dumps({"error": err}, indent=2)
        return json.dumps({"success": True, "message": "Fund closed"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def estimate_swap_cost(fund_id: int, old_bot_id: str, new_bot_id: str, new_bot_domain: str) -> str:
    """Estimate the friction cost (in bps) of swapping a bot in a fund.

    Use this before calling swap_bot_in_fund to understand the cost of
    winding down the old bot's positions and opening new ones.

    Args:
        fund_id: The fund's ID.
        old_bot_id: The bot being considered for removal.
        new_bot_id: The replacement bot.
        new_bot_domain: The replacement bot's domain.

    Returns the estimated friction in bps of fund AUM.
    """
    try:
        fm = _get_fund_manager()
        cost_bps = fm.estimate_swap_cost(fund_id, old_bot_id, new_bot_id, new_bot_domain)
        return json.dumps({"success": True, "estimated_friction_bps": round(cost_bps, 2)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def browse_fund_marketplace(domain: Optional[str] = None, min_sharpe: Optional[float] = None) -> str:
    """Browse bots available for adding to a fund roster.

    Shows bots with their performance stats and available capacity.
    Requires the trading engine to be running.

    Args:
        domain: Filter by domain (e.g. "eth_usdc").
        min_sharpe: Minimum Sharpe ratio filter.

    Returns a JSON array of marketplace bot entries.
    """
    try:
        engine = _get_engine()
        if not engine:
            return json.dumps({"error": "Trading engine not available. Start the engine to browse bots."}, indent=2)
        fm = _get_fund_manager()
        filters = {}
        if domain:
            filters["domain"] = domain
        if min_sharpe is not None:
            filters["min_sharpe"] = min_sharpe
        bots = fm.get_marketplace_bots(engine, filters=filters if filters else None)
        return json.dumps({"success": True, "bots": bots[:20]}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── Resources (read-only context) ────────────────────────

@mcp.resource("creator-api://docs")
def creator_api_docs() -> str:
    """The full CREATOR_API.md documentation for AI agents."""
    docs_path = os.path.join(os.path.dirname(__file__), "CREATOR_API.md")
    if os.path.exists(docs_path):
        with open(docs_path, "r", encoding="utf-8") as f:
            return f.read()
    return "CREATOR_API.md not found. See the repository root."


@mcp.resource("creator-api://strategy-template")
def strategy_template() -> str:
    """A copy-pasteable strategy template implementing the v2 contract."""
    return '''"""
Strategy: [Your Strategy Name]
Domain: eth_usdc
"""

from domains.strategy_contract import Strategy, Signal, SignalDirection

METADATA = {
    "name": "[Your Strategy Name]",
    "domain": "eth_usdc",
    "declared_sl_bps": 150.0,      # Stop-loss: 1.5%
    "declared_tp_bps": 300.0,      # Take-profit: 3.0%
    "declared_hold_seconds": 3600,  # Max hold: 1 hour
    "warmup_bars": 20,             # Bars needed before trading
    "required_features": [],        # External data feeds needed
}


class MyStrategy(Strategy):
    """Describe your strategy's edge here."""

    def initialize(self, ctx) -> None:
        """Called once before the first bar. Set up indicators."""
        pass

    def on_bar(self, ctx):
        """Called once per closed bar. Return a Signal or None."""
        closes = ctx.closes(lookback=20)
        if len(closes) < 20:
            return None

        # Example: simple momentum
        sma_fast = sum(closes[-5:]) / 5
        sma_slow = sum(closes[-20:]) / 20

        if sma_fast > sma_slow:
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
                metadata={"reason": "sma_crossover_up"},
            )
        elif sma_fast < sma_slow:
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
                metadata={"reason": "sma_crossover_down"},
            )
        return None
'''


# ── Entry point ──────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
