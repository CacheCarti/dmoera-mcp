"""
dMoERA Creator Studio — MCP Server (API Client Edition)

Exposes the dMoERA Creator API as Model Context Protocol tools so any
AI agent (Claude, Cursor, Windsurf, Devin, Copilot, etc.) can:
  - Discover available trading domains and data feeds
  - List and inspect bots/strategies and their performance
  - Sandbox-backtest strategy code before submission
  - Submit strategies for full validation and live deployment
  - Read market regime and feature data for strategy logic

This is a thin API client — it talks to a running dMoERA backend
via HTTP. No internal dMoERA code is imported or included.

Configuration:
  Set DMOERA_API_URL environment variable (default: http://localhost:8000)
  Set DMOERA_API_KEY environment variable for authenticated endpoints (optional)

Run standalone:
    python mcp_creator_server.py

Or configure in your AI client's MCP settings:
    {
      "mcpServers": {
        "dmoera-creator": {
          "command": "python",
          "args": ["mcp_creator_server.py"],
          "env": {
            "DMOERA_API_URL": "https://api.dmoera.xyz"
          }
        }
      }
    }
"""
import os
import json
import urllib.request
import urllib.error
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ── Configuration ────────────────────────────────────────
API_URL = os.environ.get("DMOERA_API_URL", "http://localhost:8000").rstrip("/")
# API_KEY is read from env var at startup (for stdio mode) OR from the
# DMOERA_API_KEY HTTP header on each request (for hosted/Smithery mode).
# _get_api_key() checks both, with the header taking precedence.
import contextvars
_API_KEY_ENV = os.environ.get("DMOERA_API_KEY", "")
_API_KEY_CTX = contextvars.ContextVar("api_key_header", default="")

mcp = FastMCP(
    "dmoera-creator",
    instructions=(
        "dMoERA Creator Studio — build, test, and deploy crypto trading strategies. "
        "Available tools: list_domains, list_bots, get_bot_profile, get_feature_catalog, "
        "get_market_regime, get_current_prices, sandbox_backtest, submit_strategy, "
        "list_strategies, get_strategy_report, get_marketplace_bots, get_tournament_status, "
        "open_source_strategy, fork_strategy, get_open_source_leaderboard, delist_strategy. "
        "Read the creator-api-docs resource for the full strategy contract and examples."
    ),
)


def _resolve_api_key(explicit_key: str = "") -> str:
    """Resolve the API key: explicit param > HTTP header > env var."""
    if explicit_key:
        return explicit_key
    header_key = _API_KEY_CTX.get()
    if header_key:
        return header_key
    return _API_KEY_ENV


# ── HTTP helper ──────────────────────────────────────────
def _api_get(path: str, api_key: str = "") -> dict:
    """Make a GET request to the dMoERA API."""
    url = f"{API_URL}{path}"
    req = urllib.request.Request(url)
    key = _resolve_api_key(api_key)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body[:500]}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}. Is the dMoERA backend running at {API_URL}?"}
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, body: dict, api_key: str = "") -> dict:
    """Make a POST request to the dMoERA API."""
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    key = _resolve_api_key(api_key)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": f"HTTP {e.code}: {raw[:500]}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}. Is the dMoERA backend running at {API_URL}?"}
    except Exception as e:
        return {"error": str(e)}


# ── Discovery Tools ──────────────────────────────────────

# Static domain list — this is public information, not internal code
_DOMAINS = [
    {"key": "eth_usdc", "name": "ETH/USDC Swing", "type": "swing", "base_asset": "ETH", "quote_asset": "USDC", "grading_seconds": 3600, "feed_symbols": ["ETHUSDT"]},
    {"key": "btc_usdc", "name": "BTC/USDC Swing", "type": "swing", "base_asset": "BTC", "quote_asset": "USDC", "grading_seconds": 3600, "feed_symbols": ["BTCUSDT"]},
    {"key": "sol_usdc", "name": "SOL/USDC Swing", "type": "swing", "base_asset": "SOL", "quote_asset": "USDC", "grading_seconds": 3600, "feed_symbols": ["SOLUSDT"]},
    {"key": "eth_usdc_scalp", "name": "ETH/USDC Scalp", "type": "scalp", "base_asset": "ETH", "quote_asset": "USDC", "grading_seconds": 300, "feed_symbols": ["ETHUSDT"]},
    {"key": "btc_usdc_scalp", "name": "BTC/USDC Scalp", "type": "scalp", "base_asset": "BTC", "quote_asset": "USDC", "grading_seconds": 300, "feed_symbols": ["BTCUSDT"]},
    {"key": "sol_usdc_scalp", "name": "SOL/USDC Scalp", "type": "scalp", "base_asset": "SOL", "quote_asset": "USDC", "grading_seconds": 300, "feed_symbols": ["SOLUSDT"]},
]


