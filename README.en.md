# Data AI

> OpenClaw / Claude Code with Jupyter Lab and Rstudio

An integrated **Python + R** data analysis workbench, powered by the **OpenClaw AI Agent** as its brain, connecting **JupyterLab (Python)** and **RStudio (R)** — two interactive analysis engines — through the **MCP protocol** to unify tool interfaces and enable seamless cross-language data flow. Command with natural language, access via mobile phone or browser — data analysis made simple and accessible.

------------------------------------------------------------------------

## Why This Exists

Python and R each have irreplaceable ecosystems. Traditional solutions (like Posit/Quarto) focus on R-side integration, with Python relying on reticulate — a fragmented experience. This solution uses **OpenClaw Agent as the glue layer** + **MCP Server as the bridge** + **CSV sharing for data exchange**, letting both languages play to their strengths and collaborate smoothly on a single platform.

### Core Advantages

- 🏠 **Data never leaves the server**, deployable on local networks with all-in-one appliances
- 🇨🇳 **Verified on domestic IT infrastructure**: Kylin V10 + Kunpeng CPU (ARM64) + full domestic LLMs
- 🔄 **LLM hot-swappable** (DeepSeek / GLM / MiniMax / Kimi, etc.)
- 🪶 Lightweight browser interface, easy to deploy and maintain
- 🔓 Fully open source and free
- 📊 AI贯穿 **coding phase** + **data analysis phase**

------------------------------------------------------------------------

## Architecture

### High-Level Architecture

```
                          ┌──────────────────────┐
                          │  User (Browser UI)   │
                          │ JupyterLab / RStudio │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │    OpenClaw Agent    │  ← AI Brain
                          │Dialog + Route + MCP  │  ← All tools via MCP
                          └──┬───────────────┬───┘
                             │               │
              ┌──────────────▼──┐    ┌───────▼─────────────┐
              │ MCP Server      │    │  MCP Server         │
              │ jupyter-mcp     │    │  r-session          │
              │ (Python)        │    │  (Python)           │
              │ ZMQ → kernel    │    │  HTTP → R API       │
              └──────┬──────────┘    └──────┬──────────────┘
                     │                      │
              ┌──────▼─────────┐    ┌───────▼──────────────┐
              │  Jupyter       │    │  R API (httpuv)      │
              │  Kernel        │    │  Same-process non-   │
              │  (IPython)     │    │  blocking HTTP       │
              │  Python objs   │    │  → eval() on         │
              └──────┬─────────┘    │  .GlobalEnv          │
                     │              │  RStudio R Session   │
                     │              └──────┬───────────────┘
                     │                     │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼─────────────┐
                     │  r2py Shared Directory │
                     │  (~/r2py/*.csv)         │
                     │  R ↔ Python data sync  │
                     └────────────────────────┘
```

### Two Data Flow Paths in Detail

#### ① Python Side (jupyter-mcp)

```
OpenClaw Agent
    │ callTool(run_code, ...) ← MCP Protocol
    ▼
jupyter-mcp-server.py  (MCP Server, Python, runs in graphrag conda env)
    │ Reads ~/.jupyter-mcp/current → gets kernel connection info
    │ jupyter_client library connects to kernel via ZMQ
    ▼
Jupyter Kernel  (IPython, running in JupyterLab)
    │ Code executes in kernel → modifies Python objects in kernel namespace
    │ For export_data / import_data:
    ▼
r2py/ Shared Directory  (CSV files)
```

**Communication Protocol:** `jupyter_client` + ZMQ (Shell / IOPub / Stdin / Control / Heartbeat — 5 channels)

```
MCP Server                              Jupyter Kernel
    │    execute_request (Shell)              │
    ├────────────────────────────────────────>│
    │    execute_reply   (Shell)              │
    │<────────────────────────────────────────┤
    │    execute_input   (IOPub)              │
    │    stream/result/error (IOPub)          │
    │<────────────────────────────────────────┤
    │    status: idle    (IOPub)              │
    │<────────────────────────────────────────┤
```

