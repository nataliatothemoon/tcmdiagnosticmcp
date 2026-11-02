"""MCP entrypoint. The server chooses the questions and the report wording."""

from __future__ import annotations

from tcm_eczema_mcp.service import Service

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover - exercised only when the sdk is absent
    MCPServer = None  # type: ignore[misc, assignment]

INSTRUCTIONS = (
    "You are the host for a cited eczema case-study workup. "
    "Show the server's terms, questions, disclosure, and report markdown as written. "
    "Do not invent questions, pattern names, acupoints, or herbs. "
    "Map tongue and lesion photos only onto the checklist fields the tools accept. "
    "Collect name and email for the private follow-up list. Do not put them in notes, questions, or the report. "
    "Call build_report only after the disclosure has been shown, and pass the person's opt-out choice."
)

mcp = MCPServer("tcm-eczema-case-study", instructions=INSTRUCTIONS) if MCPServer else None
_service: Service | None = None


def get_service() -> Service:
    global _service
    if _service is None:
        _service = Service()
    return _service


def _bind(fn):
    if mcp is None:
        return fn
    return mcp.tool()(fn)


@_bind
def start_case(
    purpose: str,
    age_years: int,
    sex: str,
    study_date: str,
    name: str,
    email: str,
) -> dict:
    """Open a case or a mailing-list entry. purpose is eczema, curious, or both. name and email go only to the private follow-up list."""
    return get_service().start_case(
        purpose=purpose,
        age_years=age_years,
        sex=sex,
        study_date=study_date,
        name=name,
        email=email,
    )


@_bind
def attach_image(case_number: str, kind: str, source_path: str) -> dict:
    """Copy a tongue or lesion photo into the local case folder. kind is tongue or lesion. This does not interpret the photo."""
    return get_service().attach_image(case_number, kind, source_path)


@_bind
def record_tongue(
    case_number: str,
    body_color: str,
    shape: str,
    tooth_marks: str,
    coat_color: str,
    coat_thickness: str,
    coat_greasy: str,
    cracks: str,
    region_tip: str,
    region_sides: str,
    region_center: str,
    region_root: str,
) -> dict:
    """Record the tongue checklist. Use only the allowed values from the tool error text if unsure. Do not add a diagnosis."""
    return get_service().record_tongue(
        case_number,
        body_color=body_color,
        shape=shape,
        tooth_marks=tooth_marks,
        coat_color=coat_color,
        coat_thickness=coat_thickness,
        coat_greasy=coat_greasy,
        cracks=cracks,
        region_tip=region_tip,
        region_sides=region_sides,
        region_center=region_center,
        region_root=region_root,
    )


@_bind
def record_lesions(
    case_number: str,
    sites: list[str],
    morphology: str,
    sensation: str,
    stage: str,
) -> dict:
    """Record lesion sites and form after the tongue. sites use the checklist codes, including posterior_thighs when that skin is involved."""
    return get_service().record_lesions(
        case_number,
        sites=sites,
        morphology=morphology,
        sensation=sensation,
        stage=stage,
    )


@_bind
def get_next_question(case_number: str) -> dict:
    """Return the next server-authored step. Show prompt and options as written."""
    return get_service().get_next_question(case_number)


@_bind
def submit_answer(case_number: str, question_id: str, option_id: str) -> dict:
    """Save the chosen option for the current question. option_id must be one of the ids just returned."""
    return get_service().submit_answer(case_number, question_id, option_id)


@_bind
def build_report(case_number: str, opt_out: bool, notes: str | None = None) -> dict:
    """Release the report after the disclosure. opt_out true skips the knowledge-base copy. notes must not contain the name or email."""
    return get_service().build_report(case_number, opt_out=opt_out, notes=notes)


@_bind
def get_case(case_number: str) -> dict:
    """Fetch one local case by case number."""
    return get_service().get_case(case_number)


@_bind
def query_cases(
    age_min: int | None = None,
    age_max: int | None = None,
    sex: str | None = None,
    pattern_id: str | None = None,
    site: str | None = None,
    tongue_body_color: str | None = None,
    study_date_from: str | None = None,
    study_date_to: str | None = None,
) -> list[dict]:
    """Query saved cases. pattern_id matches the leader or a pattern within 3 points of it. Opted-out sessions are absent."""
    filters = {
        "age_min": age_min,
        "age_max": age_max,
        "sex": sex,
        "pattern_id": pattern_id,
        "site": site,
        "tongue_body_color": tongue_body_color,
        "study_date_from": study_date_from,
        "study_date_to": study_date_to,
    }
    return get_service().query_cases(**{key: value for key, value in filters.items() if value is not None})


@_bind
def get_follow_up(case_number: str) -> dict:
    """Return the private name and email for one case. This is not part of the knowledge-base case file."""
    return get_service().get_follow_up(case_number)


@_bind
def list_mailing_list() -> list[dict]:
    """Return the private mailing list of names and emails. Case findings are not included."""
    return get_service().list_mailing_list()


def main() -> None:
    if mcp is None:
        raise RuntimeError("The mcp package is not installed.")
    mcp.run()


if __name__ == "__main__":
    main()
