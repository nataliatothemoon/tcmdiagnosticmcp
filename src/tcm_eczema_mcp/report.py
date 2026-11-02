"""Render the case-study report from cited knowledge only."""

from __future__ import annotations

from tcm_eczema_mcp.knowledge import Knowledge
from tcm_eczema_mcp.texts import BOTH_NOTE, ETIOLOGY, LIMITS

LABELS = {
    "pale": "pale",
    "light_red": "light red",
    "red": "red",
    "red_tip_and_sides": "red at the tip and sides",
    "crimson": "deep red",
    "thin": "thin",
    "moderate": "moderate",
    "swollen": "swollen",
    "absent": "absent",
    "present": "present",
    "white": "white",
    "yellow": "yellow",
    "none": "absent",
    "scanty_or_peeled": "scanty or peeled",
    "thick": "thick",
    "yes": "yes",
    "no": "no",
    "unremarkable": "unremarkable",
    "redder": "redder than the rest",
    "paler": "paler than the rest",
    "thicker_coat": "thicker coat",
    "peeled": "peeled coat",
    "weeping_vesicles": "weeping vesicles or blisters",
    "papules_little_exudate": "papules with little exudation",
    "dry_rough_lichenified": "dry, rough, or lichenified skin",
    "itch_without_heat": "itch without the skin feeling hot",
    "itch_with_heat": "itch with a hot feeling",
    "burning": "burning",
    "acute": "acute",
    "subacute": "subacute",
    "chronic": "chronic",
    "hands": "hands",
    "fingers": "fingers",
    "feet": "feet",
    "ankles": "ankles",
    "elbow_flexures": "inner elbows",
    "upper_lip": "upper lip",
    "posterior_thighs": "back of the thighs",
    "face_other": "other face",
    "trunk": "trunk",
    "scalp": "scalp",
    "other": "other",
}


