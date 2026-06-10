---
output:
  html_document: default
  word_document: default
---

# jupyter-mcp: Principles, Architecture & Implementation

> Empowering AI agents to perform interactive data analysis in Jupyter Lab, just like a human would

------------------------------------------------------------------------

## I. Overall Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Browser (JupyterLab UI)                    │
│  ┌─────────────────────┐  ┌────────────────────────────────┐ │
│  │ Notebook (.ipynb)   │  │ .py + Console                  │ │
│  │ auto-reload ext     │  │ console-adopt ext              │ │
│  └─────────┬───────────┘  └──────────┬─────────────────────┘ │
└────────────┼─────────────────────────┼───────────────────────┘
             │                         │
             │  HTTP / WebSocket       │
             ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│              Jupyter Server (JupyterHub)                     │
│       /api/contents /api/kernels /api/sessions               │
│       /api/kernels/{id}/channels (WebSocket)                 │
└────────────┬──────────────────────────┬──────────────────────┘
             │                          │
             │   ZMQ (jupyter_client)   │  ZMQ (WebSocket proxy)
             ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Jupyter Kernel                            │
│                (IPython / graphrag)                          │
│         Shell / IOPub / Stdin / Control / Heartbeat          │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ ZMQ (jupyter_client)
             ▼
┌──────────────────────────────────────────────────────────────┐
│              jupyter-mcp MCP Server (Python)                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  JupyterKernel (ZMQ Connection Manager)              │   │
│  │  - find_registered_kernel() → auto-discover & connect│   │
│  │  - connect(conn_file)  → BlockingKernelClient        │   │
│  │  - execute(code)       → ZMQ Shell + IOPub           │   │
│  │  - list_objects()      → global variable introspection│   │
│  │  - preview_object()    → variable detail preview     │   │
│  │  - get_loaded_packages()                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MCP Protocol Layer                                  │   │
│  │  - mcp.types.Tool definitions (10 tools)             │   │
│  │  - handle_call_tool dispatch                         │   │
│  │  - stdio / HTTP SSE dual transport mode              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  NotebookClient (Jupyter Server API Client)          │   │
│  │  - Manipulate .ipynb cells via REST API              │   │
│  │  - add_code_cell() → PUT /api/contents               │   │
│  │  - write_outputs()  → write results back to Cell     │   │
│  │  - zmq_outputs_to_cell_outputs() format conversion   │   │
│  │  - create checkpoint → triggers frontend refresh     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  shared_dir (R ↔ Python Data Exchange)               │   │
│  │  - SHARED_DIR default: ~/workspace/r2py/             │   │
│  │  - export_data/import_data via CSV                   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
             │
             │ MCP Protocol (stdio / SSE)
             ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenClaw Gateway                               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MCP Runtime Manager                                 │   │
│  │  - Process lifecycle (spawn/kill/restart)            │   │
│  │  - Tool discovery (listTools)                        │   │
│  │  - Tool invocation (callTool)                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tool Router                                         │   │
│  │  jupyter-mcp__run_code → MCP → kernel                │   │
│  │  jupyter-mcp__health_check → MCP → kernel            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
         AI Model (DeepSeek / GLM / Kimi ...)
```

------------------------------------------------------------------------

## II. Core Component Details

### 2.1 hook.py — Kernel Registration Module

**Purpose:** A registration function that runs inside the Jupyter kernel, writing kernel connection info to a file for the MCP Server to discover.

**Usage:** Execute in a Notebook cell or .py Console:

``` python
from jupyter_mcp import hook
hook.register()           # First registration
hook.register(force=True) # Overwrite existing registration
```

**How It Works:**

```
When register() is called:
  1. Check if running in an IPython kernel environment (get_ipython())
  2. Find the current kernel's connection file (~/.local/share/jupyter/runtime/kernel-*.json)
     - Method 1: Look for -f flag in sys.argv (ipykernel standard)
     - Method 2: Read JPY_CONNECTION_FILE environment variable
     - Method 3: Scan the runtime directory (fallback)
  3. Read the connection file → get shell_port, iopub_port, key, etc.
  4. Detect current mode:
     - Read jupyter_session field from connection file
     - Ends with .ipynb → mode="notebook"
     - Ends with .py → mode="console"
  5. Find Jupyter Server info (jpserver-*.json)
     - Match strategy: take the newest one with a still-running PID
  6. Write to ~/.jupyter-mcp/current (JSON format)
     - Contains full connection field (for connection file reconstruction)
     - Contains jupyter_server field (for REST API calls)
