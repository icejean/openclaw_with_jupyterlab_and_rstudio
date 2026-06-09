#!/usr/lib64/anaconda3/envs/graphrag/bin/python3
"""
r-session-mcp-server.py — MCP Server for R Session API
======================================================

将 R Session API 包装为 MCP 协议的工具，供 OpenClaw / Claude Desktop 等调用。

使用方法：
  1. 在 RStudio Console 中 source("r-session-api.R")
  2. 运行本 MCP 服务器: python3 r-session-mcp-server.py
  3. 在 OpenClaw 中配置 MCP 连接（见 README.md）

环境变量：
  R_API_HOST   R API 地址（默认 127.0.0.1）
  R_API_PORT   R API 端口（默认 8161）
  MCP_PORT     MCP 服务器端口（默认 8100），0=stdio模式

依赖安装：
  pip install mcp httpx
"""

import os
import json
import sys
import httpx
import logging
from typing import Any

# ── 配置 ──────────────────────────────────────────────────────────────────

R_API_HOST = os.environ.get("R_API_HOST", "127.0.0.1")
R_API_PORT = int(os.environ.get("R_API_PORT", "8161"))
R_API_BASE = f"http://{R_API_HOST}:{R_API_PORT}"

logging.basicConfig(
    level=logging.INFO,
    format="[R-MCP] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# R API Token 认证（环境变量 R_API_TOKEN，为空则不启用）
R_API_TOKEN = os.environ.get("R_API_TOKEN", "")
if R_API_TOKEN:
    log.info("🔐 R API Token 认证已启用")
else:
    log.warning("⚠️  R API Token 未配置")
# R ↔ Python 数据交换目录（每个用户工作区下，自己管理）
# 默认: ~/.openclaw/workspace/r2py/
# 多用户时各用户目录天然隔离，互不可见
SHARED_DIR = os.environ.get("R2PY_SHARED_DIR", os.environ.get("R_SHARED_DIR", os.path.expanduser("~/.openclaw/workspace/r2py")))

# ── HTTP 客户端 ───────────────────────────────────────────────────────────

# 清理代理环境变量，避免 ALL_PROXY=socks5 导致 httpx Client 初始化崩溃
# httpx 的 Client 在初始化时解析代理配置，即使 NO_PROXY 包含 127.0.0.1 也不行
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("https_proxy", None)

_client_headers = {}
if R_API_TOKEN:
    _client_headers["Authorization"] = f"Bearer {R_API_TOKEN}"
_client = httpx.Client(base_url=R_API_BASE, timeout=30.0, headers=_client_headers)


def rpc_get(path: str) -> dict:
    """调用 R API GET 接口"""
    resp = _client.get(path)
    resp.raise_for_status()
    return resp.json()


def rpc_post(path: str, body: dict) -> dict:
    """调用 R API POST 接口"""
    resp = _client.post(path, json=body)
    resp.raise_for_status()
    return resp.json()


# ── MCP 服务器 ────────────────────────────────────────────────────────────

try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.sse import SseServerTransport
    from mcp.server import NotificationOptions
except ImportError:
    print("需要安装 mcp 包: pip install mcp httpx", file=sys.stderr)
    sys.exit(1)


server = Server("r-session-mcp")


def make_text(content: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=content)]


# ── 工具定义 ──────────────────────────────────────────────────────────────

