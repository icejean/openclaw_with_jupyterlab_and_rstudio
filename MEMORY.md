# MEMORY.md - 长期记忆

## 工具使用

### 搜索引擎选择
- **国内/中文搜索** → 使用 `baidu-search` 技能
- **国际/英文搜索** → 使用 `web_search`（Brave）

baidu-search 已配置在 `~/.openclaw/workspace/skills/`，需确保 `skills.load.extraDirs` 包含该路径，并在 `skills.entries.baidu-search.env` 中配置 `BAIDU_API_KEY`。

### 嵌入式模式限制
- **当前运行模式**：Embedded Agent（嵌入式/本地模式），无 gateway 和 plugin 支持
- **影响工具**：`web_search`（Brave Search）等依赖 plugin provider 的工具不可用
- **国际搜索替代路径**：
  - **直接调 Brave Search API**（最稳定，无需 gateway）：
    ```bash
    # Web 搜索
    curl -s --compressed "https://api.search.brave.com/res/v1/web/search?q=<query>&count=10" \
      -H "X-Subscription-Token: <API_KEY>"

    # News 搜索
    curl -s --compressed "https://api.search.brave.com/res/v1/news/search?q=<query>&count=10&freshness=week" \
      -H "X-Subscription-Token: <API_KEY>"
    ```
  - API Key 在 `~/.openclaw/openclaw.json` 的 `plugins.entries.brave.config.webSearch.apiKey` 中


### 浏览器自动化
- **运行环境**：云服务器部署的OpenClaw
- **推荐工具**：使用 `agent-browser` 技能进行浏览器自动化操作
- **关键参数**：必须添加 `--no-sandbox` 参数，因为云服务器环境需要禁用沙箱
- **基础命令示例**：
  ```bash
  agent-browser open <URL> --args "--no-sandbox"
  agent-browser snapshot -i
  agent-browser click @e1
  ```

## 邮件处理守则

### 核心规则
- **删除邮件**：必须经人工确认后方可执行
- **往外发送邮件**：必须经人工确认后方可执行

### 执行流程
1. 接收到邮件删除或发送请求时，先向用户确认操作内容
2. 得到明确同意后，再执行相应操作
3. 操作完成后，向用户反馈执行结果

## 代码生成偏好
- 优先使用 **Claude Code** 生成代码（包括算法实现、全栈开发、脚本编写等）
- 默认编程语言：Python
- Python程序默认运行环境：Conda虚拟环境 `graphrag`
- Claude Code配置文件位置：`~/.claude/settings.json`
- **嵌入式模式下调用方式**（无 gateway/plugin，不走 skill，直接 CLI）：

  ```bash
  # 最简单的非交互式调用
  echo '<prompt>' | claude --print --model deepseek-v4-pro

  # 允许写文件 + 读文件
  echo '<prompt>' | claude --print --model deepseek-v4-pro --allowedTools "Write,Bash,Read"

  # 沙箱环境（无网络，完全跳过权限确认）
  echo '<prompt>' | claude --print --model deepseek-v4-pro --dangerously-skip-permissions
  ```


## 🏗️ 整体解决方案定位

### Fast-Python-AI，平替 Posit AI

**方案组成：**
| 组件 | 用途 |
|---|---|
| **OpenClaw** | AI 代理框架，连接用户 ↔ 工具 ↔ LLM |
| **Claude Code / Vibe Coding** | AI 辅助编码阶段 |
| **R 语言 / RStudio (r-session)** | 数据分析（R 语言） |
| **Python / Jupyter Lab (jupyter-mcp)** | 数据分析（Python 语言） |

**核心优势：**
- 🏠 **数据不出服务器不出境**，内网可配合一体机部署
- 🇨🇳 **国内信创环境已验证**：麒麟 V10 + 鲲鹏 CPU ARM aarch64 + 一体机满血版国产 LLM
- 🔄 **LLM 可按需切换**（DeepSeek / GLM / MiniMax / Kimi / 国产满血版等）
- 🪶 轻量级浏览器界面，易用易部署易维护
- 🔓 完全开源免费
- 📊 AI 不仅应用于**编码阶段**，还应用于**数据分析阶段**，深入了一个维度

---

## 🎯 场景判断：什么时候用 jupyter-mcp