```

**Registration File Structure (~/.jupyter-mcp/current):**

``` json
{
  "kernel_conn_file": "/home/openclaw/.local/share/.../kernel-xxx.json",
  "kernel_name": "graphrag",
  "notebook": "untitled.py",
  "mode": "console",
  "source_path": "/home/openclaw/.openclaw/workspace/untitled.py",
  "pid": 12345,
  "hostname": "vm-12-2-ubuntu",
  "timestamp": 1717000000.0,
  "transport": "tcp",
  "ip": "127.0.0.1",
  "connection": {
    "shell_port": 49281,
    "iopub_port": 47395,
    "key": "xxx",
    "transport": "tcp",
    "signature_scheme": "hmac-sha256",
    "ip": "127.0.0.1",
    "stdin_port": 49282,
    "control_port": 49283,
    "hb_port": 49284,
    "kernel_name": "python3"
  },
  "jupyter_server": {
    "url": "http://127.0.0.1:44153/user/openclaw/",
    "token": "xxx",
    "base_url": "/user/openclaw/",
    "port": 44153,
    "pid": 12300
  }
}
```

### 2.2 jupyter-mcp-server.py — MCP Server

**Purpose:** Acts as the bridge between OpenClaw and the Jupyter kernel, encapsulating kernel capabilities as MCP tools.

**Shebang & Runtime Environment:**

``` python
#!/usr/lib64/anaconda3/envs/graphrag/bin/python3
```

The MCP Server runs in the `graphrag` conda environment. Although the server process uses this Python, **code execution is sent to the Jupyter kernel** — code runs in the kernel's environment regardless of which Python the MCP Server uses.

**Communication:** Uses the `jupyter_client` library to connect directly to the kernel via ZMQ (bypassing the Jupyter Server HTTP API).

**Environment Variables:**

| Variable | Default | Description |
|----|----|----|
| `JUPYTER_MCP_HOST` | `127.0.0.1` | MCP Server listen address |
| `JUPYTER_MCP_PORT` | `0` | Port; `0` = stdio mode |
| `JUPYTER_MCP_TIMEOUT` | `120` | Kernel code execution timeout (seconds) |
| `JUPYTER_MCP_REGISTER` | `~/.jupyter-mcp/current` | Registration file path |
| `R2PY_SHARED_DIR` | `~/workspace/r2py/` | R↔Python data exchange directory |
| `JUPYTER_SHARED_DIR` | Same as `R2PY_SHARED_DIR` | Jupyter-side override |

**ZMQ Channels:**

| Channel | Purpose | Socket Type |
|----|----|----|
| Shell | Send execute_request, receive execute_reply | DEALER → ROUTER |
| IOPub | Receive execute_input/result/stream/error broadcasts | SUB |
| Stdin | Receive input() requests | DEALER → ROUTER |
| Control | Send interrupt/shutdown | DEALER → ROUTER |
| Heartbeat | Check kernel liveness | REQ → REP |

**Auto-Discovery & Connection:**

``` python
find_registered_kernel():
  1. Read ~/.jupyter-mcp/current
  2. Get kernel_conn_file path
  3. If connection file doesn't exist → rebuild temp file from connection field
     (prevents cleanup after kernel restart)
  4. Create JupyterKernel instance and connect
  5. Verify heartbeat → confirm connection success
