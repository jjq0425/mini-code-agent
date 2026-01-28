# Mini Code Agent

```
   ███╗   ███╗██╗███╗   ██╗██╗     █████╗ ██████╗
   ████╗ ████║██║████╗  ██║██║    ██╔══██╗██╔══██╗
   ██╔████╔██║██║██╔██╗ ██║██║    ███████║██████╔╝
   ██║╚██╔╝██║██║██║╚██╗██║██║    ██╔══██║██╔══██╗
   ██║ ╚═╝ ██║██║██║ ╚████║██║    ██║  ██║██║  ██║
   ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝    ╚═╝  ╚═╝╚═╝  ╚═╝
```

> **工程化 + 学术风的最小可用 Code Agent**：以 LangGraph 为核心编排，引入 DashScope 兼容模式 API，面向可靠、可复现实验与工程落地。

---

## 项目概述

**Mini Code Agent** 是一个轻量、可扩展的 Code Agent 框架，主打 **工程可复用** 与 **研究可验证**：

- **工程化**：以 `uv` 作为依赖与运行管理器；提供稳定的 CLI 入口与脚本化调用方式。
- **学术范式**：清晰划分 Agent、工具与执行入口，便于对比不同提示策略、工具集成方案与图结构变体。
- **可扩展性**：原生支持 MCP（Model Context Protocol）工具接入，便于扩展外部系统能力。

---

## 功能特性

- **LangGraph ReAct Agent**：基于图结构组织推理与工具调用流程。
- **内置工具集**：文件读写、执行 bash 命令（便于最小闭环实验）。
- **DashScope 兼容模式**：可直接使用阿里云百炼 API 进行推理调用。
- **可选 MCP 接入**：支持飞书等生态工具连接，形成“能力外延”。

---

## 安装与环境准备
### 0) 预先准备

- 在运行或安装依赖前，务必先激活 Python 虚拟环境（venv）。
  - 创建并激活（在根目录）：
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```
### 1) 安装依赖

```bash
uv sync
```



### 2) 配置环境变量

- 配置环境变量：复制并编辑模板 `.env.template` 为 `.env`

> 具体说明参考.env.template


---

## 运行示例

### Part1：CLI 快速调用【不推荐】

```bash
uv run code-agent "请列出当前目录下的文件"
uv run python -m code_agent.main "请读取 README.md 并总结"
```

> 推荐使用带Hook监控的运行

### Part2：带Hook监控的运行模块【推荐】

```bash
python -m monitor.run_agent_with_monitor "你的问题"
```
### Part3：运行sandbox-mcp 【使用代码运行MCP时必须】
请另外启动一个终端进程：
```bash
python3 sandbox-mcp/server.py
```

---

## 代码结构

```
mini-code-agent/
├── src/
│   └── code_agent/
│       ├── agent.py        # LangGraph Agent 组织与构建
│       ├── tools.py        # 文件读写、bash 等工具封装
│       └── main.py         # CLI 入口与运行逻辑
├── pyproject.toml          # 依赖与运行配置
└── README.md               # 项目说明文档
```

---

## 设计理念（Academic Notes）

- **可复现性（Reproducibility）**：依赖由 `uv` 锁定，减少实验环境漂移。
- **可扩展性（Extensibility）**：工具与 Agent 逻辑解耦，便于替换提示模板或模型后端。
- **可解释性（Interpretability）**：以图结构呈现 Agent 行为路径，适合教学与研究复现。

---

## MCP 生态与拓展

本仓库提供两个MCP入口：


- 飞书 MCP 入口：
    - 远程MCP，提供飞书文档读写能力，**MCP Server部署在飞书侧**
    - 具体说明请参考<https://open.feishu.cn/page/mcp/7599298337598835670>
    - 若需获取接入链接，请私聊
- 代码运行 MCP(即sandbox-mcp目录下):
    - 远程MCP，提供Python代码运行能力，**MCP Server部署在本机侧，但仍需通过MCP交互**



---

## 许可与致谢

本项目以轻量实现为主，旨在为**工程实践**与**学术实验**提供统一起点。欢迎扩展、复用与提出改进建议。

## Contributor

@jjq0425; @xiaoxuan668