| 场景 | 用什么 | 原因 |
|---|---|---|
| **Jupyter Lab 交互式数据分析**（探索数据、画图、建模） | `jupyter-mcp` | 代码在 kernel 中执行，结果实时显示在 Notebook/Console |
| **写 Python 脚本完成某个任务**（爬虫、处理文件、自动化等） | 直接 exec / 命令行执行 | jupyter-mcp 是交互式分析工具，不是通用 Python 执行器 |

**核心原则：** `jupyter-mcp` 只用于 Jupyter Lab 中的交互式数据分析。不要用它执行通用 Python 任务。

---

## Python 交互式数据分析 (Jupyter MCP)

### 架构
```
AI 模型 ⇄ OpenClaw ⇄ MCP (jupyter-mcp) ⇄ ZMQ (jupyter_client) ⇄ Jupyter Lab Kernel
```
- 代码：`~/workspace/jupyter_mcp/`
- Server：`~/workspace/jupyter_mcp/jupyter-mcp-server.py`
- 注册文件：`~/.jupyter-mcp/current`

### 通用工具（两种模式共用）
| 工具 | 功能 |
|---|---|
| `list_objects` | 列出 kernel 中所有变量 |
| `preview_data` | 预览变量详情 |
| `get_loaded_packages` | 列出已加载的包 |
| `health_check` | 检查连接状态 |

### 使用步骤
1. 在 Jupyter Lab 中运行 `from jupyter_mcp import hook; hook.register()`
2. MCP Server 自动连接 kernel
3. 使用 `run_code` 执行分析代码
4. 结果自动显示在 Notebook 或 Console（取决于模式）

---

### 📓 Notebook 模式（.ipynb）

**场景：** JupyterLab 中打开 .ipynb 文件做交互式分析

**启动：** 在 Notebook cell 中运行 `hook.register()`（自动检测为 notebook 模式）

**工作流程：**
1. `run_code` 执行代码 → 自动插入新 Cell 到 .ipynb 文件
2. `jupyterlab-auto-reload` 扩展在 3 秒内自动刷新 Notebook 显示
3. 结果写回 Cell 中，包含执行序号和输出

**可用工具：** `run_code`（自动插 Cell + 写回结果）

**注意：** JupyterHub-singleuser 跑在 base conda 环境（`/usr/lib64/anaconda3/bin/jupyterhub-singleuser`），扩展需安装到 **base 环境的全局路径** `/usr/lib64/anaconda3/share/jupyter/labextensions/`，而非 graphrag 环境（`.../envs/graphrag/share/jupyter/labextensions/`）
  - `jupyterlab-console-adopt` 自定义扩展已安装到此路径 ✅
  - `jupyterlab-auto-reload` 也在这里有一份副本，确保 JupyterHub 能加载

---

### 🐍 .py + Console 模式

**场景：** JupyterLab 中打开 .py 文件 + "Create Console for Editor" 做交互式分析

**启动：** 在 .py 文件或 Console 中运行 `hook.register()`（自动检测为 console 模式）

**工作流程：**
1. `run_code` 执行代码 → **不修改 .py 文件**
2. `jupyterlab-console-adopt` 扩展自动捕获 kernel IOPub 消息
3. 在 Console 中创建 CodeCell 显示源码 + 输出（执行序号 `[1]`、`[2]`...）
4. 代码**不重复执行**，仅捕获已有的执行结果

**原理：** Console 只显示自身 session 的输出（JupyterLab issue #9936）。console-adopt 监听 kernel.iopubMessage（所有 session 的消息），检测外部 execute_input → 创建 CodeCell + 伪 future 捕获后续消息。

**MCP 工具的 Console 可见性：** `export_data` / `import_data` 内部通过 kernel `execute_request` 执行代码，会触发 `execute_input` 消息，因此 `console-adopt` 也能捕获并生成 Console CodeCell（各 1 个）。`run_code` 同理。所有经 kernel 执行的代码，在 `.py + Console` 模式下均可见。

**可用工具：**
| 工具 | 功能 |
|---|---|
| `run_code` | 执行代码（不写回 .py） |
| `read_source` | 读取 .py 源码内容 |
| `write_source` | 写入/覆盖 .py 源码文件 |
| `append_source` | 追加代码到 .py 源码末尾 |

### ⚠️ Python 作图：中文字体配置

