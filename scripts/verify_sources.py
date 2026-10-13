"""Read official public pages; emit fingerprints and sanity checks, never auto-publish knowledge."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    "https://wxq.qq.com/cp/a202609xszy/index.html": {
        "six_players": "6位棋手", "starting_health": "60生命值", "hero_cost": "英雄牌固定消耗3能量",
        "sale_return": "出售英雄牌获得1能量", "auction_tie": "先出价者会获得拍品", "hero_cap": "最高等级为999级",
        "white_silver_refresh": "白银段位", "baige_copy": "每进行4次英雄合成",
    },
    "https://wxq.qq.com/": {"beginner_lineup": "三分登场流", "totem_lineup": "大河图腾流", "tactics_lineup": "逐鹿战术牌流"},
}


def main():
    pages = []
    for url, checks in PAGES.items():
        with urlopen(Request(url, headers={"User-Agent":"GameQueryAgent-source-audit/0.1"}), timeout=30) as response:
            raw = response.read(2_000_000)
        html = raw.decode("utf-8")
        text = re.sub(r"(?s)<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>", "", html)
        text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", text))
        pages.append({"url":url, "sha256":hashlib.sha256(raw).hexdigest(), "byte_count":len(raw), "checks":{name: value in text for name, value in checks.items()}})
    report = {"checked_at":datetime.now(timezone.utc).isoformat(), "scope":"当前网页是否仍包含开发代理已阅读的关键事实；不是所有条目或最新版本正确性的证明。", "pages":pages}
    path = ROOT / "data/source_audit.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if not all(all(p["checks"].values()) for p in pages):
        raise SystemExit("官方页面内容变化：请人工复核 source_audit.json，知识库未自动修改。")
    print("Official source fingerprints saved; 11 sanity checks passed.")


if __name__ == "__main__":
    main()
