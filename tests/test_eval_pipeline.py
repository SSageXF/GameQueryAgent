import copy
import json
from types import SimpleNamespace

import pytest

from app.config import ROOT, Settings
from app.retrieval import Retriever
from app.schemas import ChatResponse
from eval.dataset import read_cases, validate_cases
from eval.run import judge
from eval import run as runner
from eval.rescore import rescore


@pytest.fixture(scope='module')
def dataset():
    return read_cases(ROOT/'eval/cases.jsonl')


def test_dataset_meets_required_coverage_and_all_ids_exist(dataset):
    coverage=validate_cases(dataset,set(Retriever().by_id))
    assert coverage['case_count']>=12 and coverage['multi_turn_cases']>=2
    assert set(coverage['intents'])=={'knowledge','advice','chitchat','out_of_scope'}
    assert {'unknown','clarification','unsupported','injection'} <= coverage['tags'].keys()


def test_dataset_rejects_unknown_evidence_and_duplicate_cases(dataset):
    sample=copy.deepcopy(dataset[:1])
    with pytest.raises(ValueError,match='Duplicate'):
        validate_cases(sample+sample,set(Retriever().by_id))
    sample[0]['turns'][0]['expected_knowledge_groups']=[['missing-id']]
    with pytest.raises(ValueError,match='Unknown knowledge'):
        validate_cases(sample,set(Retriever().by_id))


def test_equivalent_source_is_accepted_but_wrong_answer_is_not(dataset):
    turn=next(c['turns'][0] for c in dataset if c['id']=='K06')
    record=Retriever().by_id['WIKI-e1fa16f06be8039f4004']
    result={'answer':'初始1级，最高999级。','intent':'knowledge','status':'answered','retrieved_ids':[record['id']],
            'sources':[{'id':record['id'],'url':record['source_url'],'excerpt':record['body']}]}
    scored=judge(turn,result,{record['id']:record})
    assert scored['retrieval_hit'] and scored['retrieval_recall']==1 and scored['answer_pass']
    result['answer']='初始1级，最高3星。'
    assert judge(turn,result,{record['id']:record})['answer_pass'] is False
    result['answer']='初始1级，最高999级。'
    result['sources'][0]['excerpt']='这是伪造的引文'
    assert judge(turn,result,{record['id']:record})['source_integrity'] is False


async def test_runner_keeps_gold_out_of_agent_and_counts_degradation(dataset,tmp_path,monkeypatch):
    case=copy.deepcopy(next(c for c in dataset if c['id']=='MT04'))
    path=tmp_path/'cases.jsonl'
    path.write_text(json.dumps(case,ensure_ascii=False)+'\n',encoding='utf-8')
    seen=[]
    answers=['无法读取个人战绩。','无法获取好友在线状态。','当前只提供王者万象棋问答，王者荣耀不在范围内。']
    class FakeAgent:
        def __init__(self,*args,**kwargs):self.retriever=SimpleNamespace()
        async def chat(self,request):
            body=request.model_dump()
            assert set(body)=={'message','history'}
            assert all(set(item)=={'role','content'} for item in body['history'])
            if seen:assert body['history'][-1]['content']==answers[len(seen)-1]
            seen.append(body)
            return ChatResponse(answer=answers[len(seen)-1],intent='out_of_scope',status='unsupported',
                                sources=[],retrieved_ids=[],latency_ms=1,timings_ms={},mode='live',model_used=True,
                                request_id='test',routing={'status':'model' if len(seen)<3 else 'fallback','retrieval_required':False},
                                generation_error=None if len(seen)<3 else 'router_failure')
    monkeypatch.setattr(runner,'Agent',FakeAgent)
    monkeypatch.setattr(runner,'load_settings',lambda:Settings(mode='live',base_url='https://test.invalid',api_key='test',model='test',retrieval_backend='lexical'))
    args=SimpleNamespace(mode='live',variant='enhanced',split='all',cases='',dataset=path,output=tmp_path/'out')
    report=await runner.run(args)
    assert len(seen)==3 and report['summary']['response_rate']['numerator']==3
    assert report['summary']['success_rate']['numerator']==2
    assert report['summary']['answer_pass_rate']['numerator']==2
    assert report['summary']['degraded_responses']==1
    assert (tmp_path/'out/live-enhanced-all.md').exists()
    source=tmp_path/'out/live-enhanced-all.json'
    original=source.read_bytes()
    monkeypatch.setattr(runner,'Agent',lambda *a,**kw:pytest.fail('Rescore must never call Agent'))
    replay=rescore(source,path,tmp_path/'rescored.json')
    assert source.read_bytes()==original
    assert replay['new_model_calls']==0 and replay['summary']['answer_pass_rate']==report['summary']['answer_pass_rate']
    assert [r['result'] for r in replay['rows']]==[r['result'] for r in report['rows']]
    with pytest.raises(ValueError,match='Preserve'):
        rescore(source,path,source)


@pytest.mark.parametrize('case_id,turn_index,answer',[
    ('MT04',0,'没有账号接口，读不到你的个人战绩。'),
    ('MT04',1,'好友在线情况查不到，没有好友在线数据接口。'),
    ('V01',0,'没法确认体验服最新版本的技能。'),
])
def test_natural_limitations_are_not_forced_to_use_one_template(dataset,case_id,turn_index,answer):
    turn=next(c['turns'][turn_index] for c in dataset if c['id']==case_id)
    result={'answer':answer,'intent':turn['expected_intent'],'status':turn['expected_status'],
            'sources':[],'retrieved_ids':[],'retrieval_plan':None}
    assert judge(turn,result,{})['answer_pass']


