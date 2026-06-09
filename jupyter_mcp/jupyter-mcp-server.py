#!/usr/lib64/anaconda3/envs/graphrag/bin/python3
"""
jupyter-mcp-server.py — MCP Server for Jupyter Kernel
======================================================

将 Jupyter Lab 的 Python kernel 包装为 MCP 协议的工具，供 OpenClaw 调用。

使用方法：
  1. 在 Jupyter Lab 中运行 hook.register() 注册当前 kernel
  2. 启动本 MCP 服务器: python3 jupyter-mcp-server.py
  3. 在 OpenClaw 中配置 MCP 连接

环境变量:
  JUPYTER_MCP_HOST     MCP 服务器监听地址（默认 127.0.0.1）
  JUPYTER_MCP_PORT     MCP 服务器端口（默认 0，0=stdio 模式）
  JUPYTER_MCP_TIMEOUT  kernel 代码执行超时秒数（默认 120）
  JUPYTER_MCP_REGISTER 注册文件路径（默认 ~/.jupyter-mcp/current）

依赖安装:
  pip install mcp httpx jupyter-client
"""

import os
import sys
import json
import time
import logging
import tempfile
import traceback
import asyncio
from typing import Any

# ── 配置 ──────────────────────────────────────────────────────────────────

REGISTER_FILE = os.environ.get(
    "JUPYTER_MCP_REGISTER",
    os.path.expanduser("~/.jupyter-mcp/current"),
)
EXEC_TIMEOUT = int(os.environ.get("JUPYTER_MCP_TIMEOUT", "120"))
# R ↔ Python 数据交换目录（每个用户工作区下，自己管理）
# 默认: ~/.openclaw/workspace/r2py/
# 多用户时各用户目录天然隔离，互不可见
SHARED_DIR = os.environ.get("R2PY_SHARED_DIR", os.environ.get("JUPYTER_SHARED_DIR", os.path.expanduser("~/.openclaw/workspace/r2py")))

