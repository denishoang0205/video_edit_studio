import ast
import operator
from typing import Any
from src.crewai_core.domain.interfaces.tool import ITool, ToolResult


class CalculatorTool(ITool):
    """Safe Math Expression Evaluator Tool."""

    name: str = "calculator"
    description: str = "Performs mathematical evaluations on numeric expressions (e.g. '15 * 40 + 200')."
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "The math expression to evaluate."}
        },
        "required": ["expression"]
    }

    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _eval(self, node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return self._operators[type(node.op)](self._eval(node.left), self._eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return self._operators[type(node.op)](self._eval(node.operand))
        else:
            raise TypeError(f"Unsupported syntax in math expression: {type(node)}")

    async def run(self, **kwargs: Any) -> ToolResult:
        expression = kwargs.get("expression", "")
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval(tree.body)
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Invalid calculation expression: {str(e)}")
