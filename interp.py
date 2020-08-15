from model import *

# Top level function that interprets an entire program. It creates the
# initial environment that's used for storing variables.

def interpret_program(model):
    # Make the initial environment (a dict)
    env = [{}]
    interpret(model, env)


# Internal function to interpret a node in the environment
@singledispatch
def interpret(node, env):
    raise RuntimeError(f"Can't interpret {node}")

eval_literals = {
        Float: float,
        Integer: int}

type_to_literal = {
        'float': Float,
        'int': Integer,
        'char': Char}

eval_binops = {
        '>': lambda x, y: x > y,
        '<': lambda x, y: x < y,
        '<=': lambda x, y: x <= y,
        '>=': lambda x, y: x >= y,
        '==': lambda x, y: x == y,
        '+': lambda x, y: x + y,
        '-': lambda x, y: x - y,
        '*': lambda x, y: x * y,
        '/': lambda x, y: x / y
        }

@interpret.register(Literal)
def _(node, env):
    if node.value is None:
        return node
    return eval_literals[type(node)](node.value)

@interpret.register(BinOp)
def _(node, env):
    return eval_binops[node.op](interpret(node.left, env), interpret(node.right, env))

@interpret.register(Body)
def _(node, env):
    for statement in node.statements:
        res = interpret(statement, env)
    return res

@interpret.register(Print)
def _(node, env):
    return print(interpret(node.value, env))

@interpret.register(VarDecl)
def _(node, env):
    env[-1][node.name] = interpret(node.value, env)

@interpret.register(ConstAssign)
def _(node, env):
    if node.name in env[-1]:
        raise NameError(f"Const {node} already assigned")
    env[-1][node.name] = interpret(node.value, env)

@interpret.register(VarAssign)
def _(node, env):
    if node.name in env[-1]:
        env[-1][node.name] = interpret(node.value, env)
        return
    raise NameError(f"Node {node} not initialized")

@interpret.register(Ref)
def _(node, env):
    for ev in env[::-1]:
        if node.name in ev:
            return ev[node.name]
    raise NameError(f"Node {node} not initialized")

@interpret.register(If)
def _(node, env):
    if interpret(node.cond, env):
        interpret(node.body, env)
    elif node.cdr is not None:
        interpret(node.cdr, env)

@interpret.register(While)
def _(node, env):
    while interpret(node.cond, env):
        interpret(node.body, env)

@interpret.register(CompoundExpression)
def _(node, env):
    env_inner = {}
    for e in env:
        for k, v in e.items():
            env_inner[k] = v
    return interpret(node.body, [env_inner])

@interpret.register(Func)
def _(node, env):
    def f(env, *binds):
        for arg, bind in zip(node.args, binds):
            env[-1][arg.name] = bind
        try:
            return interpret(node.body, env)
        except ReturnValue as r:
            return r.args[0]
    env[-1][node.name] = f

@interpret.register(Prog)
def _(node, env=[{}]):
    for statement in node.statements:
        interpret(statement, env)
    if 'main' in env[-1]:
        return interpret(Call('main'), env)

@interpret.register(Call)
def _(node, env):
    for e in env[::-1]:
        if node.name in e:
            return e[node.name](env + [{}], *(interpret(arg, env) for arg in node.args))
    raise NameError(f"Function {node} not declared")

class ReturnValue(Exception):
    pass

@interpret.register(Return)
def _(node, env):
    raise ReturnValue(interpret(node.value, env))

@interpret.register(Struct)
def _(node, env):
    raise NotImplemented