```

**Code Execution Flow:**

```
execute(code):
  1. kc.execute(code)  → send execute_request to Shell channel
     - msg_id = UUID (for matching responses)
  2. Loop to collect messages (0.5s IOPub poll + 0.01s Shell poll):
     a. Shell channel: get_shell_msg() → execute_reply
        - Contains execution_count, status (ok/error)
     b. IOPub channel: get_iopub_msg()
        - execute_input: kernel-broadcasted source code (for display)
        - stream: stdout/stderr output
        - execute_result: expression evaluation result
        - display_data: matplotlib charts (base64 PNG)
        - error: exception info (ename + evalue + traceback)
        - status: busy / idle (execution complete flag)
  3. When status=idle and shell_reply received → end
  4. Timeout protection (default 120 seconds)
```

**Introspection Implementation:**

All introspection operations (list_objects, preview_object, get_loaded_packages) are implemented by **executing Python code inside the kernel**, rather than using Jupyter's native inspect protocol.

``` python
# list_objects example: execute introspection code in kernel
code = """
import sys, types, builtins, json

objs = {}
for name, obj in globals().items():
    if name.startswith('_'): continue
    objs[name] = {
        'type': type(obj).__name__,
        'size': sys.getsizeof(obj),
        'shape': list(obj.shape) if hasattr(obj, 'shape') else None,
    }
print('__JUPYTER_MCP_JSON__')
print(json.dumps(objs, default=str))
"""
result = kernel.execute(code)
# Parse JSON after __JUPYTER_MCP_JSON__ marker from stdout
```

**Key Design — `__JUPYTER_MCP_JSON__` Marker Protocol:**

Structured data exchange between MCP Server and kernel uses a **marker protocol**:

1. MCP Server sends introspection code to the kernel for execution
2. The code collects information and prints a `__JUPYTER_MCP_JSON__` marker line
3. JSON-serialized results follow the marker line
4. MCP Server parses the JSON after the marker from stdout

Advantages:
- No dependency on Jupyter protocol extensions (maintains compatibility)
- JSON data can coexist with regular stdout output
- Kernel introspection code is fully controllable and extensible

------------------------------------------------------------------------

### 2.3 NotebookClient — Notebook Operations Module

**Purpose:** Manipulates .ipynb files via the Jupyter Server REST API (insert cells, write results, create checkpoints).

``` python
class NotebookClient:
    def __init__(self, server_info, notebook_path):
        # Store server URL + token
        # Temporarily mask http_proxy/https_proxy (avoid proxy interference)

    def get_notebook() -> dict
        # GET /api/contents/{path}?content=1

    def save_notebook(nb: dict)
        # PUT /api/contents/{path}
        # Also triggers checkpoint creation (POST /api/contents/{path}/checkpoints)
        # Checkpoint 201 response → auto-reload detects the change

    def add_code_cell(code: str) -> (cell_index, cell_json)
        # Get current notebook
        # Calculate next execution_count from existing cells
        # Append new code Cell at the end
        # PUT to save
        # Return cell_index + metadata (execution_count)

    def write_outputs(cell_index, exec_count, outputs)
        # Get current notebook
        # Update specified cell's outputs + execution_count
        # PUT to save

    def zmq_outputs_to_cell_outputs(result) -> (outputs, display_lines)
        # stream → stream output (including stderr)
        # execute_result → execute_result output
        # display_data (image/png) → display_data output
        # error → error output (strip ANSI escape codes)
```

**NotebookClient Creation Flow:**

```
get_notebook_client():
  1. Get jupyter_server info from ~/.jupyter-mcp/current
  2. Extract kernel ID from connection filename
  3. Call GET /api/sessions → find notebook path for current kernel
  4. If sessions API fails → fall back to notebook field in registration file
