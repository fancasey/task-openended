import csv
import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output

import verifier
from contract import GradeStudentInput, RecordGradesInput
from plugin.grading import get_grading_batch, pin_teacher_scores
from plugin.grading_data import WORKBOOK, workbook_data


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
