import triton
import triton.language as tl
from triton._filecheck import filecheck_test, run_filecheck_test

# ===-----------------------------------------------------------------------===#
# Unit Tests
# ===-----------------------------------------------------------------------===#


@triton.jit
def anchor(v):
    pass


@tl.aggregate
class Pair:
    first: tl.tensor
    second: tl.tensor

    @tl.core.builtin
    def __init__(self, first, second, _semantic=None):
        self.first = first
        self.second = second

    def get_first(self):
        return self.first

    @tl.core.builtin
    def get_second(self, _semantic=None):
        return self.second

    def unpack(self):
        return self.get_first(), self.get_second()

    def mutate_first(self, value):
        self.first = value

    def mutate_second(self, value):
        self.second = value


@filecheck_test
@triton.jit
def test_assign_attribute():
    # CHECK-LABEL: assign_attribute
    # CHECK: %c11_i32 = arith.constant 11 : i32
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    scalar = 11
    pair = Pair(tl.arange(0, 4), scalar)
    # CHECK: %c42_i32 = arith.constant 42 : i32
    # CHECK-NEXT: call @{{.*}}anchor{{.*}}([[RANGE]], %c42_i32)
    pair.second = 42
    anchor(pair)


@filecheck_test
@triton.jit
def test_augassign_attribute():
    # CHECK-LABEL: test_augassign_attribute
    # CHECK: %c11_i32 = arith.constant 11 : i32
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    scalar = 11
    pair = Pair(tl.arange(0, 4), scalar)
    # CHECK: %c42_i32 = arith.constant 42 : i32
    # CHECK: [[VALUE:%.*]] = arith.addi %c11_i32, %c42_i32
    pair.second += 42
    # CHECK-NEXT: call @{{.*}}anchor{{.*}}([[RANGE]], [[VALUE]])
    anchor(pair)


@filecheck_test
@triton.jit
def test_jit_method():
    # CHECK-LABEL: test_jit_method
    # CHECK: %c11_i32 = arith.constant 11 : i32
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    scalar = 11
    # CHECK: [[V:%.*]]:4 = tt.call @{{.*}}unpack{{.*}}([[RANGE]], %c11_i32)
    pair = Pair(tl.arange(0, 4), scalar)
    a, b = pair.unpack()
    # CHECK: call @{{.*}}anchor{{.*}}([[V]]#0)
    anchor(a)
    # CHECK: call @{{.*}}anchor{{.*}}([[V]]#1)
    anchor(b)


@tl.aggregate
class TypeWithBuiltinInitializer:
    value: tl.tensor

    @tl.core.builtin
    def __init__(self, _semantic=None):
        self.value = tl.arange(0, 4, _semantic=_semantic)

    @tl.core.builtin
    def modify(self, value, _semantic=None):
        self.value = value


@filecheck_test
@triton.jit
def test_aggregate_initializers():
    # CHECK-LABEL: test_aggregate_initializers
    value = TypeWithBuiltinInitializer()
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    # CHECK: call @{{.*}}anchor{{.*}}([[RANGE]])
    anchor(value)
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 8 : i32, start = 4 : i32}
    # CHECK: call @{{.*}}anchor{{.*}}([[RANGE]])
    value.modify(tl.arange(4, 8))
    anchor(value)


@filecheck_test
@triton.jit
def test_aggregate_modification_in_for_loop():
    # CHECK-LABEL: test_aggregate_modification_in_for_loop
    value = TypeWithBuiltinInitializer()
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    for i in range(0, 2):
        # CHECK: [[RET:%.*]] = scf.for
        # CHECK-SAME: iter_args([[ITER:%.*]] = [[RANGE]])
        value.modify(tl.arange(4, 8))
        # CHECK: [[RANGE:%.*]] = tt.make_range {end = 8 : i32, start = 4 : i32}
        # CHECK: yield [[RANGE]]

    anchor(value)
    # CHECK: call @{{.*}}anchor{{.*}}([[RET]])