def render_report(bundle: dict, knowledge: Knowledge) -> str:
    case = bundle["case"]
    lines: list[str] = [
        f"# Eczema case study {case['case_number']}",
        "",
        LIMITS,
        "",
        "## Case",
        "",
        f"- Case number: {case['case_number']}",
        f"- Study date: {case['study_date']}",
        f"- Age: {case['age_years']}",
        f"- Sex: {case['sex']}",
        f"- Purpose: {case['purpose']}",
        f"- Knowledge version: {knowledge.version}",
        "",
        "## How this result was reached",
        "",
        ETIOLOGY,
        "",
        "Pattern names below are the four patterns in that consensus. "
        "A sign adds or removes points only when the consensus names it for that pattern. "
        "The pulse was not assessed.",
        "",
        "## Tongue",
        "",
    ]
    tongue = bundle["tongue"]
    lines.extend(
        [
            f"- Body color: {LABELS[tongue['body_color']]}",
            f"- Shape: {LABELS[tongue['shape']]}",
            f"- Tooth marks: {LABELS[tongue['tooth_marks']]}",
            f"- Coat color: {LABELS[tongue['coat_color']]}",
            f"- Coat thickness: {LABELS[tongue['coat_thickness']]}",
            f"- Greasy coat: {LABELS[tongue['coat_greasy']]}",
            f"- Cracks: {LABELS[tongue['cracks']]}",
            "- Regions, recorded only and not scored: "
            f"tip {LABELS[tongue['region_tip']]}; "
            f"sides {LABELS[tongue['region_sides']]}; "
            f"center {LABELS[tongue['region_center']]}; "
            f"root {LABELS[tongue['region_root']]}.",
            "",
            "Region names follow the classical map in the tongue-inspection review "
            f"({knowledge.source_line('tongue-review')}). They do not change the pattern score.",
            "",
            "## Lesions",
            "",
            f"- Stage: {LABELS[bundle['lesions']['stage']]}",
            f"- Form: {LABELS[bundle['lesions']['morphology']]}",
            f"- Sensation: {LABELS[bundle['lesions']['sensation']]}",
            "- Sites: " + ", ".join(LABELS[site] for site in bundle["sites"]) + ".",
            "",
            "Sites are stored so cases can be compared later. A site does not by itself select a pattern.",
            "",
            "## Questions and answers",
            "",
        ]
    )
    if not bundle["answers"]:
        lines.append("No inquiry items applied. Inspection had already ruled out every pattern these questions inform.")
        lines.append("")
    for answer in bundle["answers"]:
        lines.append(f"- {answer['prompt']} **{answer['label']}**")
        if answer["scored"]:
            lines.append("  This answer changed the score for at least one pattern still in the differential.")
        else:
            lines.append("  This answer is stored and does not change the pattern score.")
    lines.extend(["", "## Patterns incompatible with inspection", ""])
    if not bundle["ruled_out"]:
        lines.append("None. All four consensus patterns remained possible after inspection.")
    for item in bundle["ruled_out"]:
        pattern = knowledge.patterns_by_id[item["pattern_id"]]
        lines.append(
            f"- {pattern['name_en']} ({pattern['name_zh']}): {item['reason']}"
        )
    lines.extend(["", "## Scores for patterns that remained possible", ""])
    if not bundle["ranked"]:
        lines.append("Inspection did not leave a consensus pattern to score.")
    for pattern_id in bundle["ranked"]:
        pattern = knowledge.patterns_by_id[pattern_id]
        lines.append(f"- {pattern['name_en']} ({pattern['name_zh']}): {bundle['scores'][pattern_id]}")
    lines.append("")
    if bundle["leader"] is None:
        lines.extend(
            [
                "## Leading pattern",
                "",
                "No consensus pattern remained after inspection, so this report does not assign one.",
                "",
            ]
        )
    else:
        weak = bundle["scores"][bundle["leader"]] <= 0
        lines.extend(["## Leading pattern", ""])
        if weak:
            lines.append(
                "The highest score is not positive. The name below is the closest consensus pattern, "
                "and the match is limited."
            )
            lines.append("")
        _pattern_block(lines, knowledge, bundle, bundle["leader"])
        if bundle["runner_up"]:
            lines.extend(["## Close second pattern", ""])
            lines.append(
                "This pattern finished within 3 points of the leader, so both stay visible."
            )
            lines.append("")
            _pattern_block(lines, knowledge, bundle, bundle["runner_up"])
        others = [
            pattern_id
            for pattern_id in bundle["ranked"]
            if pattern_id not in {bundle["leader"], bundle["runner_up"]}
        ]
        if others:
            lines.extend(["## Other patterns that remained possible", ""])
            for pattern_id in others:
                _pattern_block(lines, knowledge, bundle, pattern_id)

    lines.extend(["## What did not decide the pattern", ""])
    unscored = [answer for answer in bundle["answers"] if not answer["scored"]]
    if unscored:
        lines.append("These answers were kept and did not add or remove points:")
        lines.append("")
        for answer in unscored:
            lines.append(f"- {answer['prompt']} {answer['label']}")
        lines.append("")
    else:
        lines.append("Every answer in this workup carried a cited weight.")
        lines.append("")
    if bundle["notes"]:
        lines.append(bundle["notes"])
        lines.append("")
        lines.append("Those notes are context. They are not a pattern name and they are not in the score.")
        lines.append("")

    lines.extend(["## Daily care from the consensus", ""])
    for item in knowledge.care:
        lines.append(f"- {item['text']}")
    lines.append("")

    lines.extend(["## Acupuncture points named in the consensus", ""])
    lines.append(knowledge.main_points["method_note"])
    lines.append("")
    lines.append("Main points for eczema in the consensus:")
    lines.append("")
    for point in knowledge.main_points["points"]:
        lines.append(f"- {point['code']} {point['en']} ({point['zh']})")
    lines.append("")
    for pattern_id in _reported_patterns(bundle):
        pattern = knowledge.patterns_by_id[pattern_id]
        if pattern["needle_method"] == "reducing":
            method = "a reducing method"
        else:
            method = "an even method"
        lines.append(
            f"For {pattern['name_en']} ({pattern['name_zh']}), the consensus uses {method}."
        )
        if pattern["extra_points"]:
            lines.append("Added points:")
            lines.append("")
            for point in pattern["extra_points"]:
                lines.append(f"- {point['code']} {point['en']} ({point['zh']})")
            lines.append("")
        else:
            lines.append("No added points are listed for this pattern beyond the main set.")
            lines.append("")

    lines.extend(["## Herbal formulas named in the consensus", ""])
    lines.append(
        "Formulas are named for a licensed practitioner. This report does not give a dose."
    )
    lines.append("")
    for pattern_id in _reported_patterns(bundle):
        pattern = knowledge.patterns_by_id[pattern_id]
        herbs = ", ".join(pattern["herbs"])
        lines.append(
            f"- {pattern['name_en']}: {pattern['formula']} ({pattern['formula_zh']}). "
            f"Principle: {pattern['principle']} ({pattern['principle_zh']}). "
            f"Herbs named in the consensus: {herbs}. {pattern['herbs_note']}"
        )
        related = pattern.get("related_formula")
        if related:
            lines.append(f"  {related['text']}")
    if not _reported_patterns(bundle):
        lines.append("No formula is named, because no consensus pattern remained.")
    lines.append("")

    lines.extend(["## External care named in the consensus", ""])
    external_lines = _external_lines(knowledge, bundle)
    if external_lines:
        lines.extend(external_lines)
    else:
        lines.append("No external method in this knowledge pack matched the recorded stage and lesion form.")
    lines.append("")

    if case["purpose"] == "both":
        lines.extend(["## General check-in", "", BOTH_NOTE, ""])

    lines.extend(["## Sources", ""])
    used = _used_sources(bundle, knowledge)
    for source_id in sorted(used):
        lines.append(f"- {knowledge.source_line(source_id)}")
    lines.append("")
    lines.append(
        "The Guangxi hospital series is listed as context for which syndromes were common in that clinic. "
        "Its color measurements are not used as weights."
    )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _pattern_block(lines: list[str], knowledge: Knowledge, bundle: dict, pattern_id: str) -> None:
    pattern = knowledge.patterns_by_id[pattern_id]
    lines.append(f"### {pattern['name_en']} ({pattern['name_zh']})")
    lines.append("")
    lines.append(pattern["mechanism"])
    lines.append("")
    supporting = [row for row in bundle["evidence"] if row["pattern"] == pattern_id and row["weight"] > 0]
    against = [row for row in bundle["evidence"] if row["pattern"] == pattern_id and row["weight"] < 0]
    lines.append("Supports this pattern:")
    lines.append("")
    if supporting:
        for row in supporting:
            lines.append(f"- {row['statement']} ({row['weight']:+d})")
    else:
        lines.append("- No cited sign in this workup supported it.")
    lines.append("")
    lines.append("Counts against this pattern:")
    lines.append("")
    if against:
        for row in against:
            lines.append(f"- {row['statement']} ({row['weight']:+d})")
    else:
        lines.append("- No cited sign in this workup counted against it.")
    lines.append("")


