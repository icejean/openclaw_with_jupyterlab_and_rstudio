# 🦞 R Session AI — 连接 R 与 AI 助手的轻量方案

在 RStudio Server 中运行，让 AI 助手（OpenClaw / Claude Desktop / 任何 MCP 客户端）能读取、分析、操作当前 R session 中的数据——**数据完全不出服务器**。

## 架构

```
┌── RStudio Server ────────────────────────────────────────────────────┐
│                                                                      │
│  R Console (当前 session, 正常交互)                                  │
│    ├── library(xxx)         ← 用户照常操作                          │
│    ├── df <- read.csv(...)                                           │
│    └── source("r-session-api.R")  ← 启动 API（指定端口 + Token）    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  R Session API (httpuv::startServer, 同进程非阻塞 HTTP)      │    │
│  │                                                              │    │
│  │  ├── GET  /health     ← 健康检查                            │    │
│  │  ├── GET  /env        ← 浏览 R 环境变量                     │    │
│  │  ├── GET  /preview/x  ← 预览数据                            │    │
│  │  ├── GET  /packages   ← 已加载包                            │    │
│  │  ├── POST /eval       ← 执行 R 代码 → 修改 session (echo)   │    │
│  │  └── POST /eval/quiet ← 静默执行 R 代码                     │    │
│  │                                                              │    │
│  │  └─ 所有请求验证 Bearer Token，无 Token 或错误 → 401        │    │
│  └──────────────────────┬──────────────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────────────┘
                          │ HTTP (127.0.0.1:{R_API_PORT})
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  OpenClaw (主进程)                                                   │
│                                                                      │
│  ┌─ openclaw.json 中 mcp.servers.r-session ──────────────────────┐  │
│  │  command: python3 r-session-mcp-server.py                     │  │
│  │  env: { R_API_HOST, R_API_PORT, R_API_TOKEN }                │  │
│  │  以 stdio 子进程方式启动 MCP Server                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                         │                                            │
│                         │ 子进程 stdin/stdout                         │
│                         ▼                                            │
│  ┌─ r-session-mcp-server.py ───────────────────────────────────┐   │
│  │  通过 HTTP 调用 R API (自动携带 Bearer Token)                │   │
│  │  ├── list_objects → GET /env                                │   │
│  │  ├── run_code    → POST /eval {code: "..."}                 │   │
│  │  └── export_data → POST /eval {fwrite 代码}                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 关键设计

- **同一进程**：API 在 R 主进程内运行，`startServer` 不阻塞 Console
- **可写回**：`POST /eval` 执行的代码直接作用在 `.GlobalEnv`
- **仅本地**：监听 `127.0.0.1`，数据不出服务器
- **Token 认证**：所有 API 请求必须携带 Bearer Token，防止非授权访问
- **模型无关**：模型由 OpenClaw 控制，可换任意国产/本地模型

---

## 快速开始

### 1. 安装 R 依赖

在 R Console 中：

``` r
install.packages(c("httpuv", "jsonlite"))
```

### 2. 启动 R API Server

在 RStudio Console 中执行：

``` r
# 先设置 Token（用于 API 请求认证，必设！）
options(rsession_api_token = "your-secret-token-here")

# 启动 API（默认端口 8161，可自定义端口见下方说明）
source("r-session-ai/r-session-api.R")
```

你会看到：

```
┌─────────────────────────────────────────────┐
│  🦞 R Session API 已启动                    │
│  地址: http://127.0.0.1:8161                │
│  Token 认证: ✅ 已启用                       │
│  Console Echo: ✅ 开启 (source=echo)         │
└─────────────────────────────────────────────┘
```

Console 可以继续正常使用 R。

### 3. 在 OpenClaw 中配置 MCP Server（推荐：stdio 模式）

在 `openclaw.json` 的 `mcp.servers` 中添加：

```json
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

**示例（graphrag conda 环境）：**

