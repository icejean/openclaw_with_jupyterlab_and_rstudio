---
output:
  html_document: default
  word_document: default
---

# jupyter-mcp: 原理、架构与实现详解

> 让 AI 智能体像人一样在 Jupyter Lab 中做交互式数据分析

------------------------------------------------------------------------

## 一、整体架构

```         
┌──────────────────────────────────────────────────────────────┐
│                   浏览器 (JupyterLab UI)                     │
│  ┌─────────────────────┐  ┌────────────────────────────────┐ │
│  │ Notebook (.ipynb)   │  │ .py + Console                  │ │
│  │ auto-reload 扩展    │  │ console-adopt 扩展             │ │
│  └─────────┬───────────┘  └──────────┬─────────────────────┘ │
└────────────┼─────────────────────────┼───────────────────────┘
             │                         │
             │  HTTP / WebSocket       │
             ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│              Jupyter Server (JupyterHub)                     │
│       /api/contents /api/kernels /api/sessions               │
│       /api/kernels/{id}/channels (WebSocket)                 │
└────────────┬──────────────────────────┬──────────────────────┘
             │                          │
             │   ZMQ (jupyter_client)   │  ZMQ (WebSocket proxy)
             ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Jupyter Kernel                            │
│                (IPython / graphrag)                          │
│         Shell / IOPub / Stdin / Control / Heartbeat          │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ ZMQ (jupyter_client)
             ▼
┌──────────────────────────────────────────────────────────────┐
│              jupyter-mcp MCP Server (Python)                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  JupyterKernel (ZMQ 连接管理)                        │    │
│  │  - find_registered_kernel() → 自动发现并连接         │    │
│  │  - connect(conn_file)  → BlockingKernelClient        │    │
│  │  - execute(code)       → ZMQ Shell + IOPub           │    │
│  │  - list_objects()      → 内省全局变量（JSON 协议）   │    │
│  │  - preview_object()    → 预览变量详情                │    │
│  │  - get_loaded_packages()                             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  MCP Protocol 层                                     │    │
│  │  - mcp.types.Tool 定义（10 个工具）                  │    │
│  │  - handle_call_tool 分发                             │    │
│  │  - stdio / HTTP SSE 两种传输模式                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  NotebookClient (Jupyter Server API 客户端)          │    │
│  │  - 通过 REST API 操作 .ipynb cell                    │    │
│  │  - add_code_cell() → PUT /api/contents               │    │
│  │  - write_outputs()  → 写回执行结果到 Cell            │    │
│  │  - zmq_outputs_to_cell_outputs() 格式转换            │    │
│  │  - create checkpoint → 触发前端刷新                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  shared_dir (R ↔ Python 数据交换)                    │    │
│  │  - SHARED_DIR 默认 ~/workspace/r2py/                 │    │
│  │  - export_data/import_data 通过 CSV 交换             │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
             │
             │ MCP Protocol (stdio / SSE)
             ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenClaw Gateway                               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MCP Runtime Manager                                 │   │
│  │  - 进程生命周期管理 (spawn/kill/restart)             │   │
│  │  - 工具发现 (listTools)                              │   │
│  │  - 工具调用 (callTool)                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tool Router                                         │   │
│  │  jupyter-mcp__run_code → MCP → kernel                │   │
│  │  jupyter-mcp__health_check → MCP → kernel            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
         AI 模型（DeepSeek / GLM / Kimi ...）
```

------------------------------------------------------------------------

## 二、核心组件详解

### 2.1 hook.py — kernel 注册模块

**作用：** 在 Jupyter kernel 内部运行的注册函数，将 kernel 的连接信息写入文件，供 MCP Server 发现。

**运行方式：** 在 Notebook cell 或 .py Console 中执行：

``` python
from jupyter_mcp import hook
hook.register()           # 首次注册
hook.register(force=True) # 覆盖已有注册
```

**工作原理：**

```         
register() 被调用时：
  1. 检查是否在 IPython kernel 环境中（get_ipython()）
  2. 查找当前 kernel 的连接文件（~/.local/share/jupyter/runtime/kernel-*.json）
     - 方法1: 从 sys.argv 找 -f 参数（ipykernel 标准方式）
     - 方法2: 从 JPY_CONNECTION_FILE 环境变量
     - 方法3: 遍历 runtime 目录（兜底）
  3. 读取连接文件 → 获取 shell_port, iopub_port, key 等信息
  4. 检测当前模式：
     - 读取连接文件中的 jupyter_session 字段
     - 以 .ipynb 结尾 → mode="notebook"
     - 以 .py 结尾 → mode="console"
  5. 查找 Jupyter Server 信息（jpserver-*.json）
     - 匹配方法：取最新的、PID 进程仍在运行的 jpserver-*.json
  6. 写入 ~/.jupyter-mcp/current（JSON 格式）
     - 包含完整的 connection 字段（重建连接文件用）
     - 包含 jupyter_server 字段（REST API 调用用）
```