@mcp.tool()
def list_domains() -> str:
    """List all available trading domains on dMoERA.

    Domains define what asset pair a strategy trades, what time horizon
    it uses (scalp=5m, swing=1h), and what data is available.
    Strategies must declare which domain they belong to.

    Returns a JSON array of domain objects with: key, name, type,
    base_asset, quote_asset, grading_seconds, and feed_symbols.
    """
    return json.dumps(_DOMAINS, indent=2)


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
    data = _api_get("/api/leaderboard")
    if "error" in data:
        return json.dumps(data, indent=2)

    bots = []
    for d in data.get("domains", []):
        d_key = d.get("domain_key", d.get("key", ""))
        if domain and d_key != domain:
            continue
        for b in d.get("bots", []):
            bots.append({
                "bot_id": b.get("bot_id", ""),
                "domain": d_key,
                "strategy_name": b.get("name", b.get("strategy_name", "unknown")),
                "sharpe": round(b.get("sharpe", b.get("sharpe_proxy", 0)), 3),
                "win_rate": round(b.get("win_rate", 0), 3),
                "total_trades": b.get("total_trades", b.get("total_predictions", 0)),
                "return_bps": round(b.get("return_bps", b.get("realized_return_bps", 0)), 1),
                "validation_score": round(b.get("validation_score", b.get("score", 0)), 1),
            })
    bots = bots[:max(1, min(limit, 100))]
    return json.dumps(bots, indent=2)


@mcp.tool()
def get_bot_profile(bot_id: str) -> str:
    """Get detailed profile and performance stats for a specific bot.

    Args:
        bot_id: The bot identifier (e.g. "Eth_Full_Ensemble").

    Returns JSON with: bot_id, domain, strategy type, full performance
    metrics (Sharpe, Sortino, Calmar, profit factor, win rate, return,
    max drawdown, avg trade), and proven tier.
    """
    data = _api_get(f"/api/strategy/{bot_id}/performance")
    if "error" in data:
        # Try the leaderboard and search for the bot
        lb = _api_get("/api/leaderboard")
        for d in lb.get("domains", []):
            for b in d.get("bots", []):
                if b.get("bot_id") == bot_id:
                    return json.dumps({
                        "bot_id": bot_id,
                        "domain": d.get("domain_key", ""),
                        "strategy_name": b.get("name", ""),
                        "performance": {
                            "sharpe": b.get("sharpe", b.get("sharpe_proxy", 0)),
                            "win_rate": b.get("win_rate", 0),
                            "total_trades": b.get("total_trades", b.get("total_predictions", 0)),
                            "total_return_bps": b.get("return_bps", b.get("realized_return_bps", 0)),
                            "max_drawdown_bps": b.get("max_drawdown_bps", 0),
                        },
                        "proven_tier": b.get("proven_tier", "unproven"),
                    }, indent=2)
        return json.dumps(data, indent=2)
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
def get_feature_catalog() -> str:
    """List all data feeds available to strategies via ctx.features.

    Features are external data that strategies can read during on_bar().
    Each feature has a status: "live" (available now) or "planned" (roadmap).

    Returns JSON array of features with: key, label, description, unit,
    example, cadence, source, and status.
    """
    data = _api_get("/api/creator/features")
    if "error" in data:
        return json.dumps(data, indent=2)
    return json.dumps(data.get("features", []), indent=2)


# ── Market Data Tools ────────────────────────────────────

@mcp.tool()
def get_market_regime() -> str:
    """Get current market regime classification.

    Returns the aggregate regime (e.g. "bull_calm", "bear_volatile"),
    per-symbol regimes, crisis score, and the derivatives data driving
    the classification (funding rates, open interest, long/short ratios).

    Regime determines which trade directions are allowed:
    - bull_* -> longs only
    - bear_* -> shorts only
    - neutral_* -> both longs and shorts
    - crisis/meltdown -> no new positions
    """
    return json.dumps(_api_get("/api/regime"), indent=2, default=str)


