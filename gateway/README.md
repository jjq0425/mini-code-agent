# Helicone Gateway

使用 [Helicone](https://github.com/Helicone/helicone) 搭建 LLM Gateway，实现**请求追踪、监控与分析**。该网关位于模型供应商（如 OpenAI）与业务代码之间，统一透传请求并记录调用信息，便于后续在 Helicone UI 中检索、回放与分析。

---

## 目录结构

```
./gateway
├── README.md          # 网关搭建与使用说明（本文件）
└── bootstrap.sh       # 一键拉取 Helicone 并启动（可选）
```

---

## 先决条件

- **Docker + Docker Compose**（推荐 v2）
- **Git**

---

## 快速开始（推荐）

> 该方式直接使用 Helicone 官方仓库的部署配置。

1. **拉取 Helicone 源码**

   ```bash
   cd gateway
   git clone https://github.com/Helicone/helicone.git
   ```

2. **配置环境变量**

   进入 `helicone/` 目录后，复制其示例环境文件并编辑：

   ```bash
   cd helicone
   cp .env.example .env
   ```

   然后根据你的环境填写（数据库、ClickHouse、JWT 密钥、OpenAI Key 等）。
   > 不同版本的 Helicone 环境变量可能会调整，请以 Helicone 官方仓库内的 `.env.example` 为准。

3. **启动 Helicone**

   ```bash
   docker compose up -d
   ```

4. **验证服务状态**

   ```bash
   docker compose ps
   ```

   常见默认端口（如与上游一致）：
   - **Helicone UI**：`http://localhost:3000`
   - **Helicone Proxy/Gateway**：`http://localhost:8787/v1`

> 如端口与实际不一致，请以 `docker compose ps` 或 Helicone 官方配置为准。

---

## 一键启动（可选）

`gateway/bootstrap.sh` 会自动完成 **克隆仓库 → 复制 .env.example → 启动容器**：

```bash
cd gateway
bash bootstrap.sh
```

> 首次启动前仍需编辑 `gateway/helicone/.env` 填写关键参数。

---

## 接入方式（在业务代码中使用 Gateway）

Helicone Gateway 对接方式与 OpenAI SDK 类似，只需：
1. **替换 API Base URL 为网关地址**
2. **附加 Helicone 认证头**（使用 UI 中生成的 API Key）

### 示例：curl

```bash
curl https://localhost:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Helicone-Auth: Bearer $HELICONE_API_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "你好，Helicone"}]
  }'
```

### 示例：Python（OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    api_key="<OPENAI_API_KEY>",
    base_url="http://localhost:8787/v1",
    default_headers={
        "Helicone-Auth": "Bearer <HELICONE_API_KEY>",
    },
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "通过网关追踪"}],
)
print(response.choices[0].message.content)
```

---

## ModelScope 适配

如果你使用 **ModelScope（通义系列 / 开源模型 / OpenAI 兼容 API）**，依旧可以通过 Helicone Gateway 进行追踪与监控，核心做法是：

1. **请求仍指向 Helicone Gateway**（如 `http://localhost:8787/v1`）。  
2. **Authorization 使用 ModelScope 的 API Key**（而非 OpenAI Key）。  
3. **保持 `Helicone-Auth` 头部不变**，用于写入 Helicone 追踪数据。  

> 前提：ModelScope 提供 OpenAI 兼容接口时，Helicone 可作为透明代理使用。若你使用的是非 OpenAI 兼容接口，需要在上游 SDK 或路由层做适配。

### 示例：Python（OpenAI SDK + ModelScope Key）

```python
from openai import OpenAI

client = OpenAI(
    api_key="<MODELSCOPE_API_KEY>",
    base_url="http://localhost:8787/v1",
    default_headers={
        "Helicone-Auth": "Bearer <HELICONE_API_KEY>",
    },
)

response = client.chat.completions.create(
    model="qwen-plus",
    messages=[{"role": "user", "content": "通过 Helicone 追踪 ModelScope 请求"}],
)
print(response.choices[0].message.content)
```

### 示例：curl

```bash
curl http://localhost:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MODELSCOPE_API_KEY" \
  -H "Helicone-Auth: Bearer $HELICONE_API_KEY" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "通过 Helicone 追踪 ModelScope"}]
  }'
```

---

## 常见问题

1. **无法访问 UI 或 Gateway**
   - 先确认容器是否全部健康：`docker compose ps`
   - 查看 Helicone 代理服务端口映射是否正确

2. **请求未在 UI 中展示**
   - 确认请求走的是 Helicone Gateway 地址
   - 确认 `Helicone-Auth` 是否正确
   - 若使用 ModelScope，确认 `Authorization` 使用的是 ModelScope API Key

3. **版本差异导致环境变量变化**
   - 以 Helicone 官方仓库中的 `.env.example` 为准
   - 更新后重新 review 配置

---

## 说明

本目录仅提供 Helicone Gateway 的**集成与启动流程**说明，运行参数与部署细节以 Helicone 官方仓库为准。
如需完整部署能力、扩展存储或自定义策略，请参考：
- <https://github.com/Helicone/helicone>
