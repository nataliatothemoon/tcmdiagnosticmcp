import json
from pathlib import Path

import pytest

from tcm_eczema_mcp.knowledge import Knowledge
from tcm_eczema_mcp.service import Service

REGIONS = {
    "region_tip": "unremarkable",
    "region_sides": "unremarkable",
    "region_center": "unremarkable",
    "region_root": "unremarkable",
}

REFERENCE_TONGUE = {
    "body_color": "light_red",
    "shape": "swollen",
    "tooth_marks": "present",
    "coat_color": "white",
    "coat_thickness": "thin",
    "coat_greasy": "no",
    "cracks": "present",
    "region_tip": "unremarkable",
    "region_sides": "unremarkable",
    "region_center": "thicker_coat",
    "region_root": "thicker_coat",
}

REFERENCE_ANSWERS = {
    "thirst": "no",
    "restlessness": "unknown",
    "bitter_taste": "no",
    "stool_dry": "unknown",
    "urine_during_flare": "unknown",
    "appetite": "good",
    "fatigue": "yes",
    "abdominal_distension": "no",
    "loose_stool": "unknown",
    "limb_heaviness": "unknown",
    "spicy_food": "often",
    "alcohol": "never",
    "fishy_food": "unknown",
    "cycle_timing": "unknown",
}

REFERENCE_NOTES = (
    "Context recorded and not scored: flares with stress; the skin worsens when the weather changes; "
    "iced drinks are craved; the low back and knees feel weak when energy drops."
)


@pytest.fixture
def knowledge() -> Knowledge:
    return Knowledge()


@pytest.fixture
def svc(tmp_path: Path, knowledge: Knowledge) -> Service:
    return Service(
        db_path=tmp_path / "cases.sqlite",
        image_root=tmp_path / "images",
        contribution_root=tmp_path / "contributions",
        private_path=tmp_path / "private.sqlite",
        knowledge=knowledge,
    )


CONTACT = {"name": "Amina Farouk", "email": "amina.farouk@example.com"}


def test_server_module_registers_tools() -> None:
    from tcm_eczema_mcp.server import build_report, mcp, start_case

    assert mcp is not None
    assert start_case.__name__ == "start_case"
    assert build_report.__name__ == "build_report"


def test_knowledge_pack_is_internally_consistent(knowledge: Knowledge) -> None:
    assert knowledge.version == "consensus-2016-v1"
    assert {pattern["id"] for pattern in knowledge.patterns} == {
        "wind_heat",
        "damp_heat",
        "spleen_damp",
        "yin_blood_dry",
    }
    for question in knowledge.questions:
        assert question["options"]
        assert any(option["id"] == "unknown" for option in question["options"])


def test_contact_stays_out_of_the_knowledge_base(svc: Service) -> None:
    with pytest.raises(ValueError, match="Email"):
        svc.start_case(
            purpose="eczema",
            age_years=25,
            sex="female",
            study_date="2026-10-14",
            name="Amina Farouk",
            email="not-an-email",
        )
    assert svc.query_cases() == []
    assert svc.list_mailing_list() == []
    assert "name" not in svc.store.column_names("cases")
    assert "email" not in svc.store.column_names("cases")


def test_curious_purpose_does_not_open_a_case(svc: Service) -> None:
    opened = svc.start_case(
        purpose="curious",
        age_years=40,
        sex="male",
        study_date="2026-01-02",
        name="Sam Lee",
        email="sam.lee@example.com",
    )
    assert opened["case_number"] is None
    assert "next release" in opened["message"]
    assert svc.query_cases() == []
    assert svc.list_mailing_list() == [{"name": "Sam Lee", "email": "sam.lee@example.com"}]


