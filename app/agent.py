import asyncio
import logging
import re
import time
import uuid
from contextlib import nullcontext

from .config import Settings
from .context import prepare
from .intent import classify, missing_conditions, Decision
from .llm import AgentError, LLM
from .answers import evidence_fallback
from .retrieval import Retriever
from .query import fallback_plan
from .wiki_tools import equipment_context
from .schemas import ChatRequest, ChatResponse, Source

logger = logging.getLogger('gamequery')
LIMIT = '我还没接入账号、个人战绩或实时对局，也不能替你操作游戏。'


class Agent:
    def __init__(self, settings: Settings, llm=None, retriever=None, enhanced=True):
        self.settings = settings
        self.llm = llm or LLM(settings)
        if retriever is not None:
            self.retriever = retriever
        elif settings.retrieval_backend == 'vector':
            from .vector_store import get_vector_retriever
            self.retriever = get_vector_retriever()
        else:
            self.retriever = Retriever(enhanced=enhanced)
        self.enhanced = enhanced

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        session = self.llm.session() if self.settings.mode == 'live' and hasattr(self.llm, 'session') else nullcontext([])
        async with session as calls:
            try:
                setup_ms = (time.perf_counter()-start)*1000
                result = await self._chat(request)
                result.model_calls = list(calls)
                result.timings_ms['client_setup'] = round(setup_ms, 2)
                result.latency_ms = round((time.perf_counter()-start)*1000, 2)
                return result
            except AgentError as exc:
                exc.model_calls = list(calls)
                raise

    def fallback_decision(self, request):
        context = prepare(request.message, request.history, self.enhanced, getattr(self.retriever, 'context_entities', None))
        route = classify(context.query)
        clarification = None
        if route.intent != 'out_of_scope':
            if context.ambiguous:
                clarification = '你说的“这个”具体是哪位棋手、哪张牌或哪项机制呀？'
            elif route.intent == 'advice' and (missing := missing_conditions(route.query)):
                clarification = '再告诉我' + '、'.join(missing[:2]) + '吧，我好帮你一起判断。' + ('还缺：' + '、'.join(missing[2:]) + '。' if len(missing) > 2 else '')
        return Decision(intent=route.intent, query=route.query, restricted=route.restricted,
                        clarification=clarification,
                        reply='你好呀，我是弈宝。咱们慢慢来，可以一起看看规则，也可以聊聊刚才那局。' if route.intent == 'chitchat' else None,
                        search=fallback_plan(route.query) if route.intent in {'knowledge', 'advice'} and not clarification else None), context

    async def _chat(self, request):
        start = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]
        timings = {name: 0.0 for name in ('context_route', 'intent_planning', 'retrieval', 'generation')}
        # Live model sees the original question and bounded history, not regex-rewritten intent.
        context = prepare(request.message, request.history, enhanced=False)
        timings['context_route'] = (time.perf_counter() - start) * 1000
        route_status = 'mock_rules' if self.settings.mode == 'mock' else 'fallback'
        route_error = None
        tick = time.perf_counter()
        if self.settings.mode == 'live' and hasattr(self.llm, 'decide'):
            try:
                async with asyncio.timeout(self.settings.planner_timeout):
                    hint = self.retriever.routing_hint(request.message + ' ' + ' '.join(x['content'] for x in context.history if x['role'] == 'user'))
                    decision = await self.llm.decide(request.message, context.history, hint)
                route_status = 'model'
            except (AgentError, TimeoutError) as exc:
                # Missing credentials cannot be silently hidden by a local response.
                if isinstance(exc, AgentError) and exc.code == 'model_not_configured':
                    raise
                route_error = exc.code if isinstance(exc, AgentError) else 'router_timeout'
                decision, context = self.fallback_decision(request)
        else:
            decision, context = self.fallback_decision(request)
        timings['intent_planning'] = (time.perf_counter() - tick) * 1000
        query, intent = decision.query, decision.intent
        routing = {'status': route_status, 'intent': intent, 'resolved_query': query,
                   'retrieval_required': decision.search is not None, 'error_code': route_error}
        retrieval_plan = None
        status, evidence, used, excerpts = 'answered', [], [], {}
        excerpt_kinds, notice, generation_error = {}, None, None
        model_used = route_status == 'model'
        if intent == 'out_of_scope':
            answer, status = LIMIT + '你可以把局面告诉我，咱们一起分析。', 'unsupported'
        elif decision.clarification:
            answer, status = decision.clarification, 'needs_clarification'
        elif intent == 'chitchat':
            answer = decision.reply
        elif route_status != 'model' and re.search(r'今天.*胜率|实时|体验服|觉醒.*概率', query):
            answer, status = '这部分我还没查到核验过的版本或精确数据，资料不足。你有对应的公告或卡牌说明吗？', 'insufficient_evidence'
        else:
            tick = time.perf_counter()
            pending = self.retriever.pending(query)
            if pending:
                evidence = used = pending
                excerpts = {r['id']: r['body'][:360] for r in pending}
                answer, status = '这点资料里还标着待确认，暂时不能下结论：\n' + '\n'.join(r['body'] for r in pending), 'insufficient_evidence'
            else:
                plan = decision.search or fallback_plan(query)
                retrieval_plan = {**plan.model_dump(), 'status': route_status, 'error_code': route_error}
                evidence = await asyncio.to_thread(self.retriever.search_plan, query, plan)
                if intent == 'advice':
                    mode='钻石狂潮' if '钻石狂潮' in query else '万象大赛' if '万象大赛' in query else plan.mode
                    evidence += await asyncio.to_thread(self.retriever.supporting_mechanics, evidence, mode)
                tool_record = equipment_context(query)
                if tool_record:
                    evidence = [tool_record, *evidence[:5]]
            timings['retrieval'] = (time.perf_counter() - tick) * 1000
            if not pending:
                if not evidence:
                    answer, status = '这点我还没找到足够资料，先不猜。你能补充具体卡牌名字或那段说明吗？', 'insufficient_evidence'
                else:
                    tick = time.perf_counter()
                    try:
                        async with asyncio.timeout(self.settings.timeout):
                            generation = await self.llm.generate(query, context.history, evidence, intent)
                    except (TimeoutError, AgentError) as exc:
                        error = exc if isinstance(exc, AgentError) else AgentError('request_timeout', '这次等得有点久，请稍后重试。', 504)
                        generation = evidence_fallback(evidence, error.code)
                        logger.warning('generation_fallback request_id=%s code=%s', request_id, error.code)
                    timings['generation'] = (time.perf_counter() - tick) * 1000
                    answer = generation.answer
                    status = 'partial_answer' if generation.fallback_code else 'insufficient_evidence' if generation.insufficient_evidence else 'answered'
                    used = [r for r in evidence if r['id'] in generation.source_ids]
                    excerpts = {q.source_id: q.quote for q in generation.quotes}
                    excerpt_kinds = {q.source_id: q.kind for q in generation.quotes}
                    notice, generation_error = generation.notice, generation.fallback_code
                    model_used = model_used or (self.settings.mode == 'live' and not generation.fallback_code)
        if decision.restricted and intent != 'out_of_scope':
            answer = LIMIT + '\n\n' + answer
        if self.settings.mode == 'mock':
            answer = '【Mock 联调，非真实模型回答】\n' + answer
        result = ChatResponse(
            answer=answer, intent=intent, status=status,
            sources=[Source(id=r['id'], title=r['title'], source_title=r['source_title'], url=r['source_url'],
                            collected_at=r['collected_at'], version_scope=r['version_scope'], claim_type=r.get('claim_type', 'rule'),
                            verification=r.get('verification', 'official_page_checked'), official_url=r.get('official_url'),
                            excerpt=excerpts.get(r['id'], r['body'][:360]), excerpt_kind=excerpt_kinds.get(r['id'], 'quote')) for r in used],
            retrieved_ids=[r['id'] for r in evidence], latency_ms=round((time.perf_counter()-start)*1000, 2),
            timings_ms={k: round(v, 2) for k, v in timings.items()}, mode=self.settings.mode, model_used=model_used,
            request_id=request_id, retrieval_plan=retrieval_plan, routing=routing, notice=notice, generation_error=generation_error)
        logger.info('request_id=%s intent=%s status=%s latency_ms=%s retrieved=%s mode=%s',
                    request_id, intent, status, result.latency_ms, result.retrieved_ids, result.mode)
        return result
