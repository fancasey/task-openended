# Open-Ended Rubric Grading

Ask NanoAgent to grade one student from S1 through S5. For example, “Grade S2” grades all 12 responses, and “Grade S2 on NQ003 and NQ004” grades two. The `list-grading-data` task lists the available IDs and prompts.

The structured `grade-student` input is `{"student_id":"S2","question_ids":[]}`. An empty question list selects all questions. Use distinct IDs from `NQ001` through `NQ012` to select specific questions.

The bundled 12-question workbook supplies the response text, question, model answer, rubric, and evaluator scores. `get_grading_batch` gives the agent the grading material. The agent assigns five criterion scores from 1 to 4 with brief justifications and saves them through `record_grades`. It submits the receipts. NanoAgent calls `pin_teacher_scores` separately for the verifier, which checks the saved grades and exact question coverage.

The result shows each response total out of 20. A criterion passes when its score is within one point of any of the five teachers. A total passes when it falls within the range of the five individual teachers’ totals. The distribution warning compares how often the agent and teachers used each score on the same student’s selected responses.

Agent agreement is `100 × (1 − mean absolute error / 3)`, with each criterion compared to all five teachers. The report also shows pairwise teacher agreement on those criteria. Coverage or receipt failures invalidate the submission before scoring. Criterion and total failures are reported separately from the agreement score.

## Dataset citation

Sheikh, J.K., Soni, H.K. A benchmark dataset with human validation for AI-assisted technical answer evaluation. *Discov Educ* **5**, 726 (2026). [https://doi.org/10.1007/s44217-026-01975-z](https://doi.org/10.1007/s44217-026-01975-z)

## Run the tests

```sh
uv run pytest
```
