import copy
import json

import pytest

from app.agent import Agent
from app.config import ROOT, Settings
from app.context import normalize
from app.retrieval import Retriever
from app.schemas import ChatRequest
from eval.advice import score_advice
from eval.run import judge
from scripts.import_wzwxq import build


def snapshot():
    return json.loads((ROOT / "data/imports/wzwxq-selected.json").read_text(encoding="utf-8"))


def advice_turn():
    return next(json.loads(line)["turns"][0] for line in (ROOT/"eval/cases.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(line)["id"] == "A02")


def test_import_reproducible_and_audited():
    records, checks = build(snapshot())
    assert records == json.loads((ROOT/"data/wzwxq.json").read_text(encoding="utf-8"))
    assert len(checks) == 45 and all(c["matched"] for c in checks)
    assert all(r["mode"] == "万象大赛" for r in records)
    assert len({r["id"] for r in records}) == len(records)


def test_conflicting_field_is_quarantined():
    source = copy.deepcopy(snapshot())
    source["items"][0]["fields"][0]["site_text"] = "牺牲：永久+999"
    records, checks = build(source)
    assert records[0]["claim_type"] == "pending"
    assert not records[0]["eligible"]
    assert not checks[0]["matched"]
    assert records[0] not in Retriever(records).search("苏烈")


def test_wiki_is_authoritative_but_pending_is_excluded():
    rows = Retriever().search("苏烈")
    assert rows and all(r["verification"] in {"official_data_matched", "wiki_snapshot"} for r in rows)
    advice = Retriever().search("苏烈怎么搭配", include_interpretations=True)
    assert any(r["claim_type"] == "site_interpretation" for r in advice)
    assert all(r.get("entity") == "苏烈" for r in advice)
    assert not any(r["claim_type"] == "pending" for r in advice)


async def test_pending_response_does_not_call_model():
    class Never:
        async def generate(self, *args):
            raise AssertionError("Pending mechanism must not be sent as confirmed fact")
    result = await Agent(Settings(mode="mock"), llm=Never()).chat(ChatRequest(message="苏烈复生后是否可以重复触发牺牲？"))
    assert result.status == "insufficient_evidence"
    assert result.sources[0].claim_type == "pending"
    assert not result.model_used


def test_hero_and_commander_identity():
    assert normalize("李白技能") == "李白技能"
    assert normalize("棋手李白技能") == "白歌技能"
    assert all(r.get("entity") == "李白" for r in Retriever().search("英雄李白技能"))


def test_wrong_mode_never_retrieved():
    row = copy.deepcopy(Retriever().records[0])
    row["mode"] = "钻石狂潮"
    assert Retriever([row]).search("几个人") == []


@pytest.mark.parametrize("text", [
    "你给出的条件是：只有10点能量，所以先不升级；如果按钮费用低，就再升级。保留能量买牌，天赋很重要。",
    "使用能量提升棋手等级，每次升级获得天赋，升级价格看按钮。",
    "建议先核对规则，再结合当前阵容决定；不能保证获胜。",
])
def test_echo_and_fact_dump_are_not_advice(text):
    result = score_advice(advice_turn(), text)
    assert not result["passed"]


def test_actionable_conditional_advice_passes_rule_rubric():
    text = "建议暂缓升级，先确认升级按钮费用。因为只有10点能量，花完就没有买牌补强的余量。升级收益是天赋或上阵名额，但要保留能量买牌。如果按钮消耗较低且能保留补强预算，则可以再升级；否则先补阵容。"
    result = score_advice(advice_turn(), text)
    assert result["score"] == 10 and result["passed"]
    assert result["human_review_required"]


async def test_mock_advice_fails_stricter_quality_check():
    turn = advice_turn()
    result = (await Agent(Settings(mode="mock")).chat(ChatRequest(message=turn["message"]))).model_dump()
    assert not judge(turn, result)["answer_pass"]


def test_runtime_brand_name():
    for p in [ROOT/"app/llm.py", ROOT/"app/main.py", ROOT/"static/index.html", ROOT/"static/app.js"]:
        text = p.read_text(encoding="utf-8")
        assert "弈宝" in text and "弈伴" not in text


def test_advice_disclaimer_does_not_trigger_guarantee_violation():
    turn = advice_turn()
    turn['advice_rubric']['forbidden_recommendations'] = [r'保证.{0,5}获胜']
    assert score_advice(turn, '不能保证获胜，不保证获胜。')['violations'] == []
    assert score_advice(turn, '按照我的推荐，保证获胜。')['violations']