**注册文件结构 (\~/.jupyter-mcp/current)：**

``` json
{
  "kernel_conn_file": "/home/openclaw/.local/share/.../kernel-xxx.json",
  "kernel_name": "graphrag",
  "notebook": "untitled.py",
  "mode": "console",
  "source_path": "/home/openclaw/.openclaw/workspace/untitled.py",
  "pid": 12345,
  "hostname": "vm-12-2-ubuntu",
  "timestamp": 1717000000.0,
  "transport": "tcp",
  "ip": "127.0.0.1",
  "connection": {
    "shell_port": 49281,
    "iopub_port": 47395,
    "key": "xxx",
    "transport": "tcp",
    "signature_scheme": "hmac-sha256",
    "ip": "127.0.0.1",
    "stdin_port": 49282,
    "control_port": 49283,
    "hb_port": 49284,
    "kernel_name": "python3"
  },
  "jupyter_server": {
    "url": "http://127.0.0.1:44153/user/openclaw/",
    "token": "xxx",
    "base_url": "/user/openclaw/",
    "port": 44153,
    "pid": 12300
  }
}
```

### 2.2 jupyter-mcp-server.py — MCP Server

**作用：** 作为 OpenClaw 与 Jupyter kernel 之间的桥梁，将 kernel 能力封装为 MCP 工具。

**shebang 与实际运行环境：**

``` python
#!/usr/lib64/anaconda3/envs/graphrag/bin/python3
```

MCP Server 运行在 `graphrag` conda 环境中。虽然服务器是这个 Python，但执行的 Python 代码是**发送到 Jupyter kernel 中执行的**——不论 kernel 是哪个环境，代码在 kernel 所在环境运行。

**通信方式：** 通过 `jupyter_client` 库，使用 ZMQ 协议直接连接 kernel（不经过 Jupyter Server HTTP API）。

**环境变量：**

| 变量                   | 默认值                   | 说明                    |
|------------------------|--------------------------|-------------------------|
| `JUPYTER_MCP_HOST`     | `127.0.0.1`              | MCP 服务器监听地址      |
| `JUPYTER_MCP_PORT`     | `0`                      | 端口号，`0`=stdio 模式  |
| `JUPYTER_MCP_TIMEOUT`  | `120`                    | kernel 代码执行超时秒数 |
| `JUPYTER_MCP_REGISTER` | `~/.jupyter-mcp/current` | 注册文件路径            |
| `R2PY_SHARED_DIR`      | `~/workspace/r2py/`      | R↔Python 数据交换目录   |
| `JUPYTER_SHARED_DIR`   | 同 `R2PY_SHARED_DIR`     | jupyter 侧覆盖          |

**ZMQ 通道：**

| 通道 | 用途 | socket 类型 |
|----|----|----|
| Shell | 发送 execute_request，接收 execute_reply | DEALER → ROUTER |
| IOPub | 接收 execute_input/result/stream/error 等广播消息 | SUB |
| Stdin | 接收 input() 请求 | DEALER → ROUTER |
| Control | 发送 interrupt/shutdown | DEALER → ROUTER |
| Heartbeat | 检测 kernel 是否存活 | REQ → REP |

**自动发现与连接：**

``` python
find_registered_kernel():
  1. 读取 ~/.jupyter-mcp/current
  2. 获取 kernel_conn_file 路径
  3. 如果连接文件不存在 → 从 connection 字段重建临时连接文件
     （防止 kernel 重启导致连接文件被清理）
  4. 创建 JupyterKernel 实例并连接
  5. 验证心跳 → 确认连接成功
```

**代码执行流程：**

