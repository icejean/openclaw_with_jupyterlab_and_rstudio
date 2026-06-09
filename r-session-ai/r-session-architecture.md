---
output:
  word_document: default
  html_document: default
---

# r-session MCP Server: 原理、架构与实现详解

> 让 AI 代理直接操控 RStudio 的当前 R Session，读数据、做分析、写结果

------------------------------------------------------------------------

## 一、整体架构

```         
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RStudio Server (浏览器)                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  R Console                                                           │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ library(readxl)                                                 │ │    │
│  │  │ df <- read_excel("data.xlsx")  ← 用户照常操作                   │ │    │
│  │  │ source("r-session-api.R")      ← 启动 API                       │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                      │    │
│  │  R Environment 面板:                                                 │    │
│  │  ├── df             48 obs. of 3 variables                           │    │
│  │  ├── model          lm(formula = ...)                                │    │
│  │  └── plot            ← AI 创建的图表                                 │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ 同一个 R 进程
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     R Session (单进程，非阻塞)                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  httpuv::startServer(HOST, PORT, app)                                │    │
│  │                                                                      │    │
│  │  ├── GET /health       → { status, r_version, pid }                  │    │
│  │  ├── GET /env          → { objects: [...], count: N }                │    │
│  │  ├── GET /packages     → { packages: {...}, count: N }               │    │
│  │  ├── GET /preview/{x}  → { head, summary, str, dim, na_count }       │    │
│  │  ├── POST /eval        → eval(code, console_echo=TRUE)               │    │
│  │  ├── POST /eval/quiet  → eval(code, console_echo=FALSE)              │    │
│  │  └── 所有请求验证 Bearer Token（如果配置了）                         │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ HTTP (127.0.0.1:8161)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      r-session-mcp-server.py (Python)                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  RPC 层 (httpx，同步客户端)                                          │    │
│  │  rpc_get(path)  → GET http://127.0.0.1:8161/{path}                   │    │
│  │  rpc_post(path, body) → POST http://127.0.0.1:8161/{path}            │    │
│  │  自动携带 Authorization: Bearer <token>（如果配置了）                │    │
│  │  启动时清洗代理环境变量（ALL_PROXY/socks5 兼容）                     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  MCP 协议层                                                          │    │
│  │  - 8 个工具定义 (types.Tool)                                         │    │
│  │  - handle_call_tool 分发 — 格式化输出                                │    │
│  │  - stdio / HTTP SSE 两种传输模式                                     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  shared_dir (R ↔ Python 数据交换)                                    │    │
│  │  - export_data: R 端 fwrite → CSV → 共享目录                         │    │
│  │  - import_data: CSV → R 端 fread → .GlobalEnv                        │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               │ MCP Protocol (stdio / SSE)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway                                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  MCP Runtime: spawn python3 r-session-mcp-server.py                  │    │
│  │  Tools: r-session__run_code, r-session__preview_data, ...            │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  AI 模型 (DeepSeek / GLM / Kimi / 国产满血版 ...)                    │    │
│  │  用户 → "分析 mtcars 数据集"                                         │    │
│  │  AI  → r-session__list_objects() → 看看有什么数据                    │    │
│  │  AI  → r-session__preview_data("mtcars") → 预览                      │    │
│  │  AI  → r-session__run_code("cor(mtcars$mpg, mtcars$wt)") → 分析      │    │
│  │  AI  → r-session__export_data("result") → 导出到 CSV → Python        │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

------------------------------------------------------------------------

## 二、核心设计理念

### 2.1 为什么不用 fork/子进程？

大多数 R API 方案（如 plumber、Rserve）会在新进程中执行代码，这意味着：

-   ❌ 无法访问 RStudio 当前 session 中的变量
-   ❌ 创建的对象不会出现在 RStudio Environment 面板
-   ❌ 用户需要反复加载数据、安装包

本方案选择**同一进程 + 非阻塞 HTTP 服务**：

```         
R 主进程：
├── R Console（用户交互，不阻塞）
├── R API (httpuv::startServer，事件驱动，不阻塞)
│   └── GET/POST 请求 → eval() → 直接操作 .GlobalEnv
└── 变量在 Console、Environment 面板、API 三者间实时同步
```

`httpuv::startServer()` 基于 libuv 事件循环，与 R Console 共享同一个进程。 R Console 执行代码时，API 请求排队等待；API 处理请求时，Console 输入排队等待。 两者互相不阻塞——这是 httpuv 作为 R 异步网络框架的核心能力。

### 2.2 安全设计

| 措施       | 实现                                           |
|------------|------------------------------------------------|
| 仅本地访问 | 监听 `127.0.0.1`，默认端口 8161                |
| Token 认证 | Bearer Token，可选（R options / 环境变量配置） |
| 数据不出境 | 全程内网通信，CSV 写入本地共享目录             |
| eval 权限  | 相当于用户自己在 Console 中执行代码            |

### 2.3 Token 认证设计（2026-06-07 新增）

**背景：** 多用户场景下，R API 绑定 127.0.0.1 但所有本地用户可访问。 恶意用户可扫描端口后 `curl http://127.0.0.1:8161/eval` 执行任意 R 代码。