**系统可用字体清单（`fc-list :lang=zh`）：**
| 字体文件 | 字体名 | 适用性 |
|---|---|---|
| `SimHei` 黑体 | `SimHei` | ✅ 最佳，ASCII+CJK 完整字符集 |
| `FangSong` 仿宋 | `FangSong` | ✅ 完整字符集 |
| `SimSun` 宋体 | `SimSun` | ✅ 完整字符集 |
| `KaiTi` 楷体 | `KaiTi` | ✅ 完整字符集 |
| `Droid Sans Fallback` | `Droid Sans Fallback` | ❌ 仅 CJK，无 ASCII 字形 |
| `WenQuanYi Micro Hei` | - | ❌ 未安装 |

**在 Jupyter kernel 中作图的正确姿势：**

每次使用 `run_code` 执行 matplotlib 绘图前，必须先设定中文字体，否则中文显示为方框。

```python
# ✅ 标准初始化——放在所有 plot 代码最前面
import matplotlib
matplotlib.rcdefaults()
matplotlib.rcParams['font.sans-serif'] = ['SimHei']     # 黑体，ASCII+CJK 均有
matplotlib.rcParams['axes.unicode_minus'] = False       # 解决负号显示问题
```

> **不要用** `matplotlib.rcParams['font.family'] = 'Droid Sans Fallback'` 或 `FontProperties` 逐个设置——前者因 Droid Sans Fallback 缺失 ASCII 字形会产生大量 `Glyph missing` 警告，后者每个文本元素都要传参太麻烦。`rcParams['font.sans-serif']` 用 `SimHei` 一次性搞定所有中英文混排。

---

### 与 r-session 对比
- `jupyter-mcp`：Python 交互式数据分析，连接 Jupyter kernel，Cell/Console 可见
- `r-session`：R 语言分析，连接 RStudio session，Console 可见
- Jupyter kernel 原生支持 ZMQ 协议，不需要在 kernel 内额外起 HTTP server

## R 语言数据分析

### 通过 MCP Server "r-session" 操作当前 RSession

- R 语言数据分析任务全部通过 MCP Server `r-session` 完成
- 架构：AI 模型 ⇄ OpenClaw ⇄ MCP (r-session) ⇄ R API (httpuv) ⇄ RStudio R Session
- R API 运行在 `http://127.0.0.1:<port>`，通过 `POST /eval` 执行 R 代码
- 端口由 `openclaw.json` 中 `mcp.servers.r-session.env.R_API_PORT` 配置（本机实际 8226）
- MCP Server 位置：`~/r-session-ai/r-session-mcp-server.py`
- R API 脚本位置：`~/r-session-ai/r-session-api.R`

### 使用方式
- 先确认 R API 是否运行：`curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:<port>/health`
- 如果未运行，让用户在 RStudio Console 中执行：
  ```r
  options(rsession_api_port = 用户的端口)
  options(rsession_api_token = "<你的Token>")
  source("r-session-ai/r-session-api.R")
  ```
- 重新加载前先停旧的：`httpuv::stopServer(server)`
- 通过 `curl -X POST http://127.0.0.1:<port>/eval -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"code":"..."}'` 执行 R 代码
- 代码结果和变量直接写入 RStudio 的 RSession，图和输出显示在 RStudio IDE 中

### 可见模式（Console 回显）
- **目标**：让用户在 RStudio Console 中看到执行的源码和输出
- **方法**：先把 R 代码写入 `.R` 文件（放在 workspace 的 `R/` 子目录），然后用 `source("R/xxx.R", echo = TRUE)` 执行
- R 相关的所有 .R 文件、中间数据文件等均放入 `R/` 子目录管理
- R API 中 `safe_eval()` 的 `console_echo` 参数控制是否回显到 Console
- 绘图用 `source(echo = TRUE)` 也能正常渲染到 RStudio Plots 面板

### 关键端点
| 端点 | 用途 |
|---|---|
| `GET /health` | 健康检查 |
| `GET /env` | 列出 R 环境中的对象 |
| `GET /preview/{name}` | 预览某个对象 |
| `POST /eval` | 执行 R 代码，可修改 session |
| `POST /eval/quiet` | 静默执行 R 代码 |
| `GET /packages` | 列出已加载的包 |

### ⚠️ 注意事项：`rm(list=ls())` 会清掉 API 函数
R API 的辅助函数（`safe_eval`、`ok`、`err`、`server` 等）存储在 `.GlobalEnv` 中。如果用户在 RStudio Console 中执行 `rm(list=ls())`，API 处理器会被一并清除，需重新 `source("r-session-ai/r-session-api.R")` 恢复。

