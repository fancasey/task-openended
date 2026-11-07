"""Serve rubric-only material to the agent and persist its submitted judgements."""

import json
from dataclasses import asdict
from hashlib import sha256
from uuid import uuid4

from contract import (
    GradeReceiptOutput,
    GradingCatalogOutput,
    GradingQuestionOutput,
    QuestionSummary,
    ResponseTotal,
    TeacherReferenceOutput,
)
from verifier.grading import (
    QUESTIONS,
    RECEIPT,
    STUDENTS,
    receipt_directory,
    record_problem,
    selected_questions,
    selection_problem,
)

from .grading_data import workbook_data


def list_grading_data(_value, _workspace):
    questions, _ = workbook_data()
    return GradingCatalogOutput(
        list(STUDENTS),
        [QuestionSummary(qid, questions[STUDENTS[0], qid].prompt) for qid in QUESTIONS],
    )


def get_grading_question(selection, _workspace):
    if problem := selection_problem(selection):
        raise ValueError(problem)
    questions, _ = workbook_data()
    return GradingQuestionOutput(
        selection.student_id, [questions[selection.student_id, qid] for qid in selected_questions(selection)]
    )


def record_grades(value, workspace):
    if problem := record_problem(value):
        raise ValueError(problem)
    directory = receipt_directory(workspace)
    directory.mkdir(exist_ok=True)
    data = json.dumps({"nonce": uuid4().hex, "batch": asdict(value)}, ensure_ascii=False).encode("utf-8")
    receipt_id = sha256(data).hexdigest()
    with (directory / f"{receipt_id}.json").open("xb") as file:
        file.write(data)
    return GradeReceiptOutput(
        receipt_id,
        [ResponseTotal(r.question_id, sum(g.score for g in r.grades)) for r in value.responses],
    )


def pin_teacher_scores(selection, workspace):
    if problem := selection_problem(selection):
        raise ValueError(problem)
    _, teachers = workbook_data()
    directory = receipt_directory(workspace)
    prior = sorted(path.stem for path in directory.glob("*.json") if RECEIPT.fullmatch(path.stem))
    return TeacherReferenceOutput(
        selection.student_id, [teachers[selection.student_id, qid] for qid in selected_questions(selection)], prior
    )
