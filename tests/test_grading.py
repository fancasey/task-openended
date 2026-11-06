import csv
import os
import sys
from dataclasses import replace
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output

import verifier
from contract import (
    CriterionGrade,
    GradeStudentInput,
    GradeSubmissionOutput,
    RecordGradesInput,
    ResponseGrade,
    TeacherCriterion,
    TeacherReferenceOutput,
    TeacherResponse,
)
from plugin.grading import get_grading_batch, pin_teacher_scores, record_grades
from plugin.grading_data import WORKBOOK, workbook_data
from verifier.grading import QUESTIONS


def response(question="NQ001", score=3):
    return ResponseGrade(question, [CriterionGrade(i, score, "Explains a relevant property.") for i in range(1, 6)])


def submit(selection, receipts, reference, workspace):
    return verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput(receipts), reference, workspace
    )


def reference_for(selection, rows):
    return TeacherReferenceOutput(selection.student_id, [
        TeacherResponse("NQ001", [TeacherCriterion(i, f"Criterion {i}", row) for i, row in enumerate(rows, 1)])
    ], [])


@pytest.mark.parametrize("bad", [
    {},
    {"student_id": "S1"},
    {"student_id": ["S1", "S2"], "question_ids": []},
    {"student_id": "S1", "question_ids": "NQ001"},
    {"student_id": "S1", "question_ids": [1]},
    {"student_id": "S1", "question_ids": [], "teacher_scores": []},
])
def test_selection_schema_rejects_bad_shape(bad):
    with pytest.raises(ValueError):
        build_output(bad, GradeStudentInput)


@pytest.mark.parametrize("student, questions", [
    ("S0", []), ("S6", []), ("s1", []), ("S1,S2", []), (" S1", []), ("S1", ["NQ000"]),
    ("S1", ["NQ013"]), ("S1", ["NQ001", "NQ001"]), ("S1", ["NQ1"]),
])
def test_selection_rejects_invalid_ids(student, questions, tmp_path):
    selection = build_output({"student_id": student, "question_ids": questions}, GradeStudentInput)
    for tool in ("get_grading_batch", "pin_teacher_scores"):
        assert not verifier.verify_input(tool, selection)["valid"]
    with pytest.raises(ValueError):
        get_grading_batch(selection, tmp_path)


@pytest.mark.parametrize("score", [True, "3", 3.0, None])
def test_nested_score_type_is_strict(score):
    with pytest.raises(ValueError):
        build_output({
            "selection": {"student_id": "S1", "question_ids": []},
            "responses": [{"question_id": "NQ001", "grades": [
                {"criterion": 1, "score": score, "justification": "Evidence"}
            ]}],
        }, RecordGradesInput)


@pytest.mark.parametrize("responses", [
    [], [response("NQ002")], [response(), response()], [response(score=0)], [response(score=5)],
    [replace(response(), grades=response().grades[1:])],
    [replace(response(), grades=response().grades[:4] + [response().grades[0]])],
    [replace(response(), grades=[CriterionGrade(1, 2, "  "), *response().grades[1:]])],
    [response(f"NQ{i:03}") for i in range(1, 8)],
])
def test_rejects_invalid_record_batch(responses, tmp_path):
    selection = GradeStudentInput("S1", ["NQ001"])
    batch = RecordGradesInput(selection, responses)
    assert not verifier.verify_input("record_grades", batch)["valid"]
    with pytest.raises(ValueError):
        record_grades(batch, tmp_path)
    assert not list(tmp_path.iterdir())


def test_workbook_scope_rubric_and_teacher_order(tmp_path):
    selection = GradeStudentInput("S1", ["NQ012", "NQ001"])
    batch = get_grading_batch(selection, tmp_path)
    assert [q.question_id for q in batch.questions] == ["NQ001", "NQ012"]
    assert batch.student_id == "S1"
    first = batch.questions[0]
    assert "circular list" in first.prompt
    assert "efficient traversal" in first.student_answer
    assert "efficient traversal" in first.model_answer
    assert first.rubric[0].name == "Explanation"
    assert first.rubric[0].level_4.startswith("Accurately")
    assert all(len(q.rubric) == 5 for q in batch.questions)
    assert get_grading_batch(GradeStudentInput("S2", ["NQ001"]), tmp_path).questions[0].student_answer != first.student_answer
    assert verifier.verify_output("get_grading_batch", selection, batch, tmp_path)["valid"]
    reference = pin_teacher_scores(selection, tmp_path)
    assert reference.responses[0].criteria[0].scores == [4, 3, 4, 2, 3]