```         
execute(code):
  1. kc.execute(code)  → 发送 execute_request 到 Shell 通道
     - msg_id = UUID (用于后续匹配响应)
  2. 循环收集消息（0.5s IOPub 轮询 + 0.01s Shell 轮询）：
     a. Shell 通道：get_shell_msg() → execute_reply
        - 包含 execution_count、status (ok/error)
     b. IOPub 通道：get_iopub_msg()
        - execute_input: kernel 广播的源码（显示用）
        - stream: stdout/stderr 输出
        - execute_result: 表达式计算结果
        - display_data: matplotlib 图表（含 base64 PNG）
        - error: 异常信息（ename + evalue + traceback）
        - status: busy / idle（执行完成标志）
  3. 当收到 status=idle 且 shell_reply 已收到 → 结束
  4. 超时保护（默认 120 秒）
```

**内省（Introspection）实现方式：**

所有内省操作（list_objects、preview_object、get_loaded_packages）均通过在 **kernel 中执行 Python 代码** 实现，而非通过 Jupyter 协议的原生 inspect 请求。

``` python
# list_objects 示例：在 kernel 中执行内省代码
code = """
import sys, types, builtins, json

objs = {}
for name, obj in globals().items():
    if name.startswith('_'): continue
    objs[name] = {
        'type': type(obj).__name__,
        'size': sys.getsizeof(obj),
        'shape': list(obj.shape) if hasattr(obj, 'shape') else None,
    }
print('__JUPYTER_MCP_JSON__')
print(json.dumps(objs, default=str))
"""
result = kernel.execute(code)
# 从 stdout 中解析 __JUPYTER_MCP_JSON__ 标记后的 JSON
```

**关键设计 — `__JUPYTER_MCP_JSON__` 标记协议：**

MCP Server 与 kernel 之间的结构化数据交换采用**标记协议**：

1.  MCP Server 发送一段内省代码给 kernel 执行
2.  内省代码收集信息后，打印 `__JUPYTER_MCP_JSON__` 标记行
3.  在标记行之后打印 JSON 序列化的结果
4.  MCP Server 从 stdout 中解析标记行之后的 JSON

这样做的好处： - 不依赖 Jupyter 协议扩展（保持兼容性） - JSON 数据与普通 stdout 输出可以共存 - kernel 内省代码完全可控可扩展

------------------------------------------------------------------------

### 2.3 NotebookClient — Notebook 操作模块

**作用：** 通过 Jupyter Server REST API 操作 .ipynb 文件（插入 Cell、写回结果、创建检查点）。

``` python
class NotebookClient:
    def __init__(self, server_info, notebook_path):
        # 存储 server URL + token
        # 临时屏蔽 http_proxy/https_proxy（避免代理干扰）

    def get_notebook() -> dict
        # GET /api/contents/{path}?content=1

    def save_notebook(nb: dict)
        # PUT /api/contents/{path}
        # 同时触发创建 checkpoint（POST /api/contents/{path}/checkpoints）
        # checkpoint 创建的 201 → auto-reload 检测到变更

    def add_code_cell(code: str) -> (cell_index, cell_json)
        # 获取当前 notebook
        # 从现有 cells 计算下一个 execution_count
        # 在末尾追加新代码 Cell
        # PUT 保存
        # 返回 cell_index + 元信息（execution_count）

    def write_outputs(cell_index, exec_count, outputs)
        # 获取当前 notebook
        # 更新指定 cell 的 outputs + execution_count
        # PUT 保存

    def zmq_outputs_to_cell_outputs(result) -> (outputs, display_lines)
        # stream → stream output（含 stderr）
        # execute_result → execute_result output
        # display_data (image/png) → display_data output
        # error → error output（strip ANSI 转义码）
```

**NotebookClient 创建流程：**

```         
get_notebook_client():
  1. 从 ~/.jupyter-mcp/current 获取 jupyter_server 信息
  2. 从连接文件名提取 kernel ID
  3. 调用 GET /api/sessions → 找到当前 kernel 对应的 notebook path
  4. 如果 sessions API 失败 → 用注册文件中的 notebook 字段兜底
```

**代理回避：**

所有 REST API 调用通过 `urllib.request`（而非 `httpx`/`requests`），并在调用前后**临时屏蔽 `http_proxy`/`https_proxy` 环境变量**。这是因为服务器可能配置了全局代理（如 Clash），而 Jupyter Server 在本地 127.0.0.1 上运行，不需要经过代理。

------------------------------------------------------------------------

## 三、MCP 工具清单

### 3.1 通用工具（两种模式共用）

