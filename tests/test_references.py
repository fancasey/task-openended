from dataclasses import replace

import pytest

import verifier
from contract import GradeSubmissionOutput


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "student",
        "empty",
        "wrong-question",
        "duplicate-question",
        "missing-criterion",
        "duplicate-criterion",
        "few-scores",
        "extra-scores",
        "zero",
        "five",
        "bool",
        "float",
        "string",
        "prior-id",
    ],
)
def test_malformed_reference_is_rejected_before_submission(change, selection, make_reference, tmp_path):
    reference = make_reference([[3] * 5] * 5)
    response = reference.responses[0]
    criterion = response.criteria[0]
    if change == "missing":
        reference = None
    elif change == "student":
        reference = replace(reference, student_id="S2")
    elif change in ("empty", "wrong-question", "duplicate-question"):
        rows = {
            "empty": [],
            "wrong-question": [replace(response, question_id="NQ002")],
            "duplicate-question": [response, response],
        }
        reference = replace(reference, responses=rows[change])
    elif change == "prior-id":
        reference = replace(reference, prior_receipt_ids=["../outside"])
    else:
        if change == "missing-criterion":
            criteria = response.criteria[1:]
        elif change == "duplicate-criterion":
            criteria = [criterion] * 5
        else:
            scores = {
                "few-scores": [3] * 4,
                "extra-scores": [3] * 6,
                "zero": [0] * 5,
                "five": [5] * 5,
                "bool": [True] * 5,
                "float": [3.0] * 5,
                "string": ["3"] * 5,
            }[change]
            criteria = [replace(criterion, scores=scores), *response.criteria[1:]]
        reference = replace(reference, responses=[replace(response, criteria=criteria)])
    verdict = verifier.verify_task("grade-student", selection, GradeSubmissionOutput([]), reference, tmp_path)
    assert not verdict["valid"]
    assert verdict["score"] == 0
    assert "submission" not in verdict["message"].lower()
