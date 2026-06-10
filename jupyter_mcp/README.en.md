# jupyter-mcp — Jupyter Lab ⟷ OpenClaw Data Analysis Bridge

Connect OpenClaw directly to your Python kernel in Jupyter Lab, enabling AI-assisted Python data analysis.

## Architecture

```
┌─────────────────┐     MCP Protocol (stdio)   ┌────────────────────────┐
│   OpenClaw      │ ◄─────────────────────►     │  jupyter-mcp-server.py │
│   (AI Agent)    │    subprocess stdin/stdout  │  (MCP Server, Python)  │
└─────────────────┘                             └───────────┬────────────┘
                                                            │ ZMQ (Jupyter Protocol)
                                                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Jupyter Lab (your kernel session)              │
│  - You work in Jupyter normally                             │
│  - OpenClaw can read/modify variables in the same kernel    │
│  - DataFrames you see in Jupyter, OpenClaw can see too      │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### 1. Install Dependencies

``` bash
# In your graphrag conda environment (or your Python environment)
pip install mcp jupyter-client
```

### 2. Register the Current Kernel

Run this in any Jupyter Lab cell:

``` python
from jupyter_mcp import hook
hook.register()
```

You'll see output similar to:

```
✅ Jupyter kernel registered with MCP Server
   Connection file: /home/openclaw/.local/share/jupyter/runtime/kernel-xxx.json
   Kernel:   python3
   Notebook: analysis.py
   PID:      1234567
```

The `~/.jupyter-mcp/current` file is written; the MCP Server uses it to find the kernel.

To switch to a different kernel, run `hook.register(force=True)` in that kernel's cell.

### 3. Configure MCP Server in OpenClaw (Recommended: stdio mode)

Add this to the `mcp.servers` section of your `openclaw.json`:

``` json
"jupyter-mcp": {
  "command": "/path/to/your/python3",
  "args": [
    "/path/to/jupyter_mcp/jupyter-mcp-server.py"
  ]
}
```

**Example (graphrag conda environment):**

``` json
"jupyter-mcp": {
  "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
  "args": [
    "/home/ubuntu/.openclaw/workspace/jupyter_mcp/jupyter-mcp-server.py"
  ]
}
```

Once configured, restart OpenClaw to automatically start the MCP Server.

### 4. Usage

After connecting to OpenClaw, you can use the following tools to interact with the Jupyter kernel:

| Tool | Function |
|----|----|
| `run_code` | Execute Python code in the kernel, modify variables |
| `list_objects` | List all variables in the kernel with type/size info |
| `preview_data` | Preview variable details (DataFrame shape/dtypes/head/describe/missing values) |
| `get_loaded_packages` | List loaded package versions |
| `export_data` | Python → R data export |
| `import_data` | R → Python data import |
| `health_check` | Check connection status |

**.py + Console mode only:**

| Tool | Function |
|----|----|
| `read_source` | Read current .py source file |
| `write_source` | Overwrite .py source file |
| `append_source` | Append code to .py source file |

### 5. Manual Startup for Testing (Debugging)

To manually start the server in a terminal for testing:

``` bash
cd /path/to/jupyter_mcp
python3 jupyter-mcp-server.py
```

The server will automatically read `~/.jupyter-mcp/current` and connect to the kernel. Press Ctrl+C to stop.

## Why stdio Mode Is Recommended

| | **stdio mode (recommended)** | **HTTP / SSE mode** |
|----|----|----|
| **Communication** | OpenClaw spawns MCP Server as a subprocess, communicates via stdin/stdout | MCP Server listens on a network port, communicates via HTTP / SSE |
| **Port conflicts** | None. Each user has an independent OS process, no ports needed | Yes. Multi-user requires different port assignments, complex management |
| **Security** | No network exposure, subprocess isolation, users invisible to each other | Ports open potential attack surface |
| **Multi-user deployment** | ✅ Native support. Each user configures independently in their own OpenClaw | ❌ Requires port allocation, firewall rules, Token auth management |
| **Configuration complexity** | Low. Just command + args | High. Ports, tokens, firewalls |
| **Debugging convenience** | Run in terminal and see logs directly | Need to monitor both process and port |

**Conclusion:** stdio mode is the only correct choice for multi-user scenarios. HTTP mode is only suitable for single-user local debugging.

## Important Notes

- **Can only connect to one kernel.** If you have multiple Jupyter Lab tabs, make sure to register only the kernel you want with `hook.register(force=True)`
- **If a registered kernel is restarted,** you need to re-run `hook.register(force=True)`
- The MCP Server and kernel must be on the same machine (both connect via localhost 127.0.0.1)
- If the MCP Server can't find the kernel on startup, check that `~/.jupyter-mcp/current` exists

## Relationship with r-session

Both can coexist. r-session operates on R, jupyter-mcp operates on the Python kernel — they don't interfere with each other. Simply define both MCP Servers in your OpenClaw configuration.
