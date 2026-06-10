---
output:
  word_document: default
  html_document: default
---

# r-session MCP Server: Principles, Architecture & Implementation

> Empowering AI agents to directly control RStudio's current R Session — read data, perform analysis, write results

------------------------------------------------------------------------

## I. Overall Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RStudio Server (Browser)                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  R Console                                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │ library(readxl)                                                 │ │   │
│  │  │ df <- read_excel("data.xlsx")  ← User works as usual           │ │   │
│  │  │ source("r-session-api.R")      ← Start API                     │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  │  R Environment Panel:                                                │   │
│  │  ├── df             48 obs. of 3 variables                           │   │
│  │  ├── model          lm(formula = ...)                                │   │
│  │  └── plot           ← AI-created chart                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ Same R process
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     R Session (single process, non-blocking)                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  httpuv::startServer(HOST, PORT, app)                                │   │
│  │                                                                      │   │
│  │  ├── GET /health       → { status, r_version, pid }                  │   │
│  │  ├── GET /env          → { objects: [...], count: N }                │   │
│  │  ├── GET /packages     → { packages: {...}, count: N }               │   │
│  │  ├── GET /preview/{x}  → { head, summary, str, dim, na_count }       │   │
│  │  ├── POST /eval        → eval(code, console_echo=TRUE)               │   │
│  │  ├── POST /eval/quiet  → eval(code, console_echo=FALSE)              │   │
│  │  └── All requests verify Bearer Token (if configured)                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ HTTP (127.0.0.1:8161)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      r-session-mcp-server.py (Python)                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  RPC Layer (httpx, synchronous client)                               │   │
│  │  rpc_get(path)  → GET http://127.0.0.1:8161/{path}                   │   │
│  │  rpc_post(path, body) → POST http://127.0.0.1:8161/{path}            │   │
│  │  Auto-carries Authorization: Bearer <token> (if configured)          │   │
│  │  Cleans proxy env vars on startup (ALL_PROXY/socks5 compatible)      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  MCP Protocol Layer                                                  │   │
│  │  - 8 tool definitions (types.Tool)                                   │   │
│  │  - handle_call_tool dispatch — formatted output                      │   │
│  │  - stdio / HTTP SSE dual transport mode                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  shared_dir (R ↔ Python Data Exchange)                               │   │
│  │  - export_data: R side fwrite → CSV → shared directory               │   │
│  │  - import_data: CSV → R side fread → .GlobalEnv                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ MCP Protocol (stdio / SSE)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway                                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  MCP Runtime: spawn python3 r-session-mcp-server.py                  │   │
│  │  Tools: r-session__run_code, r-session__preview_data, ...            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  AI Model (DeepSeek / GLM / Kimi / Domestic full-powered ...)        │   │
│  │  User → "Analyze the mtcars dataset"                                 │   │
│  │  AI  → r-session__list_objects() → see what data exists             │   │
│  │  AI  → r-session__preview_data("mtcars") → preview                  │   │
│  │  AI  → r-session__run_code("cor(mtcars$mpg, mtcars$wt)") → analyze  │   │
│  │  AI  → r-session__export_data("result") → export to CSV → Python    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

------------------------------------------------------------------------

## II. Core Design Principles

### 2.1 Why Not Fork/Subprocess?

Most R API solutions (e.g., plumber, Rserve) execute code in new processes, which means:

- ❌ Cannot access variables in the current RStudio session
- ❌ Created objects don't appear in RStudio's Environment panel
- ❌ Users need to repeatedly load data and install packages

This solution chooses **same process + non-blocking HTTP**:

```
R Main Process:
├── R Console (user interaction, non-blocking)
├── R API (httpuv::startServer, event-driven, non-blocking)
│   └── GET/POST requests → eval() → direct .GlobalEnv manipulation
└── Variables sync in real-time between Console, Environment panel, and API
```

`httpuv::startServer()` is based on the libuv event loop, sharing the same process as the R Console. When the R Console is executing code, API requests queue up; when the API is processing a request, Console input queues up. Neither blocks the other — this is httpuv's core capability as an async networking framework.

### 2.2 Security Design

| Measure | Implementation |
|----|----|
| Local only | Listens on `127.0.0.1`, default port 8161 |
| Token auth | Bearer Token, optional (R options / env variable) |
| Data stays on-premises | Entirely local network communication, CSV written to local shared directory |
| eval permission | Equivalent to the user executing code in Console themselves |