@filecheck_test
@triton.jit
def test_aggregate_modification_in_while_loop():
    # CHECK-LABEL: test_aggregate_modification_in_while_loop
    value = TypeWithBuiltinInitializer()
    # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    i = 0
    # CHECK: [[C0:%.*]] = arith.constant 0 :
    while i < 1:
        # CHECK: [[RET:%.*]]:2 = scf.while ([[ITER:%.*]] = [[RANGE]], [[IV:%.*]] = [[C0]])
        # CHECK: do
        i = 1
        # CHECK: [[C1:%.*]] = arith.constant 1 :
        value.modify(tl.arange(4, 8))
        # CHECK: [[RANGE:%.*]] = tt.make_range {end = 8 : i32, start = 4 : i32}
        # CHECK: yield [[RANGE]], [[C1]]

    anchor(value)
    # CHECK: call @{{.*}}anchor{{.*}}([[RET]]#0)


@triton.jit
def forward(arg):
    return arg


@triton.jit
def list_of_functions_constexpr(arg, fns: tl.constexpr):
    for i in tl.static_range(len(fns)):
        fns[i](arg)


@filecheck_test
@triton.jit
def test_list_of_functions():
    # CHECK-LABEL: test_list_of_functions
    # CHECK: call @{{.*}}list_of_functions_constexpr{{.*}}cJITFunction(test_frontend:anchor){{.*}}cJITFunction(test_frontend:forward)

    # CHECK: tt.func private @{{.*}}list_of_functions_constexpr
    # CHECK-NEXT: call @{{.*}}anchor
    # CHECK-NEXT: call @{{.*}}forward
    list_of_functions_constexpr(tl.arange(0, 4), [anchor, forward])


@triton.jit
def accumulate(a, b):
    return a + b


# Check that we can call a function returning a value from a loop.
@filecheck_test
@triton.jit
def test_call_in_loop():
    # CHECK-LABEL: test_call_in_loop
    acc = 0
    # CHECK: scf.for
    # CHECK:   call @{{.*}}accumulate
    for i in range(10):
        acc = accumulate(acc, i)


@tl.aggregate
class FunctionParent:

    @triton.jit
    def function_with_name():
        pass


@triton.jit
def function_with_name():
    pass


@filecheck_test
@triton.jit
def test_function_name_mangling():
    # CHECK-LABEL: test_function_name_mangling
    # CHECK: call @test_frontend.function_with_name
    # CHECK: call @test_frontend.FunctionParent.function_with_name
    function_with_name()
    FunctionParent.function_with_name()


@tl.aggregate
class AggregateWithConstexpr:
    a: tl.tensor
    b: tl.constexpr

    @tl.core.builtin
    def __init__(self, a, b, _semantic=None):
        self.a = a
        self.b = b

    @staticmethod
    def create(a):
        return AggregateWithConstexpr(a, 42)

    def modify(self, a):
        self.a = a


@triton.jit
def add_rhs_constexpr(agg):
    _ = agg.a + agg.b


@filecheck_test
@triton.jit
def test_aggregate_with_constexpr():
    # CHECK-LABEL: test_aggregate_with_constexpr
    # CHECK: tt.call @"test_frontend.add_rhs_constexpr__test_frontend.AggregateWithConstexpr<i32S4S, constexpr[42]>
    agg = AggregateWithConstexpr.create(tl.arange(0, 4))
    add_rhs_constexpr(agg)

    # CHECK: tt.func private @"test_frontend.add_rhs_constexpr__test_frontend.AggregateWithConstexpr<i32S4S, constexpr[42]>
    # CHECK: %cst = arith.constant dense<42> : tensor<4xi32>
    # CHECK: arith.addi %arg0, %cst : tensor<4xi32>


@tl.constexpr_function
def constexpr_function(x):
    return x + 1


@filecheck_test
@triton.jit
def test_constexpr_function_from_jit():
    # CHECK-LABEL: test_constexpr_function
    x: tl.constexpr = constexpr_function(7)
    # CHECK: make_range {end = 8 : i32, start = 0 : i32}
    tl.arange(0, x)


def test_constexpr_function_from_python():
    assert constexpr_function(7) == 8


@triton.jit
def swap(p):
    tmp = p.first
    p.mutate_first(p.second)
    p.mutate_second(tmp)


@filecheck_test
@triton.jit
def test_assign_tuple_attrs():
    # CHECK-LABEL: test_assign_tuple_attrs
    p = Pair(tl.arange(0, 4), tl.arange(4, 8))
    # CHECK: [[P:%.*]]:2 = tt.call @{{.*}}swap
    swap(p)
    # CHECK: call @{{.*}}anchor{{.*}}([[P]]#0)
    # CHECK: call @{{.*}}anchor{{.*}}([[P]]#1)
    anchor(p.first)
    anchor(p.second)


