"""
agent.py — Core Agentic AI loop using the modern google-genai SDK.

Follows a ReAct (Reason + Act) pattern:
  1. Receive a user task.
  2. Ask Gemini what to do next (reason).
  3. If Gemini calls a tool, execute it (act) and feed the result back.
  4. Repeat until Gemini produces a final text answer.

Yields SSE-compatible dicts so Flask can stream them to the browser.
"""

from __future__ import annotations

import json
from typing import Generator

from google import genai
from google.genai import types

from tools import TOOLS, TOOL_DECLARATIONS

MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are an advanced Agentic AI assistant. You can plan, reason, and use tools to complete complex tasks autonomously.

Available tools:
- web_search: Search the internet for current information
- calculator: Evaluate mathematical expressions
- wikipedia_search: Look up factual information from Wikipedia
- get_datetime: Get the current date and time
- run_python: Execute Python code snippets

Guidelines:
1. Break complex tasks into steps. Use multiple tool calls when needed.
2. Always verify facts using tools rather than relying on training data.
3. Show your reasoning clearly before taking actions.
4. Synthesize all gathered information into a clear, helpful final answer.
5. If a task requires multiple steps, complete all of them before finishing.
"""


def _build_tools() -> list[types.Tool]:
    """Convert our TOOL_DECLARATIONS into google-genai Tool objects."""
    function_declarations = []
    for td in TOOL_DECLARATIONS:
        function_declarations.append(
            types.FunctionDeclaration(
                name=td["name"],
                description=td["description"],
                parameters=td["parameters"],
            )
        )
    return [types.Tool(function_declarations=function_declarations)]


def run_agent(task: str, api_key: str) -> Generator[dict, None, None]:
    """
    Run the agentic loop and yield step events as dicts:
      {"type": "thought",     "content": "..."}
      {"type": "tool_call",   "tool": "...", "args": {...}}
      {"type": "tool_result", "tool": "...", "content": "..."}
      {"type": "answer",      "content": "..."}
      {"type": "error",       "content": "..."}
    """
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        yield {"type": "error", "content": f"Gemini client initialization failed: {e}"}
        return

    tools = _build_tools()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=tools,
        temperature=0.2,
    )

    yield {"type": "thought", "content": f"🎯 **Task received:** {task}\n\nPlanning approach..."}

    # Build initial message history
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=task)])
    ]

    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=contents,
                config=config,
            )
        except Exception as e:
            yield {"type": "error", "content": f"Gemini API error: {e}"}
            return

        candidate = response.candidates[0]
        parts = candidate.content.parts

        text_parts = []
        function_calls = []

        for part in parts:
            if part.text:
                text_parts.append(part.text.strip())
            if part.function_call:
                function_calls.append(part.function_call)

        # Emit reasoning text
        if text_parts:
            combined = "\n\n".join(t for t in text_parts if t)
            if combined:
                yield {"type": "thought", "content": combined}

        # No tool calls → final answer
        if not function_calls:
            final = "\n\n".join(text_parts) if text_parts else "Task complete."
            contents.append(types.Content(role="model", parts=parts))
            yield {"type": "answer", "content": final}
            return

        # Add model's response to history
        contents.append(types.Content(role="model", parts=parts))

        # Execute each tool and collect results
        tool_result_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            yield {"type": "tool_call", "tool": tool_name, "args": tool_args}

            tool_fn = TOOLS.get(tool_name)
            if tool_fn is None:
                tool_result = f"Error: Tool '{tool_name}' not found."
            else:
                try:
                    tool_result = tool_fn(**tool_args)
                except Exception as e:
                    tool_result = f"Tool execution error: {e}"

            yield {"type": "tool_result", "tool": tool_name, "content": str(tool_result)}

            tool_result_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": str(tool_result)},
                    )
                )
            )

        # Add tool results back into the conversation
        contents.append(types.Content(role="user", parts=tool_result_parts))

    yield {
        "type": "error",
        "content": f"Agent reached the maximum of {MAX_ITERATIONS} iterations without a final answer.",
    }
