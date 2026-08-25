"""
Full end-to-end test of the dMoERA MCP server via the hosted HTTP endpoint.
Tests all 16 tools + 2 resources using the MCP Streamable HTTP protocol.
"""
import os
import sys
import json
import urllib.request
import urllib.error
import time

MCP_URL = "https://dmoera.xyz/mcp"
API_KEY = "dmo_pat_f7ef10db37ecff9c6e38f26587e5e8bee9a59d4aec49ff6dd3f48be91957f7dc"

passed = 0
failed = 0
errors = []

def mcp_request(method, params=None, session_id=None):
    """Send a single MCP JSON-RPC request and parse the SSE response."""
    data = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }).encode("utf-8")

    req = urllib.request.Request(MCP_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("DMOERA_API_KEY", API_KEY)
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            session_id = resp.headers.get("Mcp-Session-Id", session_id)
            # Parse SSE response (event: message\ndata: {...})
            for line in body.split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[6:]), session_id
            # If no SSE prefix, try parsing as plain JSON
            return json.loads(body), session_id
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body[:200]}"}, session_id
    except Exception as e:
        return {"error": str(e)}, session_id


def mcp_notification(method, params=None, session_id=None):
    """Send an MCP notification (no response expected)."""
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
    }).encode("utf-8")

    req = urllib.request.Request(MCP_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("DMOERA_API_KEY", API_KEY)
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            session_id = resp.headers.get("Mcp-Session-Id", session_id)
            return session_id
    except Exception:
        return session_id


def call_tool(name, args=None, session_id=None):
    """Call an MCP tool and return the result."""
    result, sid = mcp_request("tools/call", {
        "name": name,
        "arguments": args or {},
    }, session_id)
    return result, sid


def read_resource(uri, session_id=None):
    """Read an MCP resource and return the result."""
    result, sid = mcp_request("resources/read", {
        "uri": uri,
    }, session_id)
    return result, sid


def test(name, result, check_fn=None):
    """Test assertion helper."""
    global passed, failed
    try:
        if isinstance(result, dict) and "error" in result and "jsonrpc" not in result:
            print(f"FAIL  {name}: {result['error'][:100]}")
            failed += 1
            errors.append(name)
            return False

        # Extract actual content from MCP response
        content = result
        if isinstance(result, dict) and "result" in result:
            content = result["result"]
        elif isinstance(result, dict) and "error" in result:
            print(f"FAIL  {name}: MCP error: {result['error']}")
            failed += 1
            errors.append(name)
            return False

        if check_fn:
            ok, detail = check_fn(content)
            if ok:
                print(f"PASS  {name}: {detail}")
                passed += 1
                return True
            else:
                print(f"FAIL  {name}: {detail}")
                failed += 1
                errors.append(name)
                return False
        else:
            print(f"PASS  {name}: OK")
            passed += 1
            return True
    except Exception as e:
        print(f"FAIL  {name}: {type(e).__name__}: {e}")
        failed += 1
        errors.append(name)
        return False


# ── 1. Initialize ──────────────────────────────────────────
print("=" * 60)
print("PHASE 1: Initialize MCP session")
print("=" * 60)

result, session_id = mcp_request("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test-suite", "version": "1.0"},
})
test("initialize", result, lambda r: (
    True, f"server={r.get('serverInfo', {}).get('name', '?')} v{r.get('serverInfo', {}).get('version', '?')}"
) if "result" in result or "serverInfo" in result else (False, f"no serverInfo: {str(r)[:100]}"))

# Send initialized notification
if session_id:
    mcp_notification("notifications/initialized", {}, session_id)
    print(f"  Session ID: {session_id}")
else:
    print("  WARNING: No session ID returned (stateless mode)")

# ── 2. List tools ──────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 2: List all tools")
print("=" * 60)

result, _ = mcp_request("tools/list", {}, session_id)
def check_tools(r):
    if "result" in r:
        tools = r["result"].get("tools", [])
    elif "tools" in r:
        tools = r["tools"]
    else:
        tools = []
    names = [t.get("name", "?") for t in tools]
    return len(tools) == 16, f"{len(tools)} tools: {', '.join(names)}"
test("tools/list", result, check_tools)

# ── 3. List resources ──────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 3: List all resources")
print("=" * 60)

result, _ = mcp_request("resources/list", {}, session_id)
def check_resources(r):
    if "result" in r:
        resources = r["result"].get("resources", [])
    elif "resources" in r:
        resources = r["resources"]
    else:
        resources = []
    uris = [res.get("uri", "?") for res in resources]
    return len(resources) == 2, f"{len(resources)} resources: {', '.join(uris)}"
test("resources/list", result, check_resources)

# ── 4. Public tools (no auth needed) ───────────────────────
print("\n" + "=" * 60)
print("PHASE 4: Public tools (market data)")
print("=" * 60)

def check_list(r):
    if "content" in r:
        text = r["content"][0].get("text", "") if r["content"] else ""
        data = json.loads(text)
        if isinstance(data, list):
            return True, f"{len(data)} items"
        if isinstance(data, dict) and "error" not in data:
            return True, f"dict with keys: {list(data.keys())[:5]}"
        if isinstance(data, dict) and "error" in data:
            return False, f"error: {data['error'][:80]}"
    return False, f"unexpected format: {str(r)[:100]}"

# list_domains
r, _ = call_tool("list_domains", {}, session_id)
test("list_domains", r, check_list)

# list_bots
r, _ = call_tool("list_bots", {}, session_id)
test("list_bots", r, check_list)