def _reported_patterns(bundle: dict) -> list[str]:
    ordered = []
    if bundle["leader"]:
        ordered.append(bundle["leader"])
    if bundle["runner_up"]:
        ordered.append(bundle["runner_up"])
    return ordered


def _external_lines(knowledge: Knowledge, bundle: dict) -> list[str]:
    morphology = bundle["lesions"]["morphology"]
    stage = bundle["lesions"]["stage"]
    lines = []
    for item in knowledge.external.values():
        if "when_morphology" in item and morphology not in item["when_morphology"]:
            continue
        if "when_not_morphology" in item and morphology in item["when_not_morphology"]:
            continue
        if "when_stage" in item and stage not in item["when_stage"]:
            continue
        lines.append(f"- {item['text']}")
    return lines


def _used_sources(bundle: dict, knowledge: Knowledge) -> set[str]:
    used = {knowledge.main_points["source"], "tongue-review", "gx-tongue-2021", "consensus-2016"}
    for item in knowledge.care:
        used.add(item["source"])
    for row in bundle["evidence"]:
        used.add(row["source"])
    for pattern_id in _reported_patterns(bundle):
        pattern = knowledge.patterns_by_id[pattern_id]
        used.add(pattern["source"])
        related = pattern.get("related_formula")
        if related:
            used.add(related["source"])
    return used
