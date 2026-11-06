import { disclosure, h } from "./kit/components.js";

function gradingReport({ details } = {}) {
  if (!details?.responses) return h("p", { text: "No verified grades are available." });
  return h(
    "div",
    { class: "grading-report" },
    h("p", {}, h("strong", { text: `${details.student_id} · Agreement with teachers ${details.agreement_score}/100` })),
    h("p", { text: `Teacher-to-teacher agreement ${details.teacher_agreement_score}/100 · Average difference ${details.mean_absolute_error} rubric points` }),
    h("p", { text: `${details.criterion_failures} criterion checks failed · ${details.total_failures} total checks failed` }),
    ...details.responses.map((response) =>
      disclosure(
        { summary: `${response.question_id} · ${response.total}/20`, open: !response.within_teacher_total_range },
        h("p", { text: `Teacher total range ${response.teacher_total_min}–${response.teacher_total_max}${response.within_teacher_total_range ? "" : " · Outside range"}` }),
        h("ul", {}, response.criteria.map((grade) =>
          h("li", {},
            h("strong", { text: `${grade.name} · ${grade.score}/4${grade.within_tolerance ? "" : " · Outside tolerance"}` }),
            h("p", { text: grade.justification }),
          ),
        )),
      ),
    ),
  );
}

export default {
  GradeSubmissionOutput: (_output, { verdict }) => gradingReport(verdict),
};
