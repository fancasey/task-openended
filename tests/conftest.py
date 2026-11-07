import pytest

from contract import (
    CriterionGrade,
    GradeStudentInput,
    ResponseGrade,
    TeacherCriterion,
    TeacherReferenceOutput,
    TeacherResponse,
)


@pytest.fixture
def selection():
    return GradeStudentInput("S1", "NQ001")


@pytest.fixture
def make_response():
    def make(question="NQ001", scores=(3, 3, 3, 3, 3)):
        return ResponseGrade(
            question, [CriterionGrade(i, score, f"Evidence for criterion {i}") for i, score in enumerate(scores, 1)]
        )

    return make


@pytest.fixture
def make_reference():
    def make(rows, student="S1", question="NQ001"):
        return TeacherReferenceOutput(
            student,
            [
                TeacherResponse(
                    question, [TeacherCriterion(i, f"Criterion {i}", list(scores)) for i, scores in enumerate(rows, 1)]
                )
            ],
            [],
        )

    return make
