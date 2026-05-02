"""
tools.py — Tool implementations for the Agentic AI.

Each tool is a plain Python function. The agent calls these
based on Gemini's function-calling decisions.
"""

import datetime
import math
import re
import textwrap
import urllib.parse

import requests


# ─────────────────────────── WEB SEARCH ────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo Instant Answer API (no key required).
    Falls back to DuckDuckGo HTML scraping summary.
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"• **{r['title']}**\n  {r['body']}\n  URL: {r['href']}")
        if results:
            return "\n\n".join(results)
        return "No results found."
    except Exception as e:
        return f"Web search failed: {e}"


# ─────────────────────────── CALCULATOR ────────────────────────────────────

def calculator(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.
    Supports standard math operations and functions.
    """
    # Whitelist of safe names
    safe_names = {
        k: v for k, v in math.__dict__.items() if not k.startswith("_")
    }
    safe_names.update({"abs": abs, "round": round, "min": min, "max": max})
    try:
        # Strip anything that isn't math-safe
        sanitized = re.sub(r"[^0-9+\-*/().,%^ a-zA-Z_]", "", expression)
        result = eval(sanitized, {"__builtins__": {}}, safe_names)  # noqa: S307
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation error: {e}"


# ────────────────────────── WIKIPEDIA LOOKUP ────────────────────────────────

def wikipedia_search(topic: str) -> str:
    """
    Fetch the introductory summary of a Wikipedia article.
    """
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(topic)
        resp = requests.get(url, timeout=8, headers={"User-Agent": "AgenticAI/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            title = data.get("title", topic)
            extract = data.get("extract", "No summary available.")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            return f"**{title}**\n\n{extract}\n\nSource: {page_url}"
        elif resp.status_code == 404:
            return f"Wikipedia article not found for: '{topic}'"
        else:
            return f"Wikipedia returned status {resp.status_code}"
    except Exception as e:
        return f"Wikipedia lookup failed: {e}"


# ────────────────────────── DATE & TIME ────────────────────────────────────

def get_datetime() -> str:
    """Return the current date and time."""
    now = datetime.datetime.now()
    return (
        f"Current date: {now.strftime('%A, %B %d, %Y')}\n"
        f"Current time: {now.strftime('%I:%M %p')}\n"
        f"Timezone: Local system time"
    )


# ────────────────────────── CODE EXECUTION ─────────────────────────────────

def run_python(code: str) -> str:
    """
    Execute a small Python snippet in a restricted sandbox and return output.
    Only safe builtins are available — no file I/O, no network, no imports
    beyond math, datetime, and json.
    """
    import io
    import contextlib
    import json as _json

    allowed_globals = {
        "__builtins__": {
            "print": print,
            "range": range,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "sorted": sorted,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "isinstance": isinstance,
            "type": type,
        },
        "math": math,
        "datetime": datetime,
        "json": _json,
    }

    output_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_buf):
            exec(textwrap.dedent(code), allowed_globals)  # noqa: S102
        output = output_buf.getvalue().strip()
        return output if output else "(No output produced)"
    except Exception as e:
        return f"Execution error: {type(e).__name__}: {e}"


# ────────────────────────── TOOL REGISTRY ──────────────────────────────────

TOOLS = {
    "web_search": web_search,
    "calculator": calculator,
    "wikipedia_search": wikipedia_search,
    "get_datetime": get_datetime,
    "run_python": run_python,
}

# Gemini function declarations
TOOL_DECLARATIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the internet for current information, news, facts, or any topic. "
            "Use this when you need up-to-date or external information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculator",
        "description": (
            "Evaluate a mathematical expression. Supports arithmetic, algebra, "
            "trigonometry (via math module), and basic statistics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate, e.g. '2 ** 10 + sqrt(144)'.",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "wikipedia_search",
        "description": (
            "Fetch a factual summary from Wikipedia about a topic, person, place, concept, or event."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The Wikipedia topic or article title to search for.",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time. Use this when the user asks what time or date it is.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Execute a Python code snippet and return its output. "
            "Useful for calculations, data transformations, sorting, or generating structured content. "
            "Sandbox: only math, datetime, json and basic builtins are available. No I/O or network."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute. Use print() to produce output.",
                },
            },
            "required": ["code"],
        },
    },
]