### 2.3 Token Authentication Design (Added 2026-06-07)

**Background:** In multi-user environments, the R API binds to 127.0.0.1 but is accessible to all local users. Malicious users could scan ports and execute arbitrary R code via `curl http://127.0.0.1:8161/eval`.

**Solution:** Add Bearer Token authentication to both R API and MCP Server

```
┌─ openclaw.json ──────────────────────────────────┐
│ "r-session": {                                    │
│   "env": {                                        │
│     "R_API_TOKEN": "<secret>"                     │
│   }                                               │
│ }                                                 │
└───────────────────────────────────────────────────┘
     │ Passed to MCP Server
     ▼
┌─ r-session-mcp-server.py ────────────────────────┐
│ _client_headers["Authorization"]                 │
│     = f"Bearer {R_API_TOKEN}"                    │
│ → All requests carry Bearer Token                │
└───────────────────────────────────────────────────┘
     │ HTTP requests
     ▼
┌─ r-session-api.R ────────────────────────────────┐
│ API_TOKEN <- getOption(                           │
│  "rsession_api_token",                            │
│  Sys.getenv("R_API_TOKEN", ...))                  │
│  Each request validates Authorization header     │
│  Mismatch → 401 unauthorized                     │
└───────────────────────────────────────────────────┘
```

**Token priority:** `options(rsession_api_token=...)` > env var `R_API_TOKEN` > empty (no auth)

**Multi-user deployment:** Each user has a different Token, injected via `openclaw.json`'s `env`.

------------------------------------------------------------------------

## III. R-Side Core Code Details

### 3.1 R Session API Server

**Location:** `r-session-api.R`

**Startup:** Run `source("r-session-api.R")` in RStudio Console

**Dependencies:** `httpuv` (HTTP server) + `jsonlite` (JSON serialization)

#### Configuration Priority

| Setting | R options | Env Variable | Default |
|----|----|----|----|
| Port | `rsession_api_port` | `R_API_PORT` | `8161` |
| Host | `rsession_api_host` | — | `127.0.0.1` |
| Max preview rows | `rsession_api_max_rows` | — | `100` |
| str truncation level | `rsession_api_max_str` | — | `20` |
| API Token | `rsession_api_token` | `R_API_TOKEN` | Empty (no auth) |

**Priority rule:** Env variables > R options > Defaults

#### Safe Evaluator: safe_eval()

```
safe_eval(code, env = .GlobalEnv, console_echo = TRUE)
```

This is the core function, responsible for:

1. **Pre-execution snapshot:** Record `ls(envir = env)` to get current variable list
2. **Execute code:** `eval(parse(text = code), envir = env)`
   - Uses `withVisible()` to detect explicit return values
   - When `console_echo=TRUE`: `sink()` to temp file + `split=TRUE` to echo to Console simultaneously
   - When `console_echo=FALSE`: `capture.output()` captures only, no display
3. **Post-execution comparison:** Detect new/modified variables (`setdiff(after, before)`)
4. **Return value:**

``` json
{
  "success": true,
  "error": null,
  "output": ["[1] 0.89", ...],
  "result": 0.89,
  "result_class": "numeric",
  "new_objs": ["my_model", "result_df"],
  "changed": true
}
```

**Exception safety:** Wrapped in `tryCatch`; errors returned as `error` field without affecting session state.

#### HTTP Routes

| Route | Method | Purpose | Implementation |
|----|----|----|----|
| `/health` | GET | Health check | `list(status="alive", r_version, pid, host, port)` |
| `/env` | GET | List global variables | `lapply(ls(), obj_to_list)` |
| `/packages` | GET | List loaded packages | `loadedNamespaces()` + `packageVersion()` |
| `/preview/{name}` | GET | Preview object | `safe_str()`, `head()`, `summary()`, `is.na()` |
| `/eval` | POST | Execute R code | `safe_eval(code, console_echo=TRUE)` |
| `/eval/quiet` | POST | Silent execution | `safe_eval(code, console_echo=FALSE)` |
| OPTIONS | Any | CORS preflight | Returns Allow-Origin/Methods/Headers |

#### Object Serialization: obj_to_list()

Recursively converts R objects to JSON-serializable lists:

``` r
obj_to_list(name, obj, depth = 0, max_depth = 2):
  ├── name, class, type, size
  ├── data.frame / matrix → dim, colnames, dtypes, nrow, ncol, dimnames
  ├── list             → length, names
  ├── atomic (≤100)    → values
  ├── atomic (>100)    → summary
  ├── function         → args
  └── environment      → n_objects
```

