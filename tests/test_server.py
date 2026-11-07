import os
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_structured_tools(tmp_path):
    root = Path(__file__).resolve().parents[1]

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "plugin"],
            cwd=root,
            env={**os.environ, "NANOAGENT_WORKSPACE": str(tmp_path), "PYTHONPATH": str(root / "src")},
        )
        async with stdio_client(params) as streams, ClientSession(*streams) as session:
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert set(tools) == {"list_grading_data", "get_grading_question", "record_grades", "pin_teacher_scores"}
            schema = tools["get_grading_question"].inputSchema
            assert schema["properties"]["student_id"]["type"] == "string"
            assert schema["properties"]["question_ids"]["type"] == "array"
            assert not schema["additionalProperties"]
            catalog = await session.call_tool("list_grading_data", {})
            assert not catalog.isError
            assert len(catalog.structuredContent["questions"]) == 12
            selection = {"student_id": "S1", "question_ids": ["NQ001"]}
            batch = await session.call_tool("get_grading_question", selection)
            assert not batch.isError
            question = batch.structuredContent["questions"][0]
            assert set(question) == {"question_id", "prompt", "model_answer", "student_answer", "rubric"}
            assert set(question["rubric"][0]) == {"criterion", "name", "level_1", "level_2", "level_3", "level_4"}
            assert (await session.call_tool("get_grading_question", {**selection, "student_id": ["S1", "S2"]})).isError
            assert (await session.call_tool("get_grading_question", {**selection, "student_id": "S6"})).isError
            for question_ids in ([], ["NQ001", "NQ002"]):
                rejected = await session.call_tool("get_grading_question", {**selection, "question_ids": question_ids})
                assert rejected.isError
            receipt = await session.call_tool(
                "record_grades",
                {
                    "selection": selection,
                    "responses": [
                        {
                            "question_id": "NQ001",
                            "grades": [
                                {"criterion": i, "score": 3, "justification": "Evidence in the answer"}
                                for i in range(1, 6)
                            ],
                        }
                    ],
                },
            )
            assert not receipt.isError
            assert receipt.structuredContent["totals"] == [{"question_id": "NQ001", "total": 15}]

    anyio.run(run)
