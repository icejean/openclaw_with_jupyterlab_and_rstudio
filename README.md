# OpenClaw + JupyterLab + RStudio

> Python & R 双语 AI 数据分析环境 —— Fast-Python-AI，平替 Posit AI

一体化的 **Python + R** 数据分析工作台，以 **OpenClaw AI Agent** 为大脑，串联 **JupyterLab (Python)** 和 **RStudio (R)** 两个交互式分析引擎，通过 **MCP 协议**统一工具接口，实现跨语言数据流无缝流转。

------------------------------------------------------------------------

## 为什么做这个

Python 和 R 各有不可替代的生态。传统方案（如 Posit/Quarto）侧重 R 端整合，Python 端依赖 reticulate，体验割裂。这套方案用 **OpenClaw Agent 做胶水层** + **MCP Server 做连接桥** + **CSV 共享做数据交换**，让两个语言各取所长，在同一平台下顺畅协作。

### 核心优势

-   🏠 **数据不出服务器不出境**，内网可配合一体机部署
-   🇨🇳 **国内信创环境已验证**：麒麟 V10 + 鲲鹏 CPU (ARM64) + 国产满血版 LLM
-   🔄 **LLM 可按需切换**（DeepSeek / GLM / MiniMax / Kimi 等）
-   🪶 轻量级浏览器界面，易用易部署易维护
-   🔓 完全开源免费
-   📊 AI 贯穿 **编码阶段** + **数据分析阶段**

------------------------------------------------------------------------

## 架构

### 整体架构图

```         
                          ┌──────────────────────┐
                          │  用户（浏览器界面）  │
                          │ JupyterLab / RStudio │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │    OpenClaw Agent    │  ← AI 大脑
                          │对话 + 指令路由 + MCP │  ← 所有工具通过 MCP 协议暴露
                          └──┬───────────────┬───┘
                             │               │
              ┌──────────────▼──┐    ┌───────▼─────────────┐
              │ MCP Server      │    │  MCP Server         │
              │ jupyter-mcp     │    │  r-session          │
              │ (Python)        │    │  (Python)           │
              │ ZMQ 直连 kernel │    │  HTTP 调用 R API    │
              └──────┬──────────┘    └──────┬──────────────┘
                     │                      │
              ┌──────▼─────────┐    ┌───────▼──────────────┐
              │  Jupyter       │    │  R API (httpuv)      │
              │  Kernel        │    │  同进程非阻塞 HTTP   │
              │  (IPython)     │    │  → eval() 操作       │
              │  Python 对象   │    │  .GlobalEnv          │
              └──────┬─────────┘    │  RStudio R Session   │
                     │              └──────┬───────────────┘
                     │                     │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼─────────────┐
                     │  r2py 共享目录         │
                     │  (~/r2py/*.csv)        │
                     │  R ↔ Python 跨语言同步 │
                     └────────────────────────┘
```

### 两条数据流详解

#### ① Python 侧（jupyter-mcp）

```         
OpenClaw Agent
    │ callTool(run_code, ...) ← MCP 协议
    ▼
jupyter-mcp-server.py  (MCP Server, Python, 运行在 graphrag conda 环境)
    │ 读取 ~/.jupyter-mcp/current → 获取 kernel 连接信息
    │ jupyter_client 库通过 ZMQ 协议直接连接 kernel
    ▼
Jupyter Kernel  (IPython, 运行在 JupyterLab 中)
    │ 代码在 kernel 中执行 → 修改 kernel 命名空间中的 Python 对象
    │ 如果是 export_data / import_data：
    ▼
r2py/ 共享目录  (CSV 文件)
```

**通信协议：** `jupyter_client` + ZMQ（Shell / IOPub / Stdin / Control / Heartbeat 五个通道）

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

> 详细架构文档：[jupyter_mcp/jupyter-mcp-architecture.md](./jupyter_mcp/jupyter-mcp-architecture.md)

#### ② R 侧（r-session）