| 工具 | 输入 | 输出 | 说明 |
|------------------|------------------|------------------|------------------|
| `run_code` | `code: string` | stdout + 结果 | 执行 Python 代码，可修改 session 变量 |
| `list_objects` | 无 | 变量列表（类型/大小/形状/列类型） | 使用 `__JUPYTER_MCP_JSON__` 标记协议 |
| `preview_data` | `name: string` | DataFrame/Series/数组详情 | shape/dtypes/head/describe/缺失值 |
| `get_loaded_packages` | 无 | 已安装包版本列表 | 从 sys.modules 获取有 `__version__` 的包 |
| `health_check` | 无 | 连接状态 + 模式 + 路径 | 含 PID、kernel 连接文件路径 |
| `export_data` | `name: string` | CSV 文件路径 | Python → R 数据导出 |
| `import_data` | `path, var_name` | 导入确认 | R → Python 数据导入 |

### 3.2 .py + Console 模式专用

| 工具            | 输入           | 说明                        |
|-----------------|----------------|-----------------------------|
| `read_source`   | 无             | 读取当前 .py 源码文件       |
| `write_source`  | `code: string` | 覆盖写入 .py 源码文件       |
| `append_source` | `code: string` | 追加代码到 .py 源码文件末尾 |

### 3.3 模式自适配逻辑（run_code）

```         
run_code(code):
  if mode == "notebook":
    # 1. 通过 Jupyter Server REST API 插入 Cell（含计算 execution_count）
    nb_client.add_code_cell(code)
    # 2. 通过 ZMQ 执行代码
    result = kernel.execute(code)
    # 3. 通过 REST API 写回执行结果到 Cell
    nb_client.write_outputs(cell_index, ec, cell_outputs)
    # 4. checkpoint 创建 → auto-reload 扩展刷新 Notebook 显示
  else: # console
    # 1. 仅通过 ZMQ 执行代码（不修改 .py 文件）
    result = kernel.execute(code)
    # 2. console-adopt 扩展监听 iopubMessage 原始信号
    #    捕获外部 session 的 execute_input 消息 → 在 Console 中显示
```

### 3.4 R ↔ Python 数据交换工具

| 工具 | 内部实现 |
|------------------------------------|------------------------------------|
| `export_data(name)` | kernel 中执行 `obj.to_csv(path, index=False)` + 打印 shape |
| `import_data(path, var_name)` | kernel 中执行 `pd.read_csv(path)` + 打印 shape |

**共享目录：** `SHARED_DIR` 默认 `~/.openclaw/workspace/r2py/`，文件名使用 UUID 前缀。

------------------------------------------------------------------------

## 四、JupyterLab 扩展

### 4.1 jupyterlab-auto-reload

**职责：** 当 Notebook 文件被外部修改（如 MCP Server 写入 Cell）时，自动刷新 Notebook 显示。

**原理：**

``` typescript
setInterval(async () => {
  const current = tracker.currentWidget;
  if (!current) return;

  const context = current.context;
  const contentsManager = app.serviceManager.contents;

  const model = await contentsManager.get(context.path);
  const serverTime = model.last_modified;

  if (!lastModified[path]) {
    lastModified[path] = serverTime;
    return;
  }

  if (serverTime !== lastModified[path]) {
    lastModified[path] = serverTime;
    if (!isDirty) {
      await context.revert();  // 从服务器重新加载
    }
  }
}, 3000);
```

**关键点：** - 使用 JupyterLab 的 `serviceManager.contents` API - 有 dirty 保护：用户有未保存修改时跳过 - 不拦截用户操作，仅监控 `last_modified` 时间戳 - 通过 MCP 的 checkpoint 创建触发的 `201` 响应可确保 `last_modified` 被更新

**安装路径：**

```         
JupyterHub → base conda环境
/usr/lib64/anaconda3/share/jupyter/labextensions/
```

### 4.2 jupyterlab-console-adopt

**职责：** 让 Console 窗口显示 MCP（其他 Session）执行的代码和输出。

**问题背景：**

JupyterLab Console 有已知限制（issue #9936）：它只显示**自身 WebSocket 连接**发出的执行结果。原因是 Console 的 `OutputArea.future` 只匹配特定 `msg_id` 的消息。

MCP Server 通过 ZMQ（jupyter_client）直接连接 kernel，使用不同的 Session ID，因此 Console 不会显示 MCP 执行的代码和输出。

**解决方案：**

扩展监听 kernel 的 `iopubMessage` 信号——这个信号包含**所有 Session** 发出的 IOPub 消息（不经过 msg_id 过滤）。

