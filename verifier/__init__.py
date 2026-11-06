"""NanoAgent's deterministic grading verification entry points."""

from contract import Task, Tool

from . import grading


def verify_input(tool, value):
    return grading.verify_input(Tool(tool).value, value)


def verify_output(tool, input_value, output_value, workspace):
    return grading.verify_output(Tool(tool).value, input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    if Task(task) is Task.LIST_GRADING_DATA:
        return grading.verify_output(Tool.LIST_GRADING_DATA.value, arguments, output, workspace)
    return grading.verify_task(arguments, output, reference, workspace)
