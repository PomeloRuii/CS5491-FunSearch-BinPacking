"""Shared numerical AST policy v2. Local rebinding is not an array write.

NumPy 1.26 output-buffer positions/overwrite_input are refused as well as writes.
Static screening is not isolation, resource-bound, or runtime-validity proof.
"""
import ast
from interface import parse_candidate
from common import digest

NP_CALLS = frozenset('abs absolute add subtract multiply divide true_divide floor_divide power '
    'maximum minimum clip where log log1p log2 log10 exp expm1 sqrt square reciprocal '
    'sum mean std var min max median percentile quantile cumsum cumprod '
    'arange zeros_like ones_like full_like zeros ones full array asarray '
    'isfinite isnan isinf sign floor ceil round rint tanh sin cos argmin argmax '
    'sort argsort diff concatenate stack reshape dot'.split())
BUILTINS = frozenset(('len', 'float', 'int', 'abs', 'min', 'max', 'sum'))
NP_CONSTANTS = frozenset(('float64', 'float32', 'int64', 'int32', 'ndarray', 'pi', 'e', 'inf', 'nan'))
NODES = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.AnnAssign,
    ast.Return, ast.If, ast.IfExp, ast.Expr, ast.Constant, ast.Name, ast.Load, ast.Store,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call, ast.keyword, ast.Attribute,
    ast.Subscript, ast.Slice, ast.Tuple, ast.List, ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Not, ast.Invert, ast.And,
    ast.Or, ast.BitAnd, ast.BitOr, ast.BitXor, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.NotIn, ast.In)

POLICY_ID = 'phase3-numerical-ast-v2'
# Maximum positional inputs BEFORE an optional output buffer. Higher positions
# are refused even if they explicitly supply None; safe options can use keywords.
_UNARY = 'abs absolute log log1p log2 log10 exp expm1 sqrt square reciprocal isfinite isnan isinf sign floor ceil rint tanh sin cos'.split()
_BINARY = 'add subtract multiply divide true_divide floor_divide power maximum minimum'.split()
POSITIONAL_INPUT_LIMIT = {**dict.fromkeys(_UNARY, 1), **dict.fromkeys(_BINARY, 2),
    'clip': 3, 'round': 2, 'sum': 3, 'mean': 3, 'std': 3, 'var': 3,
    'min': 2, 'max': 2, 'median': 2, 'percentile': 3, 'quantile': 3,
    'cumsum': 3, 'cumprod': 3, 'argmin': 2, 'argmax': 2, 'dot': 2,
    'concatenate': 2, 'stack': 2}

def validate(source, name, finish_reason='stop'):
    parsed = parse_candidate(source, name, finish_reason)
    tree = ast.parse('def '+name+'(item, bins):\n'+parsed.body)
    function = tree.body[0]
    locals_ = {'item', 'bins', 'np'}
    operations = set()
    for node in ast.walk(function):
        if not isinstance(node, NODES):
            raise ValueError('Numerical allowlist rejects '+type(node).__name__)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name) or target.id == 'np' or target.id.startswith('_'):
                    raise ValueError('Only ordinary name rebinding is allowed; writes and np rebinding refused')
                locals_.add(target.id)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BUILTINS:
                operations.add(node.func.id)
            elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == 'np' and node.func.attr in NP_CALLS):
                operations.add('np.'+node.func.attr)
                limit = POSITIONAL_INPUT_LIMIT.get(node.func.attr)
                if limit is not None and len(node.args) > limit:
                    raise ValueError('Positional output buffers/overwrite options are refused: np.'+node.func.attr)
            else:
                raise ValueError('Only allowlisted direct numerical calls are supported')
            if any(k.arg is None or k.arg in ('out', 'overwrite_input') for k in node.keywords):
                raise ValueError('Expanded kwargs, output buffers and overwrite_input are refused')
        if isinstance(node, ast.Attribute):
            if not (isinstance(node.value, ast.Name) and node.value.id == 'np'
                    and node.attr in NP_CALLS | NP_CONSTANTS):
                raise ValueError('Object methods and non-numerical attributes are refused')
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id not in locals_ | BUILTINS:
            raise ValueError('Unknown external name: '+node.id)
    return parsed, {'policy': POLICY_ID, 'status': 'PASS',
                    'operations': sorted(operations), 'body_sha256': digest(parsed.body),
                    'risk': 'bounded numerical source; allocation/CPU/numerical and Docker residual risks remain'}