```

**Proxy Avoidance:**

All REST API calls use `urllib.request` (not `httpx`/`requests`), and **temporarily mask `http_proxy`/`https_proxy`** environment variables before and after each call. This is because the server may have a global proxy (e.g., Clash), while the Jupyter Server runs locally on 127.0.0.1 and doesn't need proxying.

------------------------------------------------------------------------

## III. MCP Tool Reference

### 3.1 Common Tools (Both Modes)

| Tool | Input | Output | Description |
|----|----|----|----|
| `run_code` | `code: string` | stdout + result | Execute Python code, modify session variables |
| `list_objects` | None | Variable list (type/size/shape/col types) | Uses `__JUPYTER_MCP_JSON__` marker protocol |
| `preview_data` | `name: string` | DataFrame/Series/array details | shape/dtypes/head/describe/missing values |
| `get_loaded_packages` | None | Installed package versions | Gets packages with `__version__` from sys.modules |
| `health_check` | None | Connection status + mode + path | Includes PID, kernel connection file path |
| `export_data` | `name: string` | CSV file path | Python → R data export |
| `import_data` | `path, var_name` | Import confirmation | R → Python data import |

### 3.2 .py + Console Mode Only

| Tool | Input | Description |
|----|----|----|
| `read_source` | None | Read current .py source file |
| `write_source` | `code: string` | Overwrite .py source file |
| `append_source` | `code: string` | Append code to .py source file |

### 3.3 Mode Auto-Adaptation Logic (run_code)

```
run_code(code):
  if mode == "notebook":
    # 1. Insert Cell via Jupyter Server REST API (calculate execution_count)
    nb_client.add_code_cell(code)
    # 2. Execute code via ZMQ
    result = kernel.execute(code)
    # 3. Write results back to Cell via REST API
    nb_client.write_outputs(cell_index, ec, cell_outputs)
    # 4. Checkpoint creation → auto-reload refreshes Notebook display
  else: # console
    # 1. Execute code via ZMQ only (no .py file modification)
    result = kernel.execute(code)
    # 2. console-adopt extension listens to raw iopubMessage signal
    #    Captures external session execute_input → displays in Console
```

### 3.4 R ↔ Python Data Exchange Tools

| Tool | Internal Implementation |
|----|----|
| `export_data(name)` | Execute `obj.to_csv(path, index=False)` in kernel + print shape |
| `import_data(path, var_name)` | Execute `pd.read_csv(path)` in kernel + print shape |

**Shared Directory:** `SHARED_DIR` defaults to `~/.openclaw/workspace/r2py/`, filenames use UUID prefix.

------------------------------------------------------------------------

## IV. JupyterLab Extensions

### 4.1 jupyterlab-auto-reload

**Purpose:** Automatically refreshes the Notebook display when the file is modified externally (e.g., MCP Server writes a Cell).

**How It Works:**

``` typescript
setInterval(async () => {
  const current = tracker.currentWidget;
  if (!current) return;

  const context = current.context;
  const contentsManager = app.serviceManager.contents;

  const model = await contentsManager.get(context.path);
  const serverTime = model.last_modified;

  if (!lastModified[path]) {
    lastModified[path] = serverTime;
    return;
  }

  if (serverTime !== lastModified[path]) {
    lastModified[path] = serverTime;
    if (!isDirty) {
      await context.revert();  // Reload from server
    }
  }
}, 3000);
```

**Key Points:**
- Uses JupyterLab's `serviceManager.contents` API
- Dirty protection: skips reload if user has unsaved changes
- Doesn't intercept user operations, only monitors `last_modified` timestamps
- MCP's checkpoint creation triggers 201 response, ensuring `last_modified` is updated

**Install Path:**

```
JupyterHub → base conda environment
/usr/lib64/anaconda3/share/jupyter/labextensions/
```

### 4.2 jupyterlab-console-adopt

**Purpose:** Enables the Console window to display code and output executed by MCP (from other Sessions).

**Problem Background:**

JupyterLab Console has a known limitation (issue #9936): it only shows results from **its own WebSocket connection**. This is because the Console's `OutputArea.future` only matches messages with a specific `msg_id`.

Since the MCP Server connects to the kernel directly via ZMQ (jupyter_client) using a different Session ID, the Console won't display MCP-executed code and output.

**Solution:**

The extension listens to the kernel's `iopubMessage` signal — this signal contains IOPub messages from **all Sessions** (without msg_id filtering).

``` typescript
kernel.iopubMessage.connect(onIOPubMessage);