> Detailed architecture doc: [jupyter_mcp/jupyter-mcp-architecture.md](./jupyter_mcp/jupyter-mcp-architecture.md)

#### ② R Side (r-session)

```
OpenClaw Agent
    │ callTool(run_code, ...) ← MCP Protocol
    ▼
r-session-mcp-server.py  (MCP Server, Python, runs in graphrag conda env)
    │ httpx client → HTTP POST + Bearer Token
    ▼
R API Server  (httpuv, runs in RStudio's R Session, same-process non-blocking)
    │ safe_eval(code) → eval(parse(text=code)) executes in .GlobalEnv
    │ Results display in real-time in RStudio Console + Environment panel
    │ For export_data / import_data:
    ▼
r2py/ Shared Directory  (CSV files)
```

**Communication Protocol:** HTTP (`httpx.Client` → `httpuv::startServer`)

```
MCP Server                              R API (httpuv)
    │  GET /health                            │
    │  GET /env                               │
    │  POST /eval  {code: "..."}              │
    ├────────────────────────────────────────>│
    │  {success, output, new_objs, ...}       │
    │<────────────────────────────────────────┤
```

**Why httpuv instead of forking a subprocess:**

Most solutions (plumber, Rserve) execute code in new processes, meaning they can't access variables in the current RStudio session and created objects don't appear in the Environment panel. httpuv is based on the libuv event loop, **sharing the same process** as the R Console without blocking the main thread — variables stay synchronized across all three surfaces.

> Detailed architecture doc: [r-session-ai/r-session-architecture.md](./r-session-ai/r-session-architecture.md)

#### ③ Cross-Language Data Exchange (r2py)

```
R Session                          Jupyter Kernel
    │                                    │
    │  export_data("df")                 │
    │  fwrite(df, "r2py/xxx.csv")        │
    └───────── CSV file ────────────────>│  pd.read_csv("r2py/xxx.csv")
    │                                    │
    │  pd.to_csv("r2py/yyy.csv")         │
    │<──────── CSV file ─────────────────┤  export_data("result")
    │  fread("r2py/yyy.csv")             │
    │                                    │
```

> See the "Data Exchange" section below for details.

------------------------------------------------------------------------

## Project Structure

```
openclaw_with_jupyterlab_and_rstudio/
│
├── jupyter_mcp/                     # Python side: Jupyter MCP Server
│   ├── jupyter-mcp-server.py        #    MCP Server (ZMQ → Jupyter Kernel)
│   ├── hook.py                      #    Kernel registration function (run in JupyterLab cell)
│   ├── setup.py                     #    pip install -e . setup script
│   ├── jupyter-mcp-architecture.md  #    Architecture design document
│   └── README.md                    #    Quick start
│
├── r-session-ai/                    # R side: R Session API + MCP Server
│   ├── r-session-api.R              #    R API Server (httpuv, runs in RStudio)
│   ├── r-session-mcp-server.py      #    MCP Server (HTTP → R API)
│   ├── r-session-architecture.md    #    Architecture design document
│   └── README.md                    #    Quick start
│
├── jupyterlab-auto-reload/          # JupyterLab extension: auto-refresh Notebook (source)
│   ├── src/index.ts                 #    TypeScript source
│   ├── lib/index.js                 #    Compiled output
│   ├── jupyterlab_auto_reload/      #    Build artifacts (includes static/)
│   ├── package.json                 #    npm dependencies & build scripts
│   ├── tsconfig.json                #    TypeScript config
│   └── setup.py                     #    Python package config
│
├── jupyterlab-console-adopt/       # JupyterLab extension: Console external session echo (source)
│   ├── src/index.ts                 #    TypeScript source
│   ├── lib/index.js                 #    Compiled output
│   ├── jupyterlab_console_adopt/    #    Build artifacts (includes static/)
│   ├── package.json                 #    npm dependencies & build scripts
│   └── tsconfig.json                #    TypeScript config
│
├── example/                         # End-to-end example: Melbourne housing LightGBM prediction
│   ├── README.md                    #    Example description
│   ├── Melbourne_housing_FULL.csv   #    Raw Kaggle dataset
│   ├── Melbourne_housing_Pre.py     #    Data preprocessing script
│   ├── Melbourne_housing_pre.csv    #    Preprocessed data
│   ├── Melbourne_housing_LGBM.py    #    LightGBM training & tuning
│   └── demo-*.png                   #    22-step mobile screenshots
│
├── .gitignore
├── LICENSE                          # MIT License
├── MEMORY.md                        # ⚠️ OpenClaw AI Agent long-term memory sample
│                                    #    Tells the AI how to drive this environment
│                                    #    Replace with your own config after cloning
├── openclaw.json                    # ⚠️ OpenClaw sample configuration
│                                    #    MCP Server / tool registration config
│                                    #    Includes jupyter-mcp, r-session connection params
│                                    #    Modify for your own environment after cloning
└── README.md                        # ← You are here
```