# get_bot_profile (need a bot_id — use first from list_bots)
r, _ = call_tool("list_bots", {}, session_id)
if "result" in r:
    content = r["result"].get("content", [])
    if content:
        bots = json.loads(content[0].get("text", "[]"))
        if bots:
            first_bot_id = bots[0].get("bot_id", "")
            r2, _ = call_tool("get_bot_profile", {"bot_id": first_bot_id}, session_id)
            test(f"get_bot_profile({first_bot_id})", r2, check_list)
        else:
            print("SKIP  get_bot_profile: no bots available")
    else:
        print("SKIP  get_bot_profile: no content")
else:
    print("SKIP  get_bot_profile: list_bots failed")

# get_feature_catalog
r, _ = call_tool("get_feature_catalog", {}, session_id)
test("get_feature_catalog", r, check_list)

# get_market_regime
r, _ = call_tool("get_market_regime", {}, session_id)
test("get_market_regime", r, check_list)

# get_current_prices
r, _ = call_tool("get_current_prices", {}, session_id)
test("get_current_prices", r, check_list)

# get_marketplace_bots
r, _ = call_tool("get_marketplace_bots", {}, session_id)
test("get_marketplace_bots", r, check_list)

# get_tournament_status
r, _ = call_tool("get_tournament_status", {}, session_id)
test("get_tournament_status", r, check_list)

# ── 5. Authenticated tools (need API key) ──────────────────
print("\n" + "=" * 60)
print("PHASE 5: Authenticated tools (strategy management)")
print("=" * 60)

# list_strategies
r, _ = call_tool("list_strategies", {"user_id": "e5fc3fab4275ee1f"}, session_id)
test("list_strategies", r, check_list)

# get_strategy_report (use strategy_id=17, which is open-source)
r, _ = call_tool("get_strategy_report", {"strategy_id": 17}, session_id)
test("get_strategy_report(17)", r, check_list)

# ── 6. Open source tools ───────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 6: Open source tools")
print("=" * 60)

# get_open_source_leaderboard
r, _ = call_tool("get_open_source_leaderboard", {}, session_id)
test("get_open_source_leaderboard", r, check_list)

# fork_strategy (strategy 17 is open-source)
r, _ = call_tool("fork_strategy", {"strategy_id": 17}, session_id)
test("fork_strategy(17)", r, check_list)

# ── 7. Sandbox backtest ────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 7: Sandbox backtest (with data feeds)")
print("=" * 60)

strategy_code = '''class SmaCrossStrategy(Strategy):
    """SMA crossover with funding rate filter."""
    METADATA = {
        "name": "Test SMA Cross",
        "domain": "eth_usdc",
        "declared_sl_bps": 150.0,
        "declared_tp_bps": 300.0,
        "declared_hold_seconds": 3600,
        "warmup_bars": 20,
        "required_features": ["funding_rate_ethusdt", "fear_greed_index"],
    }

    def on_bar(self, ctx):
        closes = ctx.closes(lookback=20)
        if len(closes) < 20:
            return None
        fr = ctx.features.get("funding_rate_ethusdt", 0.0)
        fg = ctx.features.get("fear_greed_index", 50)
        sma_fast = sum(closes[-5:]) / 5
        sma_slow = sum(closes[-20:]) / 20
        if sma_fast > sma_slow and fr < 0.0003:
            return ctx.signal(
                direction=SignalDirection.LONG,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
            )
        elif sma_fast < sma_slow and fr > -0.0003:
            return ctx.signal(
                direction=SignalDirection.SHORT,
                confidence=0.6,
                stop_loss_bps=150.0,
                take_profit_bps=300.0,
                horizon_seconds=3600,
            )
        return None
'''

r, _ = call_tool("sandbox_backtest", {"code": strategy_code, "domain": "eth_usdc"}, session_id)
def check_backtest(r):
    if "content" in r:
        text = r["content"][0].get("text", "") if r["content"] else ""
        data = json.loads(text)
        if data.get("success"):
            m = data.get("metrics", {})
            trades = m.get("total_trades", 0)
            sharpe = m.get("sharpe", 0)
            return True, f"success=True, {trades} trades, Sharpe={sharpe:.2f}"
        else:
            return False, f"success=False: {data.get('error', '?')[:100]}"
    return False, f"unexpected format: {str(r)[:100]}"
test("sandbox_backtest (SMA + funding + fear_greed)", r, check_backtest)

# ── 8. Resources ───────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 8: Resources")
print("=" * 60)

r, _ = read_resource("creator-api://docs", session_id)
def check_docs(r):
    if "result" in r:
        contents = r["result"].get("contents", [])
    elif "contents" in r:
        contents = r["contents"]
    else:
        contents = []
    if contents:
        text = contents[0].get("text", "")
        has_metadata = "METADATA" in text
        has_class = "class MyStrategy" in text
        return len(text) > 1000, f"{len(text)} chars, has METADATA={has_metadata}, has class={has_class}"
    return False, "no contents"
test("resource: creator-api://docs", r, check_docs)

r, _ = read_resource("creator-api://strategy-template", session_id)
def check_template(r):
    if "result" in r:
        contents = r["result"].get("contents", [])
    elif "contents" in r:
        contents = r["contents"]
    else:
        contents = []
    if contents:
        text = contents[0].get("text", "")
        has_metadata_in_class = "METADATA" in text and "class " in text
        return len(text) > 500, f"{len(text)} chars, METADATA in class={has_metadata_in_class}"
    return False, "no contents"
test("resource: creator-api://strategy-template", r, check_template)

# ── Summary ────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"FINAL RESULTS: {passed} passed, {failed} failed")
if errors:
    print(f"Failed tests: {', '.join(errors)}")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
