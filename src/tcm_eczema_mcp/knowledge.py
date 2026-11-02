"""Load the versioned knowledge pack."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def knowledge_dir() -> Path:
    override = os.environ.get("TCM_KNOWLEDGE_DIR")
    if override:
        return Path(override)
    bundled = ROOT / "knowledge"
    if (bundled / "patterns.yaml").is_file():
        return bundled
    raise FileNotFoundError(f"Knowledge pack not found at {bundled}")


class Knowledge:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or knowledge_dir()
        sources = _read(self.directory / "sources.yaml")
        patterns = _read(self.directory / "patterns.yaml")
        questions = _read(self.directory / "questions.yaml")
        self.version = sources["version"]
        self.sources = {item_id: body for item_id, body in sources["sources"].items()}
        self.enums = patterns["enums"]
        self.main_points = patterns["main_points"]
        self.care = patterns["care"]
        self.external = patterns["external"]
        self.patterns = patterns["patterns"]
        self.patterns_by_id = {item["id"]: item for item in self.patterns}
        self.weights = patterns["weights"]
        self.questions = questions["questions"]
        self.questions_by_id = {item["id"]: item for item in self.questions}
        self._check()

    def source_line(self, source_id: str) -> str:
        return self.sources[source_id]["citation"]

    def _check(self) -> None:
        pattern_ids = set(self.patterns_by_id)
        for source_id in self._used_sources():
            if source_id not in self.sources:
                raise ValueError(f"Unknown source id: {source_id}")
        for question in self.questions:
            unknown = set(question["informs"]) - pattern_ids
            if unknown:
                raise ValueError(f"Question {question['id']} informs unknown patterns: {unknown}")
            for option in question["options"]:
                for effect in option["effects"]:
                    if effect["pattern"] not in pattern_ids:
                        raise ValueError(
                            f"Question {question['id']} option {option['id']} "
                            f"uses unknown pattern {effect['pattern']}"
                        )
        for pattern in self.patterns:
            for rule in pattern["rule_out"]:
                if not rule["all"]:
                    raise ValueError(f"Empty rule_out on {pattern['id']}")

    def _used_sources(self) -> set[str]:
        found = {self.main_points["source"]}
        for item in self.care:
            found.add(item["source"])
        for item in self.external.values():
            found.add(item["source"])
        for pattern in self.patterns:
            found.add(pattern["source"])
            related = pattern.get("related_formula")
            if related:
                found.add(related["source"])
            for rule in pattern["rule_out"]:
                pass
        for field in self.weights.values():
            for effects in field.values():
                for effect in effects:
                    found.add(effect["source"])
        for question in self.questions:
            for option in question["options"]:
                for effect in option["effects"]:
                    found.add(effect["source"])
        return found


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a mapping")
    return data
