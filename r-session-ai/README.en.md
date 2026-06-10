# 🦞 R Session AI — Lightweight Bridge Between R and AI Agents

Run inside RStudio Server, allowing AI agents (OpenClaw / Claude Desktop / any MCP client) to read, analyze, and manipulate data in the current R session — **data never leaves the server**.

## Architecture

```
┌── RStudio Server ───────────────────────────────────────────────────────┐
│                                                                         │
│  R Console (current session, normal interaction)                       │
│    ├── library(xxx)         ← User works as usual                      │
│    ├── df <- read.csv(...)                                              │
│    └── source("r-session-api.R")  ← Start API (set port + Token)       │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  R Session API (httpuv::startServer, same-process non-blocking HTTP)│
│  │                                                              │      │
│  │  ├── GET  /health     ← Health check                        │      │
│  │  ├── GET  /env        ← Browse R environment                │      │
│  │  ├── GET  /preview/x  ← Preview data                        │      │
│  │  ├── GET  /packages   ← Loaded packages                     │      │
│  │  ├── POST /eval       ← Execute R code → modify session (echo)     │
│  │  └── POST /eval/quiet ← Execute R code silently             │      │
│  │                                                              │      │
│  │  └─ All requests verify Bearer Token, no/invalid token → 401│      │
│  └──────────────────────┬───────────────────────────────────────┘      │
└─────────────────────────┼──────────────────────────────────────────────┘
                          │ HTTP (127.0.0.1:{R_API_PORT})
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OpenClaw (main process)                                                │
│                                                                         │
│  ┌─ openclaw.json → mcp.servers.r-session ──────────────────────────┐  │
│  │  command: python3 r-session-mcp-server.py                        │  │
│  │  env: { R_API_HOST, R_API_PORT, R_API_TOKEN }                    │  │
│  │  Spawns MCP Server as stdio subprocess                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                         │                                               │
│                         │ subprocess stdin/stdout                       │
│                         ▼                                               │
│  ┌─ r-session-mcp-server.py ──────────────────────────────────────┐    │
│  │  Calls R API via HTTP (automatically carries Bearer Token)      │    │
│  │  ├── list_objects → GET /env                                   │    │
│  │  ├── run_code    → POST /eval {code: "..."}                    │    │
│  │  └── export_data → POST /eval {fwrite code}                    │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Same process**: API runs within R's main process; `startServer` does not block the Console
- **Writable**: `POST /eval` code executes directly in `.GlobalEnv`
- **Local only**: Listens on `127.0.0.1`, data never leaves the server
- **Token authentication**: All API requests must carry a Bearer Token to prevent unauthorized access
- **Model agnostic**: Model choice is controlled by OpenClaw; any model (local or domestic) can be used

------------------------------------------------------------------------

## Quick Start

### 1. Install R Dependencies

In the R Console:

``` r
install.packages(c("httpuv", "jsonlite"))
```

### 2. Start the R API Server

Execute in RStudio Console:

``` r
# First set the Token (required for API authentication!)
options(rsession_api_token = "your-secret-token-here")