#### Token Validation

Each request (except OPTIONS) validates the `Authorization` header:

``` r
auth_header <- req$HTTP_AUTHORIZATION %||% ""
token <- sub("^Bearer[[:space:]]+", "", auth_header)
if (token != API_TOKEN) {
  # Return 401
}
```

#### CORS Handling

All responses include `Access-Control-Allow-Origin: *` header. Preflight requests (OPTIONS) return 200 with allowed methods and headers (including `Authorization`).

#### Cleanup on Exit

`reg.finalizer(server, ...)` ensures the httpuv server is automatically stopped when the R session exits.

------------------------------------------------------------------------

### 3.2 Why R Can Run an HTTP Service Without Blocking the Console

``` r
server <- startServer(HOST, PORT, app)
```

`httpuv::startServer()` starts a **non-blocking** HTTP server:

1. Uses libuv event loop internally
2. Registers callback functions (`app$call`) to handle HTTP requests
3. Does not occupy the R Console's main thread
4. R Console continues to accept normal input and execute code
5. When API requests arrive, R processes them in the current event loop iteration

This is analogous to Node.js's event loop — main thread is non-blocking, I/O events are handled via callbacks.

### 3.3 Console Echo Mode Comparison

| Mode | Implementation | Console Behavior During Execution | Output Capture |
|----|----|----|----|
| `console_echo=TRUE` | `sink(file, split=TRUE)` | Output echoes to Console in real-time | Read back from temp file |
| `console_echo=FALSE` | `capture.output({ ... })` | No output displayed | Captured in memory directly |

