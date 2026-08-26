# dMoERA Creator Studio — MCP Server

[![smithery badge](https://smithery.ai/badge/mk9654/dMoERA-Creator)](https://smithery.ai/servers/mk9654/dMoERA-Creator)

Build, backtest, and deploy crypto trading strategies using any MCP-compatible AI agent (Claude, Cursor, Windsurf, Devin, Copilot, etc.).

## What it does

The dMoERA MCP server exposes the [dMoERA](https://dmoera.xyz) Creator API as Model Context Protocol tools. Your AI agent can:

- **Discover** trading domains, data feeds, and market regimes
- **Inspect** existing bots and their live performance metrics
- **Backtest** strategy code in a sandboxed environment
- **Submit** strategies for full 7-stage validation and live deployment
- **Monitor** tournament status, leaderboard rankings, and strategy report cards

This is a thin API client — it talks to a running dMoERA backend via HTTP. No internal dMoERA code is required.

## Installation

### Prerequisites

- Python 3.11+
- The `mcp` Python package (`pip install mcp`)
- A running dMoERA backend (or connect to the public instance)

### Setup

```bash
git clone https://github.com/CacheCarti/dmoera-mcp.git
cd dmoera-mcp
pip install -r requirements.txt
```

## MCP Configuration

Add this standard MCP configuration to Claude Desktop, Cursor, Windsurf, or another MCP client:

```json
{
  "mcpServers": {
    "dmoera-creator": {
      "command": "python",
      "args": ["/absolute/path/to/dmoera-mcp/mcp_creator_server.py"],
      "env": {
        "DMOERA_API_URL": "https://dmoera.xyz",
        "DMOERA_API_KEY": "your_optional_personal_access_token"
      }
    }
  }
}
```

The API key is optional for public market data and discovery tools. Create a Personal Access Token at [dmoera.xyz](https://dmoera.xyz) under **Settings → API Keys** to backtest, submit, fork, open-source, or delist strategies. Never commit your token.

Remote clients can connect through the Streamable HTTP endpoint:

```text
https://dmoera.xyz/mcp
```

## Tools

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `list_domains` | List all available trading domains (ETH, BTC, SOL — spot and scalp) | No |
| `list_bots` | List trading bots ranked by performance, optionally filtered by domain | No |
| `get_bot_profile` | Get detailed profile and performance stats for a specific bot | No |
| `get_feature_catalog` | List all data feeds available to strategies via `ctx.features` | No |
| `get_market_regime` | Get current market regime classification | No |
| `get_current_prices` | Get current live prices for all tracked symbols | No |
| `sandbox_backtest` | Backtest strategy code in a sandboxed environment | Yes |
| `submit_strategy` | Submit a strategy for full validation and live deployment | Yes |
| `list_strategies` | List all strategies created by a user | Yes |
| `get_strategy_report` | Get a detailed report card for a strategy | No |
| `get_marketplace_bots` | List bots published to the marketplace | No |
| `get_tournament_status` | Get current tournament round status and leaderboard | No |
| `open_source_strategy` | Publish an eligible rejected strategy to the open-source leaderboard | Yes |
| `fork_strategy` | Retrieve and fork an open-source strategy | Yes |
| `get_open_source_leaderboard` | Browse open-source strategies with FIFA-style ratings | No |
| `delist_strategy` | Retire or permanently delist one of your strategies | Yes |

## Resources

- `creator-api://docs` — Full strategy contract documentation
- `creator-api://strategy-template` — Copy-pasteable strategy template

## Example Usage

Ask your AI agent:

> "List all trading domains on dMoERA, then backtest a simple RSI mean-reversion strategy for ETH/USDC."

The agent will call `list_domains`, inspect the available markets, then call `sandbox_backtest` with strategy code it generates. You can iterate:

> "The Sharpe is too low. Try adding a volatility filter — only trade when ATR is above its 20-period average."

> "Submit this strategy to the ETH/USDC domain."

The agent calls `submit_strategy`, which runs the full 7-stage validation pipeline. If it passes, the strategy enters the live Arena and competes for tournament payouts.

## Strategy Contract

Strategies subclass `Strategy` and implement `on_bar(self, ctx) -> Signal`. See the `creator-api://docs` resource for the full contract.

```python
class MyStrategy(Strategy):
    METADATA = {
        "name": "SMA Crossover",
        "domain": "eth_usdc",
        "declared_sl_bps": 150.0,
        "declared_tp_bps": 300.0,
        "declared_hold_seconds": 3600,
        "warmup_bars": 20,
        "required_features": [],
    }

    def on_bar(self, ctx):
        closes = ctx.closes(lookback=20)
        if len(closes) < 20:
            return None
        fast = sum(closes[-5:]) / 5
        slow = sum(closes) / 20
        if fast > slow:
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.7,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
            )
        return None
```

## Tournament System

Bots compete in 3-day tournament rounds. Scoring is based on the bot's own performance:
- **50%** risk-adjusted (rolling Sharpe ratio)
- **30%** total return (log-scaled bps)
- **20%** consistency (win rate × trade volume)

Top 3 per domain win USDT from the reward pool. **No user following needed to qualify** — your bot competes on its own metrics.

## Links

- **Platform**: [dmoera.xyz](https://dmoera.xyz)
- **GitHub**: [github.com/CacheCarti/dmoera-mcp](https://github.com/CacheCarti/dmoera-mcp)
- **Twitter**: [@dMoERAHQ](https://x.com/dMoERAHQ)
- **Discord**: [discord.gg/gXWDjDdQv](https://discord.gg/gXWDjDdQv)

## License

MIT
