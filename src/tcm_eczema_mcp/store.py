"""SQLite case records. There is no name column."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS year_counters (
    year INTEGER PRIMARY KEY,
    last_n INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_number TEXT PRIMARY KEY,
    study_date TEXT NOT NULL,
    age_years INTEGER NOT NULL,
    sex TEXT NOT NULL,
    purpose TEXT NOT NULL,
    series_id TEXT,
    status TEXT NOT NULL,
    contributed INTEGER,
    knowledge_version TEXT NOT NULL,
    notes TEXT,
    question_plan TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tongue (
    case_number TEXT PRIMARY KEY REFERENCES cases(case_number) ON DELETE CASCADE,
    body_color TEXT NOT NULL,
    shape TEXT NOT NULL,
    tooth_marks TEXT NOT NULL,
    coat_color TEXT NOT NULL,
    coat_thickness TEXT NOT NULL,
    coat_greasy TEXT NOT NULL,
    cracks TEXT NOT NULL,
    region_tip TEXT NOT NULL,
    region_sides TEXT NOT NULL,
    region_center TEXT NOT NULL,
    region_root TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lesions (
    case_number TEXT PRIMARY KEY REFERENCES cases(case_number) ON DELETE CASCADE,
    morphology TEXT NOT NULL,
    sensation TEXT NOT NULL,
    stage TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lesion_sites (
    case_number TEXT NOT NULL REFERENCES cases(case_number) ON DELETE CASCADE,
    site TEXT NOT NULL,
    PRIMARY KEY (case_number, site)
);

CREATE TABLE IF NOT EXISTS answers (
    case_number TEXT NOT NULL REFERENCES cases(case_number) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    option_id TEXT NOT NULL,
    PRIMARY KEY (case_number, question_id)
);

CREATE TABLE IF NOT EXISTS scores (
    case_number TEXT NOT NULL REFERENCES cases(case_number) ON DELETE CASCADE,
    pattern_id TEXT NOT NULL,
    score INTEGER,
    ruled_out INTEGER NOT NULL,
    rule_out_reason TEXT,
    rank INTEGER,
    PRIMARY KEY (case_number, pattern_id)
);

CREATE TABLE IF NOT EXISTS reports (
    case_number TEXT PRIMARY KEY REFERENCES cases(case_number) ON DELETE CASCADE,
    markdown TEXT NOT NULL,
    knowledge_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT NOT NULL REFERENCES cases(case_number) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_date ON cases(study_date);
CREATE INDEX IF NOT EXISTS idx_cases_age ON cases(age_years);
CREATE INDEX IF NOT EXISTS idx_cases_sex ON cases(sex);
CREATE INDEX IF NOT EXISTS idx_cases_contributed ON cases(contributed);
CREATE INDEX IF NOT EXISTS idx_sites_site ON lesion_sites(site);
CREATE INDEX IF NOT EXISTS idx_scores_pattern ON scores(pattern_id);
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def allocate_case(
        self,
        *,
        study_date: str,
        age_years: int,
        sex: str,
        purpose: str,
        knowledge_version: str,
    ) -> str:
        year = int(study_date[:4])
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT last_n FROM year_counters WHERE year = ?",
                (year,),
            ).fetchone()
            if row is None:
                number = 1
                conn.execute(
                    "INSERT INTO year_counters(year, last_n) VALUES (?, ?)",
                    (year, number),
                )
            else:
                number = row["last_n"] + 1
                conn.execute(
                    "UPDATE year_counters SET last_n = ? WHERE year = ?",
                    (number, year),
                )
            case_number = f"CS-{year}-{number:03d}"
            conn.execute(
                """
                INSERT INTO cases (
                    case_number, study_date, age_years, sex, purpose, series_id,
                    status, contributed, knowledge_version, notes, question_plan, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, 'await_tongue', NULL, ?, NULL, NULL, ?)
                """,
                (case_number, study_date, age_years, sex, purpose, knowledge_version, now),
            )
        return case_number

    def get_case_row(self, case_number: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM cases WHERE case_number = ?",
                (case_number,),
            ).fetchone()
        return dict(row) if row else None

    def set_status(self, case_number: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE cases SET status = ? WHERE case_number = ?",
                (status, case_number),
            )

    def save_tongue(self, case_number: str, tongue: dict) -> None:
        columns = [
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
        with self.connect() as conn:
            conn.execute(
                f"""
                INSERT INTO tongue (case_number, {", ".join(columns)})
                VALUES ({", ".join("?" for _ in range(len(columns) + 1))})
                """,
                [case_number, *[tongue[column] for column in columns]],
            )
            conn.execute(
                "UPDATE cases SET status = 'await_lesions' WHERE case_number = ?",
                (case_number,),
            )

    def save_lesions(self, case_number: str, lesions: dict, sites: list[str], plan: list[str]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lesions (case_number, morphology, sensation, stage)
                VALUES (?, ?, ?, ?)
                """,
                (case_number, lesions["morphology"], lesions["sensation"], lesions["stage"]),
            )
            conn.executemany(
                "INSERT INTO lesion_sites (case_number, site) VALUES (?, ?)",
                [(case_number, site) for site in sites],
            )
            status = "disclosure" if not plan else "inquiry"
            conn.execute(
                """
                UPDATE cases
                SET question_plan = ?, status = ?
                WHERE case_number = ?
                """,
                (json.dumps(plan), status, case_number),
            )

    def tongue(self, case_number: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM tongue WHERE case_number = ?",
                (case_number,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data.pop("case_number")
        return data

    def lesions(self, case_number: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM lesions WHERE case_number = ?",
                (case_number,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data.pop("case_number")
        return data

    def sites(self, case_number: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT site FROM lesion_sites WHERE case_number = ? ORDER BY rowid",
                (case_number,),
            ).fetchall()
        return [row["site"] for row in rows]

    def question_plan(self, case_number: str) -> list[str]:
        row = self.get_case_row(case_number)
        if not row or not row["question_plan"]:
            return []
        return json.loads(row["question_plan"])

    def answers(self, case_number: str) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT question_id, option_id FROM answers WHERE case_number = ? ORDER BY question_id",
                (case_number,),
            ).fetchall()
        return {row["question_id"]: row["option_id"] for row in rows}

    def save_answer(self, case_number: str, question_id: str, option_id: str, finished: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO answers (case_number, question_id, option_id)
                VALUES (?, ?, ?)
                """,
                (case_number, question_id, option_id),
            )
            if finished:
                conn.execute(
                    "UPDATE cases SET status = 'disclosure' WHERE case_number = ?",
                    (case_number,),
                )

    def add_image(self, case_number: str, kind: str, path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO images (case_number, kind, path) VALUES (?, ?, ?)",
                (case_number, kind, path),
            )

    def images(self, case_number: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT kind, path FROM images WHERE case_number = ? ORDER BY id",
                (case_number,),
            ).fetchall()
        return [dict(row) for row in rows]

    def image_count(self, case_number: str, kind: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM images WHERE case_number = ? AND kind = ?",
                (case_number, kind),
            ).fetchone()
        return int(row["n"])

    def save_report(
        self,
        case_number: str,
        *,
        markdown: str,
        knowledge_version: str,
        notes: str | None,
        score_rows: list[dict],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE cases
                SET status = 'complete', contributed = 1, notes = ?
                WHERE case_number = ?
                """,
                (notes, case_number),
            )
            conn.execute(
                """
                INSERT INTO reports (case_number, markdown, knowledge_version)
                VALUES (?, ?, ?)
                """,
                (case_number, markdown, knowledge_version),
            )
            conn.executemany(
                """
                INSERT INTO scores (
                    case_number, pattern_id, score, ruled_out, rule_out_reason, rank
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        case_number,
                        row["pattern_id"],
                        row["score"],
                        row["ruled_out"],
                        row["rule_out_reason"],
                        row["rank"],
                    )
                    for row in score_rows
                ],
            )

    def delete_case(self, case_number: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM cases WHERE case_number = ?", (case_number,))

    def report(self, case_number: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT markdown FROM reports WHERE case_number = ?",
                (case_number,),
            ).fetchone()
        return row["markdown"] if row else None

    def query(
        self,
        *,
        age_min: int | None = None,
        age_max: int | None = None,
        sex: str | None = None,
        pattern_id: str | None = None,
        site: str | None = None,
        tongue_body_color: str | None = None,
        study_date_from: str | None = None,
        study_date_to: str | None = None,
    ) -> list[dict]:
        clauses = ["cases.contributed = 1"]
        params: list = []
        if age_min is not None:
            clauses.append("cases.age_years >= ?")
            params.append(age_min)
        if age_max is not None:
            clauses.append("cases.age_years <= ?")
            params.append(age_max)
        if sex is not None:
            clauses.append("cases.sex = ?")
            params.append(sex)
        if study_date_from is not None:
            clauses.append("cases.study_date >= ?")
            params.append(study_date_from)
        if study_date_to is not None:
            clauses.append("cases.study_date <= ?")
            params.append(study_date_to)
        if site is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM lesion_sites s WHERE s.case_number = cases.case_number AND s.site = ?)"
            )
            params.append(site)
        if tongue_body_color is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM tongue t WHERE t.case_number = cases.case_number AND t.body_color = ?)"
            )
            params.append(tongue_body_color)
        if pattern_id is not None:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM scores leader
                    WHERE leader.case_number = cases.case_number
                      AND leader.pattern_id = ?
                      AND leader.ruled_out = 0
                      AND leader.score >= (
                          SELECT MAX(other.score) - 3
                          FROM scores other
                          WHERE other.case_number = cases.case_number
                            AND other.ruled_out = 0
                      )
                )
                """
            )
            params.append(pattern_id)
        sql = f"""
            SELECT cases.case_number, cases.study_date, cases.age_years, cases.sex,
                   cases.purpose, cases.knowledge_version
            FROM cases
            WHERE {" AND ".join(clauses)}
            ORDER BY cases.study_date, cases.case_number
        """
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def column_names(self, table: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row["name"] for row in rows]