**方案：** R API + MCP Server 增加 Bearer Token 认证

```         
┌─ openclaw.json ──────────────────────┐
│ "r-session": {                       │
│   "env": {                           │
│     "R_API_TOKEN": "<secret>"        │
│   }                                  │
│ }                                    │
└──────────────────────────────────────┘
     │ 传递给 MCP Server
     ▼
┌─ r-session-mcp-server.py ────────────┐
│ _client_headers["Authorization"]     │
│     = f"Bearer {R_API_TOKEN}"        │
│ → 所有请求自带 Bearer Token          │
└──────────────────────────────────────┘
     │ HTTP 请求
     ▼
┌─ r-session-api.R ────────────────────┐
│ API_TOKEN <- getOption(              │
│  "rsession_api_token",               │
│  Sys.getenv("R_API_TOKEN", ...))     │
│ 每个请求验证 Authorization header    │
│ 不匹配 → 401 unauthorized            │
└──────────────────────────────────────┘
```

**Token 来源优先级：** `options(rsession_api_token=...)` \> 环境变量 `R_API_TOKEN` \> 空（不启用认证）

**多用户部署：** 每个用户 Token 不同，通过 `openclaw.json` 的 `env` 注入。

------------------------------------------------------------------------

## 三、R 端核心代码详解

### 3.1 R Session API Server

**位置：** `r-session-api.R`

**启动方式：** 在 RStudio Console 中运行 `source("r-session-api.R")`

**依赖：** `httpuv`（HTTP 服务器）+ `jsonlite`（JSON 序列化）

#### 配置优先级

| 配置项       | R options               | 环境变量      | 默认值       |
|--------------|-------------------------|---------------|--------------|
| 端口         | `rsession_api_port`     | `R_API_PORT`  | `8161`       |
| 主机         | `rsession_api_host`     | —             | `127.0.0.1`  |
| 最大预览行数 | `rsession_api_max_rows` | —             | `100`        |
| str 截断层级 | `rsession_api_max_str`  | —             | `20`         |
| API Token    | `rsession_api_token`    | `R_API_TOKEN` | 空（不启用） |

**配置优先级规则：** 环境变量 \> R options \> 默认值

#### 安全执行器：safe_eval()

```         
safe_eval(code, env = .GlobalEnv, console_echo = TRUE)
```

这是最核心的函数，负责：

1.  **执行前快照：** 记录 `ls(envir = env)` 获取当前变量列表
2.  **执行代码：** `eval(parse(text = code), envir = env)`
    -   使用 `withVisible()` 检测是否有显式返回值
    -   `console_echo=TRUE` 时：`sink()` 到临时文件 + `split=TRUE` 同时回显到 Console
    -   `console_echo=FALSE` 时：`capture.output()` 仅捕获不显示
3.  **执行后对比：** 检测新增/修改的变量（`setdiff(after, before)`）
4.  **返回值：**

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

**异常安全：** `tryCatch` 包裹，错误作为 `error` 字段返回，不影响 session 状态。

#### HTTP 路由

| 路由 | 方法 | 用途 | 实现 |
|------------------|------------------|------------------|------------------|
| `/health` | GET | 健康检查 | `list(status="alive", r_version, pid, host, port)` |
| `/env` | GET | 列出全局变量 | `lapply(ls(), obj_to_list)` |
| `/packages` | GET | 列出已加载包 | `loadedNamespaces()` + `packageVersion()` |
| `/preview/{name}` | GET | 预览对象 | `safe_str()`, `head()`, `summary()`, `is.na()` |
| `/eval` | POST | 执行 R 代码 | `safe_eval(code, console_echo=TRUE)` |
| `/eval/quiet` | POST | 静默执行 | `safe_eval(code, console_echo=FALSE)` |
| OPTIONS | 任意 | CORS 预检 | 返回 Allow-Origin/Methods/Headers |