```json
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

配置完成后重启 OpenClaw 即可自动拉起 MCP Server。

### 4. 安装 Python 依赖（MCP Server 端）

``` bash
pip install mcp httpx
```

### 5. 验证

```
你: 看看环境里有什么数据？
AI: → list_objects()
你: 预览一下 mtcars
AI: → preview_data("mtcars")
你: 帮我分析一下 mpg 和 wt 的关系
AI: → run_code("cor(mtcars$mpg, mtcars$wt)")
你: 帮我创建一个新的数据框，包含标准化后的变量
AI: → run_code("mtcars_scaled <- as.data.frame(scale(mtcars))")
```

执行后，变量会出现在 RStudio 的 Environment 面板中。

---

## 工具说明

| 工具 | 对应 API | 说明 |
|----|----|----|
| `list_objects()` | `GET /env` | 列出所有对象名/类/大小 |
| `preview_data(name)` | `GET /preview/{name}` | 数据框预览 + 摘要 |
| `get_object_info(name)` | `GET /preview/{name}` | 任意对象的 `str()` |
| `run_code(code, quiet)` | `POST /eval` | 执行 R 代码，**可改 session** |
| `get_loaded_packages()` | `GET /packages` | 已加载包列表 |
| `export_data(name)` | `POST /eval` | R → Python 数据导出 |
| `import_data(path, var_name)` | `POST /eval` | Python → R 数据导入 |
| `health_check()` | `GET /health` | 连接测试 |

---

## 停止

``` r
httpuv::stopServer(server)
```

---

## 多用户部署

### R API Server 端口分配

多用户环境下，每个用户的 R API Server 不能共用端口。在 `source()` 之前通过 `options()` 指定不同端口：

``` r
# 用户 A（RStudio 实例 1）
options(rsession_api_port = 8161)
options(rsession_api_token = "token-for-user-a")
source("r-session-ai/r-session-api.R")

# 用户 B（RStudio 实例 2）
options(rsession_api_port = 8162)
options(rsession_api_token = "token-for-user-b")
source("r-session-ai/r-session-api.R")

# 用户 C（RStudio 实例 3）
options(rsession_api_port = 8163)
options(rsession_api_token = "token-for-user-c")
source("r-session-ai/r-session-api.R")
```

### OpenClaw 配置（每个用户各自一份）

每个用户在各自的 `openclaw.json` 中配置对应的端口和 Token：

```json
"r-session": {
  "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
  "args": ["/home/用户目录/r-session-ai/r-session-mcp-server.py"],
  "env": {
    "R_API_HOST": "127.0.0.1",
    "R_API_PORT": "8161",        ← 与 options 中的端口一致
    "R_API_TOKEN": "token-for-user-a"  ← 与 options 中的 Token 一致
  }
}
```

### 为什么 stdio 模式适合多用户

| | **stdio 模式（推荐）** | HTTP / SSE 模式 |
|----|----|----|
| **通信方式** | OpenClaw 以子进程启动 MCP Server，通过 stdin/stdout 通信 | MCP Server 监听网络端口，通过 HTTP / SSE 通信 |
| **端口冲突** | 无。每个用户的 MCP Server 有独立的 OS 进程，不占用任何端口 | 有。MCP Server 本身也需分配端口 |
| **安全问题** | 无网络暴露，子进程天然隔离，用户间互不可见 | MCP 端口开放即有潜在攻击面 |
| **多用户部署** | ✅ 天然支持。每个用户在 `openclaw.json` 中各自配置 | ❌ MCP Server 和 R API Server 均需分配端口 |

> **注意：** 多用户环境下，R API Server 仍然需要分配不同端口（通过 `options(rsession_api_port = ...)` 指定），因为 httpuv 监听的是网络端口。但 MCP Server 之间是 stdio 隔离，完全不占用端口。

---

## 安全加固

### Token 认证设计

```
┌─ openclaw.json ────────────────────────────────────────┐
│ "r-session": {                                          │
│   "env": {                                              │
│     "R_API_TOKEN": "your-secret-token-here"            │
│   }                                                      │
│ }                                                        │
└──────────────────────┬──────────────────────────────────┘
                       │ 传递到 MCP Server 进程的环境变量
                       ▼
