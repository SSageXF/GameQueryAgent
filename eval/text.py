import re


def affirmative_match(pattern: str, text: str) -> bool:
    """Limited same-clause negation handling; never a substitute for human review."""
    for match in re.finditer(pattern, text, re.I):
        prefix = re.split(r"[。；，！？\n]", text[:match.start()])[-1]
        negated=re.search(r"不能|无法|不是|不代表|不保证|不应|不要|并非|不$", prefix)
        negated=negated or re.search(r"(?:没有|并无|无)(?:任何|所谓的|所谓)?$",prefix)
        if not negated:
            return True
    return False
