"""Case session: inspection, full workup, disclosure, and optional save."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from tcm_eczema_mcp import engine
from tcm_eczema_mcp.knowledge import ROOT, Knowledge
from tcm_eczema_mcp.private import PrivateRegistry
from tcm_eczema_mcp.report import render_report
from tcm_eczema_mcp.store import Store
from tcm_eczema_mcp.texts import CURIOUS_MESSAGE, DISCLOSURE, TERMS

TONGUE_FIELDS = [
    "body_color",
    "shape",
    "tooth_marks",
    "coat_color",
    "coat_thickness",
    "coat_greasy",
    "cracks",
    "region_tip",
    "region_sides",
    "region_center",
    "region_root",
]
TONGUE_ENUM = {
    "body_color": "body_color",
    "shape": "shape",
    "tooth_marks": "tooth_marks",
    "coat_color": "coat_color",
    "coat_thickness": "coat_thickness",
    "coat_greasy": "coat_greasy",
    "cracks": "cracks",
    "region_tip": "region",
    "region_sides": "region",
    "region_center": "region",
    "region_root": "region",
}


class Service:
    def __init__(
        self,
        db_path: Path | None = None,
        image_root: Path | None = None,
        contribution_root: Path | None = None,
        private_path: Path | None = None,
        knowledge: Knowledge | None = None,
    ) -> None:
        self.knowledge = knowledge or Knowledge()
        self.store = Store(db_path or (ROOT / "data" / "cases.sqlite"))
        self.private = PrivateRegistry(private_path or (ROOT / "data" / "private" / "registry.sqlite"))
        self.image_root = image_root or (ROOT / "data" / "cases")
        self.contribution_root = contribution_root or (ROOT / "data" / "contributions")
        self.image_root.mkdir(parents=True, exist_ok=True)
        self.contribution_root.mkdir(parents=True, exist_ok=True)

    def start_case(
        self,
        *,
        purpose: str,
        age_years: int,
        sex: str,
        study_date: str,
        name: str,
        email: str,
    ) -> dict:
        self._enum("purpose", purpose)
        self._enum("sex", sex)
        if not isinstance(age_years, int) or isinstance(age_years, bool) or not 0 <= age_years <= 120:
            raise ValueError("age_years must be an integer from 0 through 120.")
        try:
            parsed = date.fromisoformat(study_date)
        except ValueError as exc:
            raise ValueError("study_date must be YYYY-MM-DD.") from exc
        if parsed.isoformat() != study_date:
            raise ValueError("study_date must be YYYY-MM-DD.")
        if purpose == "curious":
            self.private.add_mailing_contact(name, email)
            return {
                "case_number": None,
                "purpose": purpose,
                "terms": TERMS,
                "message": CURIOUS_MESSAGE,
            }
        case_number = self.store.allocate_case(
            study_date=study_date,
            age_years=age_years,
            sex=sex,
            purpose=purpose,
            knowledge_version=self.knowledge.version,
        )
        self.private.link_case(case_number, name, email)
        return {
            "case_number": case_number,
            "purpose": purpose,
            "terms": TERMS,
            "next": "Show the terms, then record the tongue checklist. Map a tongue photo only onto the checklist fields.",
        }

    def attach_image(self, case_number: str, kind: str, source_path: str) -> dict:
        case = self._open_case(case_number)
        if case["status"] in {"complete"}:
            raise ValueError("This case is already closed.")
        if kind not in {"tongue", "lesion"}:
            raise ValueError("kind must be tongue or lesion.")
        source = Path(source_path)
        if not source.is_file():
            raise ValueError(f"Image file not found: {source_path}")
        number = self.store.image_count(case_number, kind) + 1
        folder = self.image_root / case_number
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{kind}-{number}{source.suffix.lower()}"
        shutil.copy2(source, dest)
        self.store.add_image(case_number, kind, str(dest))
        return {"case_number": case_number, "kind": kind, "stored": True}

    def record_tongue(self, case_number: str, **tongue: str) -> dict:
        case = self._open_case(case_number)
        if case["status"] != "await_tongue":
            raise ValueError("The tongue checklist can be recorded once, before the lesions.")
        cleaned = self._tongue(tongue)
        self.store.save_tongue(case_number, cleaned)
        return {
            "case_number": case_number,
            "next": "Record the lesion sites, form, sensation, and stage. Map lesion photos only onto those fields.",
        }

    def record_lesions(
        self,
        case_number: str,
        sites: list[str],
        morphology: str,
        sensation: str,
        stage: str,
    ) -> dict:
        case = self._open_case(case_number)
        if case["status"] != "await_lesions":
            raise ValueError("Record the tongue checklist before the lesions.")
        if not sites:
            raise ValueError("Record at least one lesion site.")
        unique_sites = list(dict.fromkeys(sites))
        if len(unique_sites) != len(sites):
            raise ValueError("Each lesion site should be listed once.")
        for site in unique_sites:
            self._enum("site", site)
        self._enum("morphology", morphology)
        self._enum("sensation", sensation)
        self._enum("stage", stage)
        tongue = self.store.tongue(case_number)
        lesions = {"morphology": morphology, "sensation": sensation, "stage": stage}
        plan = self._plan(case, tongue, lesions)
        self.store.save_lesions(case_number, lesions, unique_sites, plan)
        return {
            "case_number": case_number,
            "questions": len(plan),
            "next": "Ask only the questions returned by get_next_question, in order.",
        }

    def get_next_question(self, case_number: str) -> dict:
        case = self._open_case(case_number)
        if case["status"] == "await_tongue":
            return {
                "case_number": case_number,
                "kind": "step",
                "step": "record_tongue",
                "prompt": "Record the tongue checklist before any questions.",
            }
        if case["status"] == "await_lesions":
            return {
                "case_number": case_number,
                "kind": "step",
                "step": "record_lesions",
                "prompt": "Record the lesion checklist before any questions.",
            }
        plan = self.store.question_plan(case_number)
        answered = self.store.answers(case_number)
        remaining = [question_id for question_id in plan if question_id not in answered]
        if case["status"] == "inquiry" and remaining:
            question = self.knowledge.questions_by_id[remaining[0]]
            return {
                "case_number": case_number,
                "kind": "question",
                "question_id": question["id"],
                "prompt": question["prompt"],
                "options": [{"id": option["id"], "label": option["label"]} for option in question["options"]],
                "remaining": len(remaining),
            }
        if case["status"] in {"disclosure", "inquiry"} and not remaining:
            return {
                "case_number": case_number,
                "kind": "disclosure",
                "prompt": DISCLOSURE,
                "next": "Show this notice. Then call build_report with opt_out true or false. Do not write the report before that choice.",
            }
        if case["status"] == "complete":
            return {
                "case_number": case_number,
                "kind": "complete",
                "prompt": "The report for this case has already been released.",
            }
        raise ValueError(f"Case {case_number} is not ready for a question.")

    def submit_answer(self, case_number: str, question_id: str, option_id: str) -> dict:
        case = self._open_case(case_number)
        if case["status"] != "inquiry":
            raise ValueError("There is no open question on this case.")
        nxt = self.get_next_question(case_number)
        if nxt["kind"] != "question" or nxt["question_id"] != question_id:
            expected = nxt.get("question_id", nxt["kind"])
            raise ValueError(f"The next question is {expected}.")
        question = self.knowledge.questions_by_id[question_id]
        if option_id not in {option["id"] for option in question["options"]}:
            raise ValueError(f"Unknown option {option_id} for {question_id}.")
        plan = self.store.question_plan(case_number)
        answered = self.store.answers(case_number)
        remaining_after = [item for item in plan if item not in answered and item != question_id]
        self.store.save_answer(case_number, question_id, option_id, finished=not remaining_after)
        if remaining_after:
            return {"case_number": case_number, "accepted": question_id, "remaining": len(remaining_after)}
        return {
            "case_number": case_number,
            "accepted": question_id,
            "remaining": 0,
            "next": "The workup is complete. Show the disclosure from get_next_question before the report.",
        }

    def build_report(self, case_number: str, opt_out: bool, notes: str | None = None) -> dict:
        case = self._open_case(case_number)
        plan = self.store.question_plan(case_number)
        answered = self.store.answers(case_number)
        if case["status"] not in {"disclosure", "inquiry"} or any(item not in answered for item in plan):
            raise ValueError("Finish every workup question, then show the disclosure, before building the report.")
        if notes is not None and len(notes) > 2000:
            raise ValueError("Notes must be 2000 characters or fewer.")
        self._reject_contact_in_notes(case_number, notes)
        bundle = self._bundle(case, notes)
        markdown = render_report(bundle, self.knowledge)
        self._reject_contact_in_text(case_number, markdown)
        if opt_out:
            self.store.delete_case(case_number)
            folder = self.image_root / case_number
            if folder.exists():
                shutil.rmtree(folder)
            return {
                "case_number": case_number,
                "contributed": False,
                "disclosure": DISCLOSURE,
                "leader": bundle["leader"],
                "runner_up": bundle["runner_up"],
                "markdown": markdown,
            }
        score_rows = []
        ranks = {pattern_id: index + 1 for index, pattern_id in enumerate(bundle["ranked"])}
        for pattern in self.knowledge.patterns:
            pattern_id = pattern["id"]
            reason = bundle["rule_map"][pattern_id]
            score_rows.append(
                {
                    "pattern_id": pattern_id,
                    "score": None if reason else bundle["scores"].get(pattern_id, 0),
                    "ruled_out": 1 if reason else 0,
                    "rule_out_reason": reason,
                    "rank": None if reason else ranks.get(pattern_id),
                }
            )
        self.store.save_report(
            case_number,
            markdown=markdown,
            knowledge_version=self.knowledge.version,
            notes=notes,
            score_rows=score_rows,
        )
        contribution = {
            "knowledge_version": self.knowledge.version,
            "case_number": case_number,
            "study_date": case["study_date"],
            "age_years": case["age_years"],
            "sex": case["sex"],
            "purpose": case["purpose"],
            "tongue": bundle["tongue"],
            "lesions": bundle["lesions"],
            "sites": bundle["sites"],
            "answers": [
                {"question_id": answer["question_id"], "option_id": answer["option_id"]}
                for answer in bundle["answers"]
            ],
            "scores": score_rows,
            "leader": bundle["leader"],
            "runner_up": bundle["runner_up"],
        }
        path = self.contribution_root / f"{case_number}.json"
        payload = json.dumps(contribution, ensure_ascii=False, indent=2)
        self._reject_contact_in_text(case_number, payload)
        path.write_text(payload, encoding="utf-8")
        return {
            "case_number": case_number,
            "contributed": True,
            "disclosure": DISCLOSURE,
            "leader": bundle["leader"],
            "runner_up": bundle["runner_up"],
            "ruled_out": [item["pattern_id"] for item in bundle["ruled_out"]],
            "asked_question_ids": [answer["question_id"] for answer in bundle["answers"]],
            "markdown": markdown,
        }

    def get_case(self, case_number: str) -> dict:
        case = self.store.get_case_row(case_number)
        if case is None:
            raise ValueError(f"No case {case_number}.")
        payload = {
            "case_number": case["case_number"],
            "study_date": case["study_date"],
            "age_years": case["age_years"],
            "sex": case["sex"],
            "purpose": case["purpose"],
            "status": case["status"],
            "contributed": case["contributed"],
            "knowledge_version": case["knowledge_version"],
            "series_id": case["series_id"],
        }
        if case["contributed"] == 1:
            payload["tongue"] = self.store.tongue(case_number)
            payload["lesions"] = self.store.lesions(case_number)
            payload["sites"] = self.store.sites(case_number)
            payload["answers"] = self.store.answers(case_number)
            payload["local_images"] = self.store.images(case_number)
            payload["markdown"] = self.store.report(case_number)
        return payload

    def query_cases(self, **filters) -> list[dict]:
        allowed = {
            "age_min",
            "age_max",
            "sex",
            "pattern_id",
            "site",
            "tongue_body_color",
            "study_date_from",
            "study_date_to",
        }
        unknown = set(filters) - allowed
        if unknown:
            raise ValueError(f"Unknown query filters: {sorted(unknown)}")
        return self.store.query(**filters)

    def get_follow_up(self, case_number: str) -> dict:
        contact = self.private.follow_up(case_number)
        if contact is None:
            raise ValueError(f"No private follow-up contact for {case_number}.")
        return contact

    def list_mailing_list(self) -> list[dict]:
        return self.private.mailing_list()

    def _reject_contact_in_notes(self, case_number: str, notes: str | None) -> None:
        if not notes:
            return
        self._reject_contact_in_text(case_number, notes)

    def _reject_contact_in_text(self, case_number: str, text: str) -> None:
        contact = self.private.follow_up(case_number)
        if contact is None:
            return
        folded = text.casefold()
        if contact["name"].casefold() in folded or contact["email"].casefold() in folded:
            raise ValueError(
                "The knowledge-base case cannot include the name or email. "
                "Those stay in the private follow-up list."
            )

    def _plan(self, case: dict, tongue: dict, lesions: dict) -> list[str]:
        snap = engine.snapshot(tongue, lesions)
        rule_map = engine.ruled_out(self.knowledge, snap)
        active = engine.active_ids(rule_map)
        evidence = engine.inspection_evidence(self.knowledge, snap, set(active))
        totals = engine.scores_from(evidence, active)
        return engine.plan_questions(
            self.knowledge,
            totals,
            active,
            case["sex"],
            case["age_years"],
        )

    def _bundle(self, case: dict, notes: str | None) -> dict:
        tongue = self.store.tongue(case["case_number"])
        lesions = self.store.lesions(case["case_number"])
        snap = engine.snapshot(tongue, lesions)
        rule_map = engine.ruled_out(self.knowledge, snap)
        active = engine.active_ids(rule_map)
        evidence = engine.inspection_evidence(self.knowledge, snap, set(active))
        answers_raw = self.store.answers(case["case_number"])
        answer_rows = []
        for question_id in self.store.question_plan(case["case_number"]):
            option_id = answers_raw[question_id]
            question = self.knowledge.questions_by_id[question_id]
            option = next(item for item in question["options"] if item["id"] == option_id)
            added = engine.answer_evidence(question, option_id, set(active))
            evidence.extend(added)
            answer_rows.append(
                {
                    "question_id": question_id,
                    "option_id": option_id,
                    "prompt": question["prompt"],
                    "label": option["label"],
                    "scored": bool(added),
                }
            )
        totals = engine.scores_from(evidence, active)
        ranked = engine.rank_patterns(totals, active)
        leader, runner = engine.leader_and_runner(totals, active)
        return {
            "case": case,
            "tongue": tongue,
            "lesions": lesions,
            "sites": self.store.sites(case["case_number"]),
            "answers": answer_rows,
            "evidence": evidence,
            "scores": totals,
            "ranked": ranked,
            "leader": leader,
            "runner_up": runner,
            "ruled_out": [
                {"pattern_id": pattern_id, "reason": reason}
                for pattern_id, reason in rule_map.items()
                if reason
            ],
            "rule_map": rule_map,
            "notes": notes,
        }

    def _open_case(self, case_number: str) -> dict:
        case = self.store.get_case_row(case_number)
        if case is None:
            raise ValueError(f"No case {case_number}.")
        return case

    def _enum(self, name: str, value: str) -> None:
        allowed = self.knowledge.enums[name]
        if value not in allowed:
            raise ValueError(f"{name} must be one of: {', '.join(allowed)}.")

    def _tongue(self, tongue: dict) -> dict:
        missing = [field for field in TONGUE_FIELDS if field not in tongue]
        if missing:
            raise ValueError(f"Tongue checklist is missing: {', '.join(missing)}.")
        cleaned = {}
        for field in TONGUE_FIELDS:
            value = tongue[field]
            allowed = self.knowledge.enums[TONGUE_ENUM[field]]
            if value not in allowed:
                raise ValueError(f"tongue.{field} must be one of: {', '.join(allowed)}.")
            cleaned[field] = value
        return cleaned
