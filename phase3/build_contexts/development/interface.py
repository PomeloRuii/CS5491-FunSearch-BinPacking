"""AST-only handling of FunSearch priority functions; never executes candidate code."""
import ast
from dataclasses import dataclass
import re
import textwrap
from time import perf_counter

MAX_SOURCE_CHARS = 32768
PROMPT_ID = "funsearch-obp-concise-v2"


@dataclass(frozen=True)
class ParsedCandidate:
    function_name: str
    body: str
    parse_seconds: float


def expected_name(prompt):
    name = "priority_v" + str(prompt.version_generated)
    tree = ast.parse(prompt.code)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if not functions or functions[-1].name != name:
        raise ValueError("Database prompt version does not match its final function header.")
    return name


def messages_for(prompt):
    name = expected_name(prompt)
    system = (
        "You write numerical Python priority heuristics for the actual FunSearch "
        "online bin-packing specification. NumPy is already imported as np. "
        "For each arriving positive item, the packer filters residual capacities "
        "with valid_bin_indices = np.nonzero((bins - item) >= 0)[0], then calls "
        "priority(item, bins[valid_bin_indices]). Your function must return a "
        "one-dimensional NumPy score array of the same length and order as that "
        "filtered bins array. Unused empty bins are included among feasible bins. "
        "The packer chooses valid_bin_indices[np.argmax(scores)]; first maximum "
        "wins ties. Preserve this selection rule. Return scores, never a bin index, "
        "packing, or total bin count. The unchanged evaluator maximizes negative "
        "mean bins used. Use only item, bins, np and ordinary numerical Python. "
        "Do not mutate inputs, import modules, use randomness, call earlier versions, "
        "access files/network/processes, or produce helper functions. "
        "Output exactly one complete function with the requested name/signature. "
        "Write concise executable numerical code, at most 12 lines. "
        "Do not include comments, docstrings, reasoning, explanation or Markdown. "
        "End with the score-array return statement.")
    user = (
        prompt.code + "\n\n"
        "Complete the final version as exactly:\n"
        f"def {name}(item: float, bins: np.ndarray) -> np.ndarray:\n"
        "Return the complete function only.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_candidate(source, name, finish_reason="stop"):
    start = perf_counter()
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE_CHARS:
        raise ValueError("Candidate is empty, not text, or exceeds the source limit.")
    if finish_reason != "stop":
        raise ValueError("Candidate generation did not complete normally: " + str(finish_reason))
    code = source.strip()
    if code.startswith("~~~"):
        raise ValueError("Only raw Python or one Python backtick fence is supported.")
    if code.startswith("```"):
        match = re.fullmatch(r"```(?:python|py)?\s*\n([\s\S]*?)\n```", code)
        if not match:
            raise ValueError("Malformed or multiple code fences.")
        code = match.group(1)
    tree = ast.parse(code)
    if len(list(ast.walk(tree))) > 3000:
        raise ValueError("Candidate AST exceeds the size limit.")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Exactly one ordinary top-level function is required.")
    node = tree.body[0]
    if node.name != name or node.decorator_list:
        raise ValueError("Unexpected function name or decorators.")
    args = node.args
    if (args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs
            or args.defaults or args.kw_defaults or [a.arg for a in args.args] != ["item", "bins"]):
        raise ValueError("Required arguments are exactly (item, bins), with no defaults.")
    allowed_annotations = {"item": "float", "bins": "np.ndarray"}
    for arg in args.args:
        if arg.annotation is not None and ast.unparse(arg.annotation) != allowed_annotations[arg.arg]:
            raise ValueError("Unsupported or executable argument annotation.")
    if node.returns is not None and ast.unparse(node.returns) != "np.ndarray":
        raise ValueError("The return annotation must be np.ndarray.")
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.AsyncFunctionDef,
                 ast.Global, ast.Nonlocal, ast.Lambda, ast.Yield, ast.YieldFrom,
                 ast.Await, ast.With, ast.AsyncWith)
    bad_names = {"exec", "eval", "compile", "open", "__import__", "getattr", "setattr",
                 "globals", "locals", "vars", "os", "sys", "socket", "subprocess"}
    returns = []
    for child in ast.walk(node):
        if isinstance(child, forbidden) or (isinstance(child, ast.FunctionDef) and child is not node):
            raise ValueError("Unsupported statement or nested definition.")
        if isinstance(child, ast.Name):
            if child.id in bad_names or child.id.startswith("__"):
                raise ValueError("Unsupported capability name.")
            if child.id.startswith("priority_v") and child.id != name:
                raise ValueError("Unavailable ancestor function reference.")
        if isinstance(child, ast.Attribute) and child.attr.startswith("__"):
            raise ValueError("Dunder attribute access is unsupported.")
        if isinstance(child, ast.Return):
            returns.append(child)
            if child.value is None or isinstance(child.value, ast.Constant):
                raise ValueError("Return a score array, not a scalar literal.")
            if (isinstance(child.value, ast.Call) and isinstance(child.value.func, ast.Attribute)
                    and child.value.func.attr in ("argmax", "argmin")):
                raise ValueError("The packer performs bin selection; return scores.")
    if not returns:
        raise ValueError("No return statement found.")
    body = textwrap.indent(ast.unparse(ast.Module(body=node.body, type_ignores=[])), "    ")
    return ParsedCandidate(name, body, perf_counter() - start)
