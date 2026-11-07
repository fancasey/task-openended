"""Each source record is a separate case, so failures identify its student and criterion."""

import csv

import pytest

from contract import GradeStudentInput
from plugin.grading import get_grading_batch, pin_teacher_scores
from plugin.grading_data import WORKBOOK, workbook_data

with WORKBOOK.with_name("Input file for NLP of 12 question scores.csv").open(
    encoding="utf-8-sig", newline=""
) as source:
    ROWS = list(csv.DictReader(source))


def test_dataset_has_exactly_the_expected_records():
    questions, teachers = workbook_data()
    expected = {(f"S{s}", f"NQ{q:03}") for s in range(1, 6) for q in range(1, 13)}
    assert set(questions) == set(teachers) == expected
    keys = [(r["StudentID"], r["QID"], r["Rubric"]) for r in ROWS]
    assert len(keys) == len(set(keys)) == 300
    assert {(s, q) for s, q, _ in keys} == expected
    assert all(sum((r["StudentID"], r["QID"]) == key for r in ROWS) == 5 for key in expected)


@pytest.mark.parametrize("row", ROWS, ids=[f"{r['StudentID']}-{r['QID']}-{r['Rubric']}" for r in ROWS])
def test_workbook_record_matches_companion_csv(row):
    questions, teachers = workbook_data()
    key = row["StudentID"], row["QID"]
    question = questions[key]
    criterion = next(item for item in question.rubric if item.name == row["Rubric"])
    assert question.student_answer.strip() == row["ResponseText"].strip()
    assert all((criterion.level_1, criterion.level_2, criterion.level_3, criterion.level_4))
    teacher = teachers[key].criteria[criterion.criterion - 1]
    assert teacher.name == row["Rubric"]
    assert len(teacher.scores) == 5
    assert all(type(score) is int and 1 <= score <= 4 for score in teacher.scores)
    assert round(sum(teacher.scores) / 5) == int(row["Score"])


@pytest.mark.parametrize("student", [f"S{i}" for i in range(1, 6)])
@pytest.mark.parametrize("question", [f"NQ{i:03}" for i in range(1, 13)])
def test_tools_serve_the_requested_response_only(student, question, tmp_path):
    selection = GradeStudentInput(student, [question])
    batch = get_grading_batch(selection, tmp_path)
    reference = pin_teacher_scores(selection, tmp_path)
    assert batch.student_id == reference.student_id == student
    assert [q.question_id for q in batch.questions] == [question]
    assert [q.question_id for q in reference.responses] == [question]
    assert [r.criterion for r in batch.questions[0].rubric] == [1, 2, 3, 4, 5]
    assert batch.questions[0].prompt and batch.questions[0].model_answer and batch.questions[0].student_answer
    assert not list(tmp_path.iterdir())