logging.basicConfig(
    level=logging.INFO,
    format="[Jupyter-MCP] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# ── Jupyter Kernel 连接管理 ────────────────────────────────────────────────


class JupyterKernel:
    """连接到 Jupyter kernel 并执行代码"""

    def __init__(self, conn_file: str):
        self.conn_file = conn_file
        self.kc = None
        self._connected = False

    def connect(self) -> str | None:
        """连接到 kernel。返回错误信息或 None"""
        try:
            import jupyter_client

            # 加载连接文件
            with open(self.conn_file) as f:
                conn_info = json.load(f)

            self.kc = jupyter_client.BlockingKernelClient()
            self.kc.load_connection_file(self.conn_file)

            # 启动 channels
            self.kc.start_channels()

            # 等待心跳确认连接
            deadline = time.time() + 10
            while time.time() < deadline:
                if self.kc.is_alive():
                    self._connected = True
                    log.info(f"已连接到 kernel: {conn_info.get('kernel_name', 'python3')}")
                    log.info(f"  连接文件: {self.conn_file}")
                    return None
                time.sleep(0.1)

            return "kernel 心跳超时，无法建立连接"

        except ImportError:
            return "缺少依赖: pip install jupyter-client"
        except FileNotFoundError:
            return f"kernel 连接文件不存在: {self.conn_file}"
        except Exception as e:
            return f"连接 kernel 失败: {e}"

    def execute(self, code: str, timeout: int = EXEC_TIMEOUT) -> dict:
        """在 kernel 中执行代码并返回结果"""
        if not self._connected or not self.kc:
            return {"success": False, "error": "未连接到 kernel"}

        msg_id = self.kc.execute(code)
        return self._collect_output(msg_id, timeout)

    def _collect_output(self, msg_id: str, timeout: int) -> dict:
        """收集 kernel 执行结果"""
        result = {
            "success": True,
            "output": [],
            "error": None,
            "execute_result": None,
            "display_data": [],
            "execution_count": None,
        }

        timeout_time = time.time() + timeout
        shell_done = False

        while time.time() < timeout_time:
            # 检查 Shell 通道的 execute_reply
            if not shell_done:
                try:
                    shell_msg = self.kc.get_shell_msg(timeout=0.01)
                    if shell_msg.get("parent_header", {}).get("msg_id") == msg_id:
                        content = shell_msg.get("content", {})
                        result["execution_count"] = content.get("execution_count")
                        shell_done = True
                except Exception:
                    pass

            # IOPub 通道的消息
            try:
                msg = self.kc.get_iopub_msg(timeout=0.5)
            except Exception:
                # 如果 shell 已完成且 IOPub 已空闲，可以跳出
                if shell_done:
                    break
                continue

            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue

            msg_type = msg.get("msg_type", "")
            content = msg.get("content", {})

            if msg_type == "stream":
                text = content.get("text", "")
                name = content.get("name", "stdout")
                result["output"].append({"name": name, "text": text})

            elif msg_type == "execute_input":
                result["execution_count"] = content.get("execution_count")

            elif msg_type == "execute_result":
                data = content.get("data", {})
                text = data.get("text/plain", "")
                result["execute_result"] = text
                if "image/png" in data:
                    result["display_data"].append({
                        "type": "image/png",
                        "data": data["image/png"],
                    })

            elif msg_type == "display_data":
                data = content.get("data", {})
                text = data.get("text/plain", "")
                result["display_data"].append({
                    "type": "text/plain",
                    "data": text,
                })
                if "image/png" in data:
                    result["display_data"].append({
                        "type": "image/png",
                        "data": data["image/png"],
                    })

            elif msg_type == "error":
                result["success"] = False
                result["error"] = {
                    "ename": content.get("ename", ""),
                    "evalue": content.get("evalue", ""),
                    "traceback": content.get("traceback", []),
                }

            elif msg_type == "status":
                execution_state = content.get("execution_state", "")
                if execution_state == "idle" and shell_done:
                    break

        else:
            result["success"] = False
            result["error"] = {"ename": "TimeoutError", "evalue": f"执行超时 ({timeout}s)"}

        return result

    def list_objects(self) -> dict:
        """列出 kernel 中的变量"""
        code = """
import sys, types, builtins

def _inspect_objects():
    _skip_types = (types.ModuleType, types.FunctionType, types.BuiltinFunctionType,
                   types.BuiltinMethodType, type)
    _ns = dict(globals())

    objs = {}
    for name, obj in _ns.items():
        if name.startswith('_'):
            continue

        # 跳过模块、函数等
        if isinstance(obj, _skip_types):
            continue

        info = {
            'type': type(obj).__name__,
            'size': _try_get_size(obj),
        }

        # DataFrame / Series 特殊处理
        _modname = type(obj).__module__
        if 'pandas' in _modname:
            if hasattr(obj, 'shape'):
                info['shape'] = list(obj.shape)
            if hasattr(obj, 'dtypes') and hasattr(obj.dtypes, 'items'):
                info['dtypes'] = {str(k): str(v) for k, v in obj.dtypes.items()}
            info['pandas'] = True

        # numpy array
        elif 'numpy' in _modname:
            if hasattr(obj, 'shape'):
                info['shape'] = list(obj.shape)
            if hasattr(obj, 'dtype'):
                info['dtype'] = str(obj.dtype)

        # list / dict / tuple
        elif hasattr(obj, '__len__'):
            try:
                info['length'] = len(obj)
            except (TypeError, OverflowError):
                pass

        objs[name] = info

    return objs

def _try_get_size(obj):
    try:
        return sys.getsizeof(obj)
    except (TypeError, RecursionError):
        return 0

import json
print('__JUPYTER_MCP_JSON__')
print(json.dumps(_inspect_objects(), default=str, ensure_ascii=False))
"""
        result = self.execute(code)
        if result["success"]:
            for out in result.get("output", []):
                lines = out.get("text", "").strip().split("\n")
                for i, line in enumerate(lines):
                    if line.strip() == "__JUPYTER_MCP_JSON__":
                        json_str = "\n".join(lines[i+1:])
                        try:
                            objs = json.loads(json_str)
                            return {"success": True, "objects": objs, "count": len(objs)}
                        except json.JSONDecodeError:
                            pass
            return {"success": False, "error": "未找到输出"}
        return {"success": False, "error": str(result.get("error", "未知错误"))}

    def preview_object(self, name: str) -> dict:
        """预览 kernel 中的变量"""
        # 验证名字是否合法
        if not name.isidentifier():
            return {"success": False, "error": f"'{name}' 不是合法的 Python 变量名"}

        code = f"""
import json, sys

obj = __builtins__.__dict__.get('_', None)
{name}  # 确保变量存在

# 对象基本信息
_info = {{
    'name': '{name}',
    'type': type({name}).__name__,
    'module': type({name}).__module__,
    'size': sys.getsizeof({name}),
}}

# DataFrame / Series
_mod = type({name}).__module__
if 'pandas' in _mod:
    try:
        import pandas as _pd
        if isinstance({name}, _pd.DataFrame):
            _info['shape'] = list({name}.shape)
            _info['dtypes'] = {{str(k): str(v) for k, v in {name}.dtypes.to_dict().items()}}
            _info['columns'] = list({name}.columns)
            _info['index'] = [str({name}.index[0]), str({name}.index[-1])] if len({name}) > 0 else []
            _info['head'] = {name}.head(10).to_dict(orient='split') if hasattr({name}, 'head') else None
            _info['describe'] = {name}.describe().to_dict() if hasattr({name}, 'describe') else None
            _info['na_counts'] = {{str(k): int(v) for k, v in {name}.isna().sum().items()}}
        elif isinstance({name}, _pd.Series):
            _info['shape'] = [{name}.shape[0]]
            _info['dtype'] = str({name}.dtype)
            _info['head'] = {name}.head(10).tolist()
            _info['describe'] = {name}.describe().to_dict()
    except Exception:
        pass

elif 'numpy' in _mod:
    import numpy as _np
    if isinstance({name}, _np.ndarray):
        _info['shape'] = list({name}.shape)
        _info['dtype'] = str({name}.dtype)
        _info['min'] = float({name}.min()) if {name}.size > 0 else None
        _info['max'] = float({name}.max()) if {name}.size > 0 else None
        _info['mean'] = float({name}.mean()) if {name}.size > 0 and {name}.dtype.kind in 'fiu' else None

elif isinstance({name}, (list, tuple)):
    _info['length'] = len({name})
    _info['head'] = list({name}[:10])

elif isinstance({name}, dict):
    _info['length'] = len({name})
    _info['keys'] = list({name}.keys())[:20]

elif isinstance({name}, str):
    _info['length'] = len({name})
    _info['preview'] = {name}[:200]

import json
print('__JUPYTER_MCP_JSON__')
print(json.dumps(_info, default=str, ensure_ascii=False))
"""
        result = self.execute(code)
        if result["success"]:
            for out in result.get("output", []):
                lines = out.get("text", "").strip().split("\n")
                for i, line in enumerate(lines):
                    if line.strip() == "__JUPYTER_MCP_JSON__":
                        json_str = "\n".join(lines[i+1:])
                        try:
                            info = json.loads(json_str)
                            return {"success": True, "data": info}
                        except json.JSONDecodeError:
                            pass
            return {"success": False, "error": "未找到输出"}
        return {"success": False, "error": str(result.get("error", "无法预览对象"))}

    def get_loaded_packages(self) -> dict:
        """获取已加载的包"""
        code = """
import sys, json

def _safe_version(mod):
    try:
        v = mod.__version__
        if isinstance(v, bytes):
            return v.decode('utf-8')
        return str(v)
    except Exception:
        return 'unknown'

pkgs = {k: v for k, v in sorted(sys.modules.items()) if v is not None and hasattr(v, '__version__')}
print('__JUPYTER_MCP_JSON__')
print(json.dumps({pkg: _safe_version(mod) for pkg, mod in pkgs.items()}, ensure_ascii=False))
"""
        result = self.execute(code)
        if result["success"]:
            for out in result.get("output", []):
                lines = out.get("text", "").strip().split("\n")
                for i, line in enumerate(lines):
                    if line.strip() == "__JUPYTER_MCP_JSON__":
                        json_str = "\n".join(lines[i+1:])
                        try:
                            pkgs = json.loads(json_str)
                            return {"success": True, "packages": pkgs, "count": len(pkgs)}
                        except json.JSONDecodeError:
                            pass
            return {"success": False, "error": "未找到输出"}
        return {"success": False, "error": str(result.get("error", "无法获取包列表"))}

    def health(self) -> dict:
        if self._connected and self.kc and self.kc.is_alive():
            return {
                "success": True,
                "data": {
                    "status": "alive",
                    "conn_file": self.conn_file,
                    "connected": True,
                },
            }
        return {"success": False, "error": "kernel 未连接"}

    def shutdown(self):
        if self.kc:
            try:
                self.kc.stop_channels()
            except Exception:
                pass
            self.kc = None
            self._connected = False


# ── 从注册文件读取目标 kernel ──────────────────────────────────────────────


def find_registered_kernel() -> JupyterKernel | None:
    """从注册文件中读取 kernel 连接信息并返回连接好的 JupyterKernel 对象"""
    if not os.path.exists(REGISTER_FILE):
        log.warning(f"注册文件不存在: {REGISTER_FILE}")
        log.warning("请在 Jupyter Lab 中运行: from jupyter_mcp import hook; hook.register()")
        return None

    try:
        with open(REGISTER_FILE) as f:
            reg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"读取注册文件失败: {e}")
        return None

    conn_file = reg.get("kernel_conn_file")
    if not conn_file or not os.path.exists(conn_file):
        # 尝试从注册信息中的 connection 字段重建连接文件
        conn = reg.get("connection")
        if conn and all(k in conn for k in ["shell_port", "iopub_port", "key"]):
            # 写一个临时连接文件
            tmp_dir = os.path.expanduser("~/.jupyter-mcp")
            os.makedirs(tmp_dir, exist_ok=True)
            conn_file = os.path.join(tmp_dir, f"kernel-{reg['pid']}.json")
            with open(conn_file, "w") as f:
                json.dump(conn, f)
            log.info(f"从注册信息重建连接文件: {conn_file}")
        else:
            log.error(f"kernel 连接文件不存在: {conn_file}")
            log.error("请重新运行 hook.register()")
            return None

    kernel = JupyterKernel(conn_file)
    err = kernel.connect()
    if err:
        log.error(f"连接 kernel 失败: {err}")
        return None

    return kernel