------------------------------------------------------------------------

## Component Details

### Component Reference

| Component | Language | Runtime | Communication | Target | Operates On |
|----|----|----|----|----|----|
| **jupyter-mcp** | Python | graphrag conda | ZMQ (jupyter_client) | Jupyter Kernel | Kernel namespace Python objects |
| **r-session** | Python | graphrag conda | HTTP (httpx) → httpuv | R API → RStudio R Session | .GlobalEnv R objects |
| **R API** | R | RStudio same process | httpuv (non-blocking HTTP) | Current R Session | eval() → direct environment access |
| **jupyterlab-auto-reload** | TypeScript | JupyterLab frontend | Jupyter Contents API | Jupyter Server | .ipynb files |
| **jupyterlab-console-adopt** | TypeScript | JupyterLab frontend | kernel.iopubMessage | Jupyter Kernel | Console CodeCell |

### Operation Modes

#### Python Side (jupyter-mcp)

| Feature | Description |
|----|----|
| Display location | Notebook Cell / Console window (auto-detected by hook) |
| Code execution | Sent to kernel via ZMQ |
| Introspection | Kernel introspection code + `__JUPYTER_MCP_JSON__` marker protocol |
| File operations | Notebook mode: REST API writes .ipynb; Console mode: no .py file modification |
| Extension dependencies | `jupyter-client`, `mcp`, `urllib` (Notebook mode) |
| Startup | Auto-connects after running `hook.register()` in JupyterLab |

#### R Side (r-session)

| Feature | Description |
|----|----|
| Display location | RStudio Console + Environment panel + Plots panel |
| Code execution | eval(parse(text=code)) in .GlobalEnv |
| Console echo | sink(split=TRUE) real-time echo to Console |
| Auth | Bearer Token (optional, required for multi-user) |
| Dependencies | httpuv (R side), httpx + mcp (Python side) |
| Startup | Run `source("r-session-api.R")` in RStudio Console |

------------------------------------------------------------------------

## Data Exchange (R ↔ Python)

### Architecture

```
R Session                    CSV File                    Jupyter Kernel
    │                           │                            │
    │  fwrite(df, path) ───────>│                            │
    │                           │  pd.read_csv(path) ───────>│
    │                           │                            │
    │  <─────── pd.read_csv()   │                            │
    │  fread(path) ─────────────│<─────── to_csv(path)       │
```

### Tools

| Direction | MCP Tools | Internal Implementation |
|----|----|----|
| R → Python | r-session.export_data → jupyter-mcp.import_data | `data.table::fwrite` → CSV → `pd.read_csv` |
| Python → R | jupyter-mcp.export_data → r-session.import_data | `pd.to_csv` → CSV → `data.table::fread` |

### Type Mapping

**Python → R (lossless ✅):**

