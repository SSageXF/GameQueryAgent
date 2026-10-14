"""User-visible failures found in the requirements audit, with no model network."""
import json
import httpx
import pytest

from app.agent import Agent
from app.config import ROOT, Settings
from app.llm import LLM
from app.intent import Decision
from app.query import CatalogSelection, QueryPlan, resolve_mode
from app.retrieval import Retriever
from app.schemas import ChatRequest
from eval import upgrade_eval


@pytest.fixture(scope='module')
def retriever():
    return Retriever()


def test_shared_label_does_not_exclude_auction_rule(retriever):
    q='竞拍结束后的分红跟血量有什么关系？'
    rows=retriever.search_plan(q,QueryPlan(queries=[q],mode='通用'))
    assert any(r['id']=='A03' and '生命越低' in r['body'] for r in rows)


@pytest.mark.parametrize('message,proposed,history,expected',[
    ('那苏烈呢？','通用',[{'role':'user','content':'钻石狂潮里的技能'}],'钻石狂潮'),
    ('现在回到万象大赛','钻石狂潮',[{'role':'user','content':'钻石狂潮'}],'万象大赛'),
    ('竞拍分红','通用',[],'万象大赛'),
])
def test_mode_follows_user_context(message,proposed,history,expected):
    assert resolve_mode(message,proposed,history)==expected


def test_typed_alias_cannot_turn_commander_into_hero(retriever):
    hint=retriever.routing_hint('棋手李白技能')
    assert {'alias':'棋手李白','name':'白歌','section':'players'} in hint['entity_aliases']
    query,plan=retriever.ground_plan('棋手李白的技能是什么？','英雄李白的技能',QueryPlan(queries=['英雄李白技能']))
    rows=retriever.search_plan(query,plan)
    assert any(r.get('entity')=='白歌' and r.get('field')=='skillSections' for r in rows)
    assert not any(r.get('entity')=='李白' for r in rows)
    hero=retriever.search_plan('英雄李白的技能',QueryPlan(queries=['李白技能']))
    assert any(r['id']=='WX-hero-1311-skill' for r in hero)


def test_partial_catalog_does_not_hide_other_type_or_skill(retriever):
    q='苏烈和白歌的技能分别是什么？'
    plan=QueryPlan(queries=[q],selection=CatalogSelection(section='hero',names=['苏烈','白歌']))
    rows=retriever.search_plan(q,plan)
    assert {'WX-hero-sulie-skill','WIKI-a707692151fe8ded9573'} <= {r['id'] for r in rows}


def test_advice_support_includes_upgrade_cost_and_population(retriever):
    rows=[retriever.by_id['WIKI-79c68b769e0390cb63a4']]
    extra=retriever.supporting_rules(rows,'万象大赛')
    assert {'C04','E04','E03','R01','R02','WIKI-8d1c3420e3a98a6b2db6'} <= {r['id'] for r in extra}
    assert not retriever.supporting_rules(rows,'钻石狂潮')


def test_lineup_siblings_include_later_stages_and_report_partial_budget(retriever):
    row=retriever.by_id['WIKI-089260827f7f61696a6e']
    complete=retriever.expand_documents([row],'万象大赛')
    assert len(complete)==5 and any('阶段：late' in r['body'] for r in complete)
    assert all(r['document_total']==r['document_returned']==5 for r in complete)
    partial=retriever.expand_documents([row],'万象大赛',max_extra=0)
    assert len(partial)==1 and partial[0]['document_total']==5 and partial[0]['document_returned']==1


async def test_tool_cannot_mix_modes_when_query_omits_mode(retriever):
    captured=[]
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][-1]['content'])
        if 'catalog' in data:
            result={'intent':'knowledge','query':'苏烈40级红莲炎甲的装备价值是多少？',
                    'search':{'queries':['苏烈装备价值'],'mode':'钻石狂潮'}}
        else:
            captured.extend(data['evidence'])
            result={'answer':'现有这些资料没有对应模式的装备价值计算结果。','source_ids':[],'insufficient_evidence':True}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result,ensure_ascii=False)}}]})
    s=Settings(base_url='https://test.invalid/v1',api_key='test',model='test',retrieval_backend='lexical')
    await Agent(s,llm=LLM(s,httpx.MockTransport(handler)),retriever=retriever).chat(
        ChatRequest(message='钻石狂潮里，苏烈40级红莲炎甲的装备价值是多少？'))
    assert captured and all(r['mode'] in {'钻石狂潮','通用'} for r in captured)
    assert not any(r['id'].startswith('TOOL-equipment') for r in captured)


async def test_auxiliary_eval_rejects_unconfigured_live_before_creating_agent(tmp_path,monkeypatch):
    monkeypatch.setattr(upgrade_eval,'load_settings',lambda:Settings(mode='mock',retrieval_backend='lexical'))
    monkeypatch.setattr(upgrade_eval,'Agent',lambda *a:pytest.fail('Must validate before running'))
    with pytest.raises(SystemExit,match='真实评测未运行'):
        await upgrade_eval.run(tmp_path/'live.json')
    assert not (tmp_path/'live.json').exists()


async def test_auxiliary_mock_is_labelled_and_preserves_old_reports(tmp_path,monkeypatch):
    monkeypatch.setattr(upgrade_eval,'load_settings',lambda:Settings(mode='mock',retrieval_backend='lexical'))
    target=tmp_path/'mock.json'
    report=await upgrade_eval.run(target,mode='mock')
    assert report['mode']=='mock' and all(r['result']['mode']=='mock' for r in report['rows'])
    assert not any(r['result']['model_calls'] for r in report['rows'])
    original=target.read_bytes()
    with pytest.raises(SystemExit,match='已存在'):
        await upgrade_eval.run(target,mode='mock')
    assert target.read_bytes()==original


def test_evidence_link_ids_are_real_and_distinct(retriever):
    links=json.loads((ROOT/'data/retrieval_links.json').read_text(encoding='utf-8'))['links']
    assert all(set(link['from_ids']+link['to_ids']) <= retriever.by_id.keys() for link in links)


def test_length_flag_does_not_discard_complete_valid_plan():
    content=json.dumps({'intent':'knowledge','query':'白歌技能','search':{'queries':['白歌技能']}})
    result=LLM._parse({'finish_reason':'length','message':{'content':content+' '*4000}},Decision)
    assert result.query=='白歌技能'
    with pytest.raises(ValueError):
        LLM._parse({'finish_reason':'length','message':{'content':content[:-3]}},Decision)


async def test_live_router_failure_still_retrieves_version_question(retriever):
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][-1]['content'])
        if 'catalog' in data:
            return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{"intent":'}}]})
        assert data['query']=='体验服最新版本白歌技能是什么？'
        assert any(r.get('entity')=='白歌' for r in data['evidence'])
        answer={'answer':'现有快照不能确认体验服最新技能。','source_ids':[],'insufficient_evidence':True}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer,ensure_ascii=False)}}]})
    s=Settings(base_url='https://test.invalid',api_key='test',model='test',retrieval_backend='lexical')
    result=await Agent(s,llm=LLM(s,httpx.MockTransport(handler)),retriever=retriever).chat(
        ChatRequest(message='体验服最新版本白歌技能是什么？'))
    assert result.routing['status']=='fallback' and result.retrieved_ids
    assert '正式服还是体验服' not in result.answer

