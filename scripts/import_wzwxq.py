"""Curated import. Network snapshots are staged; offline rebuild is deterministic."""
import argparse
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SELECTION = {
    "hero": (1, "heroCards", ["苏烈", "曜", "孙膑", "孙尚香", "弈星", "盾山", "赵云", "白起", "李白"]),
    "equipment": (4, "equipCards", ["风暴巨剑", "圣者法典", "雷鸣刃", "守护者之铠", "力量腰带", "破碎圣杯"]),
    "effect": (2, "effectCards", ["吸纳人才", "研读会", "惊喜补贴", "古币", "图腾仪式", "遗志"]),
    "talent": (8, "talentCards", ["兵行诡招", "里程碑", "整装待发", "存款利息", "复印机", "防御领域"]),
}
SNAPSHOT = ROOT / "data/imports/wzwxq-selected.json"
OFFICIAL = "https://game.gtimg.cn/images/amside/ide_timer/589094_oscard_new_{}.js"


def plain(value):
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", value or "")))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stage(cache: Path):
    selected, audit = [], []
    for kind, (number, key, names) in SELECTION.items():
        wiki_raw = (cache / f"{kind}.json").read_bytes()
        official_raw = (cache / f"official-{number}.js").read_bytes()
        wiki, official = json.loads(wiki_raw)["items"], json.loads(official_raw)[key]
        by_id = {str(x["id"]): x for x in official}
        counts = Counter()
        for row in wiki:
            if row.get("versionStatus") != "current_official" or row.get("temporarilyOffShelf"):
                counts["excluded_historical_supplementary_or_off_shelf"] += 1
                continue
            if row["name"] not in names:
                counts["outside_curated_beginner_scope"] += 1
                continue
            off = by_id.get(str(row.get("rawId")))
            if not off or off["name"] != row["name"]:
                counts["excluded_missing_official_identity"] += 1
                continue
            fields = [("original", row.get("original", ""), plain(off.get("desc")))]
            hero = off.get("heroCard") or {}
            if row.get("awakening"):
                fields.append(("awakening", row["awakening"], plain((hero.get("awakeingCard") or {}).get("desc"))))
            if row.get("officialSkill"):
                skill = row["officialSkill"]
                matching = next((s for s in hero.get("skillList", []) if s["name"] == skill.get("name")), {})
                fields.append(("skill", skill.get("original", ""), plain(matching.get("desc"))))
            selected.append({
                "kind": kind, "id": row["id"], "name": row["name"], "raw_id": str(off["id"]),
                "site_version": row.get("version"), "site_status": row["versionStatus"],
                "source_url": "https://wzwxq.com/explore/" + row["id"], "official_url": OFFICIAL.format(number),
                "mode_evidence": "站点万象大赛图鉴分类 + 官网常规卡牌目录中同ID同名对象；不读取钻石狂潮目录",
                "fields": [{"field": field, "site_text": text, "official_text": official_text} for field, text, official_text in fields],
                "site_interpretation": row.get("formal", ""), "pending": row.get("pending", ""),
            })
            counts["selected"] += 1
        audit.append({"kind": kind, "url": f"https://wzwxq.com/explorer-catalogs/{kind}.json", "official_url": OFFICIAL.format(number), "site_sha256": digest(wiki_raw), "official_sha256": digest(official_raw), "candidate_count": len(wiki), "selection_counts": dict(counts)})
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {"collected_at": datetime.now(timezone.utc).isoformat(), "selection_rationale": "基础成长、资源、前排、装备与天赋取舍；显式白名单，小规模导入而非全站镜像", "catalogs": audit, "items": selected}
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def build(snapshot):
    records, decisions = [], []
    labels = {"original": "卡面原文", "awakening": "觉醒卡面", "skill": "技能原文"}
    for item in snapshot["items"]:
        base = {
            "entity": item["name"], "entity_type": item["kind"], "topic": "万象大赛·" + item["kind"],
            "source_title": "万象棋知识站", "source_url": item["source_url"],
            "collected_at": snapshot["collected_at"][:10], "verified_at": snapshot["collected_at"][:10],
            "mode": "万象大赛", "site_version": item["site_version"],
            "version_scope": f"知识站标注：{item['site_version']}；与{snapshot['collected_at'][:10]}采集官网字段比对，不代表全部最新规则",
            "official_url": item["official_url"], "mode_evidence": item["mode_evidence"],
            "aliases": [item["name"]],
        }
        parent_ids = []
        for field in item["fields"]:
            matched = bool(field["official_text"]) and plain(field["site_text"]) == plain(field["official_text"])
            kid = "WX-" + item["id"] + "-" + field["field"]
            records.append({**base, "id": kid, "title": item["name"] + "·" + labels[field["field"]], "body": plain(field["site_text"]),
                "claim_type": "official_original" if matched else "pending", "verification": "official_data_matched" if matched else "conflicting_sources",
                "eligible": matched, "official_text": field["official_text"], "site_text": field["site_text"],
                "verification_method": "相同raw_id及名称；仅去除HTML标签和空白后逐字段完全一致"})
            decisions.append({"id": kid, "matched": matched, "field": field["field"]})
            if matched:
                parent_ids.append(kid)
        if item["site_interpretation"]:
            records.append({**base, "id": "WX-"+item["id"]+"-interpretation", "title": item["name"]+"·站方解释",
                "body": "【站方解释，不是官方规则或实战保证】"+item["site_interpretation"], "claim_type": "site_interpretation",
                "verification": "site_attributed_only", "eligible": bool(parent_ids), "parent_ids": parent_ids})
        if item["pending"]:
            records.append({**base, "id": "WX-"+item["id"]+"-pending", "title": item["name"]+"·待确认",
                "body": "【待确认，不能当成已证实机制】"+item["pending"], "claim_type": "pending", "verification": "unconfirmed", "eligible": False})
    return records, decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true", help="Read downloaded cache into a minimal reviewable snapshot")
    parser.add_argument("--refresh", action="store_true", help="Download public catalogs, stage and rebuild")
    args = parser.parse_args()
    cache = ROOT / "artifacts/import"
    if args.refresh:
        cache.mkdir(parents=True, exist_ok=True)
        for kind, (number, _, _) in SELECTION.items():
            for url, name in [(f"https://wzwxq.com/explorer-catalogs/{kind}.json", f"{kind}.json"), (OFFICIAL.format(number), f"official-{number}.js")]:
                with urlopen(url, timeout=30) as response:
                    (cache/name).write_bytes(response.read())
    if args.stage or args.refresh:
        stage(cache)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    records, decisions = build(snapshot)
    (ROOT/"data/wzwxq.json").write_text(json.dumps(records, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    report = {"collected_at": snapshot["collected_at"], "snapshot_sha256": digest(SNAPSHOT.read_bytes()), "catalogs": snapshot["catalogs"], "selected_objects": len(snapshot["items"]), "record_counts": dict(Counter(r["claim_type"] for r in records)), "field_checks": decisions}
    (ROOT/"data/imports/wzwxq-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("selected_objects", "record_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
