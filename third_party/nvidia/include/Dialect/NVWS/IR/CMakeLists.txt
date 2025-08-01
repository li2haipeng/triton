set(MLIR_BINARY_DIR ${CMAKE_BINARY_DIR})

set(LLVM_TARGET_DEFINITIONS NVWSOps.td)
mlir_tablegen(Dialect.h.inc -gen-dialect-decls -dialect=nvws)
mlir_tablegen(Dialect.cpp.inc -gen-dialect-defs -dialect=nvws)
mlir_tablegen(Ops.h.inc -gen-op-decls)
mlir_tablegen(Ops.cpp.inc -gen-op-defs)
mlir_tablegen(Types.h.inc -gen-typedef-decls -typedefs-dialect=nvws)
mlir_tablegen(Types.cpp.inc -gen-typedef-defs -typedefs-dialect=nvws)
add_mlir_doc(NVWSDialect NVWSDialect dialects/ -gen-dialect-doc)
add_mlir_doc(NVWSOps NVWSOps dialects/ -gen-op-doc)
add_public_tablegen_target(NVWSTableGen)

set(LLVM_TARGET_DEFINITIONS NVWSAttrDefs.td)
mlir_tablegen(NVWSAttrDefs.h.inc -gen-attrdef-decls)
mlir_tablegen(NVWSAttrDefs.cpp.inc -gen-attrdef-defs)
mlir_tablegen(NVWSAttrEnums.h.inc -gen-enum-decls)
mlir_tablegen(NVWSAttrEnums.cpp.inc -gen-enum-defs)

set(LLVM_TARGET_DEFINITIONS NVWSOpInterfaces.td)
mlir_tablegen(NVWSOpInterfaces.h.inc -gen-op-interface-decls)
mlir_tablegen(NVWSOpInterfaces.cpp.inc -gen-op-interface-defs)

add_public_tablegen_target(NVWSAttrDefsIncGen)
