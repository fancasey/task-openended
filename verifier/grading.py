"""Validate grading requests and score immutable submissions against the pinned evaluators."""

import json
import re
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path

from contract import CriterionGrade, GradeStudentInput, RecordGradesInput, ResponseGrade

from .checks import result

STUDENTS = tuple(f"S{i}" for i in range(1, 6))
QUESTIONS = tuple(f"NQ{i:03}" for i in range(1, 13))
CRITERIA = {1, 2, 3, 4, 5}
SCORES = (1, 2, 3, 4)
RECEIPT = re.compile(r"[0-9a-f]{64}")
RECEIPT_FOLDER = "grading-receipts"


def selection_problem(value):
    if value.student_id not in STUDENTS:
        return "student_id must be one of S1 through S5"
    if not isinstance(value.question_ids, list) or any(q not in QUESTIONS for q in value.question_ids):
        return "question_ids must contain only NQ001 through NQ012"
    if len(value.question_ids) != len(set(value.question_ids)):
        return "question_ids must be distinct"
    return None


def question_problem(value):
    if problem := selection_problem(value):
        return problem
    if len(value.question_ids) != 1:
        return "request exactly one question per call"
    return None


def selected_questions(value):
    return sorted(value.question_ids) or list(QUESTIONS)


def record_problem(value):
    if problem := selection_problem(value.selection):
        return problem
    if len(value.responses) != 1:
        return "record exactly one response per call"
    requested = selected_questions(value.selection)
    seen = set()
    for response in value.responses:
        qid = response.question_id
        if qid not in requested or qid in seen:
            return f"{qid} must be a distinct selected question"
        seen.add(qid)
        if len(response.grades) != 5 or {g.criterion for g in response.grades} != CRITERIA:
            return f"{qid} must have exactly one grade for each criterion 1 through 5"
        for grade in response.grades:
            if type(grade.criterion) is not int:
                return f"{qid} must use integer criterion IDs"
            if type(grade.score) is not int or grade.score not in SCORES:
                return f"{qid} criterion {grade.criterion} must be an integer from 1 to 4"
            if not isinstance(grade.justification, str) or not grade.justification.strip():
                return f"{qid} criterion {grade.criterion} requires a justification"
    return None


def reference_problem(selection, reference):
    if reference is None or reference.student_id != selection.student_id:
        return "missing teacher reference for the selected student"
    if sorted(row.question_id for row in reference.responses) != selected_questions(selection):
        return "teacher reference must cover each selected question once"
    for response in reference.responses:
        if len(response.criteria) != 5 or {c.criterion for c in response.criteria} != CRITERIA:
            return f"{response.question_id} has an incomplete teacher rubric"
        for criterion in response.criteria:
            if len(criterion.scores) != 5 or any(type(s) is not int or s not in SCORES for s in criterion.scores):
                return f"{response.question_id} must have five valid teacher scores per criterion"
    if any(not RECEIPT.fullmatch(value) for value in reference.prior_receipt_ids):
        return "invalid prior receipt ID in teacher reference"
    return None


def receipt_directory(workspace):
    root = Path(workspace).resolve()
    directory = root / RECEIPT_FOLDER
    if directory.resolve() != directory:
        raise ValueError("grading receipts must stay in the workspace receipt directory")
    return directory


def read_receipt(workspace, receipt_id):
    if not RECEIPT.fullmatch(receipt_id):
        raise ValueError("invalid grading receipt ID")
    path = receipt_directory(workspace) / f"{receipt_id}.json"
    if path.resolve() != path:
        raise ValueError("grading receipt must be a regular workspace file")
    data = path.read_bytes()
    if sha256(data).hexdigest() != receipt_id:
        raise ValueError("grading receipt contents changed")
    return json.loads(data)["batch"]


def verify_input(tool, value):
    if tool == "record_grades":
        problem = record_problem(value)
    elif tool == "get_grading_question":
        problem = question_problem(value)
    elif tool == "list_grading_data":
        problem = None
    else:
        problem = selection_problem(value)
    return result(problem is None, problem or "Valid grading input")


