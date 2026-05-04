import json
import os
import subprocess
import lexico
import sintactico_ast
import semantico


codigo_fuente = """
int suma(int a, int b) {
    int c = a + b;
    return c;
};

int main() {
    println("Inicio del programa");

    int resultado = suma(3, 4);
    print("Resultado de suma(3,4): ");
    println(resultado);

    int x = 10;
    if (x > 5) {
        println("x es mayor que 5");
    } else {
        println("x es menor o igual a 5");
    };
};
"""


# ==========================
# ANÁLISIS LÉXICO
# ==========================

tokens = lexico.identificar_tokens(codigo_fuente)

print("=== TOKENS ENCONTRADOS ===")
for tipo, valor in tokens:
    print(f"  {tipo:12}: {valor}")


# ==========================
# ANÁLISIS SINTÁCTICO
# ==========================

try:
    print("\n=== ANÁLISIS SINTÁCTICO ===")
    parser = sintactico_ast.Parser(tokens)
    arbol_ast = parser.parsear()
    print("Análisis sintáctico completado sin errores.")
except SyntaxError as e:
    print(f"Error: {e}")
    arbol_ast = None


# ==========================
# ANÁLISIS SEMÁNTICO
# ==========================

if arbol_ast:
    try:
        print("\n=== ANÁLISIS SEMÁNTICO ===")
        analizador_sem = semantico.AnalizadorSemantico()
        analizador_sem.analizar(arbol_ast)
        print("Análisis semántico completado sin errores.")
    except Exception as e:
        print(f"Error semántico: {e}")
        arbol_ast = None


# ==========================
# FUNCIÓN PARA IMPRIMIR AST
# ==========================

def imprimir_ast(nodo):
    if isinstance(nodo, lexico.NodoPrograma):
        return {
            'programa': 'Noname',
            'funciones': [imprimir_ast(f) for f in nodo.funciones],
            'main': imprimir_ast(nodo.main)
        }
    elif isinstance(nodo, lexico.NodoFuncion):
        return {
            "nombre": nodo.nombre[1],
            "parametros": [imprimir_ast(p) for p in nodo.parametros],
            "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo]
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
        return {"tipo": "for", "inicio": imprimir_ast(nodo.inicio), "condicion": imprimir_ast(nodo.condicion),
                "incremento": imprimir_ast(nodo.incremento), "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo]}
    return {}


# ==========================
# COMPILAR CON NASM + LD
# ==========================

def compilar(codigo_asm, nombre_base="programa"):
    """
    Recibe el codigo ensamblador como string y lo compila con nasm + gcc.

    Pasos:
      1. Guardar el codigo en  <nombre_base>.asm
      2. nasm -f elf32 <nombre_base>.asm -o <nombre_base>.o
      3. gcc -m32 <nombre_base>.o  -o <nombre_base>

    Detecta automaticamente si se corre desde Windows (usa wsl) o desde Linux directamente.
    Retorna True si la compilacion fue exitosa, False en caso contrario.
    """
    import platform
    # En Windows los comandos de Linux se invocan via WSL; en Linux se llaman directo
    en_windows = platform.system() == "Windows"
    prefijo    = ["wsl"] if en_windows else []

    archivo_asm = f"{nombre_base}.asm"
    archivo_obj = f"{nombre_base}.o"
    archivo_bin = nombre_base

    # --- Paso 1: Escribir el archivo .asm ---
    print(f"\n[Paso 1] Guardando codigo ensamblador en '{archivo_asm}'...")
    with open(archivo_asm, "w") as f:
        f.write(codigo_asm)
    print(f"         Archivo guardado ({len(codigo_asm)} bytes).")

    # --- Paso 2: Ensamblar con nasm ---
    print(f"\n[Paso 2] Ensamblando con nasm...")
    cmd_nasm = prefijo + ["nasm", "-f", "elf32", archivo_asm, "-o", archivo_obj]
    print(f"         Comando: {' '.join(cmd_nasm)}")
    resultado_nasm = subprocess.run(cmd_nasm, capture_output=True, text=True)
    if resultado_nasm.returncode != 0:
        print(f"         ERROR en nasm:\n{resultado_nasm.stderr}")
        return False
    print(f"         Ensamblado exitoso -> '{archivo_obj}'")

    # --- Paso 3: Enlazar con ld ---
    # Usamos ld directamente (sin gcc) porque el codigo generado usa solo syscalls
    # de Linux (int 0x80), sin ninguna funcion de la libreria de C. gcc necesita
    # las libs de C en 32-bit instaladas (gcc-multilib), ld no las necesita.
    print(f"\n[Paso 3] Enlazando con ld...")
    cmd_ld = prefijo + ["ld", "-m", "elf_i386", archivo_obj, "-o", archivo_bin]
    print(f"         Comando: {' '.join(cmd_ld)}")
    resultado_ld = subprocess.run(cmd_ld, capture_output=True, text=True)
    if resultado_ld.returncode != 0:
        print(f"         ERROR en ld:\n{resultado_ld.stderr}")
        return False
    print(f"         Enlazado exitoso  -> '{archivo_bin}'")

    print(f"\n Compilacion completa. Ejecutar con: ./{archivo_bin}")
    print(f"\n Ejecutando programa...\n")
    subprocess.run(prefijo + [f"./{archivo_bin}"])
    return True


# ==========================
# MOSTRAR AST Y TRADUCCIONES
# ==========================

if arbol_ast:
    print("\n=== AST GENERADO ===")
    print(json.dumps(imprimir_ast(arbol_ast), indent=4))

    print("\n=== TRADUCCIÓN A PYTHON ===")
    print(arbol_ast.traducirPy())

    print("\n=== TRADUCCIÓN A RUBY ===")
    print(arbol_ast.traducirRuby())

    print("\n=== CÓDIGO ENSAMBLADOR (NASM x86 32-bit) ===")
    asm = arbol_ast.generarCodigo()
    print(asm)

    # Intentar compilar (requiere nasm instalado)
    print("\n=== COMPILACIÓN CON NASM + LD ===")
    exito = compilar(asm, nombre_base="programa")
    if not exito:
        print("\n[Info] nasm no esta instalado en este entorno.")
        print("       Para compilar el programa ejecuta:")
        print("         nasm -f elf32 programa.asm -o programa.o")
        print("         ld -m elf_i386 programa.o -o programa")
        print("         ./programa")