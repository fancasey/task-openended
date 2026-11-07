# Open-Ended Rubric Grading

Grade open-ended student responses with a rubric and compare the results with teacher scores.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_grading_data` | Lists student IDs and question prompts. |
| `get_grading_question` | Returns exactly one student's answer with its prompt, model answer, and rubric. `question_ids` must contain exactly one ID; empty and multi-question lists are rejected. |
| `record_grades` | Saves exactly one response per call and returns a receipt and totals. Each response needs five criterion scores from 1 to 4 with brief justifications. |
| `pin_teacher_scores` | Supplies the five teachers' scores per criterion. NanoAgent calls it separately for the verifier. |

The agent fetches, grades, and records one question before fetching the next, in question order. Each `record_grades` call keeps the original task input as `selection` and includes exactly one response. The agent submits one receipt per selected question. The verifier checks the saved grades and exact question coverage before scoring. The result shows each response total out of 20. A criterion passes when its score is within one point of any of the five teachers. A total passes when it falls within the range of the five individual teachers’ totals.

Agreement with teachers is `100 × (1 − mean absolute error / 3)`, with each criterion compared to all five teachers. The report also shows pairwise teacher agreement on those criteria. Criterion and total failures are reported separately from the agreement score.

### Tasks

| Task | Purpose | Example request |
| --- | --- | --- |
| `list-grading-data` | Lists the available student IDs and question prompts. | “List the students and questions.” |
| `grade-student` | Grades all or selected responses for one student from S1 through S5. | “Grade S2” or “Grade S2 on NQ003 and NQ004.” |

The structured `grade-student` input is `{"student_id":"S2","question_ids":[]}`. An empty question list selects all questions for the task; the agent still fetches and records each question separately. Use distinct IDs from `NQ001` through `NQ012` to select specific questions.

## Layout

- `nanoagent.yaml` declares the runtime, tools, and tasks. `contract.py` defines their inputs and outputs.
- `src/plugin/` contains the tool server, grading tools, and bundled dataset.
- `verifier/` checks tool inputs and outputs, receipt integrity, coverage, and agreement with teacher scores.
- `tests/` separates schema checks, dataset checks, scoring, teacher references, receipt integrity, tool output validation, and server integration. Each of the 300 source rubric records is reported separately, alongside all 60 student/question selections. Scoring tests compare results with independent arithmetic; receipt tests cover changed files, malformed payloads, prior-task receipts, and symlink escapes.

### Dataset citation

Sheikh, J.K., Soni, H.K. A benchmark dataset with human validation for AI-assisted technical answer evaluation. *Discov Educ* **5**, 726 (2026). [https://doi.org/10.1007/s44217-026-01975-z](https://doi.org/10.1007/s44217-026-01975-z)

## Develop and run

From the plugin root, use Python 3.12 or later and `uv` to install the locked dependencies and run the tests.

```sh
uv sync --frozen
uv run --frozen pytest
```

NanoAgent starts the tool server over standard input and output with the command declared in `nanoagent.yaml`.

```sh
uv run --frozen python -m plugin
```