@filecheck_test
@triton.jit
def test_reassign_aggregate_with_constexpr():
    # CHECK-LABEL: test_reassign_aggregate_with_constexpr
    agg = AggregateWithConstexpr.create(tl.arange(0, 4))
    var = 1
    # CHECK: [[AGG:%.*]] = scf.if {{.*}} -> (tensor<4xi32>)
    # CHECK:   [[VALUE:%.*]] = tt.call {{.*}}modify
    # CHECK:   yield [[VALUE]]
    # CHECK: else
    # CHECK:   [[VALUE:%.*]] = tt.call {{.*}}modify
    # CHECK:   yield [[VALUE]]
    if var == 0:
        agg.modify(tl.arange(4, 8))
    else:
        agg.modify(tl.arange(8, 12))
    # CHECK: call @{{.*}}anchor{{.*}}([[AGG]])
    anchor(agg)


@tl.constexpr_function
def make_shape(m, n):
    return (m, n)


@tl.constexpr_function
def add_shape_dims(m, n):
    return m + n


@filecheck_test
@triton.jit
def test_constexpr_getitem():
    # CHECK-LABEL: test_constexpr_getitem
    # CHECK: make_range {end = 12 : i32, start = 4 : i32}
    shape: tl.constexpr = make_shape(4, 8)
    sum: tl.constexpr = add_shape_dims(shape[0], shape[1])
    tl.arange(4, sum)


@tl.constexpr_function
def make_constexpr_closure(x):
    x = tl.constexpr(x)

    @triton.jit
    def inner(shape: tl.constexpr):
        return tl.full(shape, x, dtype=tl.int32)

    return inner


@filecheck_test
@triton.jit
def test_constexpr_closure():
    # CHECK-LABEL: test_constexpr_closure
    closure: tl.constexpr = make_constexpr_closure(42)

    # CHECK: arith.constant dense<42> : tensor<128x128xi32>
    closure((128, 128))


@tl.constexpr_function
def make_constexpr_generator(f):
    f = tl.constexpr(f)

    @triton.jit
    def inner(lhs):
        return lhs + f(lhs.shape, lhs.dtype)

    return inner


@triton.jit
def inner_function(shape: tl.constexpr, dtype: tl.constexpr):
    return tl.full(shape, 42, dtype)


@filecheck_test
@triton.jit
def test_constexpr_generator():
    # CHECK: func public @test_constexpr_generator
    # CHECK:   [[RANGE:%.*]] = tt.make_range {end = 128 : i32, start = 0 : i32}
    # CHECK:   call @{{.*}}make_constexpr_generator.<locals>.inner{{.*}}([[RANGE]])

    # CHECK: func private @{{.*}}make_constexpr_generator.<locals>.inner
    # CHECK:   [[RHS:%.*]] = tt.call @{{.*}}inner_function
    # CHECK:   [[RESULT:%.*]] = arith.addi %arg0, [[RHS]]
    # CHECK:   return [[RESULT]]

    # CHECK: func private @{{.*}}inner_function
    # CHECK:   %cst = arith.constant dense<42> : tensor<128xi32>
    # CHECK:   return %cst
    generator: tl.constexpr = make_constexpr_generator(inner_function)
    lhs = tl.arange(0, 128)
    generator(lhs)


@tl.constexpr_function
def Box(T):

    @tl.aggregate
    class BoxImpl:
        value: T

        def create(value):
            return BoxImpl(value)

        @tl.core.builtin
        def __init__(self, value, _semantic=None):
            self.value = value

    return BoxImpl


def test_late_bound_class_reference():
    TensorBox = Box(tl.tensor)

    @triton.jit
    def kernel():
        # CHECK: [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
        # CHECK: call @{{.*}}anchor{{.*}}([[RANGE]])
        value = TensorBox(tl.arange(0, 4))
        anchor(value)

    run_filecheck_test(kernel)


@triton.jit
def mutate_and_produce(x):
    return tl.arange(0, 16)


@triton.jit
def mutate_and_produce_tuple(x):
    return tl.arange(0, 16), tl.arange(16, 32)


