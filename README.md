# 弈宝 · 王者万象棋问答 Agent

一个有来源、能追问的新手训练向导。FastAPI + 原生 HTML/JS + Qdrant 本地向量数据库，使用 BGE 中文嵌入模型，无需 Docker 或额外嵌入 API。

**当前状态：大模型在一次调用中完成意图分类和检索规划，使用本地向量库按需检索；引用问题不再阻断回答。来源区展示核验过的引文或标明供参考的入库原文，不展示虚构来源。已做真实对话与耗时回归；小样本通过不代表完整语义质量验收，详见[改造与实测](docs/agent-upgrade.md)。**

## 快速运行（PowerShell / Python 3.11+）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
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
LLM_THINKING=auto
```

密钥只放后端 `.env`，该文件已忽略。无需将密钥交给网页。环境变量优先于 `.env`；如果此前在终端设置过 Mock，先运行 `Remove-Item Env:AGENT_MODE -ErrorAction SilentlyContinue`。修改配置后重启服务。

`LLM_THINKING=auto` 对名称包含 DeepSeek 的模型发送 `thinking.type=disabled`，减少短问答的推理等待；其他模型不额外发送该参数。`enabled/disabled` 可显式配置服务支持的行为。DeepSeek 还启用 JSON 输出格式；当前已配置的代理服务通过真实调用验证，不代表任意服务兼容。既有 `.env` 无需更换密钥即可使用默认优化。

生成结果中的短引文、重复编号、缺失或不匹配引文不再导致整段回答失败。已知来源的不匹配片段改为展示对应资料真实原文，并标注供参考；未知来源省略，正文保留。纯文本回答、JSON中完整正文之后损坏的引用字段也可恢复。没有可用正文时最多自动重试一次；截断时重试预算为4000 token，两次共用生成阶段超时。仍失败或接口异常时，有检索证据则返回资料摘录（`partial_answer`），并说明尚未完成模型整理。前端网络/服务异常使用普通对话气泡与保留原问题的重试按钮，不显示红框。

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
# 本轮9个真实场景回归（含模型分类、引用原文、阶段耗时，会调用API）
.\.venv\Scripts\python.exe -m eval.upgrade_eval
# 可重复的词法基线对照（向量后端下不是纯词法基线实验）
$env:RETRIEVAL_BACKEND="lexical"
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant baseline --split development
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant enhanced --split development
.\.venv\Scripts\python.exe -m eval.run --mode mock --variant enhanced --split holdout
Remove-Item Env:RETRIEVAL_BACKEND
# 重新核对官网关键事实并记录页面指纹，需要联网
.\.venv\Scripts\python.exe scripts/verify_sources.py
```

固定数据集共 32 个案例、36 个请求轮次，含两组三轮追问。评测会调用与网页相同的 `Agent.chat`，逐轮保留真实返回，绝不向被测 Agent 传入评分规则或预期答案。`2026-10-13-layered/` 是历史 Mock 报告，`2026-10-13-live/` 是历史真实模型报告；当前向量检索专项在 `eval/reports/2026-10-13-vector/`，10/10命中未调用回答模型，不能作为新版回答正确率。固定集仍需更新部分模式边界和等价证据标签，详见[作业要求对照与缺口](docs/project-audit.md)。同一模式/变体/分区重跑会覆盖同名报告；保留实验请指定 `--output eval/reports/experiment-name`。

使用向量后端独立评测前先停止网页后端，避免两个进程占用同一个本地数据库。

基础检索最多6条，情境建议可额外补充最多2条触发时点定义。新响应记录 `client_setup/intent_planning/retrieval/generation`；生成失败保留已完成的意图和检索结果，模型调用日志计入分类、生成、失败和重试。历史报告沿用旧口径。规则评分与引用逐字校验不能完整判断幻觉或策略推论，仍需人工核对。

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

返回 `answer`、`intent`、`status`、`sources`、`retrieved_ids`、`retrieval_plan`、`routing`、`model_calls`、`latency_ms`、`timings_ms`、`mode`、`model_used` 和 `request_id`。`routing`记录模型分类或故障回退，`retrieval_plan`记录查询、关键词、实体与模式，`model_calls`记录各次调用耗时及服务返回的token计数（不含密钥或思考文本）。`sources[].excerpt`始终取自入库原文，`excerpt_kind=quote`表示模型引文逐字匹配，`reference`表示后端选取的资料摘录，不表示逐句支持答案。`notice`说明无可核验来源或资料降级，`generation_error`记录降级原因。四类意图为 `knowledge/advice/chitchat/out_of_scope`；状态为 `answered/partial_answer/needs_clarification/insufficient_evidence/unsupported`。无可用回答的配置或请求异常仍保留非成功HTTP状态，前端以普通对话提示呈现，不回显模型服务原始错误或密钥。

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
- [项目与作业要求对照](docs/project-audit.md)：模块地图、逐项验收、现存缺口及收尾顺序。
- `requirements-lock.txt`：本次 Windows / Python 3.11.5 环境的完整依赖快照；精确复现可安装该文件。

支持的模型协议为非流式 Chat Completions，模型须按提示输出 JSON。不同厂商的鉴权、参数及结构化输出能力仍需实际联调；当前未承诺所有兼容服务都能直接使用。

名称已统一为“弈宝”。历史报告保持当时输出。当前全量资料离线重建：`python scripts/build_wiki.py --from-snapshot`，联网刷新与解析步骤见上述说明。
