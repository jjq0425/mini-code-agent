# Mini Code Agent (LangGraph + DashScope)

基于 LangGraph 构建的 code agent，使用阿里云百炼 DashScope 兼容模式 API。

## 功能

- 通过 LangGraph ReAct agent 调用工具。
- 内置工具：读文件、写文件、执行 bash 命令。
- 使用 `uv` 管理依赖与运行。

## 安装

```bash
uv sync
```

若使用了 SOCKS 代理，请确保已安装 `httpx[socks]` 依赖（本项目已包含）。  

## 配置环境变量

```bash
export DASHSCOPE_API_KEY="sk-xxx"
```

如需加载 MCP 工具，可配置以下地址（可同时设置）：  

```bash
export MCP_FEISHU_URL="http://127.0.0.1:8000"
export MCP_SANDBOX_URL="http://127.0.0.1:9000"
```

## 运行示例

```bash
uv run code-agent "请列出当前目录下的文件"
```

或直接运行模块：

```bash
uv run python -m code_agent.main "请读取 README.md 并总结"
```

## 代码结构

- `src/code_agent/tools.py`：封装文件读写与 bash 工具。
- `src/code_agent/agent.py`：创建 LangGraph agent。
- `src/code_agent/main.py`：命令行入口。


## Env配置
飞书MCP：https://open.feishu.cn/page/mcp/7599298337598835670
