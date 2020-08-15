from functools import singledispatch

class Node:
    pass

class Literal(Node):
    type_name = None
    pass

class Struct(Node):
    def __init__(self, name, *decs):
        self.name = name
        self.decs = decs

    def __repr__(self):
        return f'Struct({self.name}, {self.decs})'

class Func(Node):
    def __init__(self, name, body, *args, type_name=None):
        self.name = name
        self.args = args
        self.body = body
        self.type_name = type_name
    def __repr__(self):
        return f'Func({self.name}, {self.args}, {self.body}, type_name={self.type_name})'

class Call(Node):
    def __init__(self, name, *args):
        self.name = name
        self.args = args
    def __repr__(self):
        return f'Call({self.name}, {self.args})'

class Return(Node):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f'Return({self.value})'

class CompoundExpression(Node):
    def __init__(self, body):
        self.body = body
    def __repr__(self):
        return f'CompoundExpression({self.cond}, {self.body})'

class If(Node):
    def __init__(self, cond, body, cdr=None):
        self.cond = cond
        self.body = body
        self.cdr = cdr
    def __repr__(self):
        return f'If({self.cond}, {self.body}, cdr={self.cdr})'

class While(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

    def __repr__(self):
        return f'While({self.cond}, {self.body})'

class Ref(Node):
    def __init__(self, name, attr=None):
        if attr is not None:
            name += attr
        self.name = name
    def __repr__(self):
        return f'Ref({self.name})'

class VarAssign(Node):
    '''
    Example: pi = 3.14
    '''
    def __init__(self, name, value):
        self.name = name
        self.value = value
    
    def __repr__(self):
        return f'VarAssign({self.name}, {self.value})'

class ConstAssign(Node):
    '''
    Example: const pi = 3.14
    '''
    def __init__(self, name, value, type_name=None):
        self.name = name
        self.value = value
        self.type_name = type_name
    
    def __repr__(self):
        return f'ConstAssign({self.name}, {self.value}, type_name={self.type_name})'

class VarDecl(Node):
    '''
    Example: var x float
    '''
    def __init__(self, name, type_name, value=None):
        self.name = name
        self.type_name = type_name
        self.value = value
    
    def __repr__(self):
        return f'VarDecl({self.name}, type_name={self.type_name}, value={self.value})'

class Float(Literal):
    '''
    Example: 42.0
    '''
    type_name = 'float'
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Float({self.value})'

class Char(Literal):
    '''
    Example: 'H'
    '''
    type_name = 'char'
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Char({self.value})'


class Integer(Literal):
    '''
    Example: 42
    '''
    type_name = 'int'
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Integer({self.value})'

class BinOp(Node):
    '''
    Example: left + right
    '''
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def __repr__(self):
        return f'BinOp({self.op}, {self.left}, {self.right})'


class Body(Node):
    '''
    Example: statement; statement;
    '''
    def __init__(self, *statements):
        self.statements = statements

    def __repr__(self):
        return f'Body{tuple(statement for statement in self.statements)};'

class Prog(Body):
    pass

class Print(Node):
    '''
    Example: print stuff
    '''
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Print({self.value})'

# ------ Debugging function to convert a model into source code (for easier viewing)

NEWLINE = '\n'
INDENT = '    '
@singledispatch
def to_source(node, indent=0):
    raise RuntimeError(f"Can't convert {node} to source")

@to_source.register(Literal)
def _(node, indent=0):
    return indent * INDENT + repr(node.value)

@to_source.register(BinOp)
def _(node, indent=0):
    return indent * INDENT + f'{to_source(node.left)} {node.op} {to_source(node.right)}'

@to_source.register(Body)
def _(node, indent=0):
    return '\n'.join(f'{to_source(statement, indent + 1)};' for statement in node.statements)

@to_source.register(Print)
def _(node, indent=0):
    return indent * INDENT + f'print {to_source(node.value)}'

@to_source.register(VarDecl)
def _(node, indent=0):
    ret = f'var {node.name} {node.type_name}'
    if node.value is not None:
        ret += f' = {to_source(node.value)}'
    return indent * INDENT + ret

@to_source.register(ConstAssign)
def _(node, indent=0):
    return indent * INDENT + f'const {node.name} = {to_source(node.value)}'

@to_source.register(VarAssign)
def _(node, indent=0):
    return indent * INDENT + f'{node.name} = {to_source(node.value)}'

@to_source.register(Ref)
def _(node, indent=0):
    return indent * INDENT + f'{node.name}' + ('' if node.attr is None else f'.{node.attr}')

@to_source.register(If)
def _(node, indent=0):
    ret = f'''if {to_source(node.cond, 0)} {{
{to_source(node.body, indent)}
{indent * INDENT}}}'''
    if node.cdr is not None:
        ret += f'''
{indent * INDENT}else {{
{to_source(node.cdr, indent)}
{indent * INDENT}}}'''
        return indent * INDENT + ret

@to_source.register(While)
def _(node, indent=0):
    return f'''{indent * INDENT}while {to_source(node.cond, 0)} {{
{to_source(node.body, indent)}
{indent * INDENT}}}'''

@to_source.register(CompoundExpression)
def _(node, indent=0):
    return indent * INDENT + '{ ' + to_source(node.body) + ' }'

@to_source.register(Func)
def _(node, indent=0):
    return indent * INDENT + f'''func {node.name}({', '.join(map(to_source, node.args))}) {node.type_name} {{
{to_source(node.body, indent)}
{indent * INDENT}}}'''

@to_source.register(Return)
def _(node, indent=0):
    return indent * INDENT + f'return {to_source(node.value)}'

@to_source.register(Call)
def _(node, indent=0):
    return indent * INDENT + f'{node.name}({", ".join(map(to_source, node.args))})'

@to_source.register(Struct)
def _(node, indent=0):
    return indent * INDENT + f'''struct {node.name} {{
{(NEWLINE).join(map(lambda x: indent * INDENT + to_source(x, indent), node.decs))}
}}'''
