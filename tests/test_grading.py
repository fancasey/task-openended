import pytest
from slimconfig import build_output

import verifier
from contract import GradeStudentInput, GradeSubmissionOutput, RecordGradesInput
from plugin.grading import get_grading_question, pin_teacher_scores


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"student_id": "S1"},
        {"student_id": ["S1", "S2"], "question_id": "NQ001"},
        {"student_id": "S1", "question_ids": []},
        {"student_id": "S1", "question_ids": ["NQ001", "NQ002"]},
        {"student_id": "S1", "question_ids": "NQ001"},
        {"student_id": "S1", "question_ids": [1]},
        {"student_id": "S1", "question_ids": [], "teacher_scores": []},
    ],
)
def test_selection_schema_rejects_bad_shape(bad):
    with pytest.raises(ValueError):
        build_output(bad, GradeStudentInput)


@pytest.mark.parametrize("student, question", [
    ("S0", "NQ001"), ("S6", "NQ001"), ("s1", "NQ001"), ("S1,S2", "NQ001"),
    (" S1", "NQ001"), ("S1", "NQ000"), ("S1", "NQ013"), ("S1", "NQ1"),
    ("S1", ""), ("S1", "NQ001,NQ002"), ("S1", "all"),
])
def test_selection_rejects_invalid_ids(student, question, make_response, make_reference, tmp_path):
    selection = build_output({"student_id": student, "question_id": question}, GradeStudentInput)
    for tool in ("get_grading_question", "pin_teacher_scores"):
        assert not verifier.verify_input(tool, selection)["valid"]
    for tool in (get_grading_question, pin_teacher_scores):
        with pytest.raises(ValueError):
            tool(selection, tmp_path)
    value = RecordGradesInput(selection, [make_response()])
    assert not verifier.verify_input("record_grades", value)["valid"]
    verdict = verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput([]), make_reference([[3] * 5] * 5), tmp_path
    )
    assert not verdict["valid"]


@pytest.mark.parametrize("score", [True, "3", 3.0, None])
def test_nested_score_type_is_strict(score):
    with pytest.raises(ValueError):
        build_output(
            {
                "selection": {"student_id": "S1", "question_id": "NQ001"},
                "responses": [
                    {"question_id": "NQ001", "grades": [{"criterion": 1, "score": score, "justification": "Evidence"}]}
                ],
            },
            RecordGradesInput,
        )


def test_workbook_scope_rubric_and_teacher_order(tmp_path):
    selection = GradeStudentInput("S1", "NQ001")
    batch = get_grading_question(selection, tmp_path)
    assert [q.question_id for q in batch.questions] == ["NQ001"]
    assert batch.student_id == "S1"
    first = batch.questions[0]
    assert "circular list" in first.prompt
    assert "efficient traversal" in first.student_answer
    assert "efficient traversal" in first.model_answer
    assert first.rubric[0].name == "Explanation"
    assert first.rubric[0].level_4.startswith("Accurately")
    assert all(len(q.rubric) == 5 for q in batch.questions)
    assert (
        get_grading_question(GradeStudentInput("S2", "NQ001"), tmp_path).questions[0].student_answer
        != first.student_answer
    )
    assert verifier.verify_output("get_grading_question", selection, batch, tmp_path)["valid"]
    reference = pin_teacher_scores(selection, tmp_path)
    assert reference.responses[0].criteria[0].scores == [4, 3, 4, 2, 3]


@pytest.mark.parametrize("question", [[], ["NQ001"], ["NQ001", "NQ002"], None, 1])
def test_question_schema_rejects_non_scalar(question):
    with pytest.raises(ValueError):
        build_output({"student_id": "S1", "question_id": question}, GradeStudentInput)