### 多用户验证（2026.6.6）

**结果：方案表现完美 ✅**

- 每个用户的 RSession 是独立 OS 进程，httpuv 各自绑定不同端口，互不干扰
- `httpuv::stopServer(server)` 有效但无声，`stopAllServers()` 也支持
- `httpuv::stopAllServers()` 在另一个 R Session 中调用不会影响当前 R Session
- 适合多用户并行使用，隔离性可靠

### 安全加固：R API Token 认证（2026.6.7）

**背景：** 多用户场景下，R API 绑定 127.0.0.1 但所有本地用户可访问。恶意用户可扫描端口后
`curl http://127.0.0.1:<port>/eval` 执行任意 R 代码，劫持其他用户的 R session。

**方案：** R API + MCP Server 增加 Bearer Token 认证

```
┌─ openclaw.json ─────────────────────┐
│ "r-session": {                       │
│   "env": {                           │
│     "R_API_TOKEN": "<secret>"       │
│   }                                   │
│ }                                     │
└──────────────────────────────────────┘
     │ 传递给 MCP Server
     ▼
┌─ r-session-mcp-server.py ──────────┐
│ _client_headers["Authorization"]   │
│     = f"Bearer {R_API_TOKEN}"       │
│ → 所有请求自带 Bearer Token         │
└──────────────────────────────────────┘
     │ HTTP 请求
     ▼
┌─ r-session-api.R ─────────────────┐
│ API_TOKEN <- Sys.getenv(...)       │
│ 每个请求验证 Authorization header  │
│ 不匹配 → 401 unauthorized          │
└──────────────────────────────────────┘
```

**API Token 为空时不启用认证**（向后兼容，适合纯单用户场景）。

**多用户部署时每个用户的 Token 应不同：**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
# 输出示例: 9SSdk_n25O0jbmOf0C_5Rq3iU9Ca-oyH
```

**健康检查（带 Token）：**
```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:<port>/health
```

**MCP Server 自动读取 `R_API_TOKEN` 环境变量，在 `openclaw.json` 的 `mcp.servers.r-session.env` 中配置即可。**

### 启动依赖
- shebang 已改为 `graphrag` conda env 的 Python（`/usr/lib64/anaconda3/envs/graphrag/bin/python3`）
- 两个 MCP Server 使用相同 Python 环境

---

## R ↔ Python 双向数据交换 (2026.6.7 最终版)

两个 MCP Server（r-session + jupyter-mcp）各有一对 `export_data` / `import_data` 工具，通过 CSV 文件实现 R Session 和 Jupyter Kernel 之间的数据交换。

### 设计理念
- 跨 session 传的**只限小数据集**，大数据集在该 session 原地处理
- **只用 CSV** — R 和 Python 都原生支持，方案最简单通用
- CSV 类型可能失真，但小数据集一两个 `as.integer()` / `astype()` 就修好了
- 核心原则：**简单通用，偶尔手动修正**

### 架构
```
R Session → R API (httpuv) → r-session-mcp (Python) → CSV
                                                         ↓
