# jupyter-mcp — Jupyter Lab ⟷ OpenClaw 数据分析桥接

让 OpenClaw 直接连接你在 Jupyter Lab 里的 Python kernel，辅助你进行 Python 数据分析。

## 架构

```
┌─────────────────┐     MCP 协议 (stdio)    ┌────────────────────────┐
│   OpenClaw      │ ◄─────────────────────► │  jupyter-mcp-server.py │
│   (AI 助理)      │     子进程 stdin/stdout  │  (MCP Server, Python)  │
└─────────────────┘                          └───────────┬────────────┘
                                                          │ ZMQ (Jupyter 协议)
                                                          ▼
┌─────────────────────────────────────────────────────────┐
│              Jupyter Lab（你的 kernel session）            │
│  - 你正常在 Jupyter 里操作                                │
│  - OpenClaw 能读取/修改同一个 kernel 中的变量             │
│  - 你在 Jupyter 中看到的 DataFrame，OpenClaw 也能看到     │
└─────────────────────────────────────────────────────────┘
```

## 使用方法

### 1. 安装依赖

``` bash
# 在 graphrag conda 环境中（或你的 Python 环境）
pip install mcp jupyter-client
```

### 2. 注册当前 Kernel

在 Jupyter Lab 的任意 cell 中运行:

``` python
from jupyter_mcp import hook
hook.register()
```

你会看到类似输出:

```
✅ Jupyter kernel 已注册到 MCP 服务器
   连接文件: /home/openclaw/.local/share/jupyter/runtime/kernel-xxx.json
   Kernel:   python3
   Notebook: 绩效评分分析.py
   PID:      1234567
```

`~/.jupyter-mcp/current` 文件被写入，MCP 服务器靠它找到 kernel。

如果需要切换到另一个 kernel，就在那个 kernel 的 cell 里重新运行 `hook.register(force=True)`。

### 3. 在 OpenClaw 中配置 MCP Server（推荐：stdio 模式）

在 `openclaw.json` 的 `mcp.servers` 中添加：

```json
"jupyter-mcp": {
  "command": "/path/to/your/python3",
  "args": [
    "/path/to/jupyter_mcp/jupyter-mcp-server.py"
  ]
}
```

**示例（graphrag conda 环境）：**

```json
"jupyter-mcp": {
  "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
  "args": [
    "/home/ubuntu/.openclaw/workspace/jupyter_mcp/jupyter-mcp-server.py"
  ]
}
```

配置完成后重启 OpenClaw 即可自动拉起 MCP Server。

### 4. 使用

连接到 OpenClaw 后，你可以使用以下工具操作 Jupyter kernel:

| 工具 | 功能 |
|---|---|
| `run_code` | 在 kernel 中执行 Python 代码，修改变量 |
| `list_objects` | 列出 kernel 中所有变量及类型/大小 |
| `preview_data` | 预览变量详情（DataFrame 的 shape/dtypes/head/describe/缺失值） |
| `get_loaded_packages` | 列出已加载的包版本 |
| `export_data` | Python → R 数据导出 |
| `import_data` | R → Python 数据导入 |
| `health_check` | 检查连接状态 |

**.py + Console 模式专用：**

| 工具 | 功能 |
|---|---|
| `read_source` | 读取当前 .py 源码文件 |
| `write_source` | 覆盖写入 .py 源码文件 |
| `append_source` | 追加代码到 .py 源码文件末尾 |

### 5. 手动启动测试（调试用）

如需在终端中手动启动测试：

``` bash
cd /path/to/jupyter_mcp
python3 jupyter-mcp-server.py
```

服务器会自动读取 `~/.jupyter-mcp/current` 并连接到 kernel。测试完后按 Ctrl+C 停止。

## 为什么推荐 stdio 模式

| | **stdio 模式（推荐）** | HTTP / SSE 模式 |
|---|---|---|
| **通信方式** | OpenClaw 以子进程启动 MCP Server，通过 stdin/stdout 通信 | MCP Server 监听网络端口，通过 HTTP / SSE 通信 |
| **端口冲突** | 无。每个用户有独立的 OS 进程，不占用任何端口 | 有。多用户需分配不同端口，管理复杂 |
| **安全问题** | 无网络暴露，子进程天然隔离，用户间互不可见 | 端口开放即有潜在网络攻击面 |
| **多用户部署** | ✅ 天然支持。每个用户在 OpenClaw 中各自配置，完全隔离 | ❌ 需额外管理端口分配、防火墙、Token 认证 |
| **配置复杂度** | 低。只需配置 command + args | 高。需配端口、Token、防火墙 |
| **调试便利性** | 可在终端直接运行看日志 | 需同时关注进程和端口 |

**结论：** stdio 模式是多用户场景下唯一正确的选择。HTTP 模式仅适合单用户本地调试。

## 注意事项

- **只能连接一个 kernel。** 如果你有多个 Jupyter Lab Tab，保证只在你想要的 kernel 中运行 `hook.register()`
- **注册过的 kernel 如果重启了，** 需要重新运行 `hook.register()`
- MCP 服务器和 kernel 在同一台机器上即可（都是本地 127.0.0.1 连接）
- 如果 MCP Server 启动时提示找不到 kernel，检查 `~/.jupyter-mcp/current` 是否存在

## 和 r-session 的关系

两者可以共存。r-session 操作 R，jupyter-mcp 操作 Python kernel，互不干扰。OpenClaw 配置中同时定义两个 MCP Server 即可。