@pytest.mark.parametrize('case_id,answer,status,ids',[
    ('O02','登录和领奖这块我帮不上忙，没有接账号操作的能力。','unsupported',[]),
    ('WX03','这点目前还没确认，复生后能否重复触发牺牲仍需确认。','insufficient_evidence',['WX-hero-sulie-pending']),
    ('V01','白歌的技能是神来之笔。现有资料未必等于体验服此刻的技能。','answered',['B01']),
    ('A04','先看卡牌右侧的定位提示。把场上英雄发给我，咱们再看具体站位。','answered',['H05']),
])
def test_audited_valid_behaviors_pass_without_fixed_phrasing(dataset,case_id,answer,status,ids):
    knowledge=Retriever().by_id
    turn=next(c['turns'][0] for c in dataset if c['id']==case_id)
    result={'answer':answer,'intent':turn['expected_intent'],'status':status,'retrieved_ids':ids,
            'sources':[{'id':key,'url':knowledge[key]['source_url'],'excerpt':knowledge[key]['body']} for key in ids]}
    assert judge(turn,result,knowledge)['answer_pass']
    if ids:
        result['sources'][0]['excerpt']='伪造的原文'
        assert not judge(turn,result,knowledge)['answer_pass']


def test_partial_answer_cannot_cite_unrelated_or_unknown_sources(dataset):
    turn=next(c['turns'][0] for c in dataset if c['id']=='V01')
    record=Retriever().by_id['E03']
    result={'answer':'无法确认体验服最新版本。','intent':'knowledge','status':'answered','retrieved_ids':['E03'],
            'sources':[{'id':'E03','url':record['source_url'],'excerpt':record['body']}]}
    assert not judge(turn,result,{'E03':record})['answer_pass']


def test_life_constraints_cannot_be_omitted_from_situational_advice(dataset):
    from eval.advice import score_advice
    turn=next(c['turns'][0] for c in dataset if c['id']=='A05')
    answer='建议暂缓升级，因为只有2点能量，要保留能量买牌补强。升级收益是天赋，但先确认按钮费用。如果按钮消耗低且还能留下补强预算，则可以再升级。'
    assert not score_advice(turn,answer)['passed']
    answer+='你只有8生命，生存压力较大，应优先判断这轮是否需要补强。'
    assert score_advice(turn,answer)['passed']


def test_budget_comparison_counts_without_repeating_question_word_order(dataset):
    from eval.advice import score_advice
    turn=next(c['turns'][0] for c in dataset if c['id']=='A02')
    text='先看升级按钮费用。如果按钮要的能量不高于你现有的10点，且想靠天赋补强，可以考虑升；如果花完就没法买牌，就稳一手。'
    assert score_advice(turn,text)['passed']
    assert not score_advice(turn,'当前3级、10能量、第5回合。升级有天赋，也能买牌补强。')['passed']


@pytest.mark.parametrize('text,violation',[
    ('这个方案没有必胜保证。',False),
    ('这个方案并无任何必胜保证。',False),
    ('没有固定成员，必胜。',True),
    ('没有固定成员也必胜。',True),
])
def test_promise_negation_stays_local(text,violation):
    from eval.text import affirmative_match
    assert affirmative_match('必胜',text) is violation


@pytest.mark.parametrize('case_id,index,answer',[
    ('S03',0,'输一把确实挺难受的，先歇会儿也行。我在。'),
    ('MT04',2,'《王者荣耀》小乔技能我这没有，这边资料是《王者万象棋》的。'),
])
def test_natural_empathy_and_scope_phrasing(dataset,case_id,index,answer):
    turn=next(c['turns'][index] for c in dataset if c['id']==case_id)
    result={'answer':answer,'intent':turn['expected_intent'],'status':turn['expected_status'],
            'sources':[],'retrieved_ids':[],'retrieval_plan':None}
    assert judge(turn,result,{})['answer_pass']


def test_scope_paraphrases_do_not_replace_requested_subject(dataset):
    turn=next(c['turns'][1] for c in dataset if c['id']=='MT04')
    result={'answer':'我这没有，这边资料是万象棋的。','intent':'out_of_scope','status':'unsupported',
            'sources':[],'retrieved_ids':[],'retrieval_plan':None}
    assert not judge(turn,result,{})['answer_pass']


def test_valid_low_resource_advice_and_unsupported_card_cost_are_distinct(dataset):
    from eval.advice import score_advice
    from eval.text import affirmative_match
    turn=next(c['turns'][0] for c in dataset if c['id']=='A05')
    answer=('先留着能量，不升级。8点生命不算宽裕，需要补英雄；花光这2点又买不了人。'
            '除非按钮费用恰好2能量，且你决定赌天赋，否则先等凑够买牌预算。')
    assert score_advice(turn,answer)['passed']
    assert not score_advice(turn,answer.replace('8点生命不算宽裕，需要补英雄；',''))['passed']
    turn=next(c['turns'][0] for c in dataset if c['id']=='A03')
    answer='没有必胜保证，不用一上来就追高费卡。'
    assert [p for p in turn['forbidden_patterns'] if affirmative_match(p,answer)]==['高费卡']
