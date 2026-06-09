# 端到端示例：墨尔本房价预测

> 传统机器学习（LightGBM）与 大模型 AI（OpenClaw）的深度融合
>
> 全程在手机端个人微信中指挥 OpenClaw 完成，零代码手动编写。

## 数据来源

墨尔本房价数据集来自 [Kaggle：Melbourne Housing Market](https://www.kaggle.com/datasets/anthonypino/melbourne-housing-market)，包含约 35,000 条房产交易记录，涵盖 Suburb、Rooms、Price、Distance、Landsize、BuildingArea 等 20+ 个字段。

数据由 Domain.com.au 公开信息整理，时间跨度至 2018 年 5 月。

## 项目文件

| 文件 | 说明 |
|----|----|
| `Melbourne_housing_FULL.csv` | Kaggle 原始数据集（约 35,000 行，含缺失值） |
| `Melbourne_housing_Pre.py` | 数据预处理 Python 程序：缺失值填充、特征工程（房价对数变换、年份/类型编码等）、异常值筛选 |
| `Melbourne_housing_pre.csv` | 预处理后的干净数据集（约 9,000 行，14 个特征） |
| `Melbourne_housing_LGBM.py` | LightGBM 回归模型训练与调优程序（含 Bayesian Optimization + Hyperopt 完整调优流程） |
| `demo-1.png` ~ `demo-22.png` | 全程手机微信指挥 OpenClaw 完成分析的 22 步截图 |

## 工作流

### 传统 ML 部分（本地脚本）

预处理和模型调优是**事先准备好的传统机器学习代码**，体现了传统 ML 工程的深度：

```
原始数据 (35k rows)
    │
    ▼
Melbourne_housing_Pre.py          ← 数据预处理（932 行）
    │  • 缺失值填充（Rooms、Bedroom2、Bathroom、Car、Landsize、BuildingArea、YearBuilt）
    │  • 特征工程：价格对数变换 (LogPrice)、年份提取、房屋类型 one-hot 编码
    │  • 数据筛选：剔除空值、异常值
    │  • 排除字段：Address、SellerG、Date、CouncilArea、Regionname 等非数值型
    ▼
预处理后数据 (9k rows, 14 features)
    │
    ▼
Melbourne_housing_LGBM.py         ← 模型训练与调优（558 行）
    │  • 多种模型对比: LightGBM、XGBoost、RandomForest、SVM
    │  • 超参数调优: Bayesian Optimization + Hyperopt
    │  • 特征重要性分析: SHAP
    │  • 异常值剔除策略: 训练集 20% 偏差剔除
    │  • 评估指标: MSE、MAE、RMSE、R²
    ▼
训练好的 LightGBM 模型
```

### LLM AI 部分（OpenClaw 指挥）

上述传统 ML 代码就位后，在**手机上用微信指挥 OpenClaw** 完成整个数据分析流程（注意：demo 中 LightGBM 使用默认参数简单拟合，超参数调优不在此范围内）：

```
步骤 1-7:  RStudio 探索数据
    用户 → "加载墨尔本房价预处理好数据"
    OpenClaw → r-session.run_code 加载 CSV
            → r-session.run_code 绘图（分布/相关性/散点图矩阵）
            → 用户在手机上看图

步骤 8:   R → CSV 导出
    OpenClaw → r-session.export_data("df_ml")
            → CSV 写入 r2py/ 共享目录

步骤 9-10: Jupyter Lab 导入数据
    OpenClaw → jupyter-mcp.import_data(...)
    OpenClaw → jupyter-mcp.run_code 执行 LightGBM 训练脚本
            → 默认参数拟合模型
            → 用测试集预测

步骤 18:  Python → CSV 导出
    OpenClaw → jupyter-mcp.export_data("results")
            → 真实值 vs 预测值写入 CSV

步骤 19-22: RStudio 结果可视化
    OpenClaw → r-session.import_data(...)
            → r-session.run_code 绘制真实值 vs 预测值对比图
            → 用户在手机上看到最终效果
```

### OpenClaw 扮演的角色

```
┌────────────────────────────────────────────────────────────────┐
│                    微信（手机端）                               │
│  用户 ↔ 自然语言对话 ↔ OpenClaw                                 │
└──────────┬─────────────────────────────────────────────────────┘
           │
  ┌────────▼────────┐
  │  OpenClaw Agent │  ← 翻译自然语言 → MCP 工具调用
  │  (embedded)     │
  └────────┬────────┘
           │
     ┌─────┴─────┐
     │           │
  ┌──▼──┐   ┌───▼───┐
  │  R  │   │Python │   ← 传统 ML 能力
  │mcp  │   │ mcp   │
  │     │   │       │
  │EDA  │   │LightGBM│
  │作图 │   │默认参数│
  └─────┘   └───────┘
```

1. **胶水层** — 连接 R 的 EDA 能力和 Python 的 ML 能力，让两个生态无缝协作
2. **翻译官** — 把用户自然语言指令（"帮我看看数据长什么样"）翻译成精确的 MCP 工具调用
3. **调度器** — 编排跨语言数据流（R → CSV → Python → CSV → R），管理数据交换
4. **远程控制器** — 把手机微信变成 AI 分析终端的入口，随时随地下指令

## 示例的价值

这个示例展示了两种 AI 的融合：

| AI 类型 | 作用 | 在本示例中 |
|----|----|----|
| **传统机器学习 AI** | 数据拟合、预测、优化 | 数据预处理、LightGBM 回归模型、Bayesian 超参数调优、SHAP 特征分析 |
| **大模型 AI (LLM)** | 理解自然语言、调度工具、编排流程 | OpenClaw 理解用户意图、调用 MCP 工具、管理跨语言数据流转 |

> 传统 ML 提供**精确的数值预测能力**，大模型 AI 提供**灵活的理解与调度能力**。两者不是替代关系，而是互补关系。

## 步骤

| 步骤 | 截图 | 说明 |
|----|----|----|
| 1 | ![demo-1](demo-1.png) | 在微信中对话 OpenClaw，要求加载墨尔本房价数据 |
| 2 | ![demo-2](demo-2.png) | RStudio 加载已预处理的 Melbourne housing 数据集 |
| 3 | ![demo-3](demo-3.png) | 预览数据结构、列名、类型 |
| 4 | ![demo-4](demo-4.png) | 统计摘要——均值、中位数、分位数等 |
| 5 | ![demo-5](demo-5.png) | 绘图——房价分布直方图（RStudio Plots 面板） |
| 6 | ![demo-6](demo-6.png) | 绘图——各特征与房价的散点图矩阵 |
| 7 | ![demo-7](demo-7.png) | 相关性分析热力图 |
| 8 | ![demo-8](demo-8.png) | 将处理后的数据从 R 导出到 CSV |
| 9 | ![demo-9](demo-9.png) | Python 端从 CSV 导入数据到 Jupyter kernel |
| 10 | ![demo-10](demo-10.png) | 预览 Python 中的 DataFrame，确认数据完整 |
| 11 | ![demo-11](demo-11.png) | 划分训练集（80%）和测试集（20%） |
| 12 | ![demo-12](demo-12.png) | 安装并导入 LightGBM |
| 13 | ![demo-13](demo-13.png) | 在训练集上拟合 LightGBM 回归模型 |
| 14 | ![demo-14](demo-14.png) | 模型训练完成，查看特征重要性 |
| 15 | ![demo-15](demo-15.png) | 用测试集进行预测 |
| 16 | ![demo-16](demo-16.png) | 评估预测效果——RMSE、MAE、R² 等指标 |
| 17 | ![demo-17](demo-17.png) | 整理真实值 vs 预测值为 DataFrame |
| 18 | ![demo-18](demo-18.png) | 将预测结果从 Python 导出到 CSV |
| 19 | ![demo-19](demo-19.png) | R 端从 CSV 导入预测结果 |
| 20 | ![demo-20](demo-20.png) | RStudio 中预览预测结果数据框 |
| 21 | ![demo-21](demo-21.png) | 作图——真实房价 vs 预测房价散点图 |
| 22 | ![demo-22](demo-22.png) | 完成！全程微信遥控，零代码手动编写 |

## 涉及的工具

| 步骤 | 使用的 MCP 工具 | 说明 |
|----|----|----|
| 2-7 | `r-session.list_objects`, `preview_data`, `run_code` | R 端数据探索与可视化 |
| 8 | `r-session.export_data` | R → CSV 导出 |
| 9-10 | `jupyter-mcp.import_data`, `preview_data` | CSV → Python 导入 |
| 11-17 | `jupyter-mcp.run_code`, `list_objects` | Python 端建模与预测 |
| 18 | `jupyter-mcp.export_data` | Python → CSV 导出 |
| 19-22 | `r-session.import_data`, `run_code` | CSV → R 导入，作图 |