`sink(split=TRUE)` was chosen over `capture.output()` because:
- `capture.output()` suppresses Console output (user can't see what AI is executing)
- `sink(split=TRUE)` both captures to file AND echoes to Console simultaneously
- Users can see the AI "typing" in real-time in RStudio Console

------------------------------------------------------------------------

## IV. MCP Server Side Details

### 4.1 Python MCP Server

**Location:** `r-session-mcp-server.py`

**Shebang:** `#!/usr/lib64/anaconda3/envs/graphrag/bin/python3`

**Dependencies:** `mcp` (MCP protocol), `httpx` (HTTP client)

#### Environment Variables

| Variable | Default | Description |
|----|----|----|
| `R_API_HOST` | `127.0.0.1` | R API address |
| `R_API_PORT` | `8161` | R API port |
| `R_API_TOKEN` | Empty | Bearer Token (empty = no auth) |
| `MCP_PORT` | `0` | MCP Server port; `0` = stdio mode |
| `R2PY_SHARED_DIR` | `~/workspace/r2py/` | R↔Python data exchange directory |
| `R_SHARED_DIR` | Same as `R2PY_SHARED_DIR` | R-side override |

#### Proxy Compatibility

MCP Server **clears all proxy environment variables** on startup:

``` python
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
os.environ.pop("HTTP_PROXY", None)
# ... all 6 common proxy env vars cleared
```

This is because the system may have `ALL_PROXY=socks5://...` configured, which causes `httpx.Client()` to crash during initialization when resolving the SOCKS5 proxy — even if `NO_PROXY` includes `127.0.0.1`, because httpx resolves the proxy at Client construction time.

#### httpx Client Configuration

``` python
_client_headers = {}
if R_API_TOKEN:
    _client_headers["Authorization"] = f"Bearer {R_API_TOKEN}"
_client = httpx.Client(
    base_url=R_API_BASE,
    timeout=30.0,
    headers=_client_headers
)
```

- Synchronous client, simplifies code logic
- 30-second timeout, suitable for most R analysis tasks
- Auto-carries Token (if configured)

#### Call Flow

```
OpenClaw → callTool(run_code, {code: "..."})
                    │
                    ▼
              handle_call_tool("run_code", args)
                    │
                    ▼
              rpc_post("/eval", {"code": "..."})
                    │
                    ▼  HTTP POST (with Bearer Token)
              R Session API
                    │
                    ▼  safe_eval(code) → modifies .GlobalEnv
                    │
                    ▼  JSON response
              Python receives result
                    │
                    ▼  Format output (table/text layout)
              [types.TextContent]
                    │
                    ▼
              OpenClaw → AI Model
```

#### MCP Tool Definitions (8 tools)

| Tool | HTTP Call | Data Formatting | Output Style |
|----|----|----|----|
| `list_objects` | `GET /env` | Table: name, class, size, dims | Plain text table |
| `preview_data(name)` | `GET /preview/{name}` | str + head + summary + missing values | Structured text |
| `get_object_info(name)` | `GET /preview/{name}` | str output | Plain text |
| `run_code(code, quiet)` | `POST /eval` or `/eval/quiet` | Success/fail + output + new vars + return | Structured text |
| `get_loaded_packages` | `GET /packages` | Package name + version list | Plain text table |
| `health_check` | `GET /health` | R version, PID, address | Structured text |
| `export_data(name)` | `POST /eval` (fwrite) | CSV path + confirmation | Plain text |
| `import_data(path, var_name)` | `POST /eval` (fread) | Import confirmation | Plain text |

#### Output Formatting Details

- **list_objects:** Table with 20/18/6 column widths, Emoji icons
- **preview_data:** Sectioned display (structure → preview → summary → missing values), horizontal separators
- **run_code:** Output truncated to 200 lines + new variable list + return value summary
- **Error handling:** Three-level hierarchy (`httpx.ConnectError` → `httpx.HTTPStatusError` → generic Exception)

------------------------------------------------------------------------

## V. R ↔ Python Data Exchange

### Design Philosophy

- **Small datasets only** cross sessions; large datasets stay in their original session
- **CSV only** — R's `data.table::fwrite/fread` and Python's `pandas.read_csv/to_csv` both support it natively
- CSV type mapping may lose precision, but small datasets can be fixed with a few `as.integer()` / `astype()` calls
- Core principle: **Simple and universal, occasional manual correction**

### Architecture

```
R Session → R API (httpuv) → r-session-mcp (Python) → CSV
                                                         ↓
Jupyter Kernel ← jupyter-mcp (Python) ← CSV
```

### Tools

**r-session-mcp (R side read/write):**

| Tool | Internal Implementation |
|----|----|
| `export_data(name)` | Execute `data.table::fwrite(obj, path, row.names=FALSE)` on R side |
| `import_data(path, var_name)` | Execute `data.table::fread(path)` → `.GlobalEnv` on R side |

### Type Mapping Verified

**R → CSV → Python (`pd.read_csv`):**

| R | CSV | Python |
|----|----|----|
| integer | `1` | int64 ✅ |
| numeric | `10.5` | float64 ✅ |
| character | `Alice` | object ✅ |
| logical | `TRUE` | bool ✅ |
| IDate/Date | `2026-06-07` | object (string) ❌ → needs `pd.to_datetime()` |
| POSIXct | `2026-06-07 10:30:00` | object (string) ❌ → needs `pd.to_datetime()` |

**Python → R (`data.table::fread`):** All types lossless ✅

### Shared Directory

```
Default: ~/.openclaw/workspace/r2py/ (per user workspace, naturally isolated)
Override: R2PY_SHARED_DIR or R_SHARED_DIR env vars
Filename: UUID prefix + .csv
```

------------------------------------------------------------------------

## VI. Deployment & Configuration

### 6.1 Prerequisites

``` bash
# R side
install.packages(c("httpuv", "jsonlite"))

# Python side (graphrag conda environment)
pip install mcp httpx
```

### 6.2 Startup Flow

``` mermaid
sequenceDiagram
    participant User as User
    participant RStudio as RStudio Console
    participant RAPI as R Session API
    participant MCP as r-session-mcp-server
    participant GW as OpenClaw Gateway
    participant AI as AI Model

    User->>RStudio: library(readxl)
    User->>RStudio: df <- read_excel(...)
    User->>RStudio: source("r-session-api.R")
    RStudio->>RAPI: httpuv::startServer()
    RAPI-->>RStudio: Print startup info (including Token status)

    Note over GW: mcp.servers.r-session configured
    GW->>MCP: spawn subprocess
    MCP->>RAPI: GET /health (with Bearer Token)
    RAPI-->>MCP: {success: true, pid: 1234}
    MCP-->>GW: listTools() → 8 tools

    User->>AI: "Analyze the data"
    AI->>GW: Think → need to see data first
    GW->>MCP: callTool(list_objects)
    MCP->>RAPI: GET /env
    RAPI-->>MCP: {objects: [df, ...]}
    MCP-->>GW: Format table
    GW-->>AI: R environment has df (48×3), model ...

    AI->>GW: Need to preview df
    GW->>MCP: callTool(preview_data, "df")
    MCP->>RAPI: GET /preview/df
    RAPI-->>MCP: {head, summary, na_count}
    MCP-->>GW: Format preview
    GW-->>AI: df structure, preview, summary, missing values

    AI->>GW: Execute analysis
    GW->>MCP: callTool(run_code, {code: "..."})
    MCP->>RAPI: POST /eval {code: "..."}
    RAPI->>RStudio: safe_eval(code) ← Console can see execution
    RStudio-->>RStudio: .GlobalEnv new variables added
    RAPI-->>MCP: {output, new_objs: ["result"]}
    MCP-->>GW: Format output
    GW-->>AI: Analysis results + new variables

    GW-->>User: Show analysis conclusions
    Note over RStudio: RStudio Environment panel<br/>now shows AI-created variables
```

### 6.3 OpenClaw Configuration

``` json
{
  "mcp": {
    "servers": {
      "r-session": {
        "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
        "args": [
          "/home/openclaw/.openclaw/workspace/r-session-ai/r-session-mcp-server.py"
        ],
        "env": {
          "R_API_HOST": "127.0.0.1",
          "R_API_PORT": "8161",
          "R_API_TOKEN": ""
        }
      }
    }
  }
}
```

### 6.4 HTTP/SSE Mode

In addition to the default stdio mode, the MCP Server also supports HTTP/SSE mode:

``` bash
export MCP_PORT=8100
python3 r-session-mcp-server.py
# Starts at http://127.0.0.1:8100/sse
```

HTTP mode requires `uvicorn` and `starlette`, suitable for remote connection scenarios.

------------------------------------------------------------------------

## VII. Comparison with jupyter-mcp

| Dimension | r-session | jupyter-mcp |
|----|----|----|
| Language | R | Python |
| IDE | RStudio Server | JupyterLab |
| Display location | RStudio Console + Environment panel | Notebook Cell / Console window |
| Communication | HTTP (R API → Python MCP) | ZMQ (jupyter_client direct to kernel) |
| Data form | R objects in .GlobalEnv | Python objects in kernel namespace |
| Graphic output | RStudio Plots panel | Inline in Notebook / JupyterLab |
| Registration | `source("r-session-api.R")` | `hook.register()` |
| API process | Same-process httpuv, non-blocking | Same-process ZMQ |
| Data exchange | CSV (data.table::fwrite/fread) | CSV (pandas.to_csv/read_csv) |
| Unique advantage | Writes back to Environment panel | Real-time Notebook file sync |

------------------------------------------------------------------------

## VIII. Project File Inventory

```
r-session-ai/
├── r-session-api.R               # R Session API Server (runs in RStudio)
├── r-session-mcp-server.py       # Python MCP Server (managed by OpenClaw)
├── README.md                     # Quick start guide
└── r-session-architecture.md     # This document
```

------------------------------------------------------------------------

## IX. Known Limitations & Notes

1. **httpuv requires main thread idle:** When the R Console is executing a long-running operation (e.g., `Sys.sleep(10)` or a long loop), API requests will queue up
2. **eval security concern:** API binds to 127.0.0.1 but other local processes can access it. Production multi-user environments **must** configure Token authentication
3. **Large object transfer:** JSON serialization of large data frames may consume significant memory. `MAX_ROW` defaults to 100 rows for previews
4. **CRAN package dependencies:** `httpuv` and `jsonlite` must be pre-installed; offline environments may need local source installation
5. **Stopping:** `httpuv::stopServer(server)` or restart the R session
6. **Proxy compatibility:** If the system has a SOCKS5 proxy configured, httpx client initialization will crash. MCP Server auto-clears all proxy environment variables
7. **Token priority:** `options(rsession_api_token=...)` takes precedence over env var `R_API_TOKEN`, making it convenient for users to configure dynamically via R options
8. **Multi-user isolation:** Each user's R Session is an independent OS process; httpuv instances bind to different ports without interference. `httpuv::stopServer(server)` and `stopAllServers()` only affect the current session

------------------------------------------------------------------------

## X. Changelog

| Date | Changes |
|----|----|
| Initial | Base architecture, `safe_eval`, 6 HTTP endpoints, MCP Server stdio mode |
| v2 | Token auth (R options / env vars / Bearer Token), proxy compatibility |
| v3 | export_data/import_data (R↔Python data exchange), `console_echo=FALSE` mode |
| v4 | HTTP/SSE mode, shebang changed to graphrag env, environment variable config |
