FROM python:3.11-slim

WORKDIR /app

# Install the MCP SDK (only dependency)
RUN pip install --no-cache-dir "mcp[cli]>=1.0.0"

# Copy the server
COPY mcp_creator_server.py .

# Expose the HTTP transport port
EXPOSE 8787

# Run as HTTP server (Smithery proxies to this URL)
# Users set DMOERA_API_KEY env var when configuring their client
CMD ["python", "mcp_creator_server.py", "http"]