# ── Jupyter Server REST API 客户端（用于操作 Notebook cell）─────────────

class NotebookClient:
    """通过 Jupyter Server REST API 操作 Notebook cell"""

    def __init__(self, server_info: dict, notebook_path: str):
        self.base_url = server_info.get("url", "").rstrip("/")
        self.token = server_info.get("token", "")
        self.notebook_path = notebook_path
        self._session = None
        self._execution_counters = {}  # cache last execution count per notebook

    def _request(self, method: str, path: str = "", body: dict | None = None) -> dict:
        """发起 REST 请求（用 urllib 避免代理干扰）"""
        import os
        from urllib.request import Request, urlopen
        import json as _json

        url = f"{self.base_url}/api/contents/{self.notebook_path}{path}"
        data = _json.dumps(body).encode() if body else None

        req = Request(
            url,
            data=data,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json" if body else "text/plain",
            },
            method=method,
        )

        # 临时屏蔽代理环境变量
        old_http = os.environ.pop("http_proxy", None)
        old_https = os.environ.pop("https_proxy", None)
        try:
            with urlopen(req, timeout=10) as resp:
                return _json.loads(resp.read())
        finally:
            if old_http:
                os.environ["http_proxy"] = old_http
            if old_https:
                os.environ["https_proxy"] = old_https

    def get_notebook(self) -> dict:
        """获取 notebook 内容"""
        return self._request("GET")

    def save_notebook(self, nb: dict) -> None:
        """保存 notebook 内容，并创建 checkpoint 触发前端刷新"""
        self._request("PUT", body=nb)
        # 创建 checkpoint 促使 JupyterLab 检测到文件变更
        try:
            url = f"{self.base_url}/api/contents/{self.notebook_path}/checkpoints"
            import os
            from urllib.request import Request, urlopen
            old_http = os.environ.pop("http_proxy", None)
            old_https = os.environ.pop("https_proxy", None)
            try:
                req = Request(url, data=b"{}",
                    headers={"Authorization": f"token {self.token}",
                             "Content-Type": "application/json"},
                    method="POST")
                with urlopen(req, timeout=5) as resp:
                    if resp.status == 201:
                        log.info(f"checkpoint 创建成功")
            finally:
                if old_http: os.environ["http_proxy"] = old_http
                if old_https: os.environ["https_proxy"] = old_https
        except Exception as e:
            log.warning(f"创建 checkpoint 失败: {e}")

    def add_code_cell(self, code: str) -> tuple[int, dict]:
        """
        在 notebook 末尾添加一个代码 cell。
        返回 (cell_index, cell_json) 其中 cell_json 是待填充的 cell 骨架
        """
        nb = self.get_notebook()
        cells = nb["content"]["cells"]

        # 计算下一个 execution_count
        last_exec = max((c.get("execution_count") or 0) for c in cells)
        exec_count = last_exec + 1

        new_cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": code.splitlines(keepends=True),
        }

        cell_index = len(cells)
        cells.append(new_cell)
        nb["content"]["cells"] = cells
        self.save_notebook(nb)

        return cell_index, {"execution_count": exec_count, "cell_index": cell_index}

    def write_outputs(
        self,
        cell_index: int,
        execution_count: int,
        outputs: list[dict],
    ) -> None:
        """将执行结果写回 cell"""
        nb = self.get_notebook()
        cells = nb["content"]["cells"]

        if cell_index >= len(cells):
            log.warning(f"cell 索引 {cell_index} 超出范围 (共 {len(cells)} 个)")
            return

        cell = cells[cell_index]
        cell["execution_count"] = execution_count
        cell["outputs"] = outputs
        nb["content"]["cells"] = cells
        self.save_notebook(nb)

    def zmq_outputs_to_cell_outputs(
        self, result: dict
    ) -> tuple[list[dict], list[str]]:
        """
        将 ZMQ 执行结果转换为 notebook cell 的 outputs 格式。
        返回 (cell_outputs, display_lines)
        """
        cell_outputs = []
        display_lines = []

        # stdout/stderr
        for out in result.get("output", []):
            text = out.get("text", "")
            name = out.get("name", "stdout")
            cell_outputs.append({
                "output_type": "stream",
                "name": name,
                "text": text,
            })
            if text.strip():
                display_lines.append(text.rstrip())

        # execute_result
        exec_result = result.get("execute_result")
        if exec_result:
            cell_outputs.append({
                "output_type": "execute_result",
                "execution_count": result.get("execution_count") or 1,
                "data": {"text/plain": exec_result},
                "metadata": {},
            })
            display_lines.append(exec_result.strip())

        # error
        error = result.get("error")
        if error:
            ename = error.get("ename", "Error")
            evalue = error.get("evalue", "")
            traceback_lines = error.get("traceback", [])
            # Strip ANSI from traceback
            import re
            clean_tb = [
                re.sub(r"\x1b\[.*?m", "", line)
                for line in traceback_lines
            ]
            cell_outputs.append({
                "output_type": "error",
                "ename": ename,
                "evalue": evalue,
                "traceback": clean_tb,
            })
            display_lines.append(f"❌ {ename}: {evalue}")

        # display_data (matplotlib plots etc)
        displays = result.get("display_data", [])
        for d in displays:
            if d.get("type") == "image/png":
                cell_outputs.append({
                    "output_type": "display_data",
                    "data": {
                        "image/png": d.get("data", ""),
                        "text/plain": "<matplotlib figure>",
                    },
                    "metadata": {},
                })
                display_lines.append("📊 [包含图表]")

        return cell_outputs, display_lines