def verify_output(tool, value, output, workspace):
    problem = None
    if tool == "record_grades":
        try:
            stored = read_receipt(workspace, output.receipt_id)
            expected = [(r.question_id, sum(g.score for g in r.grades)) for r in value.responses]
            if stored != asdict(value) or [(r.question_id, r.total) for r in output.totals] != expected:
                problem = "receipt or totals differ from the recorded grades"
        except (OSError, ValueError, KeyError, TypeError) as error:
            problem = f"could not read grading receipt: {error}"
    elif tool == "pin_teacher_scores":
        problem = reference_problem(value, output)
    elif tool == "get_grading_question":
        if question_problem(value) or output.student_id != value.student_id or [q.question_id for q in output.questions] != selected_questions(value):
            problem = "grading data must cover the selected student and questions"
        elif any([r.criterion for r in q.rubric] != sorted(CRITERIA) for q in output.questions):
            problem = "grading data must include all five rubric criteria"
    elif output.student_ids != list(STUDENTS) or [q.question_id for q in output.questions] != list(QUESTIONS):
        problem = "grading catalog does not list the supported students and questions"
    return result(problem is None, problem or "Valid grading tool output")


def submission_grades(selection, output, reference, workspace):
    ids = output.receipt_ids
    requested = selected_questions(selection)
    if not 1 <= len(ids) <= len(requested) or len(set(ids)) != len(ids):
        raise ValueError("submit distinct receipts covering the selected questions")
    responses = {}
    for receipt_id in ids:
        if receipt_id in reference.prior_receipt_ids:
            raise ValueError("grading receipt predates this task")
        batch = read_receipt(workspace, receipt_id)
        scope = GradeStudentInput(**batch["selection"])
        if scope.student_id != selection.student_id or selected_questions(scope) != requested:
            raise ValueError("grading receipt is for a different selection")
        recorded = RecordGradesInput(scope, [
            ResponseGrade(row["question_id"], [CriterionGrade(**g) for g in row["grades"]])
            for row in batch["responses"]
        ])
        if problem := record_problem(recorded):
            raise ValueError(problem)
        for response in recorded.responses:
            qid = response.question_id
            if qid not in requested or qid in responses:
                raise ValueError(f"unexpected or duplicate grade for {qid}")
            responses[qid] = {grade.criterion: asdict(grade) for grade in response.grades}
    if missing := sorted(set(requested) - responses.keys()):
        raise ValueError(f"missing grades for {', '.join(missing)}")
    return responses


def verify_task(selection, output, reference, workspace):
    if problem := selection_problem(selection) or reference_problem(selection, reference):
        return result(False, problem)
    try:
        responses = submission_grades(selection, output, reference, workspace)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return result(False, f"Incomplete or invalid submission: {error}")

    reports, all_scores, all_teacher_rows = [], [], []
    criterion_failures = total_failures = 0
    for response in sorted(reference.responses, key=lambda row: row.question_id):
        grades = responses[response.question_id]
        items, teacher_rows = [], []
        for criterion in sorted(response.criteria, key=lambda item: item.criterion):
            grade = grades[criterion.criterion]
            passed = any(abs(grade["score"] - teacher) <= 1 for teacher in criterion.scores)
            criterion_failures += not passed
            items.append({**grade, "name": criterion.name, "within_tolerance": passed})
            teacher_rows.append(criterion.scores)
        scores = [grade["score"] for grade in items]
        teacher_columns = list(zip(*teacher_rows, strict=True))
        teacher_totals = [sum(column) for column in teacher_columns]
        low, high = min(teacher_totals), max(teacher_totals)
        total = sum(scores)
        passed = low <= total <= high
        total_failures += not passed
        reports.append({
            "question_id": response.question_id,
            "criteria": items,
            "total": total,
            "teacher_total_min": low,
            "teacher_total_max": high,
            "within_teacher_total_range": passed,
        })
        all_scores.extend(scores)
        all_teacher_rows.extend(teacher_rows)

    distance = sum(
        abs(score - teacher)
        for score, row in zip(all_scores, all_teacher_rows, strict=True)
        for teacher in row
    )
    mean_error = distance / (5 * len(all_scores))
    teacher_distance = sum(abs(a - b) for row in all_teacher_rows for a, b in combinations(row, 2))
    teacher_error = teacher_distance / (10 * len(all_scores))
    agreement = 1 - mean_error / 3
    valid = criterion_failures == total_failures == 0
    message = f"{selection.student_id} · {100 * agreement:.1f}/100 agreement across {len(reports)} responses"
    if not valid:
        message += f" · {criterion_failures} criterion and {total_failures} total checks failed"
    return result(
        valid,
        message,
        score=agreement,
        student_id=selection.student_id,
        agreement_score=round(100 * agreement, 2),
        mean_absolute_error=round(mean_error, 4),
        teacher_agreement_score=round(100 * (1 - teacher_error / 3), 2),
        criterion_failures=criterion_failures,
        total_failures=total_failures,
        responses=reports,
    )
