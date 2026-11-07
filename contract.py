"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    LIST_GRADING_DATA = "list_grading_data"
    GET_GRADING_QUESTION = "get_grading_question"
    RECORD_GRADES = "record_grades"
    PIN_TEACHER_SCORES = "pin_teacher_scores"


class Task(Enum):
    LIST_GRADING_DATA = "list-grading-data"
    GRADE_STUDENT = "grade-student"


@dataclass
class GradeStudentInput(Output):
    student_id: Annotated[str, "Exactly one student ID, S1 through S5"]
    question_ids: Annotated[list[str], "Distinct question IDs NQ001 through NQ012, or [] for all"]


@dataclass
class GradingQuestionInput(GradeStudentInput):
    question_ids: Annotated[list[str], "Exactly one question ID NQ001 through NQ012; empty or multiple IDs are rejected"]


@dataclass
class ListGradingInput(Output):
    pass


@dataclass
class QuestionSummary(Output):
    question_id: str
    prompt: str


@dataclass
class GradingCatalogOutput(Output):
    student_ids: list[str]
    questions: list[QuestionSummary]


@dataclass
class RubricCriterion(Output):
    criterion: Annotated[int, "Criterion number, 1 through 5"]
    name: str
    level_1: str
    level_2: str
    level_3: str
    level_4: str


@dataclass
class GradingQuestion(Output):
    question_id: str
    prompt: str
    model_answer: str
    student_answer: str
    rubric: list[RubricCriterion]


@dataclass
class GradingQuestionOutput(Output):
    student_id: str
    questions: list[GradingQuestion]


@dataclass
class CriterionGrade(Output):
    criterion: Annotated[int, "Criterion number from the rubric, 1 through 5"]
    score: Annotated[int, "An integer rubric score, 1 through 4"]
    justification: Annotated[str, "One short, specific justification grounded in the response"]


@dataclass
class ResponseGrade(Output):
    question_id: str
    grades: list[CriterionGrade]


@dataclass
class RecordGradesInput(Output):
    selection: GradeStudentInput
    responses: Annotated[list[ResponseGrade], "Grades for exactly one selected response"]


@dataclass
class ResponseTotal(Output):
    question_id: str
    total: int


@dataclass
class GradeReceiptOutput(Output):
    receipt_id: str
    totals: list[ResponseTotal]


@dataclass
class GradeSubmissionOutput(Output):
    receipt_ids: Annotated[list[str], "Copy each receipt_id returned by record_grades exactly once"]


@dataclass
class TeacherCriterion(Output):
    criterion: int
    name: str
    scores: Annotated[list[int], "Scores in the fixed evaluator order E1 through E5"]


@dataclass
class TeacherResponse(Output):
    question_id: str
    criteria: list[TeacherCriterion]


@dataclass
class TeacherReferenceOutput(Output):
    student_id: str
    responses: list[TeacherResponse]
    prior_receipt_ids: list[str]


TOOLS = {
    Tool.LIST_GRADING_DATA: (ListGradingInput, GradingCatalogOutput),
    Tool.GET_GRADING_QUESTION: (GradingQuestionInput, GradingQuestionOutput),
    Tool.RECORD_GRADES: (RecordGradesInput, GradeReceiptOutput),
    Tool.PIN_TEACHER_SCORES: (GradeStudentInput, TeacherReferenceOutput),
}
TASKS = {
    Task.LIST_GRADING_DATA: (ListGradingInput, GradingCatalogOutput),
    Task.GRADE_STUDENT: (GradeStudentInput, GradeSubmissionOutput),
}
