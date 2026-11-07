"""Compare verdicts with independent arithmetic, including exact tolerance endpoints."""

from fractions import Fraction
from itertools import combinations

import pytest

import verifier
from contract import GradeSubmissionOutput, RecordGradesInput
from plugin.grading import record_grades


@pytest.mark.parametrize("agent", range(1, 5))
@pytest.mark.parametrize("teacher", range(1, 5))
def test_uniform_scores_cover_every_distance(agent, teacher, selection, make_response, make_reference, tmp_path):
    receipt = record_grades(RecordGradesInput(selection, [make_response(scores=[agent] * 5)]), tmp_path)
    verdict = verifier.verify_task(
        "grade-student",
        selection,
        GradeSubmissionOutput([receipt.receipt_id]),
        make_reference([[teacher] * 5] * 5),
        tmp_path,
    )
    details = verdict["details"]
    assert verdict["score"] == pytest.approx(float(1 - Fraction(abs(agent - teacher), 3)))
    assert verdict["valid"] == (agent == teacher)
    assert details["criterion_failures"] == (0 if abs(agent - teacher) <= 1 else 5)
    assert details["total_failures"] == (0 if agent == teacher else 1)
    assert details["teacher_agreement_score"] == 100


@pytest.mark.parametrize("scores", [(1, 2, 3, 4, 1), (4, 1, 2, 3, 4), (2, 2, 2, 2, 2), (3, 3, 3, 3, 3)])
@pytest.mark.parametrize("teachers", [(1, 2, 3, 4, 1), (4, 4, 1, 1, 2), (2, 2, 2, 3, 3)])
def test_mixed_scores_match_independent_oracle(scores, teachers, selection, make_response, make_reference, tmp_path):
    rows = [teachers[i:] + teachers[:i] for i in range(5)]
    receipt = record_grades(RecordGradesInput(selection, [make_response(scores=scores)]), tmp_path)
    verdict = verifier.verify_task(
        "grade-student", selection, GradeSubmissionOutput([receipt.receipt_id]), make_reference(rows), tmp_path
    )
    error = Fraction(sum(abs(a - t) for a, row in zip(scores, rows) for t in row), 25)
    teacher_error = Fraction(sum(abs(a - b) for row in rows for a, b in combinations(row, 2)), 50)
    totals = [sum(row[j] for row in rows) for j in range(5)]
    failures = sum(min(abs(a - t) for t in row) > 1 for a, row in zip(scores, rows))
    total_failed = not min(totals) <= sum(scores) <= max(totals)
    assert verdict["score"] == pytest.approx(float(1 - error / 3))
    assert verdict["details"]["mean_absolute_error"] == round(float(error), 4)
    assert verdict["details"]["teacher_agreement_score"] == round(float(100 * (1 - teacher_error / 3)), 2)
    assert verdict["details"]["criterion_failures"] == failures
    assert verdict["details"]["total_failures"] == int(total_failed)
    assert verdict["valid"] == (failures == 0 and not total_failed)