TOOLS = [
    types.Tool(
        name="list_objects",
        description="列出 R session 中所有对象的名称、类、大小等信息",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="preview_data",
        description="预览 R 中数据框或矩阵的前 N 行、结构、摘要统计",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "R 环境中的对象名",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="get_object_info",
        description="获取 R 中任意对象的结构信息（str 输出）",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "R 环境中的对象名",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="run_code",
        description="在 R session 中执行 R 代码，返回输出和结果。可以修改当前 session 的变量！",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 R 代码，用分号或换行分隔多条语句",
                },
                "quiet": {
                    "type": "boolean",
                    "description": "是否静默执行（不在 Console 打印输出）",
                    "default": False,
                },
            },
            "required": ["code"],
        },
    ),
    types.Tool(
        name="get_loaded_packages",
        description="列出当前 R session 中已加载的所有包及版本号",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="health_check",
        description="检查 R session API 是否正常运行",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="export_data",
        description="从 R session 导出变量到 CSV 共享文件，供其他 session（如 Jupyter Python）使用",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "R session 中的变量名（应为 data.frame/matrix）",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="import_data",
        description="从 CSV 共享文件导入数据到 R session，例如 Jupyter Python session 导出的结果",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "CSV 文件路径",
                },
                "var_name": {
                    "type": "string",
                    "description": "R 中创建的变量名",
                },
            },
            "required": ["path", "var_name"],
        },
    ),
]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    if arguments is None:
        arguments = {}

    try:
        if name == "list_objects":
            data = rpc_get("/env")
            if not data.get("success"):
                return make_text(f"错误: {data.get('error', '未知错误')}")
            objs = data["data"]["objects"]
            lines = [
                f"📊 R 环境中共 {data['data']['count']} 个对象：",
                "─" * 60,
            ]
            for name, info in objs.items():
                cls = "/".join(info["class"][:3]) if isinstance(info["class"], list) else info["class"]
                size_kb = round(info["size"] / 1024, 1)
                dim_str = ""
                if info.get("dim"):
                    dim_str = f" [{info['dim'][0]}×{info['dim'][1]}]"
                elif info.get("length"):
                    dim_str = f" [{info['length']}]"
                lines.append(f"  {name:<20} {cls:<18} {size_kb:>6} KB{dim_str}")
            return make_text("\n".join(lines))

        elif name == "preview_data":
            obj_name = arguments["name"]
            data = rpc_get(f"/preview/{obj_name}")
            if not data.get("success"):
                return make_text(f"错误: {data.get('error', f'对象 {obj_name} 不存在')}")
            info = data["data"]

            lines = []
            lines.append(f"📋 对象: {info['name']}")
            lines.append(f"类型: {'/'.join(info['class'][:3]) if isinstance(info['class'], list) else info['class']}")
            lines.append(f"大小: {round(info['size'] / 1024, 1)} KB")
            lines.append("─" * 60)

            # str 输出
            lines.append("📐 结构:")
            for line in info.get("str", []):
                lines.append(f"  {line}")

            # 预览
            if "head" in info and info["head"] is not None:
                lines.append("\n👁️ 预览:")
                head = info["head"]
                if isinstance(head, list) and len(head) > 0:
                    # 转成类表格展示
                    import io
                    import pandas as pd  # type: ignore
                    df = pd.DataFrame(head)
                    buf = io.StringIO()
                    df.to_string(buf, max_rows=20)
                    for line in buf.getvalue().split("\n"):
                        lines.append(f"  {line}")
                else:
                    lines.append(f"  {json.dumps(head, ensure_ascii=False, default=str)}")

            # 摘要
            if "summary" in info:
                lines.append("\n📊 摘要统计:")
                for line in info["summary"]:
                    lines.append(f"  {line}")

            # 缺失值
            if info.get("na_count", 0) > 0:
                lines.append(f"\n⚠️ 缺失值: {info['na_count']} 个")
                for col, count in info.get("na_by_column", {}).items():
                    lines.append(f"  列 {col}: {count} 个 NA")

            return make_text("\n".join(lines))

        elif name == "get_object_info":
            obj_name = arguments["name"]
            data = rpc_get(f"/preview/{obj_name}")
            if not data.get("success"):
                return make_text(f"错误: {data.get('error', f'对象 {obj_name} 不存在')}")
            info = data["data"]

            lines = [
                f"📐 {info['name']} 的结构:",
                "─" * 40,
            ]
            for line in info.get("str", []):
                lines.append(f"  {line}")

            return make_text("\n".join(lines))

        elif name == "run_code":
            code = arguments["code"]
            quiet = arguments.get("quiet", False)
            endpoint = "/eval/quiet" if quiet else "/eval"
            data = rpc_post(endpoint, {"code": code})

            lines = []
            if data.get("success"):
                lines.append("✅ 执行成功")
            else:
                lines.append("❌ 执行出错")
                lines.append(f"错误: {data['data'].get('error', '未知错误')}")

            # 输出
            output = data["data"].get("output", [])
            if output and not quiet:
                truncated = False
                if len(output) > 200:
                    output = output[:200]
                    truncated = True
                lines.append("\n📝 输出:")
                for line in output:
                    lines.append(f"  {line}")
                if truncated:
                    lines.append("  ... (输出已截断)")

            # 新创建/修改的对象
            new_objs = data["data"].get("new_objs", [])
            if new_objs:
                lines.append(f"\n📦 新/变更对象: {', '.join(new_objs)}")

            # 返回值
            result = data["data"].get("result")
            if result is not None:
                result_str = data["data"].get("result_str")
                if result_str:
                    lines.append("\n🔙 返回值:")
                    for line in result_str:
                        lines.append(f"  {line}")
                else:
                    lines.append(f"\n🔙 返回值: {json.dumps(result, ensure_ascii=False, default=str)[:2000]}")

            return make_text("\n".join(lines))

        elif name == "get_loaded_packages":
            data = rpc_get("/packages")
            if not data.get("success"):
                return make_text(f"错误: {data.get('error', '未知错误')}")
            pkgs = data["data"]["packages"]
            lines = [
                f"📦 已加载 {data['data']['count']} 个包:",
                "─" * 40,
            ]
            for pkg, ver in sorted(pkgs.items()):
                lines.append(f"  {pkg:<25} v{ver}")
            return make_text("\n".join(lines))

        elif name == "health_check":
            data = rpc_get("/health")
            if not data.get("success"):
                return make_text(f"❌ R API 未响应: {data.get('error', '连接失败')}")
            info = data["data"]
            lines = [
                "✅ R Session API 运行正常",
                f"  R 版本: {info['r_version']}",
                f"  进程 PID: {info['pid']}",
                f"  监听地址: http://{info['host']}:{info['port']}",
            ]
            return make_text("\n".join(lines))

        elif name == "export_data":
            import uuid

            obj_name = arguments["name"]
            os.makedirs(SHARED_DIR, exist_ok=True)
            uid = str(uuid.uuid4())[:8]
            csv_path = f"{SHARED_DIR}/{uid}.csv"

            r_code = (
                f'data.table::fwrite({obj_name}, "{csv_path}", row.names=FALSE)\n'
            )
            resp = rpc_post("/eval", {"code": r_code})
            if not resp.get("success"):
                return make_text(f"❌ R 导出失败: {resp.get('error', '未知错误')}")

            return make_text(
                f"✅ 已从 R session 导出 `{obj_name}` → {csv_path}\n"
                f"  格式: CSV (data.table::fwrite)"
            )

        elif name == "import_data":
            path = arguments["path"]
            var_name = arguments["var_name"]

            if not os.path.exists(path):
                return make_text(f"❌ 文件不存在: {path}")

            r_code = (
                f'{var_name} <- data.table::fread("{path}")\n'
            )
            resp = rpc_post("/eval", {"code": r_code})
            if not resp.get("success"):
                return make_text(f"❌ R 导入失败: {resp.get('error', '未知错误')}")
            return make_text(
                f"✅ 已导入到 R session: `{var_name}`\n"
                f"  来源: {path}\n"
                f"  格式: CSV (data.table::fread)"
            )

        else:
            return make_text(f"未知工具: {name}")

    except httpx.ConnectError:
        return make_text(
            "❌ 无法连接到 R Session API\n"
            f"  请确认已在 RStudio Console 中运行:\n"
            f"    source(\"r-session-api.R\")\n"
            f"  API 地址: {R_API_BASE}"
        )
    except httpx.HTTPStatusError as e:
        return make_text(f"❌ R API 返回错误 ({e.response.status_code}): {e.response.text[:500]}")
    except Exception as e:
        return make_text(f"❌ 服务器错误: {str(e)}")


# ── 启动 ──────────────────────────────────────────────────────────────────

async def main_stdio():
    """使用 stdio 传输（供 OpenClaw/Claude Code 等 spawn）"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )


async def main_http(port: int):
    """使用 SSE/HTTP 传输（供远程连接）"""
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream,
                server.create_initialization_options(),
            )

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    import uvicorn
    log.info(f"MCP HTTP 服务器启动在 http://127.0.0.1:{port}/sse")
    await uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    import asyncio

    mcp_port = int(os.environ.get("MCP_PORT", "0"))

    if mcp_port > 0:
        asyncio.run(main_http(mcp_port))
    else:
        log.info("启动 stdio 模式 MCP 服务器...")
        asyncio.run(main_stdio())
