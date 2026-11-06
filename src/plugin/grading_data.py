"""Read the bundled workbook's fixed layout, including the five evaluator columns per criterion."""

from functools import cache
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from contract import GradingQuestion, RubricCriterion, TeacherCriterion, TeacherResponse

WORKBOOK = Path(__file__).with_name("dataset") / "ALL 12 Ques scores 5 Evaluators 5 students.xlsx"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
# Excel columns after Z carry the A prefix.
EVALUATOR_COLUMNS = (
    tuple("MNOPQ"),
    tuple("RSTUV"),
    ("W", "X", "Y", "Z", "AA"),
    ("AB", "AC", "AD", "AE", "AF"),
    ("AG", "AH", "AI", "AJ", "AK"),
)


def sheet_cells(book, number, shared_strings):
    sheet = ElementTree.fromstring(book.read(f"xl/worksheets/sheet{number}.xml"))
    cells = {}
    for cell in sheet.findall("s:sheetData/s:row/s:c", NS):
        value = cell.findtext("s:v", namespaces=NS)
        if value is not None:
            cells[cell.attrib["r"]] = shared_strings[int(value)] if cell.get("t") == "s" else value
    return cells


@cache
def workbook_data():
    questions, teachers = {}, {}
    with ZipFile(WORKBOOK) as book:
        table = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in item.findall(".//s:t", NS)) for item in table]
        for number in range(1, 13):
            cells = sheet_cells(book, number, strings)
            qid = f"NQ{number:03}"
            if cells["A3"] != qid:
                raise ValueError(f"Unexpected workbook question ID on sheet {number}")
            rubric = [
                RubricCriterion(i, cells[f"{column}3"], *(cells[f"{column}{row}"] for row in (7, 6, 5, 4)))
                for i, column in enumerate("EFGHI", 1)
            ]
            for student in range(1, 6):
                row = student + 2
                key = (f"S{student}", qid)
                if cells[f"K{row}"] != f"{qid}_R{student}":
                    raise ValueError(f"Unexpected workbook response ID for {key}")
                questions[key] = GradingQuestion(qid, cells["B3"], cells["J3"], cells[f"L{row}"], rubric)
                teachers[key] = TeacherResponse(qid, [
                    TeacherCriterion(criterion.criterion, criterion.name, [int(cells[f"{c}{row}"]) for c in columns])
                    for criterion, columns in zip(rubric, EVALUATOR_COLUMNS, strict=True)
                ])
    return questions, teachers