```         
OpenClaw Agent
    │ callTool(run_code, ...) ← MCP 协议
    ▼
r-session-mcp-server.py  (MCP Server, Python, 运行在 graphrag conda 环境)
    │ httpx 客户端 → HTTP POST + Bearer Token
    ▼
R API Server  (httpuv, 运行在 RStudio 的 R Session 中，同进程非阻塞)
    │ safe_eval(code) → eval(parse(text=code)) 在 .GlobalEnv 中执行
    │ 代码结果实时显示在 RStudio Console + Environment 面板
    │ 如果是 export_data / import_data：
    ▼
r2py/ 共享目录  (CSV 文件)
```

**通信协议：** HTTP（`httpx.Client` → `httpuv::startServer`）

```         
MCP Server                              R API (httpuv)
    │  GET /health                            │
    │  GET /env                               │
    │  POST /eval  {code: "..."}              │
    ├────────────────────────────────────────>│
    │  {success, output, new_objs, ...}       │
    │<────────────────────────────────────────┤
```

**为什么 R API 用 httpuv 而不是 fork 子进程：**

大多数方案（plumber、Rserve）会在新进程中执行代码，这意味着无法访问 RStudio 当前 session 中的变量，创建的对象也不会出现在 Environment 面板。httpuv 基于 libuv 事件循环，与 R Console **共享同一个进程**，不阻塞主线程，变量在三者间实时同步。

> 详细架构文档：[r-session-ai/r-session-architecture.md](./r-session-ai/r-session-architecture.md)

#### ③ 跨语言数据交换（r2py）

```         
R Session                          Jupyter Kernel
    │                                    │
    │  export_data("df")                 │
    │  fwrite(df, "r2py/xxx.csv")        │
    └───────── CSV 文件 ────────────────>│  pd.read_csv("r2py/xxx.csv")
    │                                    │
    │  pd.to_csv("r2py/yyy.csv")         │
    │<──────── CSV 文件 ─────────────────┤  export_data("result")
    │  fread("r2py/yyy.csv")             │
    │                                    │
```

> 详细说明见下方「数据交换」章节。

------------------------------------------------------------------------

## 项目结构

```         
openclaw_with_jupyterlab_and_rstudio/
│
├── jupyter_mcp/                     # Python 侧：Jupyter MCP Server
│   ├── jupyter-mcp-server.py        #    MCP Server（ZMQ 直连 Jupyter Kernel）
│   ├── hook.py                      #    Kernel 注册函数（在 JupyterLab cell 中运行）
│   ├── setup.py                     #    pip install -e . 安装脚本
│   ├── jupyter-mcp-architecture.md  #    架构设计文档（本文核心参考）
│   └── README.md                    #    快速入门
│
├── r-session-ai/                    # R 侧：R Session API + MCP Server
│   ├── r-session-api.R              #    R API Server（httpuv，在 RStudio 中运行）
│   ├── r-session-mcp-server.py      #    MCP Server（HTTP 调用 R API）
│   ├── r-session-architecture.md    #    架构设计文档（本文核心参考）
│   └── README.md                    #    快速入门
│
├── labextensions/                   # JupyterLab 4.x 自定义扩展（编译后）
│   ├── jupyterlab-auto-reload/      #    Notebook 自动刷新（MCP 写入后 3s 刷新）
│   └── jupyterlab-console-adopt/    #    Console 外部 Session 回显(.py源码模式)
│
├── .gitignore
├── MEMORY.md                        # ⚠️ OpenClaw AI Agent 长期记忆样本
│                                    #   告诉 AI 如何驱动这套环境的操作指南
│                                    #   克隆后应替换为你自己的配置
├── openclaw.json                    # ⚠️ OpenClaw 用户示例配置文件
│                                    #   MCP Server / 工具注册配置
│                                    #   包括 jupyter-mcp、r-session 等连接参数
│                                    #   克隆后需按自己的环境修改
└── README.md                        # ← 你在这里
```

