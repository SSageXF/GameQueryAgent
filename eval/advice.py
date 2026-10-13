"""Transparent rule rubric, with human review required for semantic grounding."""
import re
from eval.text import affirmative_match


def score_advice(turn, answer):
    rubric = turn.get("advice_rubric")
    if not rubric:
        return None
    # Quoting the question or echoing its conditions is not reasoning about them.
    text = "\n".join(line for line in answer.splitlines() if not re.match(r"\s*(?:>|你给出的条件是[:：]|你的问题是[:：]|资料范围[:：])", line))
    text = text.replace(turn["message"], "")
    dimensions = []
    for dimension in rubric["dimensions"]:
        matches = [[m.group(0) for pattern in group for m in re.finditer(pattern, text)] for group in dimension["all_of"]]
        passed = all(matches)
        dimensions.append({"id": dimension["id"], "description": dimension["description"], "passed": passed,
                           "points": dimension["points"] if passed else 0, "critical": dimension.get("critical", False), "matched_evidence": matches})
    violations = [p for p in rubric.get("forbidden_recommendations", []) if affirmative_match(p, text)]
    score = sum(d["points"] for d in dimensions)
    return {"score": score, "maximum": sum(d["points"] for d in rubric["dimensions"]), "threshold": rubric["threshold"],
            "passed": score >= rubric["threshold"] and all(d["passed"] for d in dimensions if d["critical"]) and not violations,
            "dimensions": dimensions, "violations": violations, "human_review_required": True}