| Python | R | CSV Intermediate |
|----|----|----|
| int64 | integer | `1` |
| float64 | numeric | `10.5` |
| object (str) | character | `Alice` |
| bool | logical | `TRUE` |
| datetime64 | IDate / POSIXct | `2026-06-07` |

**R → Python (dates/times need fixing ⚠️):**

| R | CSV | Python | Fix |
|----|----|----|----|
| integer/num/char/logical | Native | int64/float64/object/bool ✅ | None needed |
| IDate / POSIXct | `2026-06-07` | object (string) ❌ | `pd.to_datetime(df['col'])` |

### Shared Directory

```
Default: ~/.openclaw/workspace/r2py/  (per user workspace, naturally isolated)
Override: R2PY_SHARED_DIR env var
          R_SHARED_DIR (R-side override)
          JUPYTER_SHARED_DIR (Python-side override)
Filename: UUID prefix + .csv
```

------------------------------------------------------------------------

## Use Case Matrix

| Scenario | Python (jupyter-mcp) | R (r-session) |
|----|----|----|
| Data cleaning, ETL | ✅ pandas | |
| Statistical analysis, regression | | ✅ lm, glm |
| Visualization (interactive) | ✅ plotly | ✅ ggplot2 |
| Visualization (publication) | | ✅ ggplot2 |
| ML (classical) | ✅ sklearn | |
| Deep learning | ✅ PyTorch / TensorFlow | |
| Time series | | ✅ forecast |
| Report generation | ✅ nbconvert | ✅ rmarkdown |

------------------------------------------------------------------------

## Quick Start

### Prerequisites

- Python 3.11+ (Conda or VENV environment recommended, e.g. `graphrag`)
- R 4.x + RStudio Server
- Node.js 22+ (for building JupyterLab extensions)
- JupyterLab 4.x (JupyterHub recommended)

### Installation

``` bash
git clone https://github.com/icejean/openclaw_with_jupyterlab_and_rstudio.git
cd openclaw_with_jupyterlab_and_rstudio
```

Subdirectory deployment guides:

| Directory | README | Description |
|----|----|----|
| `jupyter_mcp/` | [README.md](./jupyter_mcp/README.md) | Jupyter MCP install & register |
| `r-session-ai/` | [README.md](./r-session-ai/README.md) | R API startup & MCP config |

### Recommended Usage

#### 1. OpenClaw Runtime Mode

Use `openclaw chat` in **embedded agent mode** (not gateway/Plugin mode), launched directly from the **Terminal** inside RStudio Server IDE or Jupyter Lab:

``` bash
openclaw chat
```

In this mode, OpenClaw runs as an embedded process, **does not start gateway or Plugin**, and each user's workspace is naturally and completely isolated — no port or process management needed. Ideal for multi-user deployment.

#### 2. Browser Recommendation

**Firefox is recommended.** Chrome has a known issue with Chinese IME in the Terminal — full-width punctuation characters are triggered twice, affecting coding and command-line efficiency.

#### 3. R ↔ Python Data Exchange Scope

CSV-based data exchange between RStudio and Jupyter Lab is suitable only for **small to medium intermediate datasets**. Large datasets should be processed within their original session to avoid I/O and type conversion overhead.

---

### JupyterLab Extension Installation

This repository includes complete source code for two JupyterLab 4.x extensions in the project root:

- `jupyterlab-auto-reload/` — Auto-refresh Notebook (3s after MCP writes)
- `jupyterlab-console-adopt/` — External session echo in Console (.py source mode)

Each extension contains TypeScript source (`src/`), compiled output (`lib/`), and build artifacts (`jupyterlab_*/labextension/`).

#### Build from Source

``` bash
cd jupyterlab-auto-reload
jlpm install       # Install npm dependencies
jlpm run build     # Compile TypeScript + build labextension
jupyter labextension install .   # Install to current Jupyter environment
cd ..

cd jupyterlab-console-adopt
jlpm install
jlpm run build
jupyter labextension install .
cd ..
```

#### Use Pre-Built Artifacts (No Build Required)