------------------------------------------------------------------------

## 组件详解

### 组件对照表

| 组件 | 语言 | 运行位置 | 通信方式 | 连接目标 | 操作对象 |
|------------|------------|------------|------------|------------|------------|
| **jupyter-mcp** | Python | graphrag conda | ZMQ (jupyter_client) | Jupyter Kernel | kernel 命名空间中的 Python 对象 |
| **r-session** | Python | graphrag conda | HTTP (httpx) → httpuv | R API → RStudio R Session | .GlobalEnv 中的 R 对象 |
| **R API** | R | RStudio 同进程 | httpuv (非阻塞 HTTP) | 当前 R Session | eval() → 直接操作环境 |
| **jupyterlab-auto-reload** | TypeScript | JupyterLab 前端 | Jupyter Contents API | Jupyter Server | .ipynb 文件 |
| **jupyterlab-console-adopt** | TypeScript | JupyterLab 前端 | kernel.iopubMessage | Jupyter Kernel | Console CodeCell |

### 工作模式

#### Python 侧（jupyter-mcp）

| 特性 | 说明 |
|------------------------------------|------------------------------------|
| 显示位置 | Notebook Cell / Console 窗口（由 hook 自动检测） |
| 代码执行 | 通过 ZMQ 发送到 kernel 执行 |
| 内省方式 | 在 kernel 中执行内省代码 + `__JUPYTER_MCP_JSON__` 标记协议 |
| 文件操作 | Notebook 模式：通过 REST API 写 .ipynb；Console 模式：不写 .py 源码文件 |
| 扩展依赖 | `jupyter-client`, `mcp`, `urllib`（Notebook 模式） |
| 启动方式 | 在 JupyterLab 中运行 `hook.register()` 后自动连接 |

#### R 侧（r-session）

| 特性         | 说明                                                  |
|--------------|-------------------------------------------------------|
| 显示位置     | RStudio Console + Environment 面板 + Plots 面板       |
| 代码执行     | eval(parse(text=code)) 在 .GlobalEnv 中执行           |
| Console 回显 | sink(split=TRUE) 实时回显到 Console                   |
| 安全认证     | Bearer Token（可选），多用户场景必须配置              |
| 依赖         | httpuv（R 端）、httpx + mcp（Python 端）              |
| 启动方式     | 在 RStudio Console 中运行 `source("r-session-api.R")` |

------------------------------------------------------------------------

## 数据交换（R ↔ Python）

### 架构

```         
R Session                    CSV 文件                    Jupyter Kernel
    │                           │                            │
    │  fwrite(df, path) ───────>│                            │
    │                           │  pd.read_csv(path) ───────>│
    │                           │                            │
    │  <─────── pd.read_csv()   │                            │
    │  fread(path) ─────────────│<─────── to_csv(path)       │
```

### 工具

| 方向 | MCP 工具 | 内部实现 |
|------------------------|------------------------|------------------------|
| R → Python | r-session.export_data → jupyter-mcp.import_data | `data.table::fwrite` → CSV → `pd.read_csv` |
| Python → R | jupyter-mcp.export_data → r-session.import_data | `pd.to_csv` → CSV → `data.table::fread` |

### 类型映射

**Python → R（无损 ✅）：**

| Python       | R               | CSV 中间格式 |
|--------------|-----------------|--------------|
| int64        | integer         | `1`          |
| float64      | numeric         | `10.5`       |
| object (str) | character       | `Alice`      |
| bool         | logical         | `TRUE`       |
| datetime64   | IDate / POSIXct | `2026-06-07` |

**R → Python（日期/时间需修复 ⚠️）：**

| R | CSV | Python | 修复 |
|------------------|------------------|------------------|------------------|
| integer/num/char/logical | 原生格式 | int64/float64/object/bool ✅ | 无需修复 |
| IDate / POSIXct | `2026-06-07` | object（字符串）❌ | `pd.to_datetime(df['col'])` |

