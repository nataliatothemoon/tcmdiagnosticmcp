# Eczema TCM case-study MCP

A local MCP server for one eczema workup. It starts with the tongue, then the rash, then the follow-up questions that the tongue and rash leave open. The report, the points, and the formulas come from the cited knowledge files in `knowledge/`.

This version is the eczema pathway. A general check-in for repeat tongue photos is reserved in the same server and is not built yet.

This is an educational case study. It is not a medical diagnosis or a prescription. Herbs and needles belong with a licensed practitioner.

## Run

```bash
py -3 -m pip install -e ".[dev]"
py -3 -m tcm_eczema_mcp
```

Cursor can launch it with [examples/cursor-mcp.json](examples/cursor-mcp.json). Set `cwd` to this repository.

## Session

1. `start_case` with purpose `eczema`, `curious`, or `both`, plus name, email, age, sex, and study date. Show the terms it returns. Name and email are stored only in `data/private/`.
2. `attach_image` if there is a photo, then `record_tongue`.
3. `attach_image` for rash photos, then `record_lesions`.
4. `get_next_question` and `submit_answer` until the disclosure appears. Show that text. It is the opt-out.
5. `build_report` with `opt_out` true or false. Show the returned markdown as the report.
6. `query_cases` and `get_case` read saved cases.

`curious` adds the person to the private mailing list and does not open a case. Opt-out returns the report and leaves the case out of the knowledge-base files. The private name and email remain, so a case can still be followed up. Use `get_follow_up` for that contact and `list_mailing_list` for the mailing list. Photos stay in `data/cases/` only when the knowledge-base case is saved, and they are left out of `data/contributions/`.

## Knowledge

Scoring text is in [knowledge/patterns.yaml](knowledge/patterns.yaml) and [knowledge/questions.yaml](knowledge/questions.yaml). Each weight has a source id from [knowledge/sources.yaml](knowledge/sources.yaml). The starter pack is the 2016 eczema consensus published in 2018, plus three context sources that do not add pattern names. Bump `version` when the rules change. Saved reports keep the version that wrote them.

The feature spec is [docs/features/eczema-case-study-diagnostics.md](docs/features/eczema-case-study-diagnostics.md). A public license has not been chosen yet.