def test_reference_case_is_cs_2026_001(svc: Service, tmp_path: Path) -> None:
    photo = tmp_path / "tongue.png"
    photo.write_bytes(b"\x89PNG\r\n")
    opened = svc.start_case(
        purpose="eczema",
        age_years=25,
        sex="female",
        study_date="2026-10-14",
        **CONTACT,
    )
    assert opened["case_number"] == "CS-2026-001"
    assert "opt out" in opened["terms"].lower()
    case_number = opened["case_number"]
    svc.attach_image(case_number, "tongue", str(photo))
    svc.record_tongue(case_number, **REFERENCE_TONGUE)
    svc.record_lesions(
        case_number,
        sites=["hands", "fingers", "feet", "ankles", "posterior_thighs", "elbow_flexures", "upper_lip"],
        morphology="weeping_vesicles",
        sensation="itch_without_heat",
        stage="acute",
    )
    result = _finish(svc, case_number, REFERENCE_ANSWERS, notes=REFERENCE_NOTES)
    asked = set(result["asked_question_ids"])
    assert {"appetite", "limb_heaviness", "loose_stool", "thirst", "cycle_timing"} <= asked
    assert asked.isdisjoint({"dry_mouth", "palm_sole_heat", "fever", "onset_speed"})
    assert result["leader"] in {"damp_heat", "spleen_damp"}
    assert set(result["ruled_out"]) >= {"wind_heat", "yin_blood_dry"}
    report = result["markdown"]
    assert "消风散" not in report
    assert "凉血四物汤" not in report
    assert "Spleen & Kidney" not in report
    assert "Marwa" not in report
    assert "Dubai" not in report
    assert "Amina Farouk" not in report
    assert "amina.farouk@example.com" not in report
    assert "educational case study" in report
    assert "licensed" in report
    formula = {
        "spleen_damp": "除湿胃苓汤",
        "damp_heat": "龙胆泻肝汤",
    }[result["leader"]]
    assert formula in report
    saved = json.loads((tmp_path / "contributions" / "CS-2026-001.json").read_text(encoding="utf-8"))
    assert saved["age_years"] == 25
    assert saved["sex"] == "female"
    assert saved["study_date"] == "2026-10-14"
    assert "notes" not in saved
    assert "path" not in json.dumps(saved)
    assert "tongue-1" not in json.dumps(saved)
    assert "Amina" not in json.dumps(saved)
    assert "example.com" not in json.dumps(saved)
    follow_up = svc.get_follow_up("CS-2026-001")
    assert follow_up == {
        "case_number": "CS-2026-001",
        "name": "Amina Farouk",
        "email": "amina.farouk@example.com",
    }
    found = svc.query_cases(pattern_id=result["leader"], site="posterior_thighs")
    assert [row["case_number"] for row in found] == ["CS-2026-001"]
    fetched = svc.get_case("CS-2026-001")
    assert fetched["local_images"]
    assert "name" not in fetched
    assert "email" not in fetched


def test_notes_cannot_copy_the_private_name_into_the_case(svc: Service) -> None:
    case_number = _open(svc, age=25, study_date="2026-03-01")
    _record_reference_lesions(svc, case_number)
    with pytest.raises(ValueError, match="knowledge-base"):
        _finish(svc, case_number, {}, notes="Follow up with Amina Farouk")


def test_heat_case_gets_heat_questions_and_not_spleen_questions(svc: Service) -> None:
    case_number = _open(svc, age=30, study_date="2026-10-15")
    svc.record_tongue(
        case_number,
        body_color="red",
        shape="moderate",
        tooth_marks="absent",
        coat_color="yellow",
        coat_thickness="thin",
        coat_greasy="no",
        cracks="absent",
        **REGIONS,
    )
    svc.record_lesions(
        case_number,
        sites=["elbow_flexures"],
        morphology="papules_little_exudate",
        sensation="itch_with_heat",
        stage="acute",
    )
    result = _finish(svc, case_number, {})
    asked = set(result["asked_question_ids"])
    assert {"thirst", "bitter_taste", "restlessness", "stool_dry", "cycle_timing"} <= asked
    assert asked.isdisjoint({"appetite", "limb_heaviness", "loose_stool", "dry_mouth", "palm_sole_heat"})
    assert result["leader"] == "wind_heat"
    assert "消风散" in result["markdown"]


def test_dry_case_names_the_consensus_formula_and_the_related_trial_formula(svc: Service) -> None:
    case_number = _open(svc, age=40, study_date="2026-04-01")
    svc.record_tongue(
        case_number,
        body_color="red",
        shape="thin",
        tooth_marks="absent",
        coat_color="none",
        coat_thickness="scanty_or_peeled",
        coat_greasy="no",
        cracks="present",
        **REGIONS,
    )
    svc.record_lesions(
        case_number,
        sites=["elbow_flexures"],
        morphology="dry_rough_lichenified",
        sensation="itch_without_heat",
        stage="chronic",
    )
    result = _finish(svc, case_number, {})
    assert result["leader"] == "yin_blood_dry"
    assert "凉血四物汤" in result["markdown"]
    assert "当归饮子" in result["markdown"]
    assert "appetite" not in result["asked_question_ids"]


def test_same_inspection_plans_the_same_questions(tmp_path: Path, knowledge: Knowledge) -> None:
    first = _service(tmp_path / "a", knowledge)
    second = _service(tmp_path / "b", knowledge)
    left = _question_ids(first, age=25, study_date="2026-10-14", tongue=REFERENCE_TONGUE, weeping=True)
    right = _question_ids(second, age=25, study_date="2026-10-14", tongue=REFERENCE_TONGUE, weeping=True)
    assert left == right
    assert left


