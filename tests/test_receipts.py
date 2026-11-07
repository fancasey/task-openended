import json
from dataclasses import asdict
from hashlib import sha256

import pytest

import verifier
from contract import GradeSubmissionOutput, RecordGradesInput
from plugin.grading import pin_teacher_scores, record_grades
from verifier.grading import read_receipt


@pytest.mark.parametrize("receipt_id", ["", "../outside", "/tmp/outside", "a" * 63, "a" * 65, "A" * 64, "z" * 64])
def test_receipt_id_cannot_name_an_arbitrary_file(receipt_id, selection, make_reference, tmp_path):
    verdict = verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput([receipt_id]), make_reference([[3] * 5] * 5), tmp_path
    )
    assert not verdict["valid"] and verdict["score"] == 0
    assert "invalid grading receipt ID" in verdict["message"]


@pytest.mark.parametrize("contents", [b"", b"{}", b"not-json", b"[]", b'{"batch": {}}'])
def test_changed_receipt_is_rejected(contents, selection, make_response, make_reference, tmp_path):
    receipt = record_grades(RecordGradesInput(selection, [make_response()]), tmp_path)
    (tmp_path / "grading-receipts" / f"{receipt.receipt_id}.json").write_bytes(contents)
    verdict = verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput([receipt.receipt_id]), make_reference([[3] * 5] * 5), tmp_path
    )
    assert not verdict["valid"] and verdict["score"] == 0
    assert "contents changed" in verdict["message"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"batch": {}},
        {"batch": {"selection": {}}},
        {"batch": {"selection": {"student_id": "S1", "question_id": "NQ001"}, "responses": []}},
    ],
)
def test_rehashed_malformed_receipt_still_fails(payload, selection, make_reference, tmp_path):
    directory = tmp_path / "grading-receipts"
    directory.mkdir()
    data = json.dumps(payload).encode()
    receipt_id = sha256(data).hexdigest()
    (directory / f"{receipt_id}.json").write_bytes(data)
    verdict = verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput([receipt_id]), make_reference([[3] * 5] * 5), tmp_path
    )
    assert not verdict["valid"] and verdict["score"] == 0


def test_identical_batches_get_distinct_receipts_without_overwriting(selection, make_response, tmp_path):
    batch = RecordGradesInput(selection, [make_response()])
    first = record_grades(batch, tmp_path)
    before = (tmp_path / "grading-receipts" / f"{first.receipt_id}.json").read_bytes()
    second = record_grades(batch, tmp_path)
    assert first.receipt_id != second.receipt_id
    assert read_receipt(tmp_path, first.receipt_id) == read_receipt(tmp_path, second.receipt_id) == asdict(batch)
    assert (tmp_path / "grading-receipts" / f"{first.receipt_id}.json").read_bytes() == before


def test_pin_snapshots_only_receipts_already_present(selection, make_response, tmp_path):
    old = record_grades(RecordGradesInput(selection, [make_response()]), tmp_path)
    reference = pin_teacher_scores(selection, tmp_path)
    new = record_grades(RecordGradesInput(selection, [make_response()]), tmp_path)
    assert reference.prior_receipt_ids == [old.receipt_id]
    assert new.receipt_id not in reference.prior_receipt_ids


@pytest.mark.parametrize("target", ["directory", "file"])
def test_receipt_symlinks_cannot_escape_workspace(target, selection, make_response, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    directory = tmp_path / "grading-receipts"
    if target == "directory":
        directory.symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError, match="stay in the workspace"):
            record_grades(RecordGradesInput(selection, [make_response()]), tmp_path)
    else:
        receipt = record_grades(RecordGradesInput(selection, [make_response()]), tmp_path)
        path = directory / f"{receipt.receipt_id}.json"
        destination = outside / "receipt.json"
        path.rename(destination)
        path.symlink_to(destination)
        with pytest.raises(ValueError, match="regular workspace file"):
            read_receipt(tmp_path, receipt.receipt_id)
