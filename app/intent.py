"""Pure routing: no network, knowledge-miss is never an out-of-scope signal."""
import re
from dataclasses import dataclass

from .schemas import Intent

GAME = re.compile(r"棋|英雄|天赋|能量|竞拍|拍卖|合成|阵容|站位|升级|秘技|专属|白歌|瑶妹|常小娥|小妲己|香香|庄小鱼|回合|血量|利息|觉醒")
UNSUPPORTED = re.compile(r"(?:查|读取|查看|获取|打开).{0,8}(?:我的|我最近|账号|个人).{0,8}(?:战绩|胜率|账户|段位)|(?:帮我|替我|自动).{0,6}(?:登录|充值|代打|操作|买皮肤|领取)|读取.{0,6}(?:屏幕|对局)|(?:天气|写代码|订机票)")
ADVICE = re.compile(r"该不该|要不要|怎么办|怎么打|怎么选|选哪个|建议|推荐|适合|帮我分析|如何选择|能不能赢|怎么站|怎么摆")
SMALLTALK = re.compile(r"^(你好|您好|嗨|hello|hi|谢谢.*|多谢.*|再见.*|晚安.*|你是谁.*|你叫什么.*|今天好累.*|我输了好难过.*)[！!。.?？\s]*$", re.I)


@dataclass
class Route:
    intent: Intent
    query: str
    restricted: bool = False


def classify(query: str) -> Route:
    clauses = [s.strip() for s in re.split(r"[；;，,。\n]|再讲|再介绍", query) if s.strip()]
    restricted = any(UNSUPPORTED.search(s) for s in clauses)
    allowed = [s for s in clauses if not UNSUPPORTED.search(s) and GAME.search(s)]
    if restricted and not allowed:
        return Route("out_of_scope", query, True)
    if restricted:
        query = "；".join(allowed)
    if ADVICE.search(query):
        return Route("advice", query, restricted)
    if SMALLTALK.fullmatch(query):
        return Route("chitchat", query, restricted)
    # Unknown questions stay knowledge queries; retrieval determines evidence sufficiency.
    return Route("knowledge", query, restricted)


def missing_conditions(query: str) -> list[str]:
    if not re.search(r"升级|刷新|升阶|升本", query):
        if re.search(r"站位|怎么站|怎么摆|怎么打", query) and not re.search(r"阵容[:：]|场上[:：]|前排.{1,12}后排", query):
            return ["当前上阵英雄", "主要对手或遇到的问题"]
        return []
    fields = {
        "当前回合": r"第?\d+回合|回合[:：]?\d+",
        "剩余能量": r"\d+(?:点)?能量|能量[:：]?\d+",
        "棋手等级": r"棋手.{0,8}\d+级|等级[:：]?\d+|\d+级棋手",
        "当前阵容": r"阵容[:：]|场上[:：]|上阵[:：]",
    }
    return [label for label, pattern in fields.items() if not re.search(pattern, query)]
