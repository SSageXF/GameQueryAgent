"""Run fixed cases against the exact Agent used by /api/chat. No gold leaks."""
import argparse
import asyncio
import hashlib
import json
import math
import platform
import re
import statistics
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.agent import Agent
from app.config import ROOT, load_settings
from app.llm import AgentError
from app.llm import SYSTEM
from app.intent import ROUTER_SYSTEM
from app.schemas import ChatRequest
from eval.advice import score_advice
from eval.text import affirmative_match
from eval.dataset import evidence_groups, read_cases, validate_cases


def judge(turn: dict, result: dict, knowledge=None) -> dict:
    text = result["answer"]
    groups = [any(re.search(pattern, text, re.I) for pattern in group) for group in turn["required_groups"]]
    forbidden = [p for p in turn["forbidden_patterns"] if affirmative_match(p, text)]
    expected_groups = [set(group) for group in evidence_groups(turn)]
    expected = set().union(*expected_groups) if expected_groups else set()
    retrieved = set(result["retrieved_ids"])
    cited = {s["id"] for s in result["sources"]}
    citation_ok = bool(expected & cited) if expected else not cited
    source_integrity = (all(s['id'] in knowledge and bool(s.get('excerpt'))
                           and s['excerpt'] in knowledge[s['id']]['body']
                           and s.get('url') == knowledge[s['id']]['source_url'] for s in result['sources'])
                        if knowledge is not None else None)
    # Judge executed retrieval, not an unused search field in a clarification plan.
    behavior_ok = not turn.get('forbid_retrieval') or (not retrieved and not cited and not result.get('retrieval_plan'))
    if knowledge is not None and turn.get('expected_mode'):
        behavior_ok = behavior_ok and all(knowledge[key].get('mode') in {turn['expected_mode'],'通用'} for key in retrieved if key in knowledge)
    advice = score_advice(turn, text)
    return {
        "intent_correct": result["intent"] == turn["expected_intent"],
        "retrieval_hit": bool(expected & retrieved) if expected else None,
        "retrieval_recall": sum(bool(group & retrieved) for group in expected_groups)/len(expected_groups) if expected_groups else None,
        "answer_pass": all(groups) and not forbidden and result["status"] == turn["expected_status"] and citation_ok and source_integrity is not False and behavior_ok and not result.get('generation_error') and (advice is None or advice["passed"]),
        "source_integrity": source_integrity, "behavior_check": behavior_ok,
        "advice_rubric": advice,
        "required_group_results": groups, "forbidden_matches": forbidden, "citation_check": citation_ok,
        "status_correct": result["status"] == turn["expected_status"],
    }


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "rate": round(numerator/denominator, 4) if denominator else None}


def latency(values):
    values = sorted(values)
    return {"n": len(values), "median_ms": round(statistics.median(values), 2) if values else None, "p95_ms": round(values[max(0, math.ceil(.95*len(values))-1)], 2) if values else None}


