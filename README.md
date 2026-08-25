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
git clone https://github.com/dMoERA/dmoera-mcp.git
cd dmoera-mcp
pip install -r requirements.txt
```

## Configuration

Set the backend URL via environment variable:

```bash
# Default: http://localhost:8000
export DMOERA_API_URL=https://api.dmoera.xyz

# Optional: API key for authenticated endpoints (sandbox backtest, strategy submission)
export DMOERA_API_KEY=your_api_key_here
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dmoera-creator": {
      "command": "python",
      "args": ["mcp_creator_server.py"],
      "cwd": "/path/to/dmoera-mcp",
      "env": {
        "DMOERA_API_URL": "https://api.dmoera.xyz"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "dmoera-creator": {
      "command": "python",
      "args": ["mcp_creator_server.py"],
      "cwd": "/path/to/dmoera-mcp",
      "env": {
        "DMOERA_API_URL": "https://api.dmoera.xyz"
      }
    }
  }
}
```

### Windsurf

Add to `.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "dmoera-creator": {
      "command": "python",
      "args": ["mcp_creator_server.py"],
      "cwd": "/path/to/dmoera-mcp",
      "env": {
        "DMOERA_API_URL": "https://api.dmoera.xyz"
      }
    }
  }
}
```

## Available Tools

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
    def on_bar(self, ctx):
        rsi = ctx.rsi(14)
        if rsi < 30:
            return ctx.signal(direction=SignalDirection.LONG, confidence=0.7)
        elif rsi > 70:
            return ctx.signal(direction=SignalDirection.SHORT, confidence=0.7)
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
- **GitHub**: [github.com/dMoERA/dmoera-mcp](https://github.com/dMoERA/dmoera-mcp)
- **Twitter**: [@dMoERAHQ](https://x.com/dMoERAHQ)
- **Discord**: [discord.gg/gXWDjDdQv](https://discord.gg/gXWDjDdQv)

## License

MIT