# Start the API (default port 8161, see below for custom port)
source("r-session-ai/r-session-api.R")
```

You'll see:

```
┌─────────────────────────────────────────────┐
│  🦞 R Session API Started                   │
│  Address: http://127.0.0.1:8161             │
│  Token Auth: ✅ Enabled                     │
│  Console Echo: ✅ On (source=echo)          │
└─────────────────────────────────────────────┘
```

The Console remains usable for normal R operations.

### 3. Configure MCP Server in OpenClaw (Recommended: stdio mode)

Add this to the `mcp.servers` section of your `openclaw.json`:

``` json
"r-session": {
  "command": "/path/to/your/python3",
  "args": [
    "/path/to/r-session-ai/r-session-mcp-server.py"
  ],
  "env": {
    "R_API_HOST": "127.0.0.1",
    "R_API_PORT": "8161",
    "R_API_TOKEN": "your-secret-token-here"
  }
}
```

**Example (graphrag conda environment):**

``` json
"r-session": {
  "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
  "args": [
    "/home/ubuntu/.openclaw/workspace/r-session-ai/r-session-mcp-server.py"
  ],
  "env": {
    "R_API_HOST": "127.0.0.1",
    "R_API_PORT": "8161",
    "R_API_TOKEN": "your-secret-token-here"
  }
}
```

Restart OpenClaw after configuration to automatically start the MCP Server.

### 4. Install Python Dependencies (MCP Server side)

``` bash
pip install mcp httpx
```

### 5. Verification

```
You: What data is in the RStudio environment?
AI: → list_objects()
You: Preview mtcars
AI: → preview_data("mtcars")
You: Analyze the relationship between mpg and wt
AI: → run_code("cor(mtcars$mpg, mtcars$wt)")
You: Create a new data frame with standardized variables
AI: → run_code("mtcars_scaled <- as.data.frame(scale(mtcars))")
```

After execution, variables will appear in RStudio's Environment panel.

------------------------------------------------------------------------

## Tool Reference

| Tool | API Endpoint | Description |
|----|----|----|
| `list_objects()` | `GET /env` | List all objects (name/class/size) |
| `preview_data(name)` | `GET /preview/{name}` | DataFrame preview + summary |
| `get_object_info(name)` | `GET /preview/{name}` | `str()` of any object |
| `run_code(code, quiet)` | `POST /eval` | Execute R code, **can modify session** |
| `get_loaded_packages()` | `GET /packages` | List loaded packages |
| `export_data(name)` | `POST /eval` | R → Python data export |
| `import_data(path, var_name)` | `POST /eval` | Python → R data import |
| `health_check()` | `GET /health` | Connection test |

------------------------------------------------------------------------

## Stopping

``` r
httpuv::stopServer(server)
httpuv::stopAllServers()
```

------------------------------------------------------------------------

## Multi-User Deployment

### R API Server Port Allocation

In multi-user environments, each user's R API Server must use a different port. Set the port via `options()` before `source()`:

``` r
# User A (RStudio instance 1)
options(rsession_api_port = 8161)
options(rsession_api_token = "token-for-user-a")
source("r-session-ai/r-session-api.R")

# User B (RStudio instance 2)
options(rsession_api_port = 8162)
options(rsession_api_token = "token-for-user-b")
source("r-session-ai/r-session-api.R")

# User C (RStudio instance 3)
options(rsession_api_port = 8163)
options(rsession_api_token = "token-for-user-c")
source("r-session-ai/r-session-api.R")
```

### OpenClaw Configuration (one per user)

Each user configures their own `openclaw.json` with matching port and Token:

``` json
"r-session": {
  "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
  "args": ["/home/user-name/r-session-ai/r-session-mcp-server.py"],
  "env": {
    "R_API_HOST": "127.0.0.1",
    "R_API_PORT": "8161",        ← Must match options() port
    "R_API_TOKEN": "token-for-user-a"  ← Must match options() Token
  }
}
```

### Why stdio Mode for Multi-User

| | **stdio mode (recommended)** | **HTTP / SSE mode** |
|----|----|----|
| **Communication** | OpenClaw spawns MCP Server as a subprocess, communicates via stdin/stdout | MCP Server listens on a network port, communicates via HTTP / SSE |
| **Port conflicts** | None. Each user's MCP Server is an independent OS process, no ports needed | Yes. MCP Server itself also requires a port |
| **Security** | No network exposure, subprocess isolation, users invisible to each other | MCP port opens potential attack surface |
| **Multi-user deployment** | ✅ Native support. Each user configures independently in their own `openclaw.json` | ❌ Both MCP Server and R API Server need port allocation |

> **Note:** In multi-user environments, the R API Server still needs different ports per user (specified via `options(rsession_api_port = ...)`), since httpuv listens on a network port. However, MCP Servers use stdio isolation and don't consume any ports.

------------------------------------------------------------------------

## Security

### Token Authentication Design

```
┌─ openclaw.json ───────────────────────────────────────────┐
│ "r-session": {                                             │
│   "env": {                                                 │
│     "R_API_TOKEN": "your-secret-token-here"               │
│   }                                                        │
│ }                                                          │
└──────────────────────┬─────────────────────────────────────┘
                       │ Passed to MCP Server process as env var
                       ▼