Two methods:

**Method 1: jupyter command (recommended)**

``` bash
jupyter labextension install jupyterlab-auto-reload
jupyter labextension install jupyterlab-console-adopt
```

**Method 2: Direct copy to labextensions directory**

Copy the `jupyterlab_*/labextension/` directory (note trailing `/`) to Jupyter's labextensions directory:

``` bash
# Global install (e.g. conda base environment)
cp -R jupyterlab-auto-reload/jupyterlab_auto_reload/labextension/  /usr/lib64/anaconda3/share/jupyter/labextensions/jupyterlab-auto-reload/
cp -R jupyterlab-console-adopt/jupyterlab_console_adopt/labextension/  /usr/lib64/anaconda3/share/jupyter/labextensions/jupyterlab-console-adopt/

# User-local install (no sudo needed)
cp -R jupyterlab-auto-reload/jupyterlab_auto_reload/labextension/  ~/.local/share/jupyter/labextensions/jupyterlab-auto-reload/
cp -R jupyterlab-console-adopt/jupyterlab_console_adopt/labextension/  ~/.local/share/jupyter/labextensions/jupyterlab-console-adopt/
```

> The trailing `/` on the source path means copy the directory **contents** rather than the directory itself. The target directory must be created first.

#### Verify Installation

``` bash
jupyter labextension list
# Both extensions should appear in the list
```

Restart JupyterLab after installation for changes to take effect. For JupyterHub, restart the corresponding user server.

### Reference Tutorials

> The following Zhihu (知乎) article series provide a comprehensive guide to OpenClaw installation, configuration, and usage.