#### 对象序列化：obj_to_list()

递归地将 R 对象转换为 JSON 可序列化的列表：

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

#### Token 验证

每个请求（OPTIONS 除外）验证 `Authorization` header：

``` r
auth_header <- req$HTTP_AUTHORIZATION %||% ""
token <- sub("^Bearer[[:space:]]+", "", auth_header)
if (token != API_TOKEN) {
  # 返回 401
}
```

#### CORS 处理

所有响应都包含 `Access-Control-Allow-Origin: *` 头。 预检请求（OPTIONS）返回 200 + 允许的方法和头（含 `Authorization`）。

#### 退出清理

`reg.finalizer(server, ...)` 确保 R session 退出时自动停止 httpuv 服务器。

------------------------------------------------------------------------

### 3.2 为什么 R 能启动 HTTP 服务又不阻塞 Console？

``` r
server <- startServer(HOST, PORT, app)
```

`httpuv::startServer()` 启动一个**非阻塞**的 HTTP 服务器：

1.  内部使用 libuv 事件循环
2.  注册回调函数（`app$call`）处理 HTTP 请求
3.  不占用 R Console 的主线程
4.  R Console 仍可正常输入和执行代码
5.  当 API 请求到达时，R 会在当前事件循环迭代中处理它

这类似于 Node.js 的事件循环——主线程不阻塞，I/O 事件通过回调处理。

### 3.3 Console Echo 两种模式对比

| 模式 | 实现方式 | 执行时 Console 行为 | 输出捕获 |
|------------------|------------------|------------------|------------------|
| `console_echo=TRUE` | `sink(file, split=TRUE)` | 输出实时回显到 Console | 从临时文件读回 |
| `console_echo=FALSE` | `capture.output({ ... })` | 不显示任何输出 | 直接在内存中捕获 |

选择 `sink(split=TRUE)` 而非 `capture.output()` 的原因是： - `capture.output()` 会抑制 Console 输出（用户看不到 AI 在执行什么） - `sink(split=TRUE)` 既捕获到文件，又同时回显到 Console - 用户在 RStudio Console 中能看到 AI "打字" 的实时效果

------------------------------------------------------------------------

## 四、MCP Server 端详解

### 4.1 Python MCP Server

**位置：** `r-session-mcp-server.py`

**shebang：** `#!/usr/lib64/anaconda3/envs/graphrag/bin/python3`

**依赖：** `mcp`（MCP 协议）、`httpx`（HTTP 客户端）

#### 环境变量

| 变量              | 默认值               | 说明                             |
|-------------------|----------------------|----------------------------------|
| `R_API_HOST`      | `127.0.0.1`          | R API 地址                       |
| `R_API_PORT`      | `8161`               | R API 端口                       |
| `R_API_TOKEN`     | 空                   | Bearer Token（空=不启用）        |
| `MCP_PORT`        | `0`                  | MCP 服务器端口（`0`=stdio 模式） |
| `R2PY_SHARED_DIR` | `~/workspace/r2py/`  | R↔Python 数据交换目录            |
| `R_SHARED_DIR`    | 同 `R2PY_SHARED_DIR` | R 侧覆盖                         |

#### 代理兼容性

MCP Server 启动时**清除所有代理环境变量**：

``` python
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
os.environ.pop("HTTP_PROXY", None)
# ... 6 个常见代理环境变量全部清除
```

原因是系统可能配置了 `ALL_PROXY=socks5://...`，这会导致 `httpx.Client()` 在初始化时解析 SOCKS5 代理失败而崩溃——即使 `NO_PROXY` 包含 `127.0.0.1` 也无法绕过，因为 httpx 在构造 Client 时就解析代理了。

#### httpx 客户端配置

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

-   同步客户端，简化代码逻辑
-   30 秒超时，适合大部分 R 分析任务
-   自动携带 Token（如果配置了）

#### 调用流程

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
                    ▼  safe_eval(code) → .GlobalEnv 中被修改
                    │
                    ▼  JSON 响应
              Python 收到结果
                    │
                    ▼  格式化输出（表格/文本布局）
              [types.TextContent]
                    │
                    ▼
              OpenClaw → AI 模型