@mcp.tool()
def get_current_prices() -> str:
    """Get current live prices for all tracked symbols.

    Returns JSON with symbol -> {price, change_24h_pct, volume_24h, source}
    for ETHUSDT, BTCUSDT, SOLUSDT.
    """
    data = _api_get("/api/state")
    if "error" in data:
        return json.dumps(data, indent=2)
    # Extract market prices from the state payload
    markets = data.get("markets", [])
    prices = {}
    for m in markets:
        sym = m.get("symbol_key", m.get("symbol", ""))
        if sym:
            prices[sym] = {
                "price": m.get("price", 0),
                "change_24h_pct": m.get("change_24h_pct", 0),
                "volume_24h": m.get("volume_24h", 0),
                "source": m.get("source", ""),
            }
    return json.dumps(prices, indent=2)


# ── Strategy Development Tools ───────────────────────────

@mcp.tool()
def sandbox_backtest(
    code: str,
    domain: str = "eth_usdc",
    user_id: str = "mcp_sandbox",
    api_key: str = "",
) -> str:
    """Run a sandbox backtest of strategy code without persisting anything.

    This is the fastest way to test a strategy. The code is run through
    static checks and a full backtest on historical data, but no Strategy
    rows are created. Use this for rapid iteration.

    Args:
        code: Python source code implementing the Strategy contract.
              Must define a METADATA dict and a class extending Strategy
              with an on_bar(ctx) -> Signal method. See the strategy template resource.
        domain: Trading domain (e.g. "eth_usdc", "btc_usdc", "sol_usdc").
        user_id: Identifier for the creator (requires authentication for this endpoint).
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON with: success, metrics (sharpe, sortino, win_rate,
    total_trades, return_bps, max_drawdown, regime_breakdown),
    or error details if validation failed.
    """
    result = _api_post("/api/creator/sandbox", {
        "code": code,
        "domain": domain,
    }, api_key=api_key)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def submit_strategy(
    name: str,
    domain: str,
    code: str,
    user_id: str,
    symbol: str = "ETHUSDT",
    api_key: str = "",
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
        user_id: The creator's user ID (authentication required).
        symbol: Price symbol (auto-detected from domain if omitted).
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON with: success, strategy_id, bot_id, validation results
    per stage, or error details.
    """
    result = _api_post("/api/creator/strategies", {
        "name": name,
        "domain": domain,
        "code": code,
        "symbol": symbol,
    }, api_key=api_key)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def list_strategies(user_id: str, api_key: str = "") -> str:
    """List all strategies created by a user.

    Args:
        user_id: The creator's user ID (authentication required).
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON array of strategies with: id, bot_id, name, domain,
    status, and created_at.
    """
    return json.dumps(_api_get("/api/creator/strategies", api_key=api_key), indent=2, default=str)


@mcp.tool()
def get_strategy_report(strategy_id: int) -> str:
    """Get a detailed report card for a strategy.

    Includes validation run results for all 7 stages, performance metrics,
    and the integrity block (code hash, AST hash, parameter fingerprint).

    Args:
        strategy_id: The strategy's database ID.

    Returns JSON with: strategy details, latest validation runs, metrics.
    """
    return json.dumps(_api_get(f"/api/creator/report-card/{strategy_id}"), indent=2, default=str)


# ── Marketplace Tools ────────────────────────────────────

@mcp.tool()
def get_marketplace_bots(domain: Optional[str] = None, sort: str = "rating", limit: int = 20) -> str:
    """List bots published to the marketplace.

    Args:
        domain: Filter by domain (e.g. "eth_usdc"). Omit for all domains.
        sort: Sort order — "rating", "return", "subscribers", or "newest".
        limit: Max results (default 20, max 100).

    Returns JSON array of marketplace listings with: listing_id, bot_id,
    title, description, domain, creator, monthly_price_usd, stats
    (win_rate, return_bps, sharpe), subscriber_count, and avg_rating.
    """
    params = f"?sort={sort}&limit={max(1, min(limit, 100))}"
    if domain:
        params += f"&domain={domain}"
    return json.dumps(_api_get(f"/api/marketplace/bots{params}"), indent=2, default=str)


# ── Tournament Tools ─────────────────────────────────────

@mcp.tool()
def get_tournament_status() -> str:
    """Get current tournament round status and leaderboard.

    Tournaments run every 3 days. Top 3 bots per domain win prizes
    from the reward pool. Scoring is based on the bot's own performance:
    50% risk-adjusted (rolling Sharpe), 30% total return, 20% consistency.

    Returns JSON with: current round info (round_id, start/end time,
    reward_pool_usd, total_participants, hours_remaining), and leaderboard entries.
    """
    stats = _api_get("/api/tournament/stats")
    leaderboard = _api_get("/api/tournament/leaderboard?limit=20")
    result = {
        "stats": stats,
        "leaderboard": leaderboard.get("entries", []) if "error" not in leaderboard else [],
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def open_source_strategy(strategy_id: int, api_key: str = "") -> str:
    """Convert a rejected strategy to open-source status.

    The strategy must have passed stages 1-2 (static check + in-sample with
    >=5 trades). Its code becomes public on the open-source leaderboard where
    other creators can fork it. Open-source bots cannot enter tournaments or
    receive fund allocations — they're for community learning.

    Use this when a strategy fails full validation but still has educational
    value or interesting logic worth sharing.

    Args:
        strategy_id: The ID of the strategy to open-source (from submit_strategy
                     or list_strategies).
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON with: success, strategy_id, status, bot_id, or error.
    """
    result = _api_post(f"/api/creator/strategies/{strategy_id}/open-source", {}, api_key=api_key)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def fork_strategy(strategy_id: int, api_key: str = "") -> str:
    """Get the source code from an open-source strategy for forking.

    Returns the full code + parent info. Use this to study and remix
    open-source strategies from the open-source leaderboard. The actual
    submission of the forked code goes through submit_strategy with
    parent_strategy_id set (which the backend uses to exclude the parent
    from similarity checks).

    Args:
        strategy_id: The ID of the open-source strategy to fork.
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON with: success, parent_strategy_id, parent_bot_id,
    parent_name, parent_domain, code.
    """
    result = _api_post(f"/api/creator/strategies/{strategy_id}/fork", {}, api_key=api_key)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_open_source_leaderboard(
    sort_by: str = "overall",
    domain: str = "",
    limit: int = 20,
) -> str:
    """Browse the open-source strategy leaderboard with FIFA-style ratings.

    Each strategy gets an overall rating (0-99) with sub-ratings for edge,
    drawdown control, regime fit, risk, turnover, and robustness. Strategies
    are tagged with positions (GK, DEF, MID, FWD) and tier (Bronze, Silver,
    Gold, Elite) like FIFA Ultimate Team cards.

    Use this to discover strategies worth forking. Then call fork_strategy
    with the strategy_id to get the code.

    Args:
        sort_by: Sort key — overall | edge | dd_ctrl | regime | risk |
                 turnover | robust | forks | likes | return | sharpe |
                 trades | newest
        domain: Filter by domain (e.g. "eth_usdc"). Empty = all domains.
        limit: Max entries to return.

    Returns JSON with: success, count, and bot entries with ratings,
    validation metrics, creator_username, fork_count, like_count.
    """
    params = f"sort_by={sort_by}&limit={limit}"
    if domain:
        params += f"&domain={domain}"
    result = _api_get(f"/api/open-source/leaderboard?{params}")
    # Trim the entries to the requested limit
    if isinstance(result, dict) and "bots" in result:
        result["bots"] = result["bots"][:limit]
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def delist_strategy(strategy_id: int, tombstone: bool = False, api_key: str = "") -> str:
    """Delist a strategy from the platform.

    Retired bots (tombstone=False) stay visible with their performance history
    — bad performance can't be hidden. Tombstoned bots (tombstone=True) are
    permanently removed and cannot be re-submitted.

    Args:
        strategy_id: The ID of the strategy to delist.
        tombstone: If True, permanently remove (cannot re-submit). If False,
                   just retire (can re-submit with improvements).
        api_key: Your dMoERA Personal Access Token. Required for this tool.
                 Get one at https://dmoera.xyz → Settings → API Keys.
                 (If running locally with DMOERA_API_KEY env var set, this can be omitted.)

    Returns JSON with: success, strategy_id, status.
    """
    result = _api_post(
        f"/api/creator/strategies/{strategy_id}/delist",
        {"tombstone": tombstone},
        api_key=api_key,
    )
    return json.dumps(result, indent=2, default=str)


# ── Resources (read-only context) ────────────────────────

@mcp.resource("creator-api://docs")
def creator_api_docs() -> str:
    """The full creator API documentation for AI agents."""
    # Try to fetch from the running backend, fall back to embedded summary
    try:
        data = _api_get("/api/creator/features")
        features = data.get("features", []) if "error" not in data else []
    except Exception:
        features = []

    # Build feature table with backtest mode info
    if features:
        feature_table = "| Key | Label | Backtest | Status |\n|-----|-------|----------|--------|\n"
        for f in features:
            bt = f.get("backtest_mode", "unknown")
            bt_icon = {"real": "real history", "proxy": "estimated", "none": "live only"}.get(bt, bt)
            feature_table += f"| `{f.get('key', '')}` | {f.get('label', '')} | {bt_icon} | {f.get('status', '')} |\n"
    else:
        feature_table = "Call get_feature_catalog for the full list."

    return f"""# dMoERA Creator API — Strategy Contract

## Strategy Structure

Strategies subclass `Strategy` and implement `on_bar(self, ctx) -> Signal`.
**METADATA must be a CLASS ATTRIBUTE inside the Strategy subclass**, not a
module-level variable. If METADATA is at module level, validation will fail
with "Missing required METADATA field: name".

```python
class MyStrategy(Strategy):
    METADATA = {{
        "name": "My Strategy",
        "domain": "eth_usdc",           # eth_usdc, btc_usdc, sol_usdc, or _scalp variants
        "declared_sl_bps": 150.0,       # Stop-loss: 1.5%
        "declared_tp_bps": 300.0,       # Take-profit: 3.0%
        "declared_hold_seconds": 3600,  # Max hold: 1 hour
        "warmup_bars": 20,              # Bars needed before trading
        "required_features": [],         # External data feeds (see below)
    }}

    def initialize(self, ctx) -> None:
        pass

    def on_bar(self, ctx):
        closes = ctx.closes(lookback=20)
        if len(closes) < 20:
            return None
        sma_fast = sum(closes[-5:]) / 5
        sma_slow = sum(closes[-20:]) / 20
        if sma_fast > sma_slow:
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
            )
        elif sma_fast < sma_slow:
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
            )
        return None
```

## Available ctx methods

- `ctx.closes(lookback=N)` — last N close prices (oldest first)
- `ctx.opens(lookback=N)` — last N open prices
- `ctx.highs(lookback=N)` — last N high prices
- `ctx.lows(lookback=N)` — last N low prices
- `ctx.volumes(lookback=N)` — last N volumes
- `ctx.signal(direction, confidence, stop_loss_bps, take_profit_bps, horizon_seconds)` — return a signal
- `ctx.features.get(key, default)` — external data feed value (see feature catalog)

Note: There are no built-in indicator methods. Compute RSI, EMA, SMA, ATR etc.
manually from `ctx.closes()` / `ctx.highs()` / `ctx.lows()`. Example:
`ema = sum(closes[-period:]) / period` for a simple moving average.

## SignalDirection

- `SignalDirection.LONG` — buy/long position
- `SignalDirection.SHORT` — sell/short position

## Data Feeds (ctx.features)

Strategies can read external data via `ctx.features.get(key, default)`. Each feed has a
backtest mode that determines what validation feeds it:

- **real** — true point-in-time history. Backtest scores are valid.
- **proxy** — estimated from OHLCV data. Correlated with live but different distribution.
  Prefer relative comparisons (percentile, sign, change) over absolute thresholds.
- **none** — reads the default value during validation. Any branch on it is dead code
  in backtest. Only useful for live-only logic.

{feature_table}

### Example: Funding Rate Mean Reversion

```python
class FundingFadeStrategy(Strategy):
    \"\"\"Fade extreme funding rates — crowded longs tend to unwind.\"\"\"
    METADATA = {{
        "name": "Funding Fade",
        "domain": "eth_usdc",
        "declared_sl_bps": 200.0,
        "declared_tp_bps": 400.0,
        "declared_hold_seconds": 7200,
        "warmup_bars": 20,
        "required_features": ["funding_rate_ethusdt"],
    }}

    def on_bar(self, ctx):
        fr = ctx.features.get("funding_rate_ethusdt", 0.0)
        # Positive funding = longs pay shorts = crowded long
        if fr > 0.0003:  # 0.03% per 8h = very crowded
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.55,
                stop_loss_bps=200.0,
                take_profit_bps=400.0,
                horizon_seconds=7200,
                metadata={{"reason": "funding_crowded_long", "fr": fr}},
            )
        elif fr < -0.0003:  # crowded short
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.55,
                stop_loss_bps=200.0,
                take_profit_bps=400.0,
                horizon_seconds=7200,
                metadata={{"reason": "funding_crowded_short", "fr": fr}},
            )
        return None
```

### Example: Fear & Greed Contrarian

```python
class FngContrarianStrategy(Strategy):
    \"\"\"Buy extreme fear, sell extreme greed.\"\"\"
    METADATA = {{
        "name": "FNG Contrarian",
        "domain": "btc_usdc",
        "declared_sl_bps": 150.0,
        "declared_tp_bps": 300.0,
        "declared_hold_seconds": 86400,
        "warmup_bars": 10,
        "required_features": ["fear_greed_index"],
    }}

    def on_bar(self, ctx):
        fg = ctx.features.get("fear_greed_index", 50)
        if fg < 25:  # Extreme Fear
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=86400,
                metadata={{"reason": "extreme_fear", "fg": fg}},
            )
        elif fg > 75:  # Extreme Greed
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=86400,
                metadata={{"reason": "extreme_greed", "fg": fg}},
            )
        return None
```

### Example: Cross-Asset Relative Strength

```python
class RelStrengthStrategy(Strategy):
    \"\"\"Long ETH when it's outperforming BTC.\"\"\"
    METADATA = {{
        "name": "ETH-BTC Relative Strength",
        "domain": "eth_usdc",
        "declared_sl_bps": 200.0,
        "declared_tp_bps": 400.0,
        "declared_hold_seconds": 3600,
        "warmup_bars": 20,
        "required_features": ["btc_return_pct", "eth_return_pct"],
    }}

    def on_bar(self, ctx):
        btc_mom = ctx.features.get("btc_return_pct", 0.0)
        eth_mom = ctx.features.get("eth_return_pct", 0.0)
        spread = eth_mom - btc_mom
        if spread > 1.0:  # ETH outperforming by >1%
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.55,
                stop_loss_bps=200.0,
                take_profit_bps=400.0,
                horizon_seconds=3600,
                metadata={{"reason": "eth_outperforming", "spread": spread}},
            )
        elif spread < -1.0:
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.55,
                stop_loss_bps=200.0,
                take_profit_bps=400.0,
                horizon_seconds=3600,
                metadata={{"reason": "eth_underperforming", "spread": spread}},
            )
        return None
```

### Example: Order Book Imbalance (proxy — use relative comparisons)

```python
class BookImbalanceStrategy(Strategy):
    \"\"\"Trade with order book pressure. NOTE: backtest uses an OHLCV proxy —
    compare to recent range, not a fixed threshold.\"\"\"
    METADATA = {{
        "name": "Book Imbalance Signal",
        "domain": "eth_usdc",
        "declared_sl_bps": 100.0,
        "declared_tp_bps": 200.0,
        "declared_hold_seconds": 1800,
        "warmup_bars": 50,
        "required_features": ["book_imbalance_ethusdt"],
    }}

    def on_bar(self, ctx):
        imb = ctx.features.get("book_imbalance_ethusdt", 0.0)
        # Use sign and relative strength, not absolute thresholds
        # (proxy values have different distribution than live)
        if imb > 0.15:
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.5,
                stop_loss_bps=100.0,
                take_profit_bps=200.0,
                horizon_seconds=1800,
                metadata={{"reason": "buy_pressure", "imb": imb}},
            )
        elif imb < -0.15:
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.5,
                stop_loss_bps=100.0,
                take_profit_bps=200.0,
                horizon_seconds=1800,
                metadata={{"reason": "sell_pressure", "imb": imb}},
            )
        return None
```

## Validation Stages

1. static_check — banned imports, syntax, contract compliance
2. in_sample — backtest on training data
3. out_of_sample — test on unseen data (70/30 split)
4. walk_forward — 8 rolling windows, each with fit + test
5. randomized_start — different random start points
6. perturbation — market stress test
7. holdout — server-side reserved data (pass/fail only)

## Available Features (live)

{json.dumps(features, indent=2) if features else "Call get_feature_catalog for the full list."}

## Domains

{json.dumps(_DOMAINS, indent=2)}

## Tournament

3-day rounds. Bots qualify on their own performance (rolling Sharpe, return, consistency).
Top 3 per domain win USDT from the reward pool. No user following needed to qualify.

## Open Source

If a strategy fails full validation but passes stages 1-2 (static check + in-sample
with >=5 trades), you can open-source it with `open_source_strategy`. The code becomes
public on the open-source leaderboard (FIFA-style ratings, fork counts, likes).

Browse open-source strategies with `get_open_source_leaderboard`, then call
`fork_strategy` to get the code and remix it. Forked strategies are submitted via
`submit_strategy` — the parent is excluded from similarity checks automatically.

## Bot ID Naming

Bot IDs follow the pattern: `u_{{creator_id}}_{{domain_slug}}_{{strategy_name_slug}}`
(e.g. `u_3_eth_usdc_momentum_reversal`). The creator's username is attached to the
bot in the leaderboard (not the bot_id itself). Two different creators CAN submit
strategies with the same name — they get different bot_ids. The same creator
submitting the same name again creates a new VERSION of the existing strategy
(not a duplicate).

## Authentication

To use sandbox_backtest and submit_strategy, set the DMOERA_API_KEY environment variable
to a personal access token generated from your dMoERA account settings (Settings > API Keys).
"""


@mcp.resource("creator-api://strategy-template")
def strategy_template() -> str:
    """A copy-pasteable strategy template implementing the contract."""
    return '''"""
Strategy: [Your Strategy Name]
Domain: eth_usdc
"""

class MyStrategy(Strategy):
    """Describe your strategy's edge here."""

    METADATA = {
        "name": "[Your Strategy Name]",
        "domain": "eth_usdc",
        "declared_sl_bps": 150.0,
        "declared_tp_bps": 300.0,
        "declared_hold_seconds": 3600,
        "warmup_bars": 20,
        "required_features": [],
    }

    def initialize(self, ctx) -> None:
        """Called once before the first bar. Set up indicators."""
        pass

    def on_bar(self, ctx):
        """Called once per closed bar. Return a Signal or None."""
        closes = ctx.closes(lookback=20)
        if len(closes) < 20:
            return None

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


if __name__ == "__main__":
    import sys
    # Default to stdio (for local AI clients like Claude, Cursor, Windsurf).
    # Use "python mcp_creator_server.py http" to run as a hosted HTTP server
    # (for Smithery and other remote directories).
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport in ("http", "streamable-http"):
        port = int(os.environ.get("MCP_PORT", "8787"))
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = port
        mcp.settings.host = host
        # Allow external hosts through the DNS rebinding protection
        mcp.settings.transport_security.allowed_hosts = [
            "dmoera.xyz",
            "dmoera.xyz:*",
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ]
        mcp.settings.transport_security.allowed_origins = [
            "https://dmoera.xyz",
            "https://www.dmoera.xyz",
            "http://127.0.0.1:*",
            "http://localhost:*",
        ]
        # Wrap the ASGI app to read DMOERA_API_KEY from the HTTP header on each
        # request (Smithery and other hosted clients pass it as a header).
        # We can't use mcp.run() because it creates a new app internally —
        # instead we get the app, wrap it, and run uvicorn directly.
        import uvicorn
        import anyio

        starlette_app = mcp.streamable_http_app()

        # ASGI middleware wrapper — intercepts the raw ASGI scope to read headers
        # before the MCP server processes the request.
        class ApiKeyASGIMiddleware:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    for name, value in scope.get("headers", []):
                        if name == b"dmoera_api_key":
                            key = value.decode("utf-8")
                            _API_KEY_CTX.set(key)
                            print(f"[MCP] API key from header: {key[:16]}...")
                            break
                await self.app(scope, receive, send)

        app = ApiKeyASGIMiddleware(starlette_app)
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        anyio.run(server.serve)
    else:
        mcp.run()
