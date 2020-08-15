from typecheck import check_program, get_var
from parse import parse_source
from llvmlite import ir
from model import *

# Define LLVM types corresponding to Wabbit types
llvm_type = {
'int': ir.IntType(32),
'float': ir.DoubleType(),
'bool': ir.IntType(1),
'char': ir.IntType(8)}

binop_lookup = {
        'int':
        {
            '+': 'add',
            '-': 'sub',
            '*': 'mul',
            '/': 'sdiv'},
        'float':
        {
            '+': 'fadd',
            '-': 'fsub',
            '*': 'fmul',
            '/': 'fdiv'}
        }

# The LLVM world that Wabbit is populating
class WabbitLLVMModule:
    def __init__(self, init=True):
        if not init:
            return
        self.mod = ir.Module('Wabbit')

    def get_func(self, name, type_name, *args):
        self.func = ir.Function(self.mod, ir.FunctionType(llvm_type[type_name], args), name=name)
        self.block = self.func.append_basic_block('entry')
        self.builder = ir.IRBuilder(self.block)

# Top-level function
def generate_program(model):
    mod = WabbitLLVMModule()
    generate(model, mod, [{}])
    return mod

# Internal function to to generate code for each node type
@singledispatch
def generate(node, mod, env):
    raise RuntimeError(f"Can't generate code for {node}")

@generate.register(Prog)
def _(node, mod, env):
    for statement in node.statements:
        generate(statement, mod, env)

@generate.register(Body)
def _(node, mod, env):
    for child in node.statements:
        generate(child, mod, env)

@generate.register(BinOp)
def _(node, mod, env):
    left = generate(node.left, mod, env)
    right = generate(node.right, mod, env)
    # Allocate the result variable
    type_name = node.type_name
    if type_name in binop_lookup:
        if node.op in binop_lookup[type_name]:
            return getattr(mod.builder, binop_lookup[type_name][node.op])(left, right)
        else:
            raise NotImplemented(node)
    if node.type_name in ('int', 'bool'):
        return mod.builder.icmp_signed(node.op, left, right)
    # fcmp isn't a thing...
    return mod.builder.fcmp(node.op, left, right)

@generate.register(Literal)
def _(node, mod, env):
    return llvm_type[node.type_name](node.value)

@generate.register(ConstAssign)
def _(node, mod, env):
    env[-1][node.name] = generate(node.value, mod, env)

@generate.register(VarDecl)
def _(node, mod, env):
    env[-1][node.name] = mod.builder.alloca(
                llvm_type[node.type_name],
                name=node.name)
    if node.value is not None:
        assignment = VarAssign(node.name, node.value)
        generate(assignment, mod, env)

@generate.register(VarAssign)
def _(node, mod, env):
    var = get_var(node.name, env)
    val = generate(node.value, mod, env)
    mod.builder.store(val, var)

def load(var, mod):
    if isinstance(var, ir.instructions.AllocaInstr):
        var = mod.builder.load(var)
    return var

@generate.register(Ref)
def _(node, mod, env):
    var = get_var(node.name, env)
    return load(var, mod)

def process_if(node, mod, env):
    # Perform the comparison
    testvar = generate(node.cond, mod, env)

    # Make two blocks
    then_block = mod.func.append_basic_block('then')
    merge_block = mod.func.append_basic_block('merge')

    # Perform the comparison
    testvar = generate(node.cond, mod, env)

    # Emit the branch instruction
    mod.builder.cbranch(testvar, then_block, merge_block)

    # Generate code in the then-branch
    mod.builder.position_at_end(then_block)
    generate(node.body, mod, env)
    mod.builder.branch(merge_block)

    mod.builder.position_at_end(merge_block)


def process_if_else(node, mod, env):
    # Perform the comparison
    testvar = generate(node.cond, mod, env)

    # Make three blocks
    then_block = mod.func.append_basic_block('then')
    else_block = mod.func.append_basic_block('else')
    merge_block = mod.func.append_basic_block('merge')

    # Emit the branch instruction
    mod.builder.cbranch(testvar, then_block, else_block)

    # Generate code in the then-branch
    mod.builder.position_at_end(then_block)
    generate(node.body, mod, env)
    mod.builder.branch(merge_block)

    # Generate code in the else-branch
    mod.builder.position_at_end(else_block)
    generate(node.cdr, mod, env)
    mod.builder.branch(merge_block)

    mod.builder.position_at_end(merge_block)

@generate.register(If)
def _(node, mod, env):
    if node.cdr is None:
        return process_if(node, mod, env)
    process_if_else(node, mod, env)

@generate.register(While)
def _(node, mod, env):
    # Make a new basic-block for the loop test
    while_block = mod.func.append_basic_block('while')
    mod.builder.branch(while_block)
    mod.builder.position_at_end(while_block)

    # Perform the comparison
    testvar = generate(node.cond, mod, env)

    # Make two blocks
    then_block = mod.func.append_basic_block('then')
    break_block = mod.func.append_basic_block('break')

    mod.builder.cbranch(testvar, then_block, break_block)

    mod.builder.position_at_end(then_block)
    generate(node.body, mod, env)
    mod.builder.branch(while_block)
    mod.builder.position_at_end(break_block)

@generate.register(Return)
def _(node, mod, env):
    print(node)
    mod.builder.store(generate(node.value, mod, env), mod.ret)

@generate.register(Func)
def _(node, mod, env):
    new = WabbitLLVMModule(init=False)
    new.mod = mod.mod
    args = tuple(llvm_type[arg.type_name] for arg in node.args)
    new.get_func(node.name, node.type_name, *args)
    new.ret = new.builder.alloca(llvm_type[node.type_name])
    env[-1][node.name] = node
    env = env + [{}]
    for vardecl, arg in zip(node.args, new.func.args):
        env[-1][vardecl.name] = new.builder.alloca(llvm_type[vardecl.type_name])
        new.builder.store(new.func.args[0], env[-1][vardecl.name])
    env[-2][node.name] = node
    node.env = env
    node.mod = new
    generate(node.body, new, env)
    new.builder.ret(load(new.ret, new))

@generate.register(Call)
def _(node, mod, env):
    func_node = get_var(node.name, env)
    args = list(generate(arg, mod, env) for arg in node.args)
    var = mod.builder.alloca(llvm_type[node.type_name])
    mod.builder.store(
            mod.builder.call(func_node.mod.func, args),
            var)
    return load(var, mod)

# Sample main program that runs the compiler
def main(text):

    model = parse_source(text)
    print(model)
    env = check_program(model)
    biop = model.statements[0].body.statements[0].cond
    # print(biop, biop.type_name)
    mod = generate_program(model)
    with open('out.ll', 'w') as file:
        file.write(str(mod.mod))
    print('Wrote out.ll')
    return mod.mod

if __name__ == '__main__':
    text = '''
    func llvm(x int) int {
    if x > 1 {
        return x * llvm(x - 1);
    }
    else {
        return 1;
    }
}
'''
    code = main(text)
    print(code)