```

#### MCP 工具定义（8 个）

| 工具 | HTTP 调用 | 数据格式化 | 输出特征 |
|------------------|------------------|------------------|------------------|
| `list_objects` | `GET /env` | 表格：名称、类、大小、维度 | 纯文本表格 |
| `preview_data(name)` | `GET /preview/{name}` | str + head + summary + 缺失值 | 结构化文本 |
| `get_object_info(name)` | `GET /preview/{name}` | str 输出 | 纯文本 |
| `run_code(code, quiet)` | `POST /eval` 或 `/eval/quiet` | 成功/失败 + 输出 + 新变量 + 返回值 | 结构化文本 |
| `get_loaded_packages` | `GET /packages` | 包名+版本列表 | 纯文本表格 |
| `health_check` | `GET /health` | R 版本、PID、地址 | 结构化文本 |
| `export_data(name)` | `POST /eval`（fwrite） | CSV 路径 + 确认 | 纯文本 |
| `import_data(path, var_name)` | `POST /eval`（fread） | 导入确认 | 纯文本 |

#### 输出格式化细节

-   **list_objects：** 对齐列宽 20/18/6 的表格，含 Emoji 图标
-   **preview_data：** 分节展示（结构→预览→摘要→缺失值），用水平分隔线
-   **run_code：** 输出截断 200 行 + 新变量列表 + 返回值摘要
-   **错误处理：** 三层次（`httpx.ConnectError` → `httpx.HTTPStatusError` → 通用 Exception）

------------------------------------------------------------------------

## 五、R ↔ Python 数据交换

### 设计理念

-   跨 session 传的**只限小数据集**，大数据集在该 session 原地处理
-   **只用 CSV** — R 的 `data.table::fwrite/fread` 和 Python 的 `pandas.read_csv/to_csv` 都原生支持
-   CSV 类型可能失真，但小数据集一两个 `as.integer()` / `astype()` 就修好了
-   核心原则：**简单通用，偶尔手动修正**

### 架构

```         
R Session → R API (httpuv) → r-session-mcp (Python) → CSV
                                                         ↓
Jupyter Kernel ← jupyter-mcp (Python) ← CSV
```

### 工具

**r-session-mcp（R 侧读写）：**

| 工具 | 内部实现 |
|------------------------------------|------------------------------------|
| `export_data(name)` | R 侧执行 `data.table::fwrite(obj, path, row.names=FALSE)` |
| `import_data(path, var_name)` | R 侧执行 `data.table::fread(path)` → `.GlobalEnv` |

### 类型保真实测

**R → CSV → Python（`pd.read_csv`）：**

| R | CSV | Python |
|------------------------|------------------------|------------------------|
| integer | `1` | int64 ✅ |
| numeric | `10.5` | float64 ✅ |
| character | `Alice` | object ✅ |
| logical | `TRUE` | bool ✅ |
| IDate/Date | `2026-06-07` | object（字符串）❌ → 需 `pd.to_datetime()` |
| POSIXct | `2026-06-07 10:30:00` | object（字符串）❌ → 需 `pd.to_datetime()` |

**Python → R（`data.table::fread`）：**

所有类型无损 ✅

### 共享目录

```         
默认: ~/.openclaw/workspace/r2py/（各用户工作区下，天然隔离）
覆盖: R2PY_SHARED_DIR 或 R_SHARED_DIR 环境变量
文件名: UUID 前缀 + .csv
```

------------------------------------------------------------------------

## 六、部署与配置

### 6.1 前提条件

``` bash
# R 端
install.packages(c("httpuv", "jsonlite"))

# Python 端（graphrag conda 环境）
pip install mcp httpx
```

### 6.2 启动流程

``` mermaid
sequenceDiagram
    participant User as 用户
    participant RStudio as RStudio Console
    participant RAPI as R Session API
    participant MCP as r-session-mcp-server
    participant GW as OpenClaw Gateway
    participant AI as AI Model

    User->>RStudio: library(readxl)
    User->>RStudio: df <- read_excel(...)
    User->>RStudio: source("r-session-api.R")
    RStudio->>RAPI: httpuv::startServer()
    RAPI-->>RStudio: 打印启动信息（含 Token 状态）

    Note over GW: mcp.servers.r-session 已配置
    GW->>MCP: spawn 子进程
    MCP->>RAPI: GET /health（带 Bearer Token）
    RAPI-->>MCP: {success: true, pid: 1234}
    MCP-->>GW: listTools() → 8 个工具

    User->>AI: "分析一下数据"
    AI->>GW: 思考 → 需要先看数据
    GW->>MCP: callTool(list_objects)
    MCP->>RAPI: GET /env
    RAPI-->>MCP: {objects: [df, ...]}
    MCP-->>GW: 格式化表格
    GW-->>AI: R 环境中有 df (48×3), model ...

    AI->>GW: 需要预览 df
    GW->>MCP: callTool(preview_data, "df")
    MCP->>RAPI: GET /preview/df
    RAPI-->>MCP: {head, summary, na_count}
    MCP-->>GW: 格式化预览
    GW-->>AI: df 结构、预览、摘要、缺失值

    AI->>GW: 执行分析
    GW->>MCP: callTool(run_code, {code: "..."})
    MCP->>RAPI: POST /eval {code: "..."}
    RAPI->>RStudio: safe_eval(code) ← Console 可看到执行
    RStudio-->>RStudio: .GlobalEnv 新增变量
    RAPI-->>MCP: {output, new_objs: ["result"]}
    MCP-->>GW: 格式化输出
    GW-->>AI: 分析结果 + 新变量

    GW-->>User: 展示分析结论
    Note over RStudio: RStudio Environment 面板<br/>已出现 AI 创建的新变量
