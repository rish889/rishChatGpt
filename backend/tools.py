import ast
import operator
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information (news, facts, anything that "
                "might have changed since training) and return a handful of relevant "
                "results with snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate an arithmetic expression (+, -, *, /, //, %, **, parentheses) "
                "and return the numeric result. Use this instead of computing nontrivial "
                "math yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "e.g. '(3 + 4) * 2 / 7'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


def web_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return "Web search is not configured (missing TAVILY_API_KEY)."

    try:
        res = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": 5,
                "include_answer": False,
            },
            timeout=15,
        )
        res.raise_for_status()
    except httpx.HTTPError as e:
        return f"Web search failed: {e}"

    results = res.json().get("results", [])
    if not results:
        return "No results found."

    return "\n\n".join(f"{r['title']}\n{r['url']}\n{r['content']}" for r in results)


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression near {ast.dump(node)}")


def calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as e:
        return f"Error evaluating expression: {e}"
    return str(result)


TOOL_FUNCTIONS = {
    "web_search": web_search,
    "calculate": calculate,
}


def call_tool(name: str, arguments: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}"
    try:
        return func(**arguments)
    except TypeError as e:
        return f"Invalid arguments for {name}: {e}"