┌─ r-session-mcp-server.py ─────────────────────────────┐
│ _client_headers["Authorization"] =                     │
│     f"Bearer {R_API_TOKEN}"                            │
│ → 所有 HTTP 请求自动携带 Bearer Token                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP 请求（含 Authorization header）
                       ▼
┌─ R Session API (r-session-api.R) ─────────────────────┐
│                                                         │
│  Token 来源优先级：                                      │
│  1. options(rsession_api_token = "...")  ← 推荐          │
│  2. Sys.getenv("R_API_TOKEN")                            │
│  3. 空 → 不启用认证（仅适合单用户本地调试）              │
│                                                         │
│  每个请求（除 OPTIONS）：                                  │
│    auth_header <- req$HTTP_AUTHORIZATION                │
│    token <- sub("^Bearer[[:space:]]+", "", auth_header) │
│    if (token != API_TOKEN) → 返回 401                   │
└──────────────────────────────────────────────────────────┘
```

### 配置步骤

**1. R 端设置 Token（二选一）：**

``` r
# 推荐：通过 options 设置（优先级最高）
options(rsession_api_token = "my-strong-token-abc123")

# 或：通过环境变量设置
Sys.setenv(R_API_TOKEN = "my-strong-token-abc123")
```

**2. OpenClaw 端配置相同 Token：**

在 `openclaw.json` 的 `env` 字段中写入同一个 Token：

```json
"env": {
  "R_API_PORT": "8161",
  "R_API_TOKEN": "my-strong-token-abc123"
}
```

### 安全原理

| 保护层 | 说明 |
|----|----|
| **Token 认证** | 所有 API 端点（除 OPTIONS）验证 Bearer Token，不匹配返回 `401 Unauthorized` |
| **仅绑定 127.0.0.1** | httpuv 只监听本地回环地址，外部网络无法访问 |
| **MCP Server 本地子进程** | stdio 模式下 MCP Server 无网络端口，纯本地通信 |
| **Token 不落盘** | 配置在 R options（内存中），不在文件系统明文存储 |

### Token 生成建议

``` bash
# 生成强随机 Token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

多用户部署时，每个用户的 Token 应不同。

---

## 高级配置

### 自定义端口

``` r
options(rsession_api_port = 9090)
options(rsession_api_token = "your-token")
source("r-session-ai/r-session-api.R")
```

### 环境变量（替代 options）

``` bash
export R_API_PORT=8161
export R_API_TOKEN=your-token
```

然后在 R 中只需 `source("r-session-ai/r-session-api.R")` 即可。

### Token 来源优先级

| 优先级 | 来源 | 设置方式 |
|----|----|----|
| 最高 | `options(rsession_api_token = "...")` | R Console 中设置 |
| 次之 | 环境变量 `R_API_TOKEN` | `Sys.setenv()` 或 `.Renviron` |
| 最低 | 空值（不启用认证） | 仅适合单用户本地调试 |

---

## 和其他方案对比

| | Posit AI | Rserve | plumber | **本方案** |
|----|----|----|----|----|
| 同一进程 | ✅ | ❌ fork | ✅ (但阻塞) | ✅ |
| Console 不阻塞 | ✅ | ✅ | ❌ | ✅ |
| 可写回 session | ✅ | ❌ | ✅ | ✅ |
| Token 认证 | ✅ | ❌ | ❌ | ✅ |
| 国内可用 | ❌ | ✅ | ✅ | ✅ |
| 数据出境 | ✅ | ❌ | ❌ | ❌ |
| 模型自由 | ❌ | ✅ | ✅ | ✅ |
| 免费 | ❌ | ✅ | ✅ | ✅ |

---

## 依赖

- **R 端：** `httpuv`, `jsonlite`（CRAN 包）
- **MCP 端（可选）：** Python 3.8+, `mcp`, `httpx`

---

## 许可

MIT