| Topic | Link |
|----|----|
| 🦞 OpenClaw Safe Keeping Tutorial (Part 1) | [Getting Started](https://zhuanlan.zhihu.com/p/2013144472117068259) |
| 🦞 OpenClaw Safe Keeping Tutorial (Part 2) | [Local Deployment](https://zhuanlan.zhihu.com/p/2020880761520227367) |
| 💬 OpenClaw Communication Channel Guide | [Feishu / WeChat / DingTalk](https://zhuanlan.zhihu.com/p/2041198920395658076) |
| 🧪 JupyterHub + OpenClaw + Claude Code Vibe Coding | [Vibe Coding Practice](https://zhuanlan.zhihu.com/p/2026562226463482280) |
| 📊 Jupyter Lab + OpenClaw AI-Assisted Data Analysis | [Data Analysis Practice](https://zhuanlan.zhihu.com/p/2045196634368242170) |
| 📈 RStudio + OpenClaw Vibe Coding & Data Analysis | [R Language Practice](https://zhuanlan.zhihu.com/p/2044067725241210044) |
| 🏗️ OpenClaw Ubuntu 24 Multi-User Deployment | [Basic Architecture](https://zhuanlan.zhihu.com/p/2046116340784697542) |
| 🏗️ OpenClaw Ubuntu 24 Multi-User Deployment (Enhanced) | [Production-Grade Enhancement](https://zhuanlan.zhihu.com/p/2046909112571662596) |

------------------------------------------------------------------------

## Typical Workflow

1. **Start the environment:** Open JupyterLab and RStudio
2. **Register Python side:** Run `hook.register()` in a Jupyter cell
3. **Start R API:** Run `source("r-session-ai/r-session-api.R")` in RStudio Console
4. **Configure OpenClaw:** Modify MCP Server parameters in `openclaw.json` for your environment
5. **Configure MEMORY.md:** Adapt `MEMORY.md` to your environment
6. **Configure Claude Code (recommended):** Claude can access domestic LLMs, works well with OpenClaw
7. **Start analyzing:** Give commands to OpenClaw via conversation

------------------------------------------------------------------------

## Production Deployment

Refer to the following docs for multi-user production deployment:

| Topic | Link |
|----|----|
| 🏗️ OpenClaw Ubuntu 24 Multi-User Deployment | [Basic Architecture](https://zhuanlan.zhihu.com/p/2046116340784697542) |
| 🏗️ OpenClaw Ubuntu 24 Multi-User Deployment (Enhanced) | [Production-Grade Enhancement](https://zhuanlan.zhihu.com/p/2046909112571662596) |

### Security Overview

The system's production security measures span the following layers:

| Layer | Measure | Description |
|----|----|----|
| **Network** | `127.0.0.1` only | R API, MCP Server (stdio mode = no network port), Jupyter MCP all listen only on loopback |
| **Authentication** | Bearer Token | All R API requests verify Token; `openclaw.json` MCP Server configures the same Token; mismatch returns 401 |
| **Process** | stdio subprocess isolation | Each user's MCP Server is an independent OS subprocess, mutually invisible, no network port consumed |
| **Workspace** | User directory isolation | Each user's workspace, shared directory (r2py), MCP registration file are all under their own home dir |
| **Proxy** | Auto-cleanup | MCP Server auto-clears proxy env vars on startup to prevent `ALL_PROXY=socks5` from crashing httpx |
| **Data** | Data stays on-premises | Entirely local network communication, CSV written to local disk, no external services |
| **Token storage** | In-memory | R API Token set via `options()` in R memory, not persisted to disk; config file Token managed by OpenClaw |

> Detailed Token auth flow: see the Security section in [r-session-ai/README.md](./r-session-ai/README.md#security)

------------------------------------------------------------------------

## End-to-End Example

> Melbourne housing price prediction — deep integration of traditional ML (LightGBM) with LLM AI (OpenClaw)
>
> Entirely orchestrated via OpenClaw through WeChat on a mobile phone — zero manual coding.

**Data source:** [Kaggle: Melbourne Housing Market](https://www.kaggle.com/datasets/anthonypino/melbourne-housing-market) (~35,000 property transaction records)

**Workflow:** Data preprocessing → RStudio loads housing data → explore/statistics/plot → export CSV to Jupyter Lab → LightGBM regression → predict → send results back to RStudio → plot actual vs predicted values

```
Traditional ML code (preprocessing + model training & tuning)
    │  (hyperparameter tuning done in local scripts, time-consuming)
    ▼
OpenClaw LLM AI orchestration (22 steps)
    ├── RStudio side: data exploration, visualization
    ├── Jupyter Lab side: LightGBM default params fitting, prediction
    └── RStudio side: result comparison plotting
```

> In this demo, OpenClaw uses LightGBM with default parameters for simple fitting. Hyperparameter tuning is traditional ML engineering outside the demo scope.

| Phase | Tool | Steps |
|----|----|----|
| RStudio EDA: load/preview/stats/plot | r-session | 1-7 |
| R → CSV export | r-session.export_data | 8 |
| CSV → Python import | jupyter-mcp.import_data | 9-10 |
| LightGBM default params fitting → predict | jupyter-mcp.run_code | 11-17 |
| Python → CSV export | jupyter-mcp.export_data | 18 |
| CSV → R import → comparison plot | r-session.import_data / run_code | 19-22 |

Full code, data, and 22-step mobile screenshots: [`example/`](./example/README.md)

------------------------------------------------------------------------

## Dependency Summary

| Component | Required Packages | Installation Command |
|----|----|----|
| **jupyter-mcp** (MCP Server) | `mcp`, `jupyter-client` | `pip install mcp jupyter-client` |
| **r-session-mcp** (MCP Server) | `mcp`, `httpx` | `pip install mcp httpx` |
| **R API Server** (R side) | `httpuv`, `jsonlite` | `install.packages(c("httpuv", "jsonlite"))` |
| **Data exchange** (R side recommended) | `data.table` | `install.packages("data.table")` |
| **Data exchange** (Python side) | `pandas` | `pip install pandas` |

> `pip install` should be run in the Python environment that runs the MCP Server (e.g., graphrag conda environment). `install.packages` should be run in R Console.

------------------------------------------------------------------------

## Environment Variable Reference

### jupyter-mcp MCP Server

| Variable | Default | Description |
|----|----|----|
| `JUPYTER_MCP_HOST` | `127.0.0.1` | MCP Server listen address (for HTTP mode; stdio mode doesn't listen) |
| `JUPYTER_MCP_PORT` | `0` | MCP Server port; `0` = stdio mode (recommended) |
| `JUPYTER_MCP_TIMEOUT` | `120` | Kernel code execution timeout (seconds) |
| `JUPYTER_MCP_REGISTER` | `~/.jupyter-mcp/current` | Kernel registration file path |

### r-session MCP Server

| Variable | Default | Description |
|----|----|----|
| `R_API_HOST` | `127.0.0.1` | R API address |
| `R_API_PORT` | `8161` | R API port |
| `R_API_TOKEN` | Empty | R API auth Token (empty = disabled) |
| `MCP_PORT` | `0` | MCP Server port; `0` = stdio mode (recommended) |

### R API Server (r-session-api.R)

| Variable / option | Default | Description |
|----|----|----|
| `options(rsession_api_port = ...)` or `R_API_PORT` | `8161` | httpuv listen port |
| `options(rsession_api_host = ...)` | `127.0.0.1` | Listen address |
| `options(rsession_api_max_rows = ...)` | `100` | Max preview rows |
| `options(rsession_api_max_str = ...)` | `20` | `str()` truncation level |
| `options(rsession_api_token = ...)` or `R_API_TOKEN` | Empty | Bearer Token (empty = no auth) |

> R options take priority over environment variables. All settings can be configured via `options()` before `source("r-session-api.R")`.

### Shared Directory

| Variable | Default | Description |
|----|----|----|
| `R2PY_SHARED_DIR` | `~/.openclaw/workspace/r2py/` | R↔Python shared directory (master entry) |
| `R_SHARED_DIR` | Same as `R2PY_SHARED_DIR` | R-side override |
| `JUPYTER_SHARED_DIR` | Same as `R2PY_SHARED_DIR` | Python-side override |

------------------------------------------------------------------------

## FAQ

### MCP Server Cannot Find Kernel

Ensure `hook.register()` has been run in a Jupyter cell and that `~/.jupyter-mcp/current` exists. If the kernel has been restarted, re-register:

``` python
from jupyter_mcp import hook
hook.register(force=True)
```

### R API Port Conflict

If startup indicates the port is already in use, a previous R API process hasn't exited cleanly:

``` r
# Option 1: Stop a specific server
httpuv::stopServer(server)

# Option 2: Stop all httpuv servers (doesn't affect Console operations)
httpuv::stopAllServers()

# Then restart
source("r-session-ai/r-session-api.R")
```

### API Broken After rm(list=ls()) in R Session

`rm(list=ls())` clears `.GlobalEnv`, which includes the R API helper functions (`safe_eval`, `ok`, `err`, `server`, etc.). After clearing, the API handler is lost and needs to be reloaded:

``` r
source("r-session-ai/r-session-api.R")
```

Consider keeping important objects in separate environments, or avoid using `rm(list=ls())` during development.

### Proxy Environment Variable Interference

A global proxy configuration (e.g., Clash's `ALL_PROXY=socks5://...`) may cause:

- **r-session MCP Server** startup failure — `httpx.Client()` initialization crashes. MCP Server auto-cleans proxy env vars on startup
- **jupyter-mcp** NotebookClient writing .ipynb via REST API goes through proxy — auto-masked temporarily

If you encounter proxy issues during manual debugging, temporarily clear proxy env vars:

``` bash
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
```

### hook.register() Registration Fails

Check that you're running in the correct kernel cell. If the connection file can't be found:

``` python
from jupyter_mcp import hook
hook.register(force=True)  # force flag overwrites existing registration file
```

------------------------------------------------------------------------

## License

MIT

------------------------------------------------------------------------

> Data AI — Let Python and R collaborate efficiently, powered by AI
