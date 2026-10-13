# 弈宝 · 王者万象棋问答 Agent

一个有来源、能追问的新手训练向导。FastAPI + 原生 HTML/JS + Qdrant 本地向量数据库，使用 BGE 中文嵌入模型，无需 Docker 或额外嵌入 API。

**当前状态：Wiki公开栏目全量快照已接入，真实模型先生成检索词再回答；10类真实检索抽查通过。模型回答质量尚未完成独立验收，详见[知识库与检索说明](docs/full-wiki.md)。**

## 快速运行（PowerShell / Python 3.11+）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

编辑 `.env`，配置支持 Chat Completions 的服务。Base URL 应包含服务要求的 API 前缀，程序会在末尾追加 `/chat/completions`。

```dotenv
AGENT_MODE=live
RETRIEVAL_BACKEND=vector
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
REQUEST_TIMEOUT_SECONDS=45
LLM_MAX_TOKENS=700
LLM_PLANNER_MAX_TOKENS=2000
LLM_PLANNER_TIMEOUT_SECONDS=20
```

密钥只放后端 `.env`，该文件已忽略。无需将密钥交给网页。环境变量优先于 `.env`；如果此前在终端设置过 Mock，先运行 `Remove-Item Env:AGENT_MODE -ErrorAction SilentlyContinue`。修改配置后重启服务。

生成模型返回 `finish_reason=length` 时，后端会将输出预算提高到 4000 token 重试一次（首次已经是 4000 时不重试），两次调用共用原有生成阶段超时。推理模型的推理过程也可能占用输出预算；重试会增加调用费用和耗时。再次截断会返回 `model_output_truncated`，不会展示不完整答案。

```powershell
.\.venv\Scripts\python.exe -m scripts.index_knowledge
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次索引会下载 `BAAI/bge-small-zh-v1.5` 并向量化全部知识。之后启动复用本地数据库；更新 Wiki 后停止后端，重新运行索引命令再启动。模型缓存位于 `data/models/`，数据库位于 `data/vector/`，均不提交 Git。原始 JSON 保留作核验与重建材料。详见[向量检索说明](docs/vector-retrieval.md)。

本地 Qdrant 仅支持一个进程打开同一目录，请保持单 worker，索引时先停止后端。`RETRIEVAL_BACKEND=lexical` 可显式切回旧检索作对照；向量索引缺失或过期时会明确报错，不会静默回退。

访问 <http://127.0.0.1:8000>，接口说明 <http://127.0.0.1:8000/docs>。默认仅绑定本机；本 Demo 没有面向公网的鉴权和限流。

没有模型时，可以明确选择 Mock 验证交互：

```powershell
$env:AGENT_MODE="mock"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

网页和每条回答都会显示 Mock 标识。Mock 只拼接检索资料，不会伪装成真实推理。`/api/health` 的 `model_configured` 只表示配置齐全，不保证服务可达。

## 测试与评测

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 单独验证模型检索规划与全量Wiki命中；不会调用回答生成
.\.venv\Scripts\python.exe -m eval.wiki_eval --live --output eval/reports/query-live.json
# 默认真实评测；没有模型配置会明确退出，不生成虚假的真实结果
.\.venv\Scripts\python.exe -m eval.run --mode live
# 可重复的本地链路检查
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant baseline --split development
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant enhanced --split development
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant enhanced --split holdout
# 重新核对官网关键事实并记录页面指纹，需要联网
.\.venv\Scripts\python.exe scripts/verify_sources.py
```

固定数据集共 32 个案例、36 个请求轮次，含两组三轮追问。评测会调用与网页相同的 `Agent.chat`，逐轮保留真实返回，绝不向被测 Agent 传入评分规则或预期答案。本轮结果在 `eval/reports/2026-10-13-layered/`；情境Mock为0/4，准确反映其没有真实建议能力。后续默认结果在 `eval/reports/`，同一模式/变体/分区重跑会覆盖同名报告；需要保留实验请指定 `--output eval/reports/experiment-name`。

新检索最多返回6条，报告输出Recall@6及查询规划耗时；旧报告保留原口径。调用失败仍会影响旧评测器的意图/检索分数，不能据此断定相应阶段本身错误。规则评分不能完整判断幻觉、复杂否定和策略质量，仍需对真实模型结果做人工抽查。

## 接口示例

```json
POST /api/chat
{
  "message": "那他的秘技呢？",
  "history": [
    {"role": "user", "content": "白歌的技能是什么？"},
    {"role": "assistant", "content": "白歌通过英雄合成获得即兴创作。"}
  ]
}
```

返回 `answer`、`intent`、`status`、`sources`、`retrieved_ids`、`retrieval_plan`、`latency_ms`、`timings_ms`、`mode`、`model_used` 和 `request_id`。`retrieval_plan`记录模型生成的查询、关键词、实体、模式及回退状态。四类意图为 `knowledge/advice/chitchat/out_of_scope`；状态为 `answered/needs_clarification/insufficient_evidence/unsupported`。异常返回 `{"error":{"code":"…","message":"…"}}`，不回显模型服务原始错误或密钥。

问题限制 1—1000 字；历史最多12条、合计12000字，实际模型历史保留最近6000字；不接受客户端 system 消息。知识引用链接由后端依据入库记录生成。网页历史仅存内存，刷新或清空后消失。

## 资料与设计

- `data/knowledge.json`：原有30条官网基础知识。
- `data/wiki/records.json`：7701条Wiki片段，运行时与30条官网基础知识合计7731条；普通检索排除待确认项，模式和历史版本分开处理。
- `data/wiki/snapshot.json.gz`、`coverage.json`：完整结构化来源快照、栏目与对象覆盖审计，站内搜索索引924项无缺项。
- `data/wiki/tool-snapshots/`：85个英雄的全等级装备价值模型数据，条件化读取，不作为实战保证。
- `data/wzwxq.json`：早期58条导入结果，仅保留作历史审计，已由全量库替代。
- [当前知识库构建、更新与查询流程](docs/full-wiki.md)。
- [本轮导入审计](docs/wzwxq-import.md)与[情境评分v2](eval/advice-rubric.md)。
- `data/source_audit.json`：两张官方页面指纹和11项关键事实检查。
- [资料核验记录](docs/knowledge-audit.md)：来源、冲突、纳入/排除边界。
- [设计与验证记录](docs/design.md)：实现取舍、评测结果和未完成项。
- `requirements-lock.txt`：本次 Windows / Python 3.11.5 环境的完整依赖快照；精确复现可安装该文件。

支持的模型协议为非流式 Chat Completions，模型须按提示输出 JSON。不同厂商的鉴权、参数及结构化输出能力仍需实际联调；当前未承诺所有兼容服务都能直接使用。

名称已统一为“弈宝”。历史报告保持当时输出。当前全量资料离线重建：`python scripts/build_wiki.py --from-snapshot`，联网刷新与解析步骤见上述说明。