``` typescript
kernel.iopubMessage.connect(onIOPubMessage);

function onIOPubMessage(_, msg) {
  if (msg.header.msg_type === 'execute_input') {
    const sessionId = msg.parent_header.session;
    if (sessionId === kernel.clientId) return;  // 跳过自有消息

    const code = msg.content.code;
    const msgId = msg.parent_header.msg_id;
    const execCount = msg.content.execution_count;

    // 1. 创建新的 CodeCell
    const cell = consoleWidget.createCodeCell();
    cell.model.sharedModel.setSource(code);
    cell.model.executionCount = execCount;

    // 2. 创建伪 future，接管 OutputArea
    const pseudoFuture = {
      onIOPub: null,
      done: new Promise(/* resolve on status=idle */),
      dispose() {},
    };
    cell.outputArea.future = pseudoFuture;

    // 3. 添加到 Console
    consoleWidget.addCell(cell, msgId);

    // 4. 转发后续 IOPub 消息到伪 future
    const forwardOutput = (_, m) => { /* 匹配 msg_id 后转发 */ };
    kernel.iopubMessage.connect(forwardOutput);

    // 5. 执行完成后清理
    pseudoFuture.done.then(() => kernel.iopubMessage.disconnect(forwardOutput));
  }
}
```

**难点解决：**

| 问题 | 解决方案 |
|------------------------------------|------------------------------------|
| Console 只显示自身 Session 消息 | 使用 `kernel.iopubMessage`（原始信号）替代 future 的过滤信号 |
| 需要创建 Console Cell 但不想重复执行代码 | 不调用 `kernel.requestExecute()`，用伪 future 捕获已有的 IOPub 消息 |
| OutputArea 需要 future 对象才能渲染 | 创建伪 future，等 OutputArea 设置 `onIOPub` 回调后转发消息 |
| 执行序号 `[n]` 为空 | 从 execute_input 消息的 execution_count 字段获取并设置 |

------------------------------------------------------------------------

## 五、通信协议对比

| 特征 | ZMQ（MCP 直连） | WebSocket（Jupyter 前端） | REST API（NotebookClient） |
|------------------|------------------|------------------|------------------|
| 连接方式 | jupyter_client (Python) | 浏览器 WebSocket API | urllib HTTP |
| Session ID | 随机生成 | 随机生成（不同） | 不适用 |
| 协议 | Jupyter Kernel Protocol 5.x | 同 ZMQ，经 HTTP 封装 | Jupyter Contents API |
| 延迟 | 低（直接连接） | 稍高（经 Server 代理） | 较高（HTTP 往返） |
| 身份认证 | 连接文件中的 key/hmac | Jupyter Server token | token |
| 持久性 | 断开需重连 | 通常长连接 | 无状态 |
| 用途 | 代码执行 + 内省 | 用户交互 | cell 读写 |

------------------------------------------------------------------------

## 六、启动与部署流程

### 前提条件

``` bash
# graphrag conda 环境中安装依赖
pip install mcp httpx jupyter-client
```

### 完整启动流程

``` mermaid
sequenceDiagram
    participant User as 用户
    participant JL as JupyterLab
    participant MCP as jupyter-mcp
    participant GW as OpenClaw Gateway

    User->>JL: 打开 Notebook/.py
    User->>JL: hook.register()
    JL->>MCP: 写入 ~/.jupyter-mcp/current
    Note over GW: 配置 mcp.servers.jupyter-mcp
    GW->>MCP: spawn 进程 (stdio mode)
    MCP->>JL: 读取注册文件，ZMQ 连接 kernel
    MCP-->>GW: 返回工具列表 (listTools)
    
    Note over User,GW: AI 分析会话
    User->>GW: "分析这组数据"
    GW->>AI: 调用 LLM
    AI->>GW: 生成分析代码
    GW->>MCP: callTool(run_code, {code})
    MCP->>JL: execute(code) via ZMQ
    JL-->>MCP: 返回执行结果
    MCP-->>GW: 格式化输出
    GW-->>User: 显示分析结果
```

### OpenClaw 配置

``` json
{
  "mcp": {
    "servers": {
      "jupyter-mcp": {
        "command": "/usr/lib64/anaconda3/envs/graphrag/bin/python3",
        "args": [
          "/home/openclaw/.openclaw/workspace/jupyter_mcp/jupyter-mcp-server.py"
        ]
      }
    }
  }
}
```

### HTTP/SSE 模式

除了默认的 stdio 模式，MCP Server 还支持 HTTP/SSE 模式：