┌─ r-session-mcp-server.py ─────────────────────────────────┐
│ _client_headers["Authorization"] =                        │
│     f"Bearer {R_API_TOKEN}"                               │
│ → All HTTP requests automatically include Bearer Token    │
└──────────────────────┬─────────────────────────────────────┘
                       │ HTTP requests (with Authorization header)
                       ▼
┌─ R Session API (r-session-api.R) ─────────────────────────┐
│                                                            │
│  Token priority:                                           │
│  1. options(rsession_api_token = "...")  ← Recommended     │
│  2. Sys.getenv("R_API_TOKEN")                              │
│  3. Empty → no auth (single-user local debug only)        │
│                                                            │
│  Each request (except OPTIONS):                            │
│    auth_header <- req$HTTP_AUTHORIZATION                   │
│    token <- sub("^Bearer[[:space:]]+", "", auth_header)    │
│    if (token != API_TOKEN) → Return 401                    │
└────────────────────────────────────────────────────────────┘
```

### Configuration Steps

**1. Set Token on the R side (pick one):**

``` r
# Recommended: via options (highest priority)
options(rsession_api_token = "my-strong-token-abc123")

# Or: via environment variable
Sys.setenv(R_API_TOKEN = "my-strong-token-abc123")
```

**2. Configure the same Token in OpenClaw:**

In your `openclaw.json` `env` field, use the same Token:

``` json
"env": {
  "R_API_PORT": "8161",
  "R_API_TOKEN": "my-strong-token-abc123"
}
```

### Security Layers

| Layer | Description |
|----|----|
| **Token authentication** | All API endpoints (except OPTIONS) verify Bearer Token; mismatch returns `401 Unauthorized` |
| **127.0.0.1 only** | httpuv only listens on the loopback address, inaccessible from external networks |
| **MCP Server local subprocess** | In stdio mode, MCP Server has no network port, pure local communication |
| **Token in memory only** | Configured in R options (in-memory), not stored in plain text on the filesystem |

### Token Generation

``` bash
# Generate a strong random Token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

In multi-user deployments, each user should have a different Token.

------------------------------------------------------------------------

## Advanced Configuration

### Custom Port

``` r
options(rsession_api_port = 8226)
options(rsession_api_token = "your-token")
source("r-session-ai/r-session-api.R")
```

### Environment Variables (Alternative to options)

``` bash
export R_API_PORT=8161
export R_API_TOKEN=your-token
```

Then just `source("r-session-ai/r-session-api.R")` in R.

### Token Priority

| Priority | Source | How to Set |
|----|----|----|
| Highest | `options(rsession_api_token = "...")` | In R Console |
| Medium | Environment variable `R_API_TOKEN` | `Sys.setenv()` or `.Renviron` |
| Lowest | Empty (no auth) | Single-user local debug only |

------------------------------------------------------------------------

## Comparison with Other Solutions

| | Posit AI | Rserve | plumber | **This Solution** |
|----|----|----|----|----|
| Same process | ✅ | ❌ fork | ✅ (but blocking) | ✅ |
| Non-blocking Console | ✅ | ✅ | ❌ | ✅ |
| Writable session | ✅ | ❌ | ✅ | ✅ |
| Token auth | ✅ | ❌ | ❌ | ✅ |
| China-usable | ❌ | ✅ | ✅ | ✅ |
| Data leaves server | ✅ | ❌ | ❌ | ❌ |
| Model freedom | ❌ | ✅ | ✅ | ✅ |
| Free | ❌ | ✅ | ✅ | ✅ |

------------------------------------------------------------------------

## Dependencies

- **R side:** `httpuv`, `jsonlite` (CRAN packages)
- **MCP side (optional):** Python 3.8+, `mcp`, `httpx`

------------------------------------------------------------------------

## License

MIT
