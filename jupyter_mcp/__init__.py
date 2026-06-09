"""jupyter-mcp — Jupyter Lab ⟷ OpenClaw 数据分析桥接

使用方法：
  1. 在 Jupyter Lab 你想让 OpenClaw 操作的 cell 里运行:
     from jupyter_mcp import hook
     hook.register()

  2. 启动 MCP 服务器:
     python3 jupyter-mcp-server.py

  3. 在 OpenClaw 中配置 MCP 连接即可使用。

注意：R 语言版本的 r-session 同理，两者可共存。
"""

__version__ = "0.1.0"
