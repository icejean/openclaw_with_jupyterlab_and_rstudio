# OpenClaw + JupyterLab + RStudio

> Fast-Python-AI 数据分析解决方案，平替 Posit AI

一个集成了 **OpenClaw AI Agent**、**JupyterLab (Python)** 和 **RStudio (R)** 的一体化数据分析开发环境。

## 架构

| 组件 | 用途 |
|---|---|
| **OpenClaw** | AI 代理框架，连接用户 ↔ 工具 ↔ LLM |
| **JupyterLab + MCP** | Python 交互式数据分析 |
| **RStudio + R API** | R 语言数据分析 |
| **r2py** | R ↔ Python 跨语言数据交换 |

## 快速开始

### 前置要求

- Python 3.10+
- Conda
- R 4.x + RStudio
- Node.js 18+

### 安装

```bash
# 克隆仓库
git clone https://github.com/icejean/openclaw_with_jupyterlab_and_rstudio.git
cd openclaw_with_jupyterlab_and_rstudio

# 查看各组件 README
```

## 项目结构

```
openclaw_with_jupyterlab_and_rstudio/
├── jupyter_mcp/          # Jupyter MCP Server
├── r-session-ai/         # R Session API
├── labextensions/        # JupyterLab 自定义扩展
├── openclaw.json         # OpenClaw 配置
└── MEMORY.md             # 项目文档
```

## 数据交换

Python ↔ R 之间通过 CSV 文件在 `r2py/` 共享目录交换数据，实现跨语言数据流。

## License

MIT
