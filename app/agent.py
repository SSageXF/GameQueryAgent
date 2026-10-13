import asyncio
import logging
import re
import time
import uuid

from .config import Settings
from .context import prepare
from .intent import classify, missing_conditions
from .llm import AgentError, LLM
from .retrieval import Retriever
from .query import fallback_plan
from .wiki_tools import equipment_context
from .schemas import ChatRequest, ChatResponse, Source

logger = logging.getLogger("gamequery")
LIMIT = "我未接入账号、个人战绩或实时对局，也不能代你执行游戏内操作。"


class Agent:
    def __init__(self, settings: Settings, llm=None, retriever=None, enhanced=True):
        self.settings = settings
        self.llm = llm or LLM(settings)
        self.retriever = retriever or Retriever(enhanced=enhanced)
        self.enhanced = enhanced

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]
        timings = {"context_route": 0.0, "query_planning": 0.0, "retrieval": 0.0, "generation": 0.0}
        retrieval_plan = None
        context = prepare(request.message, request.history, self.enhanced, getattr(self.retriever,'context_entities',None))
        route = classify(context.query)
        timings["context_route"] = (time.perf_counter() - start) * 1000
        status, evidence, used, model_used = "answered", [], [], False
        if route.intent == "out_of_scope":
            answer, status = LIMIT + "可以把局面文字发给我，或询问万象棋的基础规则。", "unsupported"
        elif context.ambiguous:
            answer, status = "请告诉我“这个”具体指哪位棋手、哪张牌或哪项机制？", "needs_clarification"
        elif route.intent == "advice" and (missing := missing_conditions(route.query)):
            answer = "请补充" + "、".join(missing[:2]) + "，我再结合条件分析。" + ("还缺：" + "、".join(missing[2:]) + "。" if len(missing) > 2 else "")
            status = "needs_clarification"
        elif re.search(r"今天.*胜率|实时|体验服|觉醒.*概率", route.query):
            answer, status = "当前知识库保存Wiki和官网资料快照，未核验你所问版本或精确数据，资料不足。请提供版本公告或具体卡牌说明后再分析。", "insufficient_evidence"
        elif pending := self.retriever.pending(route.query):
            used = pending
            evidence = pending
            answer = "这个问题在资料中仍属待确认，不能给出确定结论：\n" + "\n".join(r["body"] for r in pending)
            status = "insufficient_evidence"
        else:
            if route.intent != "chitchat":
                tick=time.perf_counter()
                plan=fallback_plan(route.query)
                planner_status='mock_rules' if self.settings.mode=='mock' else 'fallback'
                error_code=None
                if self.settings.mode=='live' and hasattr(self.llm,'plan_query'):
                    try:
                        async with asyncio.timeout(self.settings.planner_timeout):
                            plan=await self.llm.plan_query(route.query,context.history,self.retriever.catalog_hint(route.query))
                        planner_status='model'
                    except (AgentError,TimeoutError) as exc:
                        error_code=exc.code if isinstance(exc,AgentError) else 'planner_timeout'
                timings['query_planning']=(time.perf_counter()-tick)*1000
                retrieval_plan={**plan.model_dump(),'status':planner_status,'error_code':error_code}
                tick=time.perf_counter()
                evidence = self.retriever.search_plan(route.query,plan)
                tool_record=equipment_context(route.query)
                if tool_record:evidence=[tool_record,*evidence[:5]]
                timings["retrieval"] = (time.perf_counter() - tick) * 1000
            if route.intent != "chitchat" and not evidence:
                answer, status = "目前知识库没有足够资料支持这个问题。我不能编造规则；请补充具体棋手、卡牌名称或官方说明。", "insufficient_evidence"
            else:
                tick = time.perf_counter()
                try:
                    async with asyncio.timeout(self.settings.timeout):
                        generation = await self.llm.generate(route.query, context.history, evidence, route.intent)
                except TimeoutError as exc:
                    raise AgentError("request_timeout", "请求超时，请稍后重试。", 504) from exc
                timings["generation"] = (time.perf_counter() - tick) * 1000
                answer = generation.answer
                used = [r for r in evidence if r["id"] in generation.source_ids]
                model_used = self.settings.mode == "live"
                if used:
                    answer += "\n\n资料范围：已收录资料快照，具体来源、核验层级和日期见引用；不保证覆盖后续改动。"
        if route.restricted and route.intent != "out_of_scope":
            answer = LIMIT + "\n\n" + answer
        if self.settings.mode == "mock":
            answer = "【Mock 联调，非真实模型回答】\n" + answer
        result = ChatResponse(
            answer=answer, intent=route.intent, status=status,
            sources=[Source(id=r["id"], title=r["title"], source_title=r["source_title"], url=r["source_url"], collected_at=r["collected_at"], version_scope=r["version_scope"], claim_type=r.get("claim_type", "rule"), verification=r.get("verification", "official_page_checked"), official_url=r.get("official_url")) for r in used],
            retrieved_ids=[r["id"] for r in evidence], latency_ms=round((time.perf_counter()-start)*1000, 2),
            timings_ms={k: round(v, 2) for k, v in timings.items()}, mode=self.settings.mode, model_used=model_used, request_id=request_id,
            retrieval_plan=retrieval_plan,
        )
        logger.info("request_id=%s intent=%s status=%s latency_ms=%s retrieved=%s mode=%s", request_id, route.intent, status, result.latency_ms, result.retrieved_ids, result.mode)
        return result