function onIOPubMessage(_, msg) {
  if (msg.header.msg_type === 'execute_input') {
    const sessionId = msg.parent_header.session;
    if (sessionId === kernel.clientId) return;  // Skip own messages

    const code = msg.content.code;
    const msgId = msg.parent_header.msg_id;
    const execCount = msg.content.execution_count;

    // 1. Create new CodeCell
    const cell = consoleWidget.createCodeCell();
    cell.model.sharedModel.setSource(code);
    cell.model.executionCount = execCount;

    // 2. Create pseudo-future to take over OutputArea
    const pseudoFuture = {
      onIOPub: null,
      done: new Promise(/* resolve on status=idle */),
      dispose() {},
    };
    cell.outputArea.future = pseudoFuture;

    // 3. Add to Console
    consoleWidget.addCell(cell, msgId);

    // 4. Forward subsequent IOPub messages to pseudo-future
    const forwardOutput = (_, m) => { /* match msg_id then forward */ };
    kernel.iopubMessage.connect(forwardOutput);

    // 5. Clean up after execution completes
    pseudoFuture.done.then(() => kernel.iopubMessage.disconnect(forwardOutput));
  }
}
```

**Challenges Solved:**

| Problem | Solution |
|----|----|
| Console only shows own Session messages | Use `kernel.iopubMessage` (raw signal) instead of future's filtered signal |
| Need to create Console Cell without re-executing code | Don't call `kernel.requestExecute()`; use pseudo-future to capture existing IOPub messages |
| OutputArea needs future object to render | Create pseudo-future; after OutputArea sets `onIOPub` callback, forward messages |
| Execution number `[n]` shows as empty | Get and set from execute_input message's execution_count field |

------------------------------------------------------------------------

## V. Communication Protocol Comparison

| Feature | ZMQ (MCP Direct) | WebSocket (Jupyter Frontend) | REST API (NotebookClient) |
|----|----|----|----|
| Connection method | jupyter_client (Python) | Browser WebSocket API | urllib HTTP |
| Session ID | Randomly generated | Randomly generated (different) | N/A |
| Protocol | Jupyter Kernel Protocol 5.x | Same ZMQ, wrapped via HTTP | Jupyter Contents API |
| Latency | Low (direct connection) | Slightly higher (via Server proxy) | Higher (HTTP round-trip) |
| Authentication | Connection file key/hmac | Jupyter Server token | token |
| Persistence | Reconnect on disconnect | Usually long-lived | Stateless |
| Purpose | Code execution + introspection | User interaction | Cell read/write |

------------------------------------------------------------------------

## VI. Startup & Deployment

### Prerequisites

``` bash
# Install dependencies in graphrag conda environment
pip install mcp httpx jupyter-client
```

### Full Startup Flow

``` mermaid
sequenceDiagram
    participant User as User
    participant JL as JupyterLab
    participant MCP as jupyter-mcp
    participant GW as OpenClaw Gateway

    User->>JL: Open Notebook/.py
    User->>JL: hook.register()
    JL->>MCP: Write ~/.jupyter-mcp/current
    Note over GW: Configure mcp.servers.jupyter-mcp
    GW->>MCP: Spawn process (stdio mode)
    MCP->>JL: Read registration file, ZMQ connect to kernel
    MCP-->>GW: Return tool list (listTools)
    
    Note over User,GW: AI analysis session
    User->>GW: "Analyze this data"
    GW->>AI: Call LLM
    AI->>GW: Generate analysis code
    GW->>MCP: callTool(run_code, {code})
    MCP->>JL: execute(code) via ZMQ
    JL-->>MCP: Return execution result
    MCP-->>GW: Format output
    GW-->>User: Display analysis result
