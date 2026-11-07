from dataclasses import replace

import pytest

import verifier
from contract import ListGradingInput, RecordGradesInput, ResponseTotal
from plugin.grading import get_grading_batch, list_grading_data, record_grades


@pytest.mark.parametrize(
    "change", ["student", "empty", "duplicate", "wrong-question", "missing-rubric", "rubric-order"]
)
def test_batch_output_rejects_wrong_scope_or_rubric(change, selection, tmp_path):
    batch = get_grading_batch(selection, tmp_path)
    question = batch.questions[0]
    if change == "student":
        batch = replace(batch, student_id="S2")
    else:
        questions = {
            "empty": [],
            "duplicate": [question, question],
            "wrong-question": [replace(question, question_id="NQ002")],
            "missing-rubric": [replace(question, rubric=question.rubric[:4])],
            "rubric-order": [replace(question, rubric=question.rubric[::-1])],
        }
        batch = replace(batch, questions=questions[change])
    assert not verifier.verify_output("get_grading_batch", selection, batch, tmp_path)["valid"]


@pytest.mark.parametrize("change", ["student", "missing", "duplicate", "order"])
def test_catalog_is_checked_for_both_tool_and_task(change, tmp_path):
    request = ListGradingInput()
    catalog = list_grading_data(request, tmp_path)
    if change == "student":
        catalog = replace(catalog, student_ids=["S1"])
    else:
        questions = {
            "missing": catalog.questions[:-1],
            "duplicate": [catalog.questions[0]] * 12,
            "order": catalog.questions[::-1],
        }
        catalog = replace(catalog, questions=questions[change])
    assert not verifier.verify_output("list_grading_data", request, catalog, tmp_path)["valid"]
    assert not verifier.verify_task("list-grading-data", request, catalog, None, tmp_path)["valid"]


@pytest.mark.parametrize("change", ["total", "question", "empty", "missing-file", "different-batch"])
def test_record_output_must_match_saved_batch(change, selection, make_response, tmp_path):
    batch = RecordGradesInput(selection, [make_response()])
    receipt = record_grades(batch, tmp_path)
    if change == "total":
        receipt = replace(receipt, totals=[ResponseTotal("NQ001", 20)])
    elif change == "question":
        receipt = replace(receipt, totals=[ResponseTotal("NQ002", 15)])
    elif change == "empty":
        receipt = replace(receipt, totals=[])
    elif change == "missing-file":
        receipt = replace(receipt, receipt_id="0" * 64)
    else:
        batch = RecordGradesInput(selection, [make_response(scores=[4] * 5)])
    assert not verifier.verify_output("record_grades", batch, receipt, tmp_path)["valid"]
