import json
import subprocess
import sys
import platform
from pathlib import Path

import lexico
import sintactico_ast
import semantico


codigo_fuente = """
int main() {
    print("Hola mundo");
};
"""

if len(sys.argv) > 1:
    ruta_entrada = sys.argv[1]
    with open(ruta_entrada, "r", encoding="utf-8") as f:
        codigo_fuente = f.read()


def imprimir_ast(nodo):
    if isinstance(nodo, lexico.NodoPrograma):
        return {
            "programa": "Noname",
            "funciones": [imprimir_ast(f) for f in nodo.funciones],
            "main": imprimir_ast(nodo.main),
        }
    elif isinstance(nodo, lexico.NodoFuncion):
        return {
            "nombre": nodo.nombre[1],
            "parametros": [imprimir_ast(p) for p in nodo.parametros],
            "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo],
        }
    elif isinstance(nodo, lexico.NodoParametro):
        return {"id": nodo.nombre[1], "tipo": nodo.tipo[1]}
    elif isinstance(nodo, lexico.NodoAsignacion):
        return {"tipo": "asignacion", "variable": nodo.nombre[1], "expresion": imprimir_ast(nodo.expresion)}
    elif isinstance(nodo, lexico.NodoReasignacion):
        return {"tipo": "reasignacion", "variable": nodo.nombre[1], "expresion": imprimir_ast(nodo.expresion)}
    elif isinstance(nodo, lexico.NodoOperacion):
        return {"op": nodo.operador[1], "izq": imprimir_ast(nodo.izquierda), "der": imprimir_ast(nodo.derecha)}
    elif isinstance(nodo, lexico.NodoRetorno):
        return {"tipo": "return", "valor": imprimir_ast(nodo.expresion)}
    elif isinstance(nodo, lexico.NodoIdentificador):
        return nodo.nombre[1]
    elif isinstance(nodo, lexico.NodoNumero):
        return {"Numero": nodo.valor}
    elif isinstance(nodo, lexico.NodoString):
        return {"String": nodo.valor[1] if isinstance(nodo.valor, tuple) else nodo.valor}
    elif isinstance(nodo, lexico.NodoLlamadaFuncion):
        return {"LlamadaFuncion": nodo.nombre_funcion, "Argumentos": [imprimir_ast(a) for a in nodo.argumentos]}
    elif isinstance(nodo, lexico.NodoPrint):
        return {"tipo": "print", "expresion": imprimir_ast(nodo.expresion)}
    elif isinstance(nodo, lexico.NodoPrintln):
        return {"tipo": "println", "expresion": imprimir_ast(nodo.expresion)}
    elif isinstance(nodo, lexico.NodoIf):
        n = {"tipo": "if", "condicion": imprimir_ast(nodo.condicion), "cuerpo_if": [imprimir_ast(c) for c in nodo.cuerpo_if]}
        if nodo.cuerpo_else:
            n["cuerpo_else"] = [imprimir_ast(c) for c in nodo.cuerpo_else]
        return n
    elif isinstance(nodo, lexico.NodoWhile):
        return {"tipo": "while", "condicion": imprimir_ast(nodo.condicion), "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo]}
    elif isinstance(nodo, lexico.NodoFor):
        return {
            "tipo": "for",
            "inicio": imprimir_ast(nodo.inicio),
            "condicion": imprimir_ast(nodo.condicion),
            "incremento": imprimir_ast(nodo.incremento),
            "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo],
        }
    return {}


def limpiar_asm_para_mostrar(codigo_asm):
    lineas_limpias = []
    for linea in codigo_asm.splitlines():
        sin_inline = linea.split(";", 1)[0].rstrip()
        if sin_inline:
            lineas_limpias.append(sin_inline)
    return "\n".join(lineas_limpias)


def _ruta_windows_a_wsl(ruta_windows):
    ruta = Path(ruta_windows).resolve()
    unidad = ruta.drive.rstrip(":").lower()
    partes = [p for p in ruta.parts[1:] if p not in ("\\", "/")]
    return f"/mnt/{unidad}/" + "/".join(partes)


def _ejecutar_en_wsl(args):
    return subprocess.run(["wsl", "-d", "Ubuntu", "-e"] + args, capture_output=True, text=True)


def compilar(codigo_asm, nombre_base="programa"):
    en_windows = platform.system() == "Windows"

    archivo_asm = f"{nombre_base}.asm"
    archivo_obj = f"{nombre_base}.o"
    archivo_bin = nombre_base

    with open(archivo_asm, "w", encoding="utf-8") as f:
        f.write(codigo_asm)

    if en_windows:
        base_linux = _ruta_windows_a_wsl(Path.cwd())
        asm_linux = f"{base_linux}/{archivo_asm}"
        obj_linux = f"{base_linux}/{archivo_obj}"
        bin_linux = f"{base_linux}/{archivo_bin}"

        resultado_nasm = _ejecutar_en_wsl(["/usr/bin/nasm", "-f", "elf32", asm_linux, "-o", obj_linux])
    else:
        resultado_nasm = subprocess.run(["nasm", "-f", "elf32", archivo_asm, "-o", archivo_obj], capture_output=True, text=True)

    if resultado_nasm.returncode != 0:
        print(f"Error en nasm:\n{resultado_nasm.stderr}")
        return False

    if en_windows:
        resultado_ld = _ejecutar_en_wsl(["/usr/bin/ld", "-m", "elf_i386", obj_linux, "-o", bin_linux])
    else:
        resultado_ld = subprocess.run(["ld", "-m", "elf_i386", archivo_obj, "-o", archivo_bin], capture_output=True, text=True)

    if resultado_ld.returncode != 0:
        print(f"Error en ld:\n{resultado_ld.stderr}")
        return False

    if en_windows:
        resultado_run = _ejecutar_en_wsl([bin_linux])
    else:
        resultado_run = subprocess.run([f"./{archivo_bin}"], capture_output=True, text=True)

    print("\n=== RESPUESTA ===")
    if resultado_run.stdout:
        print(resultado_run.stdout, end="" if resultado_run.stdout.endswith("\n") else "\n")
    if resultado_run.stderr:
        print("[stderr]")
        print(resultado_run.stderr, end="" if resultado_run.stderr.endswith("\n") else "\n")

    return resultado_run.returncode == 0


# 1) Tokens encontrados
print("=== TOKENS ENCONTRADOS ===")
tokens = lexico.identificar_tokens(codigo_fuente)
for tipo, valor in tokens:
    print(f"  {tipo:12}: {valor}")

# 2) Análisis sintáctico
print("\n=== ANÁLISIS SINTÁCTICO ===")
try:
    parser = sintactico_ast.Parser(tokens)
    arbol_ast = parser.parsear()
    print("Análisis sintáctico completado sin errores.")
except SyntaxError as e:
    print(f"Error sintáctico: {e}")
    arbol_ast = None

# 3) Análisis semántico
if arbol_ast:
    print("\n=== ANÁLISIS SEMÁNTICO ===")
    try:
        analizador_sem = semantico.AnalizadorSemantico()
        analizador_sem.analizar(arbol_ast)
        print("Análisis semántico completado sin errores.")
    except Exception as e:
        print(f"Error semántico: {e}")
        arbol_ast = None

if arbol_ast:
    # 4) AST generado
    print("\n=== AST GENERADO ===")
    print(json.dumps(imprimir_ast(arbol_ast), indent=4, ensure_ascii=False))

    # 5) ASM
    print("\n=== ASM ===")
    asm = arbol_ast.generarCodigo()
    print(limpiar_asm_para_mostrar(asm))

    # 6) Respuesta
    exito = compilar(asm, nombre_base="programa")
    if not exito:
        print("\nFalló compilación o ejecución.")
