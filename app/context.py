import re
from dataclasses import dataclass

from .schemas import Message

# Deliberately conservative aliases: 香香 is not silently equated with a hero card.
ENTITY_ALIASES = {"棋手李白": "白歌", "棋手嫦娥": "常小娥"}
ALIASES = {**ENTITY_ALIASES, "拍卖": "竞拍", "卖牌": "出售英雄牌", "升人口": "升级", "升本": "升级"}
PEOPLE = ("白歌", "瑶妹", "常小娥", "小妲己", "香香", "庄小鱼", "苏烈", "曜", "孙膑", "孙尚香", "弈星", "盾山", "赵云", "白起", "李白")
ENTITIES = PEOPLE + ("竞拍", "天赋", "能量", "英雄")


def normalize(text: str, aliases: bool = True) -> str:
    if aliases:
        for old, new in ALIASES.items():
            text = text.replace(old, new)
    return text.strip()


@dataclass
class Context:
    query: str
    history: list[dict]
    ambiguous: bool = False


def prepare(message: str, history: list[Message], enhanced: bool = True, entity_names=None) -> Context:
    # Budget from the most recent end; no model-generated summary of untrusted history.
    recent, remaining = [], 24000
    for item in reversed(history):
        if len(item.content) > remaining:
            break
        recent.insert(0, item.model_dump())
        remaining -= len(item.content)
    query = normalize(message, enhanced)
    if not enhanced:
        return Context(query, recent)
    # Elaboration refers to the previous topic, not necessarily a named card.
    elaboration = re.compile(r"^(?:(?:你)?(?:上面|刚才|之前)说的|上文|这个|那)?[，,\s]*(?:请|再|能不能|可以)?(?:详细|具体)?(?:讲|说|解释|展开说说|展开)(?:得)?(?:详细|具体|清楚)?(?:一)?(?:点|些|下)?[。！!？?\s]*$")
    if elaboration.fullmatch(query):
        users = [normalize(x['content']) for x in recent if x['role'] == 'user']
        topics = [x for x in users if not elaboration.fullmatch(x)]
        if topics:
            return Context(topics[-1] + '；追问：' + query, recent)
        return Context(query, recent, True)
    is_followup = bool(re.search(r"这个|那个|它|他|她|那.*呢|还要|然后呢", query))
    people_names=tuple(dict.fromkeys([*PEOPLE,*(entity_names or [])]))
    def mentioned(text):
        found=[e for e in people_names if e in text]
        return [e for e in found if not any(e!=x and e in x for x in found)]
    explicit = mentioned(query)+[e for e in ENTITIES[len(PEOPLE):] if e in query]
    if is_followup and (not explicit or all(e in {"天赋", "英雄", "能量"} for e in explicit)):
        for item in reversed(recent):
            if item["role"] != "user":
                continue
            prior = normalize(item["content"])
            people = mentioned(prior)
            found = people or [e for e in ENTITIES[len(PEOPLE):] if e in prior]
            if len(found) > 1:
                return Context(query, recent, True)
            if found:
                mode='钻石狂潮 ' if '钻石狂潮' in prior and '万象大赛' not in query else ''
                query = mode + found[0] + " " + query
                return Context(query, recent)
        return Context(query, recent, True)
    # Carry user-provided situational details when the player answers a clarification.
    if recent and recent[-1]["role"] == "assistant" and any(s in recent[-1]["content"] for s in ("请补充", "请告诉", "再告诉", "还缺")) and re.search(r"\d+|阵容[:：]|场上[:：]", query):
        users = [normalize(x["content"]) for x in recent if x["role"] == "user"]
        if users:
            query = "；".join(users[-2:] + [query])
    return Context(query, recent)