@filecheck_test
@triton.jit
def test_mutable_argument():
    # CHECK-LABEL: tt.func public @test_mutable_argument
    # CHECK-NEXT:    [[FIRST0:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    # CHECK-NEXT:    [[SECOND0:%.*]] = tt.make_range {end = 8 : i32, start = 4 : i32}
    # CHECK-NEXT:    [[P1:%.*]]:2 = tt.call @{{.*}}swap{{.*}}([[FIRST0]], [[SECOND0]])
    # CHECK-NEXT:    [[FIRST1:%.*]] = tt.make_range {end = 12 : i32, start = 8 : i32}
    # CHECK-NEXT:    [[P2:%.*]]:2 = tt.call @{{.*}}mutate_first{{.*}}([[P1]]#0, [[P1]]#1, [[FIRST1]])
    # CHECK-NEXT:    [[SECOND1:%.*]] = tt.make_range {end = 20 : i32, start = 12 : i32}
    # CHECK-NEXT:    [[P3:%.*]]:2 = tt.call @{{.*}}mutate_second{{.*}}([[P2]]#0, [[P2]]#1, [[SECOND1]])
    # CHECK-NEXT:    [[P4:%.*]]:2 = tt.call @{{.*}}swap{{.*}}([[P3]]#0, [[P3]]#1)
    p = Pair(tl.arange(0, 4), tl.arange(4, 8))
    swap(p)

    box = Box(Pair)(p)
    box.value.mutate_first(tl.arange(8, 12))
    box.value.mutate_second(tl.arange(12, 20))
    swap(box.value)

    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P4]]#0, [[P4]]#1)
    anchor(box)

    # CHECK-NEXT:    [[P5:%.*]]:3 = tt.call @{{.*}}mutate_and_produce{{.*}}([[P1]]#0, [[P1]]#1)
    # CHECK-NEXT:    [[P6:%.*]]:4 = tt.call @{{.*}}mutate_and_produce_tuple{{.*}}([[P5]]#1, [[P5]]#2)
    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P5]]#0)
    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P6]]#0)
    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P6]]#1)
    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P6]]#2, [[P6]]#3)
    a = mutate_and_produce(p)
    b, c = mutate_and_produce_tuple(p)
    anchor(a)
    anchor(b)
    anchor(c)
    anchor(p)

    # CHECK-LABEL: tt.func private @{{.*}}swap
    # CHECK-NEXT:    [[P1:%.*]]:2 = tt.call @{{.*}}mutate_first{{.*}}(%arg0, %arg1, %arg1)
    # CHECK-NEXT:    [[P2:%.*]]:2 = tt.call @{{.*}}mutate_second{{.*}}([[P1]]#0, [[P1]]#1, %arg0)
    # CHECK-NEXT:    return [[P2]]#0, [[P2]]#1

    # CHECK-LABEL: tt.func private @{{.*}}mutate_first
    # CHECK-NEXT:    return %arg2, %arg1

    # CHECK-LABEL: tt.func private @{{.*}}mutate_second
    # CHECK-NEXT:    return %arg0, %arg2

    # CHECK-LABEL: tt.func private @{{.*}}mutate_and_produce
    # CHECK-NEXT:    [[RANGE:%.*]] = tt.make_range {end = 16 : i32, start = 0 : i32}
    # CHECK-NEXT:    return [[RANGE]], %arg0, %arg1

    # CHECK-LABEL: tt.func private @{{.*}}mutate_and_produce_tuple
    # CHECK-NEXT:    [[RANGE1:%.*]] = tt.make_range {end = 16 : i32, start = 0 : i32}
    # CHECK-NEXT:    [[RANGE2:%.*]] = tt.make_range {end = 32 : i32, start = 16 : i32}
    # CHECK-NEXT:    return [[RANGE1]], [[RANGE2]], %arg0, %arg1


@tl.aggregate
class JITInitializer:
    x: tl.tensor
    y: tl.constexpr

    def __init__(self, a, b, y: tl.constexpr):
        self.y: tl.constexpr = y
        self.x = a + b + tl.arange(0, self.y)

    def double(self):
        self.x *= 2