# ── 注册信息读取 ──────────────────────────────────────────────────────────

_registration: dict | None = None


def load_registration() -> dict | None:
    """读取注册文件，返回完整注册信息"""
    global _registration
    if not os.path.exists(REGISTER_FILE):
        return None
    try:
        with open(REGISTER_FILE) as f:
            _registration = json.load(f)
        return _registration
    except (json.JSONDecodeError, OSError):
        return None


def get_mode() -> str:
    """返回当前 kernel 的模式: 'notebook' 或 'console'"""
    reg = load_registration()
    if reg:
        return reg.get("mode", "notebook")
    return "notebook"


def get_source_path() -> str | None:
    """返回当前 kernel 绑定的源码文件路径（.py 或 .ipynb）"""
    reg = load_registration()
    if reg:
        return reg.get("source_path")
    return None


def get_notebook_client() -> NotebookClient | None:
    """从注册信息创建 NotebookClient"""
    reg = load_registration()
    if not reg:
        return None
    js = reg.get("jupyter_server")
    if not js:
        log.warning("注册信息缺少 Jupyter Server 信息，请重新运行 hook.register(force=True)")
        return None

    # 从 sessions API 查找当前 kernel 对应的 notebook 路径
    import os
    from urllib.request import Request, urlopen
    import json as _json
    base_url = js.get("url", "").rstrip("/")
    token = js.get("token", "")

    # 从 hook 注册信息获取 kernel ID
    kernel_conn = reg.get("kernel_conn_file", "")
    kernel_id = os.path.basename(kernel_conn).replace("kernel-", "").replace(".json", "")

    try:
        req = Request(
            f"{base_url}/api/sessions",
            headers={"Authorization": f"token {token}"},
        )
        # 临时屏蔽代理
        old_http = os.environ.pop("http_proxy", None)
        old_https = os.environ.pop("https_proxy", None)
        try:
            with urlopen(req, timeout=10) as resp:
                sessions = _json.loads(resp.read())
        finally:
            if old_http:
                os.environ["http_proxy"] = old_http
            if old_https:
                os.environ["https_proxy"] = old_https
        for session in sessions:
            sk = session.get("kernel", {})
            if sk.get("id") == kernel_id:
                nb_path = session.get("path", "")
                if nb_path:
                    log.info(f"找到 notebook 路径: {nb_path}")
                    return NotebookClient(js, nb_path)
    except Exception as e:
        log.warning(f"查询 sessions API 失败: {e}")

    # 兜底：用注册文件名
    notebook = reg.get("notebook", "Untitled.ipynb")
    log.warning(f"未从 sessions API 找到路径，使用注册文件名: {notebook}")
    return NotebookClient(js, notebook)