def test_all_workbook_responses_and_scores_match_the_companion_csv():
    questions, teachers = workbook_data()
    assert len(questions) == len(teachers) == 60
    checked = set()
    path = WORKBOOK.with_name("Input file for NLP of 12 question scores.csv")
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            key = (row["StudentID"], row["QID"])
            question = questions[key]
            criterion = next(item for item in question.rubric if item.name == row["Rubric"])
            assert question.student_answer.strip() == row["ResponseText"].strip()
            assert all((criterion.level_1, criterion.level_2, criterion.level_3, criterion.level_4))
            teacher = teachers[key].criteria[criterion.criterion - 1]
            assert teacher.name == row["Rubric"]
            assert round(sum(teacher.scores) / 5) == int(row["Score"])
            checked.add((*key, criterion.criterion))
    assert len(checked) == 300


def test_full_student_coverage_across_two_batches(tmp_path):
    selection = GradeStudentInput("S5", [])
    reference = pin_teacher_scores(selection, tmp_path)
    assert [r.question_id for r in reference.responses] == list(QUESTIONS)
    ids = []
    for questions in (QUESTIONS[:6], QUESTIONS[6:]):
        batch = RecordGradesInput(selection, [response(q) for q in questions])
        receipt = record_grades(batch, tmp_path)
        assert [row.total for row in receipt.totals] == [15] * 6
        assert verifier.verify_output("record_grades", batch, receipt, tmp_path)["valid"]
        ids.append(receipt.receipt_id)
    assert "missing grades" in submit(selection, ids[:1], reference, tmp_path)["message"]
    verdict = submit(selection, ids[::-1], reference, tmp_path)
    assert len(verdict["details"]["responses"]) == 12
    assert sum(row["agent_count"] for row in verdict["details"]["distribution"]) == 60


def test_agreement_baseline_and_distribution_warning(tmp_path):
    selection = GradeStudentInput("S1", ["NQ001"])
    reference = reference_for(selection, [[2, 3, 3, 3, 4]] * 5)
    receipt = record_grades(RecordGradesInput(selection, [response(score=3)]), tmp_path)
    verdict = submit(selection, [receipt.receipt_id], reference, tmp_path)
    assert verdict["valid"]
    assert verdict["score"] == pytest.approx(1 - 0.4 / 3)
    details = verdict["details"]
    assert details["agreement_score"] == 86.67
    assert details["mean_absolute_error"] == 0.4
    assert details["teacher_agreement_score"] == 73.33
    assert not details["distribution_warning"]
    assert details["responses"][0]["total"] == 15

    rows = [[4 if index == teacher else 3 for teacher in range(5)] for index in range(5)]
    reference = reference_for(selection, rows)
    # Each teacher has four 3s and one 4. This agent's total and all items still pass.
    row = response()
    grades = [replace(g, score=4 if g.criterion in (1, 2) else 2 if g.criterion == 3 else 3) for g in row.grades]
    receipt = record_grades(RecordGradesInput(selection, [replace(row, grades=grades)]), tmp_path)
    verdict = submit(selection, [receipt.receipt_id], reference, tmp_path)
    assert verdict["valid"]
    assert verdict["details"]["distribution_warning"]
    assert [r["deviation"] for r in verdict["details"]["distribution"]] == [0, 1, -2, 1]


