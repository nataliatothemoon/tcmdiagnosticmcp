# Eczema case-study diagnostics

## Feature Name

Eczema TCM case-study MCP

## Goal

Give a host model one repeatable eczema workup so a person can go from a tongue photo and lesion photos to a cited pattern report. The report explains the leading pattern, lifestyle care, acupoints, and herbal formulas. Cases are stored without a name so later sessions can be queried and the rules can be improved. A general, repeat check-in remains part of this same tool and is not built in this version.

## User Story

As a person with eczema, or someone helping them, I want a traditional Chinese medicine skin workup that starts with the tongue and the rash, asks the follow-up questions that match what was seen, and gives me a written report I can read, so that the same kind of case is handled the same way every time.

As the maintainer, I want each saved case to be de-identified and coded, so that I can query patterns later and replace the starter rules without changing the workflow.

## Functional Requirements

1. The session starts by choosing a purpose: eczema, curious, or both. Curious returns a next-release message and does not open a case. Eczema and both run the eczema pathway. Both adds a short note that the general track is not in this version, plus findings that did not fit the leading pattern.
2. The start states the terms in plain language and collects a name and email for the private follow-up list. The knowledge-base case never stores them. Its identifiers are case number, study date, age, and sex.
3. Inspection order is fixed: tongue checklist, then lesion sites and morphology. The host maps photos onto those fields. The server does not invent a diagnosis from free text.
4. After inspection, the server ranks the cited patterns and asks every coded question that confirms or rules out the leader and every other pattern inspection has not already ruled out. A question is skipped only when every pattern it informs is incompatible with the tongue and the lesions. There is no question cap and no early stop. Unknown is a valid answer. The same inspection and answers always produce the same next question.
5. Before the report is released, the server shows the storage notice again and requires an opt-out choice for the knowledge-base copy. Continuing saves the coded case without name or email. Opting out returns the report and deletes that case from the knowledge-base files. The private follow-up list is kept either way.
6. The report states the leading pattern, a close runner-up when there is one, evidence for and against each pattern that remained plausible, lifestyle lines, acupoints, and the herbal formula name with its principle and representative herbs. It does not give a personalized dose. Pattern names, points, herbs, and lifestyle lines come only from the knowledge files.
7. Saved research records can be fetched and queried by age, sex, date, pattern, lesion site, and tongue feature.
8. Tongue and skin photos may be stored on the local machine for the session. They are omitted from the contribution file.

## Data Requirements

Local SQLite, gitignored. The knowledge-base case tables have no name or email column.

A second database, `data/private/registry.sqlite`, stores the mailing list and the case link used for follow-up: name, email, and case number. That file is not part of the knowledge-base case export.

- Case: `case_number` (`CS-YYYY-NNN` from the study-date year), `study_date`, `age_years`, `sex`, `purpose`, `series_id` (unused, reserved), `contributed`, knowledge version, status.
- Tongue fields, lesion sites, morphology, stage, sensation.
- The questions that were asked and the chosen option.
- Pattern scores, whether a pattern was ruled out, and why.
- Report markdown.
- Local image paths, excluded from the contribution JSON.

Opt-out removes the case row and its clinical rows. Case numbers are not reused.

## User Flow

1. Give a name and email, choose purpose, age, sex, and study date. Read the terms.
2. Attach a tongue photo if one exists, and record the tongue checklist, including regions.
3. Attach lesion photos if they exist, and record sites, morphology, sensation, and stage.
4. Answer each question the server returns, in order, until the disclosure appears.
5. Opt out or continue. Then read the report.
6. If the case was saved, it can be queried later by the coded fields.

## Acceptance Criteria

- A damp, weeping inspection is asked the damp and spleen questions and is not asked the dryness-only questions.
- A heat inspection is asked the heat questions and is not asked the spleen-only questions.
- Repeating the same inputs yields the same question order and the same ranking.
- The report's pattern names exist in the knowledge pack. The October 14, 2026 reference observations are scored as `CS-2026-001` without copying an outside write-up in as the diagnosis.
- `start_case` stores name and email only in the private follow-up list. The knowledge-base case tables have no name or email column.
- Opt-out returns a report and leaves no knowledge-base row and no contribution file. The private follow-up contact remains.
- A saved case is returned by a query on pattern and lesion site.
- Contribution JSON has age, sex, date, answers, and scores, and has no photo paths, no free-text notes, and no name or email.

## Edge Cases

- Unknown answers do not add score.
- If every remaining score is weak, the report still names the highest cited pattern and says the match is limited.
- Close scores list a runner-up and the points and formula for each.
- Cycle timing is asked only for female sex, ages 12 through 55, and only when a still-plausible pattern includes that question. The answer is stored and does not change the score.
- Iced drinks are not a scoring item.
- A location, including the back of the thighs, is stored and does not by itself add a channel or organ pattern.
- Curious purpose does not create a case.
- `build_report` before the question list is finished returns an error.
- Pulse is not collected. The report says it was not assessed.
- Photo color is not treated as a clinical tongue diagnosis. The host must use the checklist.

## Non-Functional Requirements

- Knowledge files are versioned. A saved report keeps the version that produced it.
- The server, not the host model, chooses questions and the wording of patterns, points, and herbs.
- Every scoring statement cites a source id in the knowledge pack.
- The tool is local. This version does not upload cases to a shared server.
- The report tells the reader it is an educational case study, that a photo cannot replace an in-person exam, and that herbs and needles require a licensed practitioner.