### 共享目录

```         
默认:  ~/.openclaw/workspace/r2py/  （各用户工作区下，天然隔离）
覆盖:  R2PY_SHARED_DIR 环境变量
       R_SHARED_DIR（R 侧单独覆盖）
       JUPYTER_SHARED_DIR（Python 侧单独覆盖）
文件名: UUID 前缀 + .csv
```

------------------------------------------------------------------------

## 场景示例

| 场景               | Python (jupyter-mcp)    | R (r-session) |
|--------------------|-------------------------|---------------|
| 数据清洗、ETL      | ✅ pandas               |               |
| 统计分析、回归建模 |                         | ✅ lm, glm    |
| 可视化（交互式）   | ✅ plotly               | ✅ ggplot2    |
| 可视化（出版级）   |                         | ✅ ggplot2    |
| 机器学习（传统）   | ✅ sklearn              |               |
| 深度学习           | ✅ PyTorch / TensorFlow |               |
| 时间序列分析       |                         | ✅ forecast   |
| 报表生成           | ✅ nbconvert            | ✅ rmarkdown  |

------------------------------------------------------------------------

## 快速开始

### 前置要求

-   Python 3.11+（建议 Conda 或VENV环境，如 `graphrag`）
-   R 4.x + RStudio Server
-   Node.js 22+（JupyterLab 扩展构建用）
-   JupyterLab 4.x（建议 JupyterHub）

### 安装

``` bash
git clone https://github.com/icejean/openclaw_with_jupyterlab_and_rstudio.git
cd openclaw_with_jupyterlab_and_rstudio
```

各子目录有详细部署说明：

| 目录 | README | 说明 |
|------------------------|------------------------|------------------------|
| `jupyter_mcp/` | [README.md](./jupyter_mcp/README.md) | Jupyter MCP 安装与注册 |
| `r-session-ai/` | [README.md](./r-session-ai/README.md) | R API 启动与 MCP 配置 |

### 推荐使用方式

#### 1. OpenClaw 运行模式

推荐使用 `openclaw chat` **embedded agent 模式**（非网关/Plugin 模式），在 RStudio Server IDE 或 Jupyter Lab 内置的 **Terminal** 中直接启动：

``` bash
openclaw chat
```

这种方式下 OpenClaw 以内嵌进程运行，**不启动网关和 Plugin**，每个用户的工作空间天然完全隔离，无需管理端口和进程，非常适合多用户部署。

#### 2. 浏览器建议

**推荐使用 Firefox 浏览器。** Chrome 浏览器在 Terminal 中处理中文输入法存在已知问题——全角标点会连续触发两次输入，影响编码和命令行操作效率。

#### 3. R ↔ Python 数据交换范围

RStudio 和 Jupyter Lab 之间通过 CSV 文件交换数据时，仅适用于**小规模的中间数据集**。大数据集应留在原 session 中处理，避免 I/O 和类型转换开销。

---

### JupyterLab 扩展安装

本仓库包含两个预编译的 JupyterLab 4.x 扩展（位于 `labextensions/`），支持两种安装方式：

#### 全局安装（所有用户生效）

将扩展安装到 Jupyter 系统级 labextensions 目录，适合 JupyterHub 多用户环境：

``` bash
# 方式一：直接复制到系统目录（比如conda base环境）
sudo cp -r labextensions/jupyterlab-auto-reload /usr/lib64/anaconda3/share/jupyter/labextensions/
sudo cp -r labextensions/jupyterlab-console-adopt /usr/lib64/anaconda3/share/jupyter/labextensions/

# 方式二：通过 jupyter 命令安装（会自动处理 symlink）
jupyter labextension install labextensions/jupyterlab-auto-reload
jupyter labextension install labextensions/jupyterlab-console-adopt
```

#### 用户局部安装（仅当前用户生效）

适合单用户场景，无需 sudo：