@filecheck_test
@triton.jit
def test_jit_init():
    # CHECK-LABEL: tt.func public @test_jit_init
    # CHECK-NEXT:    [[RANGE0:%.*]] = tt.make_range {end = 8 : i32, start = 4 : i32}
    # CHECK-NEXT:    [[RANGE1:%.*]] = tt.make_range {end = 12 : i32, start = 8 : i32}
    # CHECK-NEXT:    [[P:%.*]] = tt.call @{{.*}}JITInitializer.__init__{{.*}}([[RANGE0]], [[RANGE1]])
    # CHECK-NEXT:    call @{{.*}}anchor{{.*}}([[P]])
    # CHECK-NEXT:    tt.make_range {end = 4 : i32, start = 0 : i32}
    p = JITInitializer(tl.arange(4, 8), tl.arange(8, 12), 4)
    anchor(p)
    tl.arange(0, p.y)

    # CHECK-LABEL: tt.func private @{{.*}}JITInitializer.__init__
    # CHECK:         [[X:%.*]] = arith.addi %arg0, %arg1
    # CHECK:         [[RANGE:%.*]] = tt.make_range {end = 4 : i32, start = 0 : i32}
    # CHECK:         [[Y:%.*]] = arith.addi [[X]], [[RANGE]]
    # CHECK:         return [[Y]]


@filecheck_test
@triton.jit
def test_modify_if_livein():
    # CHECK-LABEL: test_modify_if_livein
    none_livein = None  # noqa: F841

    # CHECK: [[LOOP_OUT:%.*]] = scf.for {{.*}} iter_args([[BOX:%.*]] = %true)
    # CHECK:   [[LIVEOUT:%.*]] = scf.if [[BOX]]
    # CHECK:     yield %false
    # CHECK:   else
    # CHECK:     yield [[BOX]]
    # CHECK:   yield [[LIVEOUT]]
    # CHECK: call @{{.*}}anchor{{.*}}([[LOOP_OUT]])
    box = Box(tl.tensor)(tl.core.to_tensor(True))
    for i in range(10):
        if box.value:
            box.value = False
    anchor(box.value)


@triton.jit
def test_mutate_object_scf_if():
    TBox: tl.constexpr = Box(tl.tensor)
    box = TBox(tl.core.to_tensor(0))
    a = box
    b = box
    box.value = tl.core.to_tensor(100)

    if tl.core.to_tensor(True):
        anchor((box, a, b))
        b.value = tl.core.to_tensor(1)
        a = TBox(tl.core.to_tensor(10))
        anchor((box, a, b))
    else:
        anchor((box, a, b))
        b.value = tl.core.to_tensor(2)
        a = TBox(tl.core.to_tensor(20))
        anchor((box, a, b))
    anchor((box, a, b))


@triton.jit
def test_mutate_object_if_toplevel():
    TBox: tl.constexpr = Box(tl.tensor)
    box = TBox(tl.core.to_tensor(0))
    a = box
    b = box
    box.value = tl.core.to_tensor(100)

    if tl.core.to_tensor(True):
        anchor((box, a, b))
        b.value = tl.core.to_tensor(1)
        a = TBox(tl.core.to_tensor(10))
        anchor((box, a, b))
    else:
        anchor((box, a, b))
        b.value = tl.core.to_tensor(2)
        a = TBox(tl.core.to_tensor(20))
        anchor((box, a, b))
        return
    anchor((box, a, b))


@triton.jit
def test_mutate_object_for():
    TBox: tl.constexpr = Box(tl.tensor)
    box = TBox(tl.core.to_tensor(0))
    a = box
    b = box
    box.value = tl.core.to_tensor(100)

    for i in range(0):
        anchor((box, a, b))
        b.value = tl.core.to_tensor(1)
        a = TBox(tl.core.to_tensor(20))
        anchor((box, a, b))
    anchor((box, a, b))


@triton.jit
def test_mutate_object_while():
    TBox: tl.constexpr = Box(tl.tensor)
    box = TBox(tl.core.to_tensor(0))
    a = box
    b = box
    box.value = tl.core.to_tensor(100)

    while box.value != 10:
        anchor((box, a, b))
        b.value = tl.core.to_tensor(1)
        a = TBox(tl.core.to_tensor(20))
        anchor((box, a, b))
    anchor((box, a, b))


from triton._filecheck import run_parser
from triton import knobs

knobs.compilation.disable_line_info = True
print(run_parser(test_mutate_object_while).str_nodebug())