async def run(args):
    settings = replace(load_settings(), mode=args.mode)
    if args.mode == "live" and not settings.ready:
        raise SystemExit("真实评测未运行：请先在 .env 配置 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY；Mock 结果不能替代真实评测。")
    path = Path(getattr(args,'dataset',ROOT/'eval/cases.jsonl'))
    cases = read_cases(path)
    knowledge_rows=sum((json.loads((ROOT/p).read_text(encoding='utf-8')) for p in ('data/knowledge.json','data/wiki/records.json')),[])
    knowledge_by_id={row['id']:row for row in knowledge_rows}
    dataset_coverage=validate_cases(cases,set(knowledge_by_id))
    cases = [c for c in cases if args.split == "all" or c["split"] == args.split]
    selected=set(getattr(args,'cases','').split(','))-{''}
    if selected:
        missing=selected-{c['id'] for c in cases}
        if missing:raise SystemExit('Unknown case IDs in this split: '+','.join(sorted(missing)))
        cases=[c for c in cases if c['id'] in selected]
    if not cases:raise SystemExit('No evaluation cases selected')
    agent = Agent(settings, enhanced=args.variant == "enhanced")
    rows = []
    for case in cases:
        history = []
        for i, turn in enumerate(case["turns"]):
            # This is the only boundary into Agent: no expectations, labels or gold text.
            request = ChatRequest(message=turn["message"], history=turn.get("history", history))
            started = time.perf_counter()
            row = {"case_id": case["id"], "turn": i+1, "split": case["split"], "message": turn["message"],
                   "input_history":request.model_dump()['history'], "expectation":turn,
                   "expected_knowledge_ids": turn["expected_knowledge_ids"], "advice_applicable": bool(turn.get("advice_rubric"))}
            try:
                result = (await agent.chat(request)).model_dump()
                row.update(response_received=True,success=not result.get('generation_error') and (result.get('routing') or {}).get('status')!='fallback',result=result)
                history += [{"role": "user", "content": turn["message"]}, {"role": "assistant", "content": result["answer"]}]
                elapsed = (time.perf_counter()-started)*1000
                judging = time.perf_counter()
                row["judgement"] = judge(turn, result,knowledge_by_id)
                row["judge_ms"] = round((time.perf_counter()-judging)*1000, 3)
            except AgentError as exc:
                elapsed = (time.perf_counter()-started)*1000
                row.update(response_received=False,success=False, error={"code": exc.code, "message": exc.message}, judge_ms=0,
                           model_calls=exc.model_calls, stage_result=exc.stage_result)
                expected_groups=[set(group) for group in evidence_groups(turn)]
                expected=set().union(*expected_groups) if expected_groups else set()
                retrieved=set(exc.stage_result.get('retrieved_ids',[]))
                row["judgement"] = {"intent_correct": exc.stage_result.get('intent') == turn['expected_intent'],
                                    "retrieval_hit": bool(expected & retrieved) if expected else None,
                                    "retrieval_recall": sum(bool(g & retrieved) for g in expected_groups)/len(expected_groups) if expected else None, "answer_pass": False}
                # Do not inject a gold answer after failure. Later follow-ups see actual history.
                history.append({"role": "user", "content": turn["message"]})
            row["elapsed_ms"] = round(elapsed, 3)
            rows.append(row)
            print(f'{case["id"]}/{i+1}: success={row["success"]} answer_pass={row["judgement"]["answer_pass"]}')
    knowledge = [r for r in rows if r["judgement"]["retrieval_hit"] is not None]
    successes = [r for r in rows if r["success"]]
    advice_rows = [r for r in rows if r.get("advice_applicable")]
    cases_pass = sum(all(r["judgement"]["answer_pass"] for r in rows if r["case_id"] == c["id"]) for c in cases)
    summary = {
        "case_count": len(cases), "turn_count": len(rows),
        "intent_accuracy": rate(sum(r["judgement"]["intent_correct"] for r in rows), len(rows)),
        "retrieval_hit_rate": rate(sum(r["judgement"]["retrieval_hit"] for r in knowledge), len(knowledge)),
        "mean_evidence_recall": statistics.mean(r["judgement"]["retrieval_recall"] for r in knowledge) if knowledge else None,
        "answer_pass_rate": rate(sum(r["judgement"]["answer_pass"] for r in rows), len(rows)),
        "case_answer_pass_rate": rate(cases_pass, len(cases)),
        "success_rate": rate(len(successes), len(rows)),
        "response_rate": rate(sum(r.get('response_received',False) for r in rows),len(rows)),
        "degraded_responses":sum(r.get('response_received',False) and not r['success'] for r in rows),
        "advice_rule_pass_rate": rate(sum(bool(r["judgement"].get("advice_rubric", {}).get("passed")) for r in advice_rows), len(advice_rows)),
        "real_model_calls": sum(len(r.get('result', {}).get('model_calls', r.get('model_calls', []))) for r in rows),
        "successful_latency": latency([r["elapsed_ms"] for r in successes]),
        "failed_latency": latency([r["elapsed_ms"] for r in rows if not r["success"]]),
        "all_latency":latency([r['elapsed_ms'] for r in rows]),
        "judge_latency":latency([r['judge_ms'] for r in rows]),
        "query_planner_successes": sum(r.get('result',{}).get('retrieval_plan',{}).get('status')=='model' for r in successes if r.get('result',{}).get('retrieval_plan')),
        "phase_median_ms": {p: statistics.median([r["result"]["timings_ms"].get(p,0) for r in successes]) if successes else None for p in ("client_setup", "context_route", "intent_planning", "retrieval", "generation")},
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode, "variant": args.variant,
        "model": settings.model if args.mode == "live" else "none", "python": platform.python_version(),
        "retrieval_backend": settings.retrieval_backend, "vector_collection": getattr(agent.retriever,'collection',None),
        "thinking": settings.thinking,
        "runtime_config":{'max_tokens':settings.max_tokens,'planner_max_tokens':settings.planner_max_tokens,
                          'timeout_seconds':settings.timeout,'planner_timeout_seconds':settings.planner_timeout},
        "dataset_coverage":dataset_coverage, "selected_case_ids":[c['id'] for c in cases],
        "quality_evaluation_complete": False,
        "notice": "Mock 仅验证链路，不代表模型质量。" if args.mode == "mock" else "规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。",
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prompt_sha256": {"router": hashlib.sha256(ROUTER_SYSTEM.encode()).hexdigest(),
                          "generation": hashlib.sha256(SYSTEM.encode()).hexdigest()},
        "knowledge_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ("data/knowledge.json", "data/wiki/records.json")},
        "rubric_version": "3.0-context-boundaries-evidence-groups",
        "scorer_sha256":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('eval/run.py','eval/advice.py','eval/text.py','eval/dataset.py')},
        "metric_denominators":{'intent_accuracy':'所有执行轮次，调用失败仍计入', 'retrieval_hit_rate':'预期证据组非空的轮次；至少一个组命中',
                               'mean_evidence_recall':'各有证据轮次的事实组覆盖率均值；组内是人工登记的等价来源',
                               'answer_pass_rate':'所有执行轮次；事实/行为/禁止断言/状态/来源及建议规则',
                               'success_rate':'所有执行轮次；模型异常或路由回退/资料摘录降级不计成功',
                               'response_rate':'所有执行轮次；收到结构化结果，包含降级回复'},
        "scoring": "固定正则事实组 + 禁止模式 + 状态 + 引用检查；不以非空作为通过标准。分母为轮数，另提供整案例通过率。人工审查尚未完成。",
        "summary": summary, "rows": rows,
    }
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.mode}-{args.variant}-{args.split}" + ('-selected' if selected else '')
    (out / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manual = [{"case_id": r["case_id"], "turn": r["turn"], "question": r["message"], "answer": r.get("result", {}).get("answer"),
               "answer_points":r['expectation']['answer_points'], "rubric":r['expectation'].get('advice_rubric'),
               "reviewer": None, "verdict": "not_reviewed", "evidence_notes": None,
               "checklist": ["是否理解上下文与请求对象", "数值和机制是否被引用原文支持", "站方解释是否归因且未升级为官方结论", "建议是否利用条件、给出动作与代价", "是否虚构事实、能力或待确认机制", *r['expectation'].get('style_checks', [])]} for r in rows]
    (out / f"{stem}-manual-review.json").write_text(json.dumps(manual, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = [f"# {args.mode.upper()} / {args.variant} / {args.split}", "", report["notice"], "", "自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。", "", "| 指标 | 分子 / 分母 | 比例 |", "| --- | --- | --- |"]
    for name in ("intent_accuracy", "retrieval_hit_rate", "answer_pass_rate", "case_answer_pass_rate", "advice_rule_pass_rate", "success_rate", "response_rate"):
        metric = summary[name]
        lines.append(f'| {name} | {metric["numerator"]}/{metric["denominator"]} | {metric["rate"]} |')
    lines += ["", f'成功调用耗时：{summary["successful_latency"]}', f'失败调用耗时：{summary["failed_latency"]}', f'实际模型调用数：{summary["real_model_calls"]}', "", "| 案例 / 轮 | 成功 | 回答规则通过 | ms |", "| --- | --- | --- | --- |"]
    lines += [f'| {r["case_id"]}/{r["turn"]} | {r["success"]} | {r["judgement"]["answer_pass"]} | {r["elapsed_ms"]} |' for r in rows]
    (out / f"{stem}.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument("--variant", choices=["baseline", "enhanced"], default="enhanced")
    parser.add_argument("--split", choices=["all", "development", "holdout"], default="all")
    parser.add_argument("--output", default=str(ROOT / "eval/reports"))
    parser.add_argument('--dataset',default=str(ROOT/'eval/cases.jsonl'))
    parser.add_argument('--cases',default='',help='Comma-separated fixed case IDs; omitted means the whole selected split')
    asyncio.run(run(parser.parse_args()))