def test_criterion_any_teacher_and_total_preserves_evaluator_columns(tmp_path):
    selection = GradeStudentInput("S1", ["NQ001"])
    reference = reference_for(selection, [[4, 1, 1, 1, 1], *([[1, 4, 1, 1, 1]] * 4)])
    receipt = record_grades(RecordGradesInput(selection, [response(score=4)]), tmp_path)
    verdict = submit(selection, [receipt.receipt_id], reference, tmp_path)
    assert not verdict["valid"]
    assert verdict["score"] > 0
    assert verdict["details"]["criterion_failures"] == 0
    assert verdict["details"]["total_failures"] == 1
    assert verdict["details"]["responses"][0]["teacher_total_max"] == 17

    reference = reference_for(selection, [[1] * 5] * 5)
    verdict = submit(selection, [receipt.receipt_id], reference, tmp_path)
    assert verdict["score"] == 0
    assert verdict["details"]["criterion_failures"] == 5
    assert verdict["details"]["teacher_agreement_score"] == 100


def test_invalid_receipts_and_pinned_scope(tmp_path):
    selection = GradeStudentInput("S1", ["NQ001", "NQ002"])
    reference = pin_teacher_scores(selection, tmp_path)
    batch = RecordGradesInput(selection, [response()])
    first = record_grades(batch, tmp_path).receipt_id
    second = record_grades(batch, tmp_path).receipt_id
    wrong_student = record_grades(RecordGradesInput(GradeStudentInput("S2", selection.question_ids), [response()]), tmp_path)
    for ids, error in [
        ([], "distinct receipts"), ([first, first], "distinct receipts"),
        ([first, second], "duplicate grade"), ([wrong_student.receipt_id], "different selection"),
        (["../anything"], "invalid grading receipt ID"), (["0" * 64], "invalid submission"),
    ]:
        verdict = submit(selection, ids, reference, tmp_path)
        assert not verdict["valid"] and verdict["score"] == 0
        assert error in verdict["message"]

    assert "predates" in submit(selection, [first], pin_teacher_scores(selection, tmp_path), tmp_path)["message"]
    assert not submit(selection, [first], replace(reference, student_id="S2"), tmp_path)["valid"]
    assert not submit(selection, [first], replace(reference, responses=[]), tmp_path)["valid"]
    path = tmp_path / "grading-receipts" / f"{first}.json"
    path.write_text("{}")
    assert "contents changed" in submit(selection, [first], reference, tmp_path)["message"]


def test_stdio_structured_tools(tmp_path):
    root = Path(__file__).resolve().parents[1]

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], cwd=root,
            env={**os.environ, "NANOAGENT_WORKSPACE": str(tmp_path), "PYTHONPATH": str(root / "src")},
        )
        async with stdio_client(params) as streams, ClientSession(*streams) as session:
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert set(tools) == {"list_grading_data", "get_grading_batch", "record_grades", "pin_teacher_scores"}
            schema = tools["get_grading_batch"].inputSchema
            assert schema["properties"]["student_id"]["type"] == "string"
            assert schema["properties"]["question_ids"]["type"] == "array"
            assert not schema["additionalProperties"]
            catalog = await session.call_tool("list_grading_data", {})
            assert not catalog.isError
            assert len(catalog.structuredContent["questions"]) == 12
            selection = {"student_id": "S1", "question_ids": ["NQ001"]}
            batch = await session.call_tool("get_grading_batch", selection)
            assert not batch.isError
            question = batch.structuredContent["questions"][0]
            assert set(question) == {"question_id", "prompt", "model_answer", "student_answer", "rubric"}
            assert set(question["rubric"][0]) == {"criterion", "name", "level_1", "level_2", "level_3", "level_4"}
            assert (await session.call_tool("get_grading_batch", {**selection, "student_id": ["S1", "S2"]})).isError
            assert (await session.call_tool("get_grading_batch", {**selection, "student_id": "S6"})).isError
            receipt = await session.call_tool("record_grades", {"selection": selection, "responses": [{
                "question_id": "NQ001", "grades": [
                    {"criterion": i, "score": 3, "justification": "Evidence in the answer"} for i in range(1, 6)
                ],
            }]})
            assert not receipt.isError
            assert receipt.structuredContent["totals"] == [{"question_id": "NQ001", "total": 15}]

    anyio.run(run)