Jupyter Kernel ← jupyter-mcp (Python) ← CSV
```

### 工具（固定 CSV格式）

**r-session-mcp：**
| 工具 | 内部实现 |
|---|---|
| `export_data(name)` | R 侧 `data.table::fwrite()` 写 CSV |
| `import_data(path, var_name)` | R 侧 `data.table::fread()` 读 CSV |

**jupyter-mcp：**
| 工具 | 内部实现 |
|---|---|
| `export_data(name)` | Python 侧 `pandas.to_csv()` 写 CSV |
| `import_data(path, var_name)` | Python 侧 `pandas.read_csv()` 读 CSV |

### 类型保真实测结果

**Python → R（`fread`）— 所有类型无损 ✅**
| Python | R | CSV 中间格式 |
|---|---|---|
| int64 | integer | `1` |
| float64 | numeric | `10.5` |
| object (str) | character | `Alice` |
| bool | logical | `True` / `False` |
| datetime64 (日期) | IDate/Date | `2026-06-07` |
| datetime64 (时间) | POSIXct | `2026-06-07 10:30:00` |

**R → Python（`read_csv`）— 日期/时间丢字符串 ❌**
| R | Python | 处理 |
|---|---|---|
| integer/num/char/logical | int64/float64/object/bool | 自动认 ✅ |
| Date / POSIXct | object (string) | `pd.to_datetime(df['col'])` 修复 |

### 共享目录
- **默认位置：** `~/.openclaw/workspace/r2py/`（各用户工作区下，天然隔离）
- **环境变量覆盖：** 设置 `R2PY_SHARED_DIR`（统一）或 `R_SHARED_DIR` / `JUPYTER_SHARED_DIR`（分别覆盖）
- **文件名：** UUID 前缀 + `.csv`

### 使用流程

数据交换有两种方式，选哪种取决于你**是否需要在 Notebook 中看到导出/导入的 Cell**：

| 方式 | .py + Console | Notebook | R Console |
|---|---|---|---|
| **MCP 工具**（`export_data` / `import_data`） | ✅ Console 可见 | ❌ 无 Cell | ✅ Console 可见 |
| **标准代码**（`pd.read_csv` / `fwrite` 等） | ✅ Console 可见 | ✅ 有 Cell | ✅ Console 可见 |

#### 方式一：MCP 工具（快速手递手）
适合不在意 Notebook Cell 显示的场景（调试、后台、.py + Console 模式）。工具自动生成 UUID 文件名。

```
# R → Python
r-session-mcp.export_data(name="df")
jupyter-mcp.import_data(path="...", var_name="df")
df['date'] = pd.to_datetime(df['date'])  # 日期修复

# Python → R
jupyter-mcp.export_data(name="result")
r-session-mcp.import_data(path="...", var_name="result")  # 全类型无损
```

#### 方式二：标准代码（Notebook Cell / Console 双可见）
适合需要在 Notebook 留痕的场景。两边都用原生读写函数，通过 `run_code` / `source(echo=TRUE)` 执行。

```
# ── R 端（写入 R/ 脚本，source(echo=TRUE) 执行）──
# 导出到 CSV 给 Python
fwrite(df, "r2py/df_from_r.csv")
# 从 Python 导入 CSV
result <- fread("r2py/result_from_py.csv")

# ── Python 端（run_code 执行，Notebook 插 Cell / Console 可见）──
# 从 R 导入
summary = pd.read_csv("r2py/summary_r.csv")
# 导出给 R
sales.to_csv("r2py/sales_export.csv", index=False)
```

| 步骤 | R 端（Console 可见） | Python Notebook 端（Cell 可见） | Python .py + Console 端（Console 可见） |
|---|---|---|---|
| 执行分析代码 | `source("R/xxx.R", echo=TRUE)` | `run_code(...)` → 插 Cell | `run_code(...)` → console-adopt 显示 |
| **导出数据** | `fwrite()` 写在 `.R` 脚本中 | `df.to_csv()` 写在 `run_code` 里 | `df.to_csv()` 写在 `run_code` 里 |
| **导入数据** | `fread()` 写在 `.R` 脚本中 | `pd.read_csv()` 写在 `run_code` 里 | `pd.read_csv()` 写在 `run_code` 里 |

> **关于 MCP 工具的 Console 可见性（2026-06-07 优化后）：**
> `export_data` / `import_data` 内部通过 kernel `execute_request` 执行代码，会触发 `execute_input` 消息。
> - `.py + Console` 模式：`console-adopt` 捕获后生成 Console CodeCell，**各 1 个**（已合并多余验证步骤）
> - Notebook 模式：MCP 工具操作不写入 .ipynb 文件，**不会产生 Cell**
>
> 需要 Notebook Cell 可见的导出/导入，用方式二（标准代码 + `run_code`）。

### MCP 配置
在 `~/.openclaw/openclaw.json` 的 `mcp.servers` 中：
- r-session：已配 env `R_API_HOST=127.0.0.1`, `R_API_PORT=8226`, `R_API_TOKEN`（端口由 `.env.R_API_PORT` 设定，各用户不同）
- jupyter-mcp：已配（无额外 env 需要）
- 多用户时需注意：
  - 每人**端口不同**（避免端口冲突），通过 `openclaw.json` 中 `mcp.servers.r-session.env.R_API_PORT` 配置
  - 每人**Token 不同**（确保安全隔离）
  - R API Token 优先级：`options(rsession_api_token=...)` > 环境变量 `R_API_TOKEN` > 空（不启用）
- 多用户时只需为每个用户设不同的 `R2PY_SHARED_DIR` 即可隔离

