"""
jupyter_mcp/hook.py — 在 Jupyter Lab cell 中运行的注册函数

在你想让 OpenClaw 连接的 kernel cell 中运行：

    from jupyter_mcp import hook
    hook.register()

这会写入 ~/.jupyter-mcp/current 文件，MCP 服务器会读取它来定位 kernel。
"""

import os
import sys
import json
import time
import socket
import glob


REGISTER_FILE = os.path.expanduser("~/.jupyter-mcp/current")
RUNTIME_DIR = os.path.expanduser("~/.local/share/jupyter/runtime")


def _find_jupyter_server() -> dict | None:
    """找到当前 Jupyter Server 的连接信息（URL + token）"""
    pattern = os.path.join(RUNTIME_DIR, "jpserver-*.json")
    for fpath in sorted(glob.glob(pattern), reverse=True):
        try:
            with open(fpath) as f:
                info = json.load(f)
            pid = info.get("pid")
            if pid and os.path.isdir(f"/proc/{pid}"):
                return {
                    "url": info.get("url", ""),
                    "token": info.get("token", ""),
                    "base_url": info.get("base_url", "/"),
                    "port": info.get("port", 8888),
                    "pid": pid,
                }
        except (json.JSONDecodeError, OSError):
            continue
    return None


def _find_connection_file() -> str | None:
    """从当前 kernel 进程中找到连接文件路径"""
    # 方法 1: 从 sys.argv 中找 -f 参数（ipykernel 标准方式）
    for i, arg in enumerate(sys.argv):
        if arg == "-f" and i + 1 < len(sys.argv):
            cf = sys.argv[i + 1]
            if os.path.exists(cf):
                return cf

    # 方法 2: 从环境变量找（某些启动方式）
    cf = os.environ.get("JPY_CONNECTION_FILE")
    if cf and os.path.exists(cf):
        return cf

    # 方法 3: 遍历 runtime 目录，找属于当前 PID 的 kernel
    runtime_dir = os.path.expanduser("~/.local/share/jupyter/runtime")
    if os.path.isdir(runtime_dir):
        my_pid = os.getpid()
        for fname in os.listdir(runtime_dir):
            if not fname.startswith("kernel-") or not fname.endswith(".json"):
                continue
            fpath = os.path.join(runtime_dir, fname)
            try:
                with open(fpath) as f:
                    info = json.load(f)
                # kernel connection file 中有 key/signature_scheme 等字段
                # 但如果不知道 PID 很难匹配… 用时间戳启发式: 取最新的
                pass
            except (json.JSONDecodeError, OSError):
                continue

    return None


def _get_kernel_name() -> str:
    """尝试获取当前 kernel 的名称"""
    # 从内核 spec 获取
    try:
        import ipykernel
        kernel = get_ipython()  # type: ignore
        if kernel and hasattr(kernel, "config"):
            kname = kernel.config.get("IPKernelApp", {}).get("kernel_name", "")
            if kname:
                return kname
    except (ImportError, NameError):
        pass

    # 从连接文件读取 kernel_name
    conn_file = _find_connection_file()
    if conn_file:
        try:
            with open(conn_file) as f:
                info = json.load(f)
            if info.get("kernel_name"):
                return info["kernel_name"]
        except (json.JSONDecodeError, OSError):
            pass

    return "python3"


def _get_notebook_name() -> str:
    """获取当前 notebook 文件名"""
    try:
        kernel = get_ipython()  # type: ignore
        if kernel and hasattr(kernel, "parent_header"):
            parent = kernel.parent_header
            if parent and "msg_id" in parent:
                pass
    except NameError:
        pass

    # 从环境变量
    session = os.environ.get("JPY_SESSION_NAME", "")
    if session:
        return os.path.basename(session)

    # 从连接文件 jupyter_session
    conn_file = _find_connection_file()
    if conn_file:
        try:
            with open(conn_file) as f:
                info = json.load(f)
            if info.get("jupyter_session"):
                return os.path.basename(info["jupyter_session"])
        except (json.JSONDecodeError, OSError):
            pass

    return "unknown"


