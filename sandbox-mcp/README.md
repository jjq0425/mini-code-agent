# Sandbox MCP Tool

一个基于 `mcp` 的简单沙箱 MCP server，用于在受控目录下执行 Python3 代码。

## 安装

在项目根目录安装依赖：

```bash
uv sync
```

或使用 `pip`：

```bash
pip install -e .
```

> 说明：`mcp` 依赖会随着项目依赖一起安装。

## 启动

```bash
python3 sandbox-mcp/server.py
```

默认沙箱目录为 `sandbox-mcp/sandbox`。

### 自定义沙箱目录

```bash
export SANDBOX_ROOT="/path/to/your/sandbox"
python3 sandbox-mcp/server.py
```

## 可用工具

- `run_python(code, timeout_s=5)`：在沙箱目录中运行 Python3 代码并返回 stdout/stderr。

## 示例

```bash
python3 sandbox-mcp/server.py
```

在 MCP client 中调用 `run_python`：

```json
{
  "code": "print('hello from sandbox')",
  "timeout_s": 5
}
```