``` bash
# 复制到用户本地扩展目录
cp -r labextensions/jupyterlab-auto-reload ~/.local/share/jupyter/labextensions/
cp -r labextensions/jupyterlab-console-adopt ~/.local/share/jupyter/labextensions/
```

#### 验证安装

``` bash
jupyter labextension list
# 应看到两个扩展均在列表中
```

安装完成后需重启 JupyterLab 才能生效。如果使用 JupyterHub，重启对应的 user server 即可。

### 参考教程

> 以下知乎专栏文章详细介绍了 OpenClaw 的安装、配置和使用，建议按顺序阅读。

| 主题 | 链接 |
|------------------------------------|------------------------------------|
| 🦞 小龙虾 OpenClaw 安全饲养教程 | [入门篇](https://zhuanlan.zhihu.com/p/2013144472117068259) |
| 🦞 小龙虾 OpenClaw 安全饲养教程之二：本机部署 | [部署篇](https://zhuanlan.zhihu.com/p/2020880761520227367) |
| 💬 OpenClaw 主流通讯渠道配置指南 | [飞书 / 微信 / 钉钉](https://zhuanlan.zhihu.com/p/2041198920395658076) |
| 🧪 JupyterHub + OpenClaw + Claude Code Vibe Coding | [Vibe Coding 实战](https://zhuanlan.zhihu.com/p/2026562226463482280) |
| 📊 Jupyter Lab + OpenClaw AI 辅助数据分析 | [数据分析实战](https://zhuanlan.zhihu.com/p/2045196634368242170) |
| 📈 RStudio + OpenClaw Vibe Coding & 数据分析 | [R 语言实战](https://zhuanlan.zhihu.com/p/2044067725241210044) |
| 🏗️ OpenClaw Ubuntu 24 多用户部署方案 | [基础架构](https://zhuanlan.zhihu.com/p/2046116340784697542) |
| 🏗️ OpenClaw Ubuntu 24 多用户部署方案生产级增强 | [生产级增强](https://zhuanlan.zhihu.com/p/2046909112571662596) |

------------------------------------------------------------------------

## 典型使用流程

1.  **启动环境：** 打开 JupyterLab 和 RStudio
2.  **注册 Python 端：** 在 Jupyter cell 中运行 `hook.register()`
3.  **启动 R API：** 在 RStudio Console 中 `source("r-session-ai/r-session-api.R")`
4.  **配置 OpenClaw：** 按自己的环境修改 `openclaw.json` 中的 MCP Server 参数
5.  配置MEMORY.md：按自己的环境修改MEMORY.md
6.  建议配置Claude Code，Claude可以接入国内LLM，适合配合OpenClaw使用
7.  **开始分析：** 在 OpenClaw 对话中发号施令

------------------------------------------------------------------------

## 依赖汇总

| 组件 | 所需包 | 安装命令 |
|----|----|----|
| **jupyter-mcp** (MCP Server) | `mcp`, `jupyter-client` | `pip install mcp jupyter-client` |
| **r-session-mcp** (MCP Server) | `mcp`, `httpx` | `pip install mcp httpx` |
| **R API Server** (R 端) | `httpuv`, `jsonlite` | `install.packages(c("httpuv", "jsonlite"))` |
| **数据交换** (R 端推荐) | `data.table` | `install.packages("data.table")` |
| **数据交换** (Python 端) | `pandas` | `pip install pandas` |

> `pip install` 在运行 MCP Server 的 Python 环境中执行（如 graphrag conda 环境），`install.packages` 在 R Console 中执行。

------------------------------------------------------------------------

## 环境变量参考

### jupyter-mcp MCP Server

| 变量 | 默认值 | 说明 |
|----|----|----|
| `JUPYTER_MCP_HOST` | `127.0.0.1` | MCP Server 监听地址（HTTP 模式用，stdio 模式无需监听） |
| `JUPYTER_MCP_PORT` | `0` | MCP Server 端口，`0` = stdio 模式（推荐） |
| `JUPYTER_MCP_TIMEOUT` | `120` | kernel 代码执行超时（秒） |
| `JUPYTER_MCP_REGISTER` | `~/.jupyter-mcp/current` | kernel 注册文件路径 |

### r-session MCP Server

| 变量 | 默认值 | 说明 |
|----|----|----|
| `R_API_HOST` | `127.0.0.1` | R API 地址 |
| `R_API_PORT` | `8161` | R API 端口 |
| `R_API_TOKEN` | 空 | R API 认证 Token（空=不启用） |
| `MCP_PORT` | `0` | MCP Server 端口，`0` = stdio 模式（推荐） |

### R API Server（r-session-api.R）

| 变量 / options | 默认值 | 说明 |
|----|----|----|
| `options(rsession_api_port = ...)` 或 `R_API_PORT` | `8161` | httpuv 监听端口 |
| `options(rsession_api_host = ...)` | `127.0.0.1` | 监听地址 |
| `options(rsession_api_max_rows = ...)` | `100` | 预览数据最大行数 |
| `options(rsession_api_max_str = ...)` | `20` | `str()` 截断层级 |
| `options(rsession_api_token = ...)` 或 `R_API_TOKEN` | 空 | Bearer Token（空=不启用认证） |

> R options 优先级高于环境变量。所有配置可在 `source("r-session-api.R")` 前通过 `options()` 设置。

### 共享目录

| 变量 | 默认值 | 说明 |
|----|----|----|
| `R2PY_SHARED_DIR` | `~/.openclaw/workspace/r2py/` | R↔Python 共享目录（总入口） |
| `R_SHARED_DIR` | 同 `R2PY_SHARED_DIR` | R 侧单独覆盖 |
| `JUPYTER_SHARED_DIR` | 同 `R2PY_SHARED_DIR` | Python 侧单独覆盖 |

------------------------------------------------------------------------

## 常见问题

### MCP Server 找不到 kernel

确保已在 Jupyter cell 中运行过 `hook.register()`，且文件 `~/.jupyter-mcp/current` 存在。如果 kernel 重启过，需重新注册：

``` python
from jupyter_mcp import hook
hook.register(force=True)
```

### R API 端口冲突

启动时提示端口被占用，说明之前的 R API 进程未正常退出：

``` r
# 方式一：停止指定 server
httpuv::stopServer(server)

# 方式二：停止所有 httpuv server（不影响 Console 操作）
httpuv::stopAllServers()

# 然后重新启动
source("r-session-ai/r-session-api.R")
```

### R session 执行 rm(list=ls()) 后 API 失效

`rm(list=ls())` 会清空 `.GlobalEnv`，而 R API 的辅助函数（`safe_eval`、`ok`、`err`、`server` 等）也存储在全局环境中。清空后 API 处理器丢失，需重新加载：

``` r
source("r-session-ai/r-session-api.R")
```

建议将需要保留的对象放在独立环境中，或避免在开发过程中使用 `rm(list=ls())`。

### 代理环境变量干扰

系统配置了全局代理（如 Clash 的 `ALL_PROXY=socks5://...`），可能导致：

- **r-session MCP Server** 启动时 `httpx.Client()` 初始化崩溃 —— MCP Server 已自动在启动时清理代理环境变量
- **jupyter-mcp** NotebookClient 通过 REST API 写 .ipynb 时走代理 —— 已自动临时屏蔽 `http_proxy`/`https_proxy`

如果手动调试遇到代理问题，可临时清除代理环境变量：

``` bash
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
```

### hook.register() 注册失败

检查 Jupyter cell 中是否在正确的 kernel 中运行。如果连接文件找不到，可以手动检查：

``` python
from jupyter_mcp import hook
hook.register(force=True)  # 加 force 参数覆盖已有的注册文件
```

------------------------------------------------------------------------

## License

MIT

------------------------------------------------------------------------

> *🐵 Jean出品 —— 让 Python 和 R 在 AI 驱动下高效协作*
