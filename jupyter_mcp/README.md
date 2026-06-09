# jupyter-mcp — Jupyter Lab ⟷ OpenClaw 数据分析桥接

让 OpenClaw 像操作 r-session 一样，直接连接你在 Jupyter Lab 里的 Python kernel，
辅助你进行 Python 数据分析。

## 架构

```
┌─────────────────┐     MCP协议      ┌────────────────────────┐
│   OpenClaw      │ ◄──────────────► │  jupyter-mcp-server.py │
│   (AI助理)       │                  │  (MCP Server, Python)  │
└─────────────────┘                  └───────────┬────────────┘
                                                 │ ZMQ (Jupyter 协议)
                                                 ▼
┌────────────────────────────────────────────────────────┐
│              Jupyter Lab (你的 kernel session)           │
│  - 你正常在 Jupyter 里操作                                │
│  - OpenClaw 能读取/修改同一个 kernel 中的变量               │
│  - 你在 Jupyter 中看到的 DataFrame，OpenClaw 也能看到       │
└────────────────────────────────────────────────────────┘
```

## 使用方法

### 1. 安装依赖

```bash
# 在 graphrag conda 环境中（或你的 Python 环境）
pip install mcp httpx jupyter-client
```

### 2. 注册当前 Kernel

在 Jupyter Lab 的任意 cell 中运行:

```python
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

### 3. 启动 MCP 服务器

```bash
cd /home/openclaw/.openclaw/workspace/jupyter-mcp
python3 jupyter-mcp-server.py
```

服务器会自动读取 `~/.jupyter-mcp/current` 并连接到 kernel。

### 4. 在 OpenClaw 中配置 MCP

在 OpenClaw 配置中添加 MCP Server 条目（类似于 r-session 的配置方式），
指向 jupyter-mcp-server.py 的启动命令。

### 5. 使用

连接到 OpenClaw 后，你可以使用以下工具操作 Jupyter kernel:

| 工具 | 功能 |
|---|---|
| `run_code` | 在 kernel 中执行 Python 代码，修改变量 |
| `list_objects` | 列出 kernel 中所有变量及类型/大小 |
| `preview_data` | 预览变量详情（DataFrame 的 shape/dtypes/head/describe/缺失值） |
| `get_loaded_packages` | 列出已加载的包版本 |
| `health_check` | 检查连接状态 |

## 注意事项

- **只能连接一个 kernel**。如果你有多个 Jupyter Lab Tab，确保只在你想要的 kernel 中运行 `hook.register()`
- **注册过的 kernel 如果重启了**，需要重新运行 `hook.register()`
- MCP 服务器和 kernel 在同一台机器上即可（都是本地 127.0.0.1 连接）

## 和 r-session 的关系

两者可以共存。r-session 操作 R，jupyter-mcp 操作 Python kernel，互不干扰。
OpenClaw 配置中同时定义两个 MCP Server 即可。