def test_opt_out_returns_the_report_and_leaves_no_research_row(svc: Service, tmp_path: Path) -> None:
    photo = tmp_path / "lesion.png"
    photo.write_bytes(b"\x89PNG\r\n")
    case_number = _open(svc, age=25, study_date="2026-10-14")
    svc.attach_image(case_number, "lesion", str(photo))
    _record_reference_lesions(svc, case_number)
    with pytest.raises(ValueError, match="Finish every workup"):
        svc.build_report(case_number, opt_out=False)
    result = _finish(svc, case_number, {}, opt_out=True)
    assert result["contributed"] is False
    assert "educational case study" in result["markdown"]
    assert svc.query_cases() == []
    assert list((tmp_path / "contributions").glob("*.json")) == []
    with pytest.raises(ValueError, match="No case"):
        svc.get_case(case_number)
    assert not (tmp_path / "images" / case_number).exists()
    assert svc.get_follow_up(case_number)["email"] == CONTACT["email"]
    nxt = svc.start_case(
        purpose="eczema",
        age_years=25,
        sex="female",
        study_date="2026-10-14",
        **CONTACT,
    )
    assert nxt["case_number"] == "CS-2026-002"


def test_both_mentions_the_general_track(svc: Service) -> None:
    opened = svc.start_case(
        purpose="both",
        age_years=25,
        sex="female",
        study_date="2026-10-14",
        **CONTACT,
    )
    _record_reference_lesions(svc, opened["case_number"])
    result = _finish(svc, opened["case_number"], REFERENCE_ANSWERS)
    assert "next release" in result["markdown"]


def test_report_pattern_headings_are_from_the_pack(svc: Service, knowledge: Knowledge) -> None:
    case_number = _open(svc, age=25, study_date="2026-10-14")
    _record_reference_lesions(svc, case_number)
    result = _finish(svc, case_number, REFERENCE_ANSWERS)
    allowed = {f"{item['name_en']} ({item['name_zh']})" for item in knowledge.patterns}
    for line in result["markdown"].splitlines():
        if line.startswith("### "):
            assert line.removeprefix("### ") in allowed


def _service(folder: Path, knowledge: Knowledge) -> Service:
    return Service(
        db_path=folder / "cases.sqlite",
        image_root=folder / "images",
        contribution_root=folder / "contributions",
        private_path=folder / "private.sqlite",
        knowledge=knowledge,
    )


def _open(svc: Service, age: int, study_date: str) -> str:
    opened = svc.start_case(
        purpose="eczema",
        age_years=age,
        sex="female",
        study_date=study_date,
        **CONTACT,
    )
    return opened["case_number"]


def _record_reference_lesions(svc: Service, case_number: str) -> None:
    svc.record_tongue(case_number, **REFERENCE_TONGUE)
    svc.record_lesions(
        case_number,
        sites=["hands", "fingers", "feet", "ankles", "posterior_thighs", "elbow_flexures", "upper_lip"],
        morphology="weeping_vesicles",
        sensation="itch_without_heat",
        stage="acute",
    )


def _question_ids(svc: Service, age: int, study_date: str, tongue: dict, weeping: bool) -> list[str]:
    case_number = _open(svc, age=age, study_date=study_date)
    svc.record_tongue(case_number, **tongue)
    if weeping:
        svc.record_lesions(
            case_number,
            sites=["hands"],
            morphology="weeping_vesicles",
            sensation="itch_without_heat",
            stage="acute",
        )
    ids = []
    while True:
        nxt = svc.get_next_question(case_number)
        if nxt["kind"] != "question":
            break
        ids.append(nxt["question_id"])
        svc.submit_answer(case_number, nxt["question_id"], "unknown")
    return ids


def _finish(svc: Service, case_number: str, answers: dict, notes: str | None = None, opt_out: bool = False) -> dict:
    while True:
        nxt = svc.get_next_question(case_number)
        if nxt["kind"] == "disclosure":
            assert "opt out" in nxt["prompt"].lower()
            break
        assert nxt["kind"] == "question"
        option_ids = {option["id"] for option in nxt["options"]}
        chosen = answers.get(nxt["question_id"], "unknown")
        if chosen not in option_ids:
            chosen = "unknown"
        svc.submit_answer(case_number, nxt["question_id"], chosen)
    return svc.build_report(case_number, opt_out=opt_out, notes=notes)
