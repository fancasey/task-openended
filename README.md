# Open-Ended Rubric Grading

Grade open-ended student responses with a rubric and compare the results with teacher scores.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_grading_data` | Lists student IDs and question prompts. |
| `get_grading_question` | Returns exactly one student's answer with its prompt, model answer, and rubric. Requires one `question_id` from `NQ001` through `NQ012`. |
| `record_grades` | Saves exactly one response per call and returns a receipt and totals. Each response needs five criterion scores from 1 to 4 with brief justifications. |
| `pin_teacher_scores` | Supplies the five teachers' scores per criterion. NanoAgent calls it separately for the verifier. |

Each grading task handles exactly one question for one student. The agent fetches that answer, grades its five criteria, and records exactly one response using the original task input as `selection`. It submits exactly one receipt. The verifier checks the saved grades and selected question before scoring. The result shows each response total out of 20. A criterion passes when its score is within one point of any of the five teachers. A total passes when it falls within the range of the five individual teachers’ totals.

Agreement with teachers is `100 × (1 − mean absolute error / 3)`, with each criterion compared to all five teachers. The report also shows pairwise teacher agreement on those criteria. Criterion and total failures are reported separately from the agreement score.

### Tasks

| Task | Purpose | Example request |
| --- | --- | --- |
| `list-grading-data` | Lists the available student IDs and question prompts. | “List the students and questions.” |
| `grade-student` | Grades exactly one question for one student from S1 through S5. | “Grade S2 on NQ003.” |

The structured `grade-student` input is `{"student_id":"S2","question_id":"NQ003"}`. Both fields are required. Choose one student from `S1` through `S5` and one question from `NQ001` through `NQ012`. Missing, empty, or multiple question IDs and the old `question_ids` field are rejected. To grade another question, start a separate task.

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