```

### 6.3 OpenClaw 配置

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

### 6.4 HTTP/SSE 模式

除了默认的 stdio 模式，MCP Server 还支持 HTTP/SSE 模式：

``` bash
export MCP_PORT=8100
python3 r-session-mcp-server.py
# 启动在 http://127.0.0.1:8100/sse
```

HTTP 模式依赖 `uvicorn` 和 `starlette`，适用于远程连接场景。

------------------------------------------------------------------------

## 七、与 jupyter-mcp 的对比

| 维度 | r-session | jupyter-mcp |
|------------------------|------------------------|------------------------|
| 语言 | R | Python |
| IDE | RStudio Server | JupyterLab |
| 显示位置 | RStudio Console + Environment 面板 | Notebook Cell / Console 窗口 |
| 通信方式 | HTTP (R API → Python MCP) | ZMQ (jupyter_client 直连 kernel) |
| 数据形式 | .GlobalEnv 中的 R 对象 | kernel 命名空间中的 Python 对象 |
| 图形输出 | RStudio Plots 面板 | Notebook 内嵌 / JupyterLab 内嵌 |
| 注册方式 | `source("r-session-api.R")` | `hook.register()` |
| API 进程 | 同进程 httpuv 非阻塞 | 同进程 ZMQ |
| 数据交换 | CSV (data.table::fwrite/fread) | CSV (pandas.to_csv/read_csv) |
| 唯一优势 | 可写回 Environment 面板 | 实时同步 Notebook 文件 |

------------------------------------------------------------------------

## 八、项目文件清单

```         
r-session-ai/
├── r-session-api.R               # R Session API Server（在 RStudio 中运行）
├── r-session-mcp-server.py       # Python MCP Server（OpenClaw 管理）
├── README.md                     # 快速入门文档
└── r-session-architecture.md     # 本文档
```

------------------------------------------------------------------------

## 九、已知限制与注意事项

1.  **httpuv 需主线程空闲**：R Console 正在执行耗时操作（如 `Sys.sleep(10)` 或长循环）时，API 请求会排队等待
2.  **eval 安全隐患**：API 绑定 127.0.0.1 但本地其他进程可访问。生产环境多用户场景**必须**配置 Token 认证
3.  **大对象传输**：JSON 序列化大数据框可能占用较多内存。`MAX_ROW` 默认限制 100 行预览
4.  **CRAN 包依赖**：`httpuv` 和 `jsonlite` 需预先安装，部分离线环境可能需要本地源安装
5.  **停止方式**：`httpuv::stopServer(server)` 或重启 R session
6.  **代理兼容**：如果系统配置了 socks5 代理，httpx 客户端初始化会崩溃。MCP Server 已自动清除所有代理环境变量
7.  **Token 优先级**：`options(rsession_api_token=...)` 优先于环境变量 `R_API_TOKEN`，方便用户通过 R options 动态配置
8.  **多用户隔离**：每个用户的 R Session 是独立 OS 进程，httpuv 各自绑定不同端口，互不干扰。`httpuv::stopServer(server)` 和 `stopAllServers()` 均只在当前 Session 有效

------------------------------------------------------------------------

## 十、变更日志

| 日期 | 变更内容 |
|------------------------------------|------------------------------------|
| 初始版 | 基础架构、`safe_eval`、6 个 HTTP 端点、MCP Server stdio 模式 |
| v2 | Token 认证（R options / 环境变量 / Bearer Token）、代理兼容性 |
| v3 | export_data/import_data（R↔Python 数据交换）、`console_echo=FALSE` 模式 |
| v4 | HTTP/SSE 模式、shebang 改为 graphrag 环境、环境变量化配置 |
