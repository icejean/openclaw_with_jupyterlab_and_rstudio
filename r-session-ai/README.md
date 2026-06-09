# 🦞 R Session AI — 连接 R 与 AI 助手的轻量方案

在 RStudio Server 中运行，让 AI 助手（OpenClaw / Claude Desktop / 任何 MCP 客户端）
能读取、分析、操作当前 R session 中的数据——**数据完全不出服务器**。

## 架构

```
┌── RStudio Server ──────────────────────────────────┐
│                                                     │
│  R Console (当前 session, 正常交互)                  │
│    ├── library(xxx)        ← 用户照常操作           │
│    ├── df <- read.csv(...)                          │
│    └── source("r-session-api.R")  ← 启动 API        │
│                                                     │
│  R Studio Terminal                                  │
│    └── openclaw tui                                 │
│         └── MCP → r-session-mcp-server.py           │
│                    ↓ HTTP                           │
│              http://127.0.0.1:8161                  │
│              ↑                                       │
│  R Session API (httpuv::startServer, 非阻塞)        │
│    ├── GET  /env         ← AI 浏览环境变量          │
│    ├── GET  /preview/x   ← AI 预览数据              │
│    └── POST /eval        ← AI 执行 R 代码 → 修改 session │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 关键设计

- **同一进程**：API 在 R 主进程内运行，`startServer` 不阻塞 Console
- **可写回**：`POST /eval` 执行的代码直接作用在 `.GlobalEnv`
- **仅本地**：监听 `127.0.0.1`，数据不出服务器
- **模型无关**：模型由 OpenClaw 控制，可换任意国产/本地模型

---

## 快速开始

### 1. 安装 R 依赖

在 R Console 中：

```r
install.packages(c("httpuv", "jsonlite"))
```

### 2. 启动 API

```r
source("r-session-api.R")
```

你会看到：

```
┌─────────────────────────────────────────────┐
│  🦞 R Session API 已启动                     │
│  地址: http://127.0.0.1:8161               │
│  ...                                        │
```

Console 可以继续正常使用 R。

### 3. 配置 OpenClaw（推荐方式）

#### 方式 A：MCP 服务器（最优雅）

```bash
# 安装 Python 依赖
pip install mcp httpx

# 告诉 OpenClaw 连接 MCP 服务器
openclaw mcp set r-session '{
  "command": "python3",
  "args": ["'$(pwd)'/r-session-mcp-server.py"],
  "env": {
    "R_API_HOST": "127.0.0.1",
    "R_API_PORT": "8161"
  }
}'
```

验证连接：

```bash
openclaw mcp show r-session
```

然后在 OpenClaw TUI 中，AI 就能通过这 6 个工具与 R session 交互了。

#### 方式 B：HTTP 模式（有独立端口）

```bash
MCP_PORT=8100 python3 r-session-mcp-server.py
```

然后在 OpenClaw 配置中：

```json
{
  "mcp": {
    "servers": {
      "r-session": {
        "url": "http://127.0.0.1:8100/sse",
        "transport": "streamable-http"
      }
    }
  }
}
```

### 4. 验证

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

| MCP 工具 | 对应 API | 说明 |
|----------|----------|------|
| `list_objects()` | `GET /env` | 列出所有对象名/类/大小 |
| `preview_data(name)` | `GET /preview/{name}` | 数据框预览 + 摘要 |
| `get_object_info(name)` | `GET /preview/{name}` | 任意对象的 `str()` |
| `run_code(code, quiet)` | `POST /eval` | 执行 R 代码，**可改 session** |
| `get_loaded_packages()` | `GET /packages` | 已加载包列表 |
| `health_check()` | `GET /health` | 连接测试 |

---

## 停止

```r
httpuv::stopServer(server)
```

---

## 高级配置

### 自定义端口

在 source 之前：

```r
options(rsession_api_port = 9090)
source("r-session-api.R")
```

### 环境变量

```bash
export R_API_PORT=9090
export MCP_PORT=8100
python3 r-session-mcp-server.py
```

### 安全加固

- 默认只监听 `127.0.0.1`，仅本机可访问
- 生产环境可加 nginx 反向代理 + 认证
- 也可用 iptables 限制来源 IP

---

## 和其他方案对比

| | Posit AI | Rserve | plumber | **本方案** |
|--|----------|--------|---------|-----------|
| 同一进程 | ✅ | ❌ fork | ✅ (但阻塞) | ✅ |
| Console 不阻塞 | ✅ | ✅ | ❌ | ✅ |
| 可写回 session | ✅ | ❌ | ✅ | ✅ |
| 国内可用 | ❌ | ✅ | ✅ | ✅ |
| 数据出境 | ✅ | ❌ | ❌ | ❌ |
| 模型自由 | ❌ | ✅ | ✅ | ✅ |
| 免费 | ❌ | ✅ | ✅ | ✅ |

---

## 依赖

- **R 端**: `httpuv`, `jsonlite`（CRAN 包）
- **MCP 端**（可选）: Python 3.8+, `mcp`, `httpx`, `pandas`, `starlette`, `uvicorn`

---

## 许可

MIT
