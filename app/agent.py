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
ROUTING_UNAVAILABLE = '这次我没能顺利处理你的问题。问题不用改，稍后再发一次就好。'
MOCK_LIMIT = '现在是 Mock 演示，可以看看万象棋问答流程，还不能读取个人数据或替你操作游戏。'


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
                clarification = '我想先和你对一下，你说的“这个”指哪位棋手、哪张牌，还是哪项机制？'
            elif route.intent == 'advice' and (missing := missing_conditions(route.query)):
                clarification = '咱们一起看看怎么选。再告诉我' + '、'.join(missing[:2]) + '吧，我好结合你的局面判断。'
        fallback_limit = MOCK_LIMIT if self.settings.mode == 'mock' else ROUTING_UNAVAILABLE
        return Decision(intent=route.intent, query=route.query, restricted=route.restricted,
                        clarification=clarification,
                        reply='我在呢。咱们可以一起看规则，也可以聊聊刚才那局。' if route.intent == 'chitchat' else fallback_limit if route.intent == 'out_of_scope' else None,
                        limitation=fallback_limit if route.restricted and route.intent!='out_of_scope' else None,
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
        if decision.search is not None:
            query,decision.search=self.retriever.ground_plan(request.message,query,decision.search,context.history)
        routing = {'status': route_status, 'intent': intent, 'resolved_query': query,
                   'retrieval_required': decision.search is not None, 'error_code': route_error}
        retrieval_plan = None
        status, evidence, used, excerpts = 'answered', [], [], {}
        excerpt_kinds, notice, generation_error = {}, None, None
        model_used = route_status == 'model'
        if intent == 'out_of_scope':
            answer, status = decision.reply, 'unsupported'
            if route_status=='fallback':
                status, generation_error = 'partial_answer', route_error or 'router_failure'
        elif decision.clarification:
            answer, status = decision.clarification, 'needs_clarification'
        elif intent == 'chitchat':
            answer = decision.reply
        elif self.settings.mode == 'mock' and re.search(r'今天.*胜率|实时|体验服|觉醒.*概率', query):
            answer, status = '这个得结合版本来看。你玩的是正式服还是体验服？咱们先对一下。', 'insufficient_evidence'
        else:
            tick = time.perf_counter()
            plan = decision.search or fallback_plan(query)
            pending = self.retriever.pending(query,mode=plan.mode)
            if pending:
                evidence = used = pending
                excerpts = {r['id']: r['body'][:360] for r in pending}
                answer, status = '这点目前还没确认。我把相关说明放在下面，咱们先看看哪些地方还不确定：\n' + '\n'.join(r['body'] for r in pending), 'insufficient_evidence'
            else:
                retrieval_plan = {**plan.model_dump(), 'status': route_status, 'error_code': route_error}
                evidence = await asyncio.to_thread(self.retriever.search_plan, query, plan)
                if intent == 'advice':
                    evidence += await asyncio.to_thread(self.retriever.supporting_rules,evidence,plan.mode,plan.include_history)
                    evidence += await asyncio.to_thread(self.retriever.supporting_mechanics,evidence,plan.mode)
                evidence=await asyncio.to_thread(self.retriever.expand_documents,evidence,plan.mode,plan.include_history)
                tool_record = equipment_context(query,mode=plan.mode)
                if tool_record:
                    evidence = [tool_record, *evidence[:5]]
            timings['retrieval'] = (time.perf_counter() - tick) * 1000
            if not pending:
                if not evidence:
                    answer, status = '这次还没查到能解答你这个问题的资料。要是方便，把游戏里对应的描述贴给我，咱们一起看看。', 'insufficient_evidence'
                else:
                    tick = time.perf_counter()
                    try:
                        async with asyncio.timeout(self.settings.timeout):
                            generation = await self.llm.generate(request.message, context.history, evidence, intent)
                    except (TimeoutError, AgentError) as exc:
                        error = exc if isinstance(exc, AgentError) else AgentError('request_timeout', '这次等得有点久，先把找到的资料留给你参考。', 504)
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
            answer = decision.limitation + '\n\n' + answer
        if self.settings.mode == 'mock':
            answer = '【Mock 演示，非模型回答】\n' + answer
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
