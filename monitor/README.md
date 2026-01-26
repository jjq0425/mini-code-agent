# LangGraph 运行监控示例

此目录提供一个最小示例，演示如何通过 LangGraph/LangChain callbacks 监听 Agent 在运行时的“用户态”信息：

- **参数与输入**：在 `on_chain_start`、`on_chat_model_start` 中记录输入参数。
- **工具调用**：在 `on_tool_start`/`on_tool_end` 中记录工具名称、输入和输出。
- **Agent 的思考过程**：通过 `on_chat_model_start` 记录模型收到的消息（可包含系统、用户、历史上下文）。

> 注意：若你不希望记录具体消息内容，可将 `AgentEventLogger(capture_messages=False)` 以禁用消息捕获。

## 使用方式

```python
from langgraph.graph import StateGraph
from monitor.langgraph_monitor import AgentEventLogger

# 假设你已有 graph
handler = AgentEventLogger(capture_messages=True)
result = graph.invoke({"messages": ["你好"]}, config={"callbacks": [handler]})

# 访问事件
for event in handler.events:
    print(event.event, event.payload)
```

## 辅助函数

`monitor/langgraph_monitor.py` 中提供 `attach_callbacks`，用于一行调用并返回结果与事件：

```python
from monitor.langgraph_monitor import attach_callbacks

result, events = attach_callbacks(graph, {"messages": ["你好"]})
```

