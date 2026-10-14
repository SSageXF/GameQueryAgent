"""Live conversation regression. Uses only fixed game questions and public wiki evidence.

Mechanical checks validate routing/context/citation integrity, not factual correctness.
Review the saved visible answers against the cited originals for semantic acceptance.
"""
import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

from app.agent import Agent
from app.config import load_settings
from app.llm import LLM
from app.schemas import ChatRequest
from app.vector_store import VectorRetriever


FIRST='和河洛相关的天赋有哪些？'
FOLLOWUP='每一个天赋的具体效果是什么'
REPORTED='目前资料里能确认和河洛相关的天赋组有五个：河洛来客、河洛精兵、河洛增援、河洛强援、河洛新援，它们的初始天赋栏目前只标了“初始天赋”，具体效果我这边还没查到。你是想了解某一个天赋组，还是想看它们的区别？'


class ContextAuditLLM(LLM):
    expected_history=[]
    question=''

    async def _complete(self, system, data, stage, budget, timeout):
        # Check the actual inputs used by both stages. Never log keys or reasoning.
        assert data.get('history',[])==self.expected_history
        assert data.get('question',data.get('query'))==self.question
        return await super()._complete(system,data,stage,budget,timeout)


async def run(output, only=None):
    settings=replace(load_settings(),mode='live',retrieval_backend='vector')
    if not settings.ready:raise RuntimeError('Configure the model in .env first')
    retriever=VectorRetriever()
    try:
        # Only the project's public knowledge snapshots are sent as evidence.
        assert all(urlparse(r['source_url']).hostname in {'wzwxq.com','wxq.qq.com'} for r in retriever.records)
        llm=ContextAuditLLM(settings)
        agent=Agent(settings,llm=llm,retriever=retriever)
        results=[]
        async def ask(label,question,history):
            llm.question, llm.expected_history=question,history
            result=await agent.chat(ChatRequest(message=question,history=history))
            quotes_ok=all(s.excerpt in retriever.by_id.get(s.id)['body'] for s in result.sources)
            report={'case':label,'question':question,'history_messages':len(history),
                    **result.model_dump(exclude={'request_id'}),
                    'checks':{'model_routed':result.routing['status']=='model',
                              'answered_without_clarification':result.status=='answered',
                              'both_stages_received_history':len(result.model_calls)>=2 and all(c['history_messages']==len(history) for c in result.model_calls),
                              'source_excerpts_are_original':quotes_ok and bool(result.sources)}}
            results.append(report)
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps({'model':settings.model,'backend':'vector','thinking':settings.thinking,
                               'generation_max_tokens':settings.max_tokens,'planner_max_tokens':settings.planner_max_tokens,
                               'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'case':label,'answer':result.answer,'plan':result.retrieval_plan,
                              'timings_ms':result.timings_ms,'checks':report['checks'],'calls':result.model_calls},ensure_ascii=False),flush=True)
            return result
        if only in {None,'fresh_catalog','natural_followup'}:
            first=await ask('fresh_catalog',FIRST,[])
            if only!='fresh_catalog':
                await ask('natural_followup',FOLLOWUP,[{'role':'user','content':FIRST},{'role':'assistant','content':first.answer}])
        history=[{'role':'user','content':FIRST},{'role':'assistant','content':REPORTED}]
        if only in {None,'reported_five_followup'}:
            await ask('reported_five_followup',FOLLOWUP,history)
        if only in {None,'explicit_topic_switch'}:
            await ask('explicit_topic_switch','先不聊天赋了，英雄购买费用是多少？',history)
    finally:
        retriever.client.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly allow configured model API calls')
    parser.add_argument('--output',type=Path,default=Path('artifacts/conversation-quality.json'))
    parser.add_argument('--case',choices=['fresh_catalog','natural_followup','reported_five_followup','explicit_topic_switch'])
    args=parser.parse_args()
    if not args.live:parser.error('Pass --live to run the paid model calls')
    asyncio.run(run(args.output,args.case))