```

### OpenClaw Configuration

``` json
{
  "mcp": {
    "servers": {
      "jupyter-mcp": {
        "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
        "args": [
          "/home/openclaw/.openclaw/workspace/jupyter_mcp/jupyter-mcp-server.py"
        ]
      }
    }
  }
}
```

### HTTP/SSE Mode

In addition to the default stdio mode, the MCP Server also supports HTTP/SSE mode:

``` bash
export JUPYTER_MCP_PORT=8765
python3 jupyter-mcp-server.py
# Starts at http://127.0.0.1:8765/sse
```

HTTP mode requires `uvicorn` and `starlette`, suitable for remote connection scenarios.

------------------------------------------------------------------------

## VII. R ↔ Python Data Exchange Details

### Design Philosophy

- **Small datasets only** cross sessions; large datasets stay in their original session
- **CSV only** — natively supported by both R and Python, simplest universal solution
- CSV type mapping may lose precision, but small datasets can be fixed with a few `astype()` calls

### Architecture

```
R Session → R API (httpuv) → r-session-mcp (Python) → CSV
                                                         ↓
Jupyter Kernel ← jupyter-mcp (Python) ← CSV
```

### Type Mapping Verified

**Python → R (`data.table::fread`):** All types lossless ✅

| Python | R | CSV Intermediate |
|----|----|----|
| int64 | integer | `1` |
| float64 | numeric | `10.5` |
| object (str) | character | `Alice` |
| bool | logical | `True` / `False` |
| datetime64 (date) | IDate/Date | `2026-06-07` |
| datetime64 (datetime) | POSIXct | `2026-06-07 10:30:00` |

**R → Python (`pd.read_csv`):** Date/time types become strings ❌ (needs `pd.to_datetime()` fix)

### Shared Directory

```
Default: ~/.openclaw/workspace/r2py/ (per user workspace, naturally isolated)
Override: R2PY_SHARED_DIR or JUPYTER_SHARED_DIR env vars
Filename: UUID prefix + .csv
```

------------------------------------------------------------------------

## VIII. Project File Inventory

```
jupyter_mcp/
├── __init__.py              # Package init
├── hook.py                  # Kernel registration (run in JupyterLab cell)
├── jupyter-mcp-server.py    # MCP Server (managed by OpenClaw)
├── setup.py                 # Editable install config (pip install -e .)
├── README.md                # Quick start guide
├── jupyter-mcp-architecture.md  # This document
└── auto_reload.js           # Standalone auto-reload JS (injectable)

jupyterlab-auto-reload/      # Notebook auto-refresh extension (source build)
├── package.json
├── src/index.ts
├── jupyterlab_auto_reload/
│   └── labextension/        # Build artifacts
└── setup.py

jupyterlab-console-adopt/    # Console external session capture extension
├── package.json
├── src/index.ts
├── jupyterlab_console_adopt/
│   └── labextension/        # Build artifacts
└── tsconfig.json
```

------------------------------------------------------------------------

## IX. Known Limitations & Notes

1. **JupyterLab version differences:** JupyterHub-singleuser may run in the base conda environment (4.x); extensions must be installed to the corresponding environment's `labextensions` path
2. **Console Session isolation:** Console not showing external Session results is a JupyterLab design limitation; the `console-adopt` extension bypasses it by listening to raw IOPub signals
3. **Plot output:** matplotlib charts are delivered as base64 PNG via `display_data` messages, rendered as images in the Console
4. **Kernel switching:** Switching kernels requires re-running `hook.register(force=True)`
5. **Single kernel only:** The registration file `~/.jupyter-mcp/current` is a single file; a later registration overwrites the previous one
6. **Proxy interference:** Jupyter Server runs locally; REST API calls need temporary masking of `http_proxy` env vars
7. **Connection file rebuild:** After kernel restart, the original connection file may be cleaned up; MCP Server rebuilds a temp file from the registration file's `connection` field

------------------------------------------------------------------------

## X. Changelog

| Date | Changes |
|----|----|
| Initial | Base architecture, ZMQ connection, kernel registration, run_code/list_objects/preview_data |
| v2 | Added NotebookClient (REST API cell operations), auto-reload extension |
| v3 | Added console-adopt extension (external Session display) |
| v4 | Added export_data/import_data (R↔Python data exchange), HTTP/SSE mode |
| v5 | Environment variable config (HOST/PORT/TIMEOUT/REGISTER/SHARED_DIR), proxy avoidance, connection file rebuild, shebang changed to graphrag env |