# ── MCP 服务器 ────────────────────────────────────────────────────────────

try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:
    print("需要安装 mcp 包: pip install mcp httpx", file=sys.stderr)
    sys.exit(1)


server = Server("jupyter-mcp")
kernel_instance: JupyterKernel | None = None


def make_text(content: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=content)]


def make_table(headers: list[str], rows: list[list[str]]) -> str:
    """生成格式化表格"""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    sep = "─" * (sum(col_widths) + 3 * len(col_widths) - 1)

    lines = [sep]
    header_line = " │ ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(f" {header_line} ")
    lines.append(sep)
    for row in rows:
        line = " │ ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row))
        lines.append(f" {line} ")
    lines.append(sep)
    return "\n".join(lines)


# ── 工具定义 ──────────────────────────────────────────────────────────────

TOOLS = [
    types.Tool(
        name="run_code",
        description="在 Jupyter kernel 中执行 Python 代码，返回输出和结果。可以修改当前 session 的变量！",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
            },
            "required": ["code"],
        },
    ),
    types.Tool(
        name="list_objects",
        description="列出 Jupyter kernel 中当前所有变量及其类型、大小等信息",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="preview_data",
        description="预览某个变量的详细内容（包括 DataFrame 的 shape/dtypes/head/describe，以及缺失值统计）",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "变量名",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="get_loaded_packages",
        description="列出当前 kernel 中已安装/加载的 Python 包及版本号",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="health_check",
        description="检查 Jupyter kernel 连接状态",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="read_source",
        description="读取当前 .py 源码文件的内容（仅 .py + Console 模式）",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="write_source",
        description="写入/覆盖 .py 源码文件（仅 .py + Console 模式）",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要写入的 Python 代码",
                },
            },
            "required": ["code"],
        },
    ),
    types.Tool(
        name="append_source",
        description="追加代码到 .py 源码文件末尾（仅 .py + Console 模式）",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要追加的 Python 代码",
                },
            },
            "required": ["code"],
        },
    ),
    types.Tool(
        name="export_data",
        description="从 Python kernel 导出变量到 CSV 共享文件，供其他 session（如 RStudio R）使用",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Python 中的变量名（pandas DataFrame 或可转为 DataFrame 的对象）",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="import_data",
        description="从 CSV 共享文件导入数据到 Python kernel，例如 R session 导出的结果",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "CSV 文件路径",
                },
                "var_name": {
                    "type": "string",
                    "description": "Python kernel 中创建的变量名",
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
    global kernel_instance

    if arguments is None:
        arguments = {}

    # 检查 kernel 连接
    if name != "health_check":
        if not kernel_instance or not kernel_instance._connected:
            return make_text(
                "❌ 未连接到 Jupyter kernel\n\n"
                "请先确保:\n"
                "  1. 在 Jupyter Lab cell 中运行: from jupyter_mcp import hook; hook.register()\n"
                "  2. 如果已注册，重启本 MCP 服务器"
            )

    try:
        if name == "run_code":
            code = arguments["code"]
            current_mode = get_mode()

            # Notebook 模式：插入 Cell + 写回结果
            # Console 模式：自动写入 .py 文件，方便手动执行看 Console 输出
            nb_client = None
            cell_index = None
            exec_count = None
            mode_note = ""

            if current_mode == "notebook":
                nb_client = get_notebook_client()
                if nb_client:
                    try:
                        cell_index, cell_meta = nb_client.add_code_cell(code)
                        exec_count = cell_meta["execution_count"]
                        mode_note = f"\n📓 Cell #{cell_index+1} 已插入 Notebook"
                    except Exception as e:
                        log.warning(f"无法写入 Notebook: {e}")
                        mode_note = f"\n⚠️ 无法写入 Notebook: {e}\n"
            else:
                # .py + Console 模式：执行代码，由 console-adopt 扩展捕获并显示到 Console
                mode_note = "\n🐍 代码已在 Console 中执行\n   (console-adopt 扩展将自动捕获并显示)"

            # 2. 执行代码
            result = kernel_instance.execute(code)

            # 3. Notebook 模式：将执行结果写回 cell
            if current_mode == "notebook" and nb_client and cell_index is not None:
                try:
                    ec = result.get("execution_count") or exec_count or 1
                    cell_outputs, _ = nb_client.zmq_outputs_to_cell_outputs(result)
                    nb_client.write_outputs(cell_index, ec, cell_outputs)
                except Exception as e:
                    log.warning(f"无法写回 Notebook: {e}")

            # 4. 构建 MCP 响应
            lines = []

            if result["success"]:
                lines.append("✅ 执行成功")
            else:
                err = result.get("error", {})
                ename = err.get("ename", "Error") if isinstance(err, dict) else "Error"
                evalue = err.get("evalue", "") if isinstance(err, dict) else str(err)
                lines.append(f"❌ {ename}: {evalue}")
                tb = err.get("traceback", []) if isinstance(err, dict) else []
                if tb:
                    lines.append("\n📋 Traceback:")
                    for line in tb[:20]:
                        lines.append(f"  {line}")

            # stdout/stderr
            outputs = result.get("output", [])
            if outputs:
                lines.append("\n📝 输出:")
                for out in outputs:
                    prefix = "" if out.get("name") == "stdout" else "⚠️ "
                    for line in out.get("text", "").rstrip().split("\n"):
                        lines.append(f"  {prefix}{line}")

            # execute_result
            exec_result = result.get("execute_result")
            if exec_result:
                lines.append("\n🔙 返回值:")
                for line in exec_result.split("\n")[:30]:
                    lines.append(f"  {line}")

            # 模式提示
            if mode_note:
                lines.append(mode_note)

            return make_text("\n".join(lines))

        elif name == "list_objects":
            result = kernel_instance.list_objects()
            if not result["success"]:
                return make_text(f"❌ {result.get('error', '未知错误')}")

            objs = result.get("objects", {})
            count = result.get("count", 0)
            if count == 0:
                return make_text("📊 Kernel 中暂无用户变量（全部以下划线开头或为模块/函数）")

            rows = []
            for name, info in sorted(objs.items()):
                obj_type = info.get("type", "?")
                size_b = info.get("size", 0)
                size_str = (
                    f"{size_b/1024:.1f} KB" if size_b > 1024
                    else f"{size_b} B"
                )

                # 额外信息
                extra = ""
                if "shape" in info:
                    shape_str = "×".join(str(s) for s in info["shape"])
                    extra = f" [{shape_str}]"
                elif "length" in info:
                    extra = f" [{info['length']}]"

                rows.append([name, obj_type, size_str, extra])

            text = f"📊 Jupyter Kernel 中共 {count} 个变量:\n\n"
            text += make_table(["名称", "类型", "大小", "维度/长度"], rows)
            return make_text(text)

        elif name == "preview_data":
            obj_name = arguments["name"]
            result = kernel_instance.preview_object(obj_name)
            if not result["success"]:
                return make_text(f"❌ {result.get('error', f'无法预览 {obj_name}')}")

            data = result["data"]
            lines = [
                f"📋 对象: {data['name']}",
                f"  类型: {data['type']}",
                f"  模块: {data.get('module', 'builtins')}",
                f"  大小: {data.get('size', 0)} B",
                "─" * 60,
            ]

            # DataFrame 详情
            if "shape" in data:
                shape = data["shape"]
                lines.append(f"\n📐 形状: {shape[0]} 行 × {shape[1]} 列")
                if "dtypes" in data:
                    lines.append("\n📊 列类型:")
                    for col, dtype in data["dtypes"].items():
                        lines.append(f"    {col:<25} {dtype}")
                if "na_counts" in data:
                    na_counts = {k: v for k, v in data["na_counts"].items() if v > 0}
                    if na_counts:
                        lines.append(f"\n⚠️ 缺失值:")
                        for col, count in na_counts.items():
                            lines.append(f"    {col:<25} {count} 个")
                if "head" in data:
                    lines.append("\n👁️ 前 10 行预览:")
                    head = data["head"]
                    if isinstance(head, dict) and "data" in head:
                        # to_dict('split') 格式
                        cols = head.get("columns", [])
                        vals = head.get("data", [])
                        if cols:
                            lines.append(f"    {'  '.join(str(c)[:15] for c in cols)}")
                            for row in vals[:10]:
                                lines.append(f"    {'  '.join(str(v)[:15] for v in row)}")
                if "describe" in data:
                    lines.append("\n📊 描述统计:")
                    desc = data["describe"]
                    for stat, vals in desc.items():
                        vals_str = ", ".join(f"{k}={v:.4f}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in list(vals.items())[:6])
                        lines.append(f"    {stat}: {vals_str}")

            # numpy
            elif "dtype" in data and "shape" in data:
                lines.append(f"\n📐 形状: {'×'.join(str(s) for s in data['shape'])}")
                lines.append(f"  类型: {data['dtype']}")
                if data.get("min") is not None:
                    lines.append(f"  范围: [{data['min']:.4f}, {data['max']:.4f}]")
                    if data.get("mean") is not None:
                        lines.append(f"  均值: {data['mean']:.4f}")

            # list / dict / str
            elif "length" in data:
                lines.append(f"\n📏 长度: {data['length']}")
                if "head" in data:
                    lines.append(f"  前 10 个: {data['head']}")
                if "keys" in data:
                    lines.append(f"  键: {data['keys']}")

            elif "preview" in data:
                lines.append(f"\n📝 内容: {data['preview']}")

            return make_text("\n".join(lines))

        elif name == "get_loaded_packages":
            result = kernel_instance.get_loaded_packages()
            if not result["success"]:
                return make_text(f"❌ {result.get('error', '未知错误')}")

            pkgs = result.get("packages", {})
            count = result.get("count", 0)
            if count == 0:
                return make_text("当前 kernel 未加载任何包（或包均无 __version__ 属性）")

            lines = [f"📦 已加载 {count} 个包:", "─" * 40]
            for pkg, ver in sorted(pkgs.items()):
                lines.append(f"  {pkg:<30} v{ver}")

            return make_text("\n".join(lines))

        elif name == "health_check":
            if kernel_instance:
                health = kernel_instance.health()
                if health["success"]:
                    current_mode = get_mode()
                    src = get_source_path()
                    mode_label = "📓 Notebook" if current_mode == "notebook" else "🐍 .py + Console"
                    src_label = src or get_notebook_client().notebook_path if current_mode == "notebook" else (src or "未知")
                    return make_text(
                        f"✅ Jupyter Kernel 连接正常\n"
                        f"  PID: {os.getpid()}\n"
                        f"  模式: {mode_label}\n"
                        f"  文件: {get_source_path() or '未知'}\n"
                        f"  连接文件: {health['data']['conn_file']}"
                    )

            return make_text(
                "❌ 未连接到 Jupyter kernel\n\n"
                "请先确保:\n"
                "  1. 在 Jupyter Lab cell 中运行: from jupyter_mcp import hook; hook.register()\n"
                "  2. 然后重启本 MCP 服务器"
            )

        elif name == "read_source":
            src_path = get_source_path()
            if not src_path or not src_path.endswith(".py"):
                return make_text("❌ 当前不是 .py + Console 模式，或找不到 .py 源文件路径")
            reg = load_registration()
            js = reg.get("jupyter_server", {}) if reg else {}
            server_root = "/home/openclaw"  # JupyterLab 的 serverRoot
            full_path = os.path.join(server_root, src_path)
            if not os.path.exists(full_path):
                return make_text(f"❌ 文件不存在: {full_path}")
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                lines = content.split("\n")
                return make_text(
                    f"📄 {src_path}（{len(lines)} 行, {len(content)} 字符）\n"
                    f"{'─' * 50}\n"
                    f"{content}"
                )
            except Exception as e:
                return make_text(f"❌ 读取文件失败: {e}")

        elif name == "write_source":
            code = arguments.get("code", "")
            src_path = get_source_path()
            if not src_path or not src_path.endswith(".py"):
                return make_text("❌ 当前不是 .py + Console 模式，或找不到 .py 源文件路径")
            server_root = "/home/openclaw"
            full_path = os.path.join(server_root, src_path)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code)
                line_count = len(code.split("\n"))
                return make_text(f"✅ 已写入 {src_path}（{line_count} 行）\n")
            except Exception as e:
                return make_text(f"❌ 写入文件失败: {e}")

        elif name == "append_source":
            code = arguments.get("code", "")
            src_path = get_source_path()
            if not src_path or not src_path.endswith(".py"):
                return make_text("❌ 当前不是 .py + Console 模式，或找不到 .py 源文件路径")
            server_root = "/home/openclaw"
            full_path = os.path.join(server_root, src_path)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write("\n" + code + "\n")
                with open(full_path) as f:
                    lines = f.readlines()
                return make_text(f"✅ 已追加代码到 {src_path}（当前共 {len(lines)} 行）\n")
            except Exception as e:
                return make_text(f"❌ 追加内容失败: {e}")

        elif name == "export_data":
            import uuid

            obj_name = arguments["name"]
            os.makedirs(SHARED_DIR, exist_ok=True)
            uid = str(uuid.uuid4())[:8]
            path = f"{SHARED_DIR}/{uid}.csv"

            # 合二为一：导出 + 形状信息，只调一次 execute
            code = (
                f"import os\n"
                f"{obj_name}.to_csv(r'{path}', index=False)\n"
                f"if hasattr({obj_name}, 'shape'):\n"
                f"    print(f'shape={{list({obj_name}.shape)}}')\n"
                f"elif hasattr({obj_name}, '__len__'):\n"
                f"    print(f'len={{len({obj_name})}}')\n"
            )
            result = kernel_instance.execute(code)
            if not result.get("success"):
                err_info = result.get("error", {})
                if isinstance(err_info, dict):
                    msg = err_info.get("evalue", str(err_info))
                else:
                    msg = str(err_info)
                return make_text(f"❌ Python 导出失败: {msg}")

            # 从 output 提取形状信息
            shape_info = ""
            for out in result.get("output", []):
                shape_info += out.get("text", "")
            shape_info = shape_info.strip()

            return make_text(
                f"✅ 已从 Python session 导出 `{obj_name}`\n"
                f"  路径: {path}\n"
                f"  格式: CSV | {shape_info}\n"
                f"  （类型可能失真，导入后一行 `.astype()` 即可）"
            )

        elif name == "import_data":
            path = arguments["path"]
            var_name = arguments["var_name"]

            if not os.path.exists(path):
                return make_text(f"❌ 文件不存在: {path}")

            # 合二为一：读取 + 验证，只调一次 execute
            code = (
                f"import pandas as pd\n"
                f"{var_name} = pd.read_csv(r'{path}')\n"
                f"if hasattr({var_name}, 'shape'):\n"
                f"    print(f'shape={{list({var_name}.shape)}}, type={{type({var_name}).__name__}}')\n"
            )
            result = kernel_instance.execute(code)
            if not result.get("success"):
                err_info = result.get("error", {})
                if isinstance(err_info, dict):
                    msg = err_info.get("evalue", str(err_info))
                else:
                    msg = str(err_info)
                return make_text(f"❌ Python 导入失败: {msg}")

            # 从 output 提取验证信息
            verify_info = ""
            for out in result.get("output", []):
                verify_info += out.get("text", "")
            verify_info = verify_info.strip()

            return make_text(
                f"✅ 已导入到 Python session: `{var_name}`\n"
                f"  来源: {path}\n"
                f"  {verify_info}\n"
                f"  （类型可能失真，用 `.astype()` 修正）"
            )

        else:
            return make_text(f"未知工具: {name}")

    except Exception as e:
        return make_text(f"❌ 服务器错误: {str(e)}\n{traceback.format_exc()}")


# ── 启动 ──────────────────────────────────────────────────────────────────

async def main_stdio():
    """stdio 模式（供 OpenClaw spawn）"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )


async def main_http(port: int, host: str = "127.0.0.1"):
    """HTTP/SSE 模式（供远程连接）"""
    from mcp.server.sse import SseServerTransport
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
    log.info(f"MCP HTTP 服务器启动在 http://{host}:{port}/sse")
    await uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import asyncio

    mcp_host = os.environ.get("JUPYTER_MCP_HOST", "127.0.0.1")
    mcp_port = int(os.environ.get("JUPYTER_MCP_PORT", "0"))

    # 启动时尝试连接已注册的 kernel
    log.info(f"查找注册的 Jupyter kernel (注册文件: {REGISTER_FILE})...")
    kernel_instance = find_registered_kernel()
    if kernel_instance:
        log.info("✅ 成功连接到 Jupyter kernel")
    else:
        log.warning("⚠️  未找到注册的 kernel，请先在 Jupyter Lab 中运行 hook.register()")
        log.warning("   也可稍后启动后再注册，然后通过 health_check 确认")

    if mcp_port > 0:
        asyncio.run(main_http(mcp_port, mcp_host))
    else:
        log.info("启动 stdio 模式 MCP 服务器...")
        asyncio.run(main_stdio())
