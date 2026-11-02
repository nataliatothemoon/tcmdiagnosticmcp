"""Deterministic inspection scoring and question selection."""

from __future__ import annotations

from tcm_eczema_mcp.knowledge import Knowledge
from tcm_eczema_mcp.texts import RUNNER_UP_MARGIN


def snapshot(tongue: dict, lesions: dict) -> dict:
    return {"tongue": tongue, "lesions": lesions}


def _get(snapshot_data: dict, path: str):
    node = snapshot_data
    for part in path.split("."):
        node = node[part]
    return node


def _matches(condition: dict, snapshot_data: dict) -> bool:
    value = _get(snapshot_data, condition["path"])
    if "eq" in condition:
        return value == condition["eq"]
    if "not_eq" in condition:
        return value != condition["not_eq"]
    if "in" in condition:
        return value in condition["in"]
    if "not_in" in condition:
        return value not in condition["not_in"]
    raise ValueError(f"Condition has no operator: {condition}")


def ruled_out(knowledge: Knowledge, snapshot_data: dict) -> dict[str, str | None]:
    """Map pattern id to a reason, or None when the pattern remains plausible."""
    result: dict[str, str | None] = {}
    for pattern in knowledge.patterns:
        reason = None
        for rule in pattern["rule_out"]:
            if all(_matches(condition, snapshot_data) for condition in rule["all"]):
                reason = rule["statement"]
                break
        result[pattern["id"]] = reason
    return result


def active_ids(rule_map: dict[str, str | None]) -> list[str]:
    return [pattern_id for pattern_id, reason in rule_map.items() if reason is None]


def inspection_evidence(knowledge: Knowledge, snapshot_data: dict, active: set[str]) -> list[dict]:
    evidence: list[dict] = []
    for path, by_value in knowledge.weights.items():
        value = _get(snapshot_data, path)
        for effect in by_value.get(value, []):
            if effect["pattern"] not in active:
                continue
            evidence.append(_effect_row(effect, origin="inspection"))
    return evidence


def answer_evidence(question: dict, option_id: str, active: set[str]) -> list[dict]:
    option = next(item for item in question["options"] if item["id"] == option_id)
    rows = []
    for effect in option["effects"]:
        if effect["pattern"] not in active:
            continue
        rows.append(_effect_row(effect, origin=f"question:{question['id']}"))
    return rows


def scores_from(evidence: list[dict], pattern_ids: list[str]) -> dict[str, int]:
    totals = {pattern_id: 0 for pattern_id in pattern_ids}
    for row in evidence:
        totals[row["pattern"]] += row["weight"]
    return totals


def rank_patterns(scores: dict[str, int], active: list[str]) -> list[str]:
    return sorted(active, key=lambda pattern_id: (-scores[pattern_id], pattern_id))


def leader_and_runner(scores: dict[str, int], active: list[str]) -> tuple[str | None, str | None]:
    ordered = rank_patterns(scores, active)
    if not ordered:
        return None, None
    leader = ordered[0]
    runner = None
    if len(ordered) > 1 and scores[ordered[1]] >= scores[leader] - RUNNER_UP_MARGIN:
        runner = ordered[1]
    return leader, runner


def question_applies(question: dict, active: set[str], sex: str, age: int) -> bool:
    if not set(question["informs"]) & active:
        return False
    when = question.get("when")
    if not when:
        return True
    if sex not in when["sex"]:
        return False
    return when["age_min"] <= age <= when["age_max"]


def plan_questions(
    knowledge: Knowledge,
    scores: dict[str, int],
    active: list[str],
    sex: str,
    age: int,
) -> list[str]:
    """Full workup. Leader questions come first. Nothing unanswered is dropped later."""
    leader, _runner = leader_and_runner(scores, active)
    chosen = [
        question
        for question in knowledge.questions
        if question_applies(question, set(active), sex, age)
    ]
    chosen.sort(key=lambda question: (0 if leader and leader in question["informs"] else 1, question["id"]))
    return [question["id"] for question in chosen]


def _effect_row(effect: dict, origin: str) -> dict:
    return {
        "pattern": effect["pattern"],
        "weight": effect["weight"],
        "source": effect["source"],
        "statement": effect["statement"],
        "origin": origin,
    }