``` bash
export JUPYTER_MCP_PORT=8765
python3 jupyter-mcp-server.py
# 启动在 http://127.0.0.1:8765/sse
```

HTTP 模式依赖 `uvicorn` 和 `starlette`，适用于远程连接场景。

------------------------------------------------------------------------

## 七、R ↔ Python 数据交换详解

### 设计理念

-   跨 session 传的**只限小数据集**，大数据集在该 session 原地处理
-   **只用 CSV** — R 和 Python 都原生支持，方案最简单通用
-   CSV 类型可能失真，但小数据集一两个 `astype()` 就修好了

### 架构

```         
R Session → R API (httpuv) → r-session-mcp (Python) → CSV
                                                         ↓
Jupyter Kernel ← jupyter-mcp (Python) ← CSV
```

### 类型保真实测

**Python → R（`data.table::fread`）：** 所有类型无损 ✅

| Python            | R          | CSV 中间格式          |
|-------------------|------------|-----------------------|
| int64             | integer    | `1`                   |
| float64           | numeric    | `10.5`                |
| object (str)      | character  | `Alice`               |
| bool              | logical    | `True` / `False`      |
| datetime64 (日期) | IDate/Date | `2026-06-07`          |
| datetime64 (时间) | POSIXct    | `2026-06-07 10:30:00` |

**R → Python（`pd.read_csv`）：** 日期/时间丢字符串 ❌（需 `pd.to_datetime()` 修复）

### 共享目录

```         
默认: ~/.openclaw/workspace/r2py/（各用户工作区下，天然隔离）
覆盖: R2PY_SHARED_DIR 或 JUPYTER_SHARED_DIR 环境变量
文件名: UUID 前缀 + .csv
```

------------------------------------------------------------------------

## 八、项目文件清单

```         
jupyter_mcp/
├── __init__.py              # 包初始化
├── hook.py                  # kernel 注册函数（在 JupyterLab cell 中运行）
├── jupyter-mcp-server.py    # MCP Server（OpenClaw 管理）
├── setup.py                 # 可编辑安装配置（pip install -e .）
├── README.md                # 快速入门文档
├── jupyter-mcp-architecture.md  # 本文档
└── auto_reload.js           # auto-reload 扩展独立 JS 版本（注入式）

jupyterlab-auto-reload/      # Notebook 自动刷新扩展（工程构建版）
├── package.json
├── src/index.ts
├── jupyterlab_auto_reload/
│   └── labextension/        # 构建产物
└── setup.py

jupyterlab-console-adopt/    # Console 外部 Session 捕获扩展
├── package.json
├── src/index.ts
├── jupyterlab_console_adopt/
│   └── labextension/        # 构建产物
└── tsconfig.json
```

------------------------------------------------------------------------

## 九、已知限制与注意事项

1.  **JupyterLab 版本差异**：JupyterHub-singleuser 可能跑在 base conda 环境（4.x），扩展需装到对应环境的 `labextensions` 路径
2.  **Console Session 隔离**：Console 不显示外部 Session 的执行结果是 JupyterLab 的设计限制，`console-adopt` 扩展通过监听原始 IOPub 信号绕过
3.  **绘图输出**：matplotlib 图表通过 `display_data` 消息传递 base64 PNG，在 Console 中以图片方式渲染
4.  **内核切换**：切换 kernel 需重新运行 `hook.register(force=True)`
5.  **只能连接一个 kernel**：注册文件 `~/.jupyter-mcp/current` 是单文件，后注册的会覆盖之前的
6.  **代理干扰**：Jupyter Server 在本地运行，REST API 调用需临时屏蔽 `http_proxy` 环境变量
7.  **连接文件重建**：kernel 重启后原始连接文件可能被清理，MCP Server 会从注册文件中的 `connection` 字段重建临时连接文件

------------------------------------------------------------------------

## 十、变更日志

| 日期 | 变更内容 |
|------------------------------------|------------------------------------|
| 初始版 | 基础架构、ZMQ 连接、kernel 注册、run_code/list_objects/preview_data |
| v2 | 新增 NotebookClient（REST API 操作 cell）、auto-reload 扩展 |
| v3 | 新增 console-adopt 扩展（外部 Session 显示） |
| v4 | 新增 export_data/import_data（R↔Python 数据交换）、HTTP/SSE 模式 |
| v5 | 环境变量化配置（HOST/PORT/TIMEOUT/REGISTER/SHARED_DIR）、代理回避、连接文件重建、shebang 改为 graphrag 环境 |