def _detect_mode() -> dict:
    """
    检测当前 kernel 的运行模式：notebook 或 console（.py + Console）。
    返回 {'mode': 'notebook'|'console', 'source_path': str|None}
    """
    conn_file = _find_connection_file()
    if not conn_file:
        return {"mode": "notebook", "source_path": None}

    try:
        with open(conn_file) as f:
            info = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"mode": "notebook", "source_path": None}

    jupyter_session = info.get("jupyter_session", "")
    if not jupyter_session:
        return {"mode": "notebook", "source_path": None}

    # .ipynb → notebook 模式
    if jupyter_session.endswith(".ipynb"):
        return {"mode": "notebook", "source_path": jupyter_session}

    # .py → console 模式（.py + Console）
    if jupyter_session.endswith(".py"):
        return {"mode": "console", "source_path": jupyter_session}

    # 其他（如 console-[id]）→ console 模式，但无源码路径
    return {"mode": "console", "source_path": jupyter_session}


def register(force: bool = False) -> None:
    """
    将当前 Jupyter kernel 注册到 MCP 服务器可发现的位置。

    参数:
        force: 如果 True，覆盖已有的注册（即使已有注册）
    """
    # 检查是否已在 IPython kernel 中运行
    try:
        get_ipython()  # type: ignore
    except NameError:
        print("❌ hook.register() 必须在 Jupyter Lab / IPython kernel 中运行")
        print("   当前环境不是 IPython kernel，无法注册")
        return

    conn_file = _find_connection_file()

    if not conn_file:
        print(
            "❌ 无法定位当前 kernel 的连接文件。"
            "请确保在 Jupyter Lab / Notebook cell 中运行此函数。"
        )
        print("   手动排查: 检查 ~/.local/share/jupyter/runtime/ 下是否有 kernel-*.json 文件")
        return

    # 读取连接文件获取详细信息
    try:
        with open(conn_file) as f:
            conn_info = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ 无法读取 kernel 连接文件 ({conn_file}): {e}")
        return

    # 检测模式
    mode_info = _detect_mode()

    # 构建注册信息
    reg_info = {
        "kernel_conn_file": conn_file,
        "kernel_name": conn_info.get("kernel_name", _get_kernel_name()),
        "notebook": _get_notebook_name(),
        "mode": mode_info["mode"],
        "source_path": mode_info["source_path"],
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "timestamp": time.time(),
        "transport": conn_info.get("transport", "tcp"),
        "ip": conn_info.get("ip", "127.0.0.1"),
        # 存储连接参数方便 MCP 服务器直接连接
        "connection": {
            "shell_port": conn_info.get("shell_port"),
            "iopub_port": conn_info.get("iopub_port"),
            "stdin_port": conn_info.get("stdin_port"),
            "control_port": conn_info.get("control_port"),
            "hb_port": conn_info.get("hb_port"),
            "ip": conn_info.get("ip", "127.0.0.1"),
            "key": conn_info.get("key"),
            "transport": conn_info.get("transport", "tcp"),
            "signature_scheme": conn_info.get("signature_scheme", "hmac-sha256"),
            "kernel_name": conn_info.get("kernel_name", "python3"),
        },
        # Jupyter Server REST API 连接信息（用于插入/保存 cell）
        "jupyter_server": _find_jupyter_server(),
    }

    # 写入注册文件
    reg_dir = os.path.dirname(REGISTER_FILE)
    os.makedirs(reg_dir, exist_ok=True)

    # 检查是否已有注册
    if os.path.exists(REGISTER_FILE) and not force:
        try:
            with open(REGISTER_FILE) as f:
                existing = json.load(f)
            if existing.get("pid") == os.getpid():
                print(
                    f"ℹ️  当前 kernel 已注册 (PID {os.getpid()})。"
                )
                print(f"   如需重新注册，请传参数 force=True")
                return
            print(
                f"ℹ️  已有其他 kernel 注册 (PID {existing.get('pid', '?')})。"
                f"使用 force=True 覆盖"
            )
            return
        except (json.JSONDecodeError, OSError):
            pass

    with open(REGISTER_FILE, "w") as f:
        json.dump(reg_info, f, indent=2, ensure_ascii=False)

    print(f"✅ Jupyter kernel 已注册到 MCP 服务器")
    print(f"   连接文件: {conn_file}")
    print(f"   Kernel:   {reg_info['kernel_name']}")
    print(f"   模式:     {'📓 Notebook' if reg_info['mode'] == 'notebook' else '🐍 .py + Console'}")
    print(f"   文件:     {reg_info['source_path'] or reg_info['notebook']}")
    print(f"   PID:      {reg_info['pid']}")
    print()
    print(f"现在可以启动或重启 jupyter-mcp-server.py，它会自动连接到这个 kernel。")
