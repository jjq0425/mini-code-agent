``python
from monitor.langgraph_monitor import AgentEventLogger

# 假设你已有 graph
handler = AgentEventLogger(capture_messages=True)
result = graph.invoke({"messages": ["你好"]}, config={"callbacks": [handler]})

# 访问事件
for event in handler.events:
    print(event.event, event.payload)
```

## 直接运行示例脚本

如果你希望直接运行一个示例脚本，可以使用：

```bash
python -m monitor.run_agent_with_monitor "你的问题"
```

该脚本会调用 `build_agent()` 并在 `graph.invoke(...)` 中挂载 callback。

## 辅助函数

`monitor/langgraph_monitor.py` 中提供 `attach_callbacks`，用于一行调用并返回结果与事件：

```python
from monitor.langgraph_monitor import attach_callbacks

result, events = attach_callbacks(graph, {"messages": ["你好"]})
```