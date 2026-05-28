# =============================================================
# interfaz.py
# Entorno visual de programación con diagrama de flujo
# Coloca junto a: lexico.py, sintactico_ast.py, semantico.py
# Ejecutar: python interfaz.py
# =============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import subprocess
import platform
import re
from pathlib import Path

# Módulos del compilador del proyecto
import lexico
import sintactico_ast
import semantico

# =============================================================
# PALETA DE COLORES DEL TEMA
# =============================================================
BG      = "#f5f3ef"   # Fondo general
BG2     = "#ffffff"   # Fondo paneles blancos
BG3     = "#eeebe5"   # Fondo cabeceras
BG4     = "#e4e0d8"   # Fondo botones neutros
BORDER  = "#d8d4cc"   # Color de bordes
TEXT    = "#1a1815"   # Texto principal
MUTED   = "#8c8580"   # Texto secundario / apagado
ACCENT  = "#5a47e0"   # Color de acento principal (morado)
GREEN   = "#1a8a4a"   # Verde éxito
RED     = "#c0392b"   # Rojo error
AMBER   = "#b45309"   # Ámbar advertencia
BLUE    = "#1d4ed8"   # Azul
TEAL    = "#0d7377"   # Teal
PINK    = "#9d174d"   # Rosa
ORANGE  = "#c2410c"   # Naranja

# =============================================================
# CONFIGURACIÓN DE NODOS — Color y forma por tipo
# =============================================================

# Colores (bg, fg) por tipo de instrucción
TIPO_COLOR = {
    "inicio":    (ACCENT, "#ffffff"),
    "fin":       (RED,    "#ffffff"),
    "asignar":   (BLUE,   "#ffffff"),
    "reasignar": (MUTED,  "#ffffff"),
    "print":     (GREEN,  "#ffffff"),
    "println":   (TEAL,   "#ffffff"),
    "if":        (AMBER,  "#1a1815"),
    "while":     (BLUE,   "#ffffff"),
    "for":       (TEAL,   "#ffffff"),
    "return":    (ORANGE, "#ffffff"),
    "funcion":   (PINK,   "#ffffff"),
    "llamada":   (MUTED,  "#ffffff"),
}

# Forma visual por tipo: "oval" | "diamond" | "rect" | "parall"
TIPO_FORMA = {
    "inicio":    "oval",
    "fin":       "oval",
    "asignar":   "rect",
    "reasignar": "rect",
    "print":     "parall",
    "println":   "parall",
    "if":        "diamond",
    "while":     "diamond",
    "for":       "diamond",
    "return":    "rect",
    "funcion":   "rect",
    "llamada":   "rect",
}

# Dimensiones base de cada nodo
NW, NH = 160, 52

# =============================================================
# CAMPOS EDITABLES POR TIPO DE NODO
# Formato: (clave, etiqueta_visible, valor_por_defecto)
# =============================================================
CAMPOS = {
    "asignar":   [
        ("tipo_var", "Tipo de dato", "int"),
        ("nombre",   "Nombre de variable", "x"),
        ("valor",    "Valor inicial", "0"),
    ],
    "reasignar": [
        ("nombre", "Variable", "x"),
        ("valor",  "Nuevo valor", "x + 1"),
    ],
    "print":     [("expr", "Expresión a imprimir", '"Hola"')],
    "println":   [("expr", "Expresión a imprimir", '"Hola"')],
    "if":        [("cond", "Condición", "x > 0")],
    "while":     [("cond", "Condición del bucle", "x > 0")],
    "for":       [
        ("tipo_var", "Tipo de dato", "int"),
        ("var",      "Variable de control", "i"),
        ("inicio",   "Valor inicial", "0"),
        ("cond",     "Condición", "i < 5"),
        ("inc",      "Incremento", "i + 1"),
    ],
    "return":    [("expr", "Valor de retorno", "0")],
    "funcion":   [
        ("tipo_ret", "Tipo de retorno", "int"),
        ("nombre",   "Nombre de función", "miFun"),
        ("params",   "Parámetros", "int a, int b"),
    ],
    "llamada":   [
        ("nombre", "Nombre de función", "miFun"),
        ("args",   "Argumentos", ""),
    ],
    "inicio":    [],
    "fin":       [],
}


def defaults(tipo):
    """Devuelve los valores por defecto de un tipo de nodo."""
    return {k: v for k, _, v in CAMPOS.get(tipo, [])}


def etiqueta_nodo(tipo, datos):
    """Genera el texto visible dentro del nodo según su tipo y datos."""
    d = datos
    if tipo == "inicio":    return "INICIO"
    if tipo == "fin":       return "FIN"
    if tipo == "asignar":   return f"{d.get('tipo_var','int')} {d.get('nombre','x')} = {d.get('valor','0')}"
    if tipo == "reasignar": return f"{d.get('nombre','x')} = {d.get('valor','...')}"
    if tipo == "print":     return f"print({d.get('expr','...')})"
    if tipo == "println":   return f"println({d.get('expr','...')})"
    if tipo == "if":        return f"if ({d.get('cond','...')})"
    if tipo == "while":     return f"while ({d.get('cond','...')})"
    if tipo == "for":       return f"for {d.get('var','i')} = {d.get('inicio','0')}..{d.get('cond','')}"
    if tipo == "return":    return f"return {d.get('expr','...')}"
    if tipo == "funcion":   return f"{d.get('tipo_ret','int')} {d.get('nombre','f')}()"
    if tipo == "llamada":   return f"{d.get('nombre','f')}({d.get('args','')})"
    return tipo


# =============================================================
# GENERACIÓN DE CÓDIGO C-LIKE DESDE EL DIAGRAMA
# =============================================================

def diagrama_a_codigo(nodos, conexiones):
    """
    Recorre el diagrama de flujo siguiendo las flechas desde el
    nodo INICIO y genera código C-like válido para el compilador.

    Soporta: secuencia, if/else, while, for, funciones, llamadas.
    Las funciones se extraen primero y luego se genera el main().
    """
    # Construir índices de adyacencia
    nodo_por_id = {n["id"]: n for n in nodos}
    hijos_de    = {n["id"]: [] for n in nodos}
    padres_de   = {n["id"]: [] for n in nodos}

    for src, dst, lbl in conexiones:
        hijos_de[src].append((dst, lbl))
        padres_de[dst].append(src)

    # Localizar nodo INICIO
    inicio = next((n for n in nodos if n["tipo"] == "inicio"), None)
    if not inicio:
        return "// Error: el diagrama no tiene nodo INICIO\n"

    visitados   = set()
    lineas_func = []
    lineas_main = []

    # 1. Generar funciones definidas por el usuario
    for n in nodos:
        if n["tipo"] == "funcion":
            d = n["datos"]
            cuerpo = _cuerpo_desde(n["id"], hijos_de, nodo_por_id, set(visitados))
            lineas_func.append(
                f"{d.get('tipo_ret','int')} {d.get('nombre','f')}({d.get('params','')}) {{\n"
                f"{cuerpo}\n"
                f"}};"
            )
            visitados.add(n["id"])

    # 2. Generar cuerpo del main() desde INICIO
    _recorrer(inicio["id"], hijos_de, nodo_por_id, visitados, lineas_main, "    ")

    body        = "\n".join(lineas_main) if lineas_main else "    // sin instrucciones"
    main_bloque = f"int main() {{\n{body}\n}};"
    partes      = lineas_func + [main_bloque]

    return "\n\n".join(partes)


def _cuerpo_desde(fn_id, hijos_de, nodo_por_id, visitados):
    """Genera el cuerpo de una función siguiendo sus conexiones directas."""
    lineas    = []
    vis_local = set(visitados)

    for dst, _ in hijos_de.get(fn_id, []):
        _recorrer(dst, hijos_de, nodo_por_id, vis_local, lineas, "    ")

    return "\n".join(lineas) if lineas else "    // sin instrucciones"



def _recorrer_cuerpo_while(nid, while_id, hijos_de, nodo_por_id, visitados, lineas, indent):
    """
    Recorre el cuerpo de un while. Se detiene cuando encuentra
    el nodo while de nuevo (flecha de regreso) o un nodo ya visitado.
    """
    if nid in visitados or nid == while_id:
        return
    nodo = nodo_por_id.get(nid)
    if not nodo:
        return

    tipo  = nodo["tipo"]
    datos = nodo["datos"]
    visitados.add(nid)

    if tipo == "asignar":
        lineas.append(
            f"{indent}{datos.get('tipo_var','int')} "
            f"{datos.get('nombre','x')} = {datos.get('valor','0')};"
        )
    elif tipo == "reasignar":
        lineas.append(f"{indent}{datos.get('nombre','x')} = {datos.get('valor','0')};")
    elif tipo == "print":
        lineas.append(f"{indent}print({datos.get('expr','')});")
    elif tipo == "println":
        lineas.append(f"{indent}println({datos.get('expr','')});")
    elif tipo == "return":
        lineas.append(f"{indent}return {datos.get('expr','0')};")
    elif tipo == "llamada":
        lineas.append(f"{indent}{datos.get('nombre','f')}({datos.get('args','')});")

    # Continuar con el siguiente nodo, ignorando flechas que regresan al while
    hijos = hijos_de.get(nid, [])
    for dst, lbl in hijos:
        if dst == while_id:
            continue  # Ignorar la flecha de regreso al while
        if dst not in visitados:
            _recorrer_cuerpo_while(dst, while_id, hijos_de, nodo_por_id, visitados, lineas, indent)


def _recorrer(nid, hijos_de, nodo_por_id, visitados, lineas, indent):
    """
    Recorre recursivamente el grafo del diagrama generando
    las líneas de código correspondientes a cada nodo.
    """
    # Evitar ciclos infinitos y nodos inexistentes
    if nid in visitados:
        return
    nodo = nodo_por_id.get(nid)
    if not nodo:
        return

    tipo  = nodo["tipo"]
    datos = nodo["datos"]
    visitados.add(nid)

    # ── Nodos que no generan código ──────────────────────
    if tipo in ("inicio", "fin"):
        pass

    # ── Declaración de variable ───────────────────────────
    elif tipo == "asignar":
        lineas.append(
            f"{indent}{datos.get('tipo_var','int')} "
            f"{datos.get('nombre','x')} = {datos.get('valor','0')};"
        )

    # ── Reasignación de variable ──────────────────────────
    elif tipo == "reasignar":
        lineas.append(f"{indent}{datos.get('nombre','x')} = {datos.get('valor','0')};")

    # ── Impresión sin salto de línea ──────────────────────
    elif tipo == "print":
        lineas.append(f"{indent}print({datos.get('expr','')});")

    # ── Impresión con salto de línea ──────────────────────
    elif tipo == "println":
        lineas.append(f"{indent}println({datos.get('expr','')});")

    # ── Retorno de función ────────────────────────────────
    elif tipo == "return":
        lineas.append(f"{indent}return {datos.get('expr','0')};")

    # ── Llamada a función ─────────────────────────────────
    elif tipo == "llamada":
        lineas.append(f"{indent}{datos.get('nombre','f')}({datos.get('args','')});")

    # ── Condicional if / else ─────────────────────────────
    elif tipo == "if":
        cond  = datos.get("cond", "true")
        hijos = hijos_de.get(nid, [])

        # Rama verdadera: etiqueta "si", "sí", "true", "s", "yes", "1"
        si_id = next(
            (d for d, l in hijos if l.lower() in ("sí","si","true","s","yes","1")),
            None
        )
        # Rama falsa: etiqueta "no", "false", "n", "0"
        no_id = next(
            (d for d, l in hijos if l.lower() in ("no","false","n","0")),
            None
        )
        # Si no hay etiquetas, usar orden de conexión
        if not si_id and hijos:
            si_id = hijos[0][0]
        if not no_id and len(hijos) > 1:
            no_id = hijos[1][0]

        lineas.append(f"{indent}if ({cond}) {{")
        if si_id:
            _recorrer(si_id, hijos_de, nodo_por_id, set(visitados), lineas, indent + "    ")
        else:
            lineas.append(f"{indent}    // vacío")

        if no_id:
            lineas.append(f"{indent}}} else {{")
            _recorrer(no_id, hijos_de, nodo_por_id, set(visitados), lineas, indent + "    ")

        lineas.append(f"{indent}}};")
        return  # No continuar con hijos normales

    # ── Bucle while ───────────────────────────────────────
    elif tipo == "while":
        cond  = datos.get("cond", "true")
        hijos = hijos_de.get(nid, [])

        # Rama "No" → nodo que sigue después del bucle (salida)
        no_id = next(
            (d for d, l in hijos if l.lower() in ("no","false","n","salir")),
            None
        )
        # Rama "Sí" → primer nodo del cuerpo del bucle
        si_id = next(
            (d for d, l in hijos if l.lower() in ("sí","si","true","s","yes","1")),
            None
        )
        # Si no hay etiquetas, usar orden: primer hijo = cuerpo, segundo = salida
        if not si_id and not no_id:
            si_id = hijos[0][0] if len(hijos) > 0 else None
            no_id = hijos[1][0] if len(hijos) > 1 else None
        elif not si_id:
            si_id = next((d for d, l in hijos if d != no_id), None)

        lineas.append(f"{indent}while ({cond}) {{")
        if si_id:
            # Recorrer el cuerpo del while sin incluir el nodo while ni el nodo de salida
            vis_while = set(visitados) | ({no_id} if no_id else set())
            _recorrer_cuerpo_while(si_id, nid, hijos_de, nodo_por_id, vis_while, lineas, indent + "    ")
        else:
            lineas.append(f"{indent}    // vacío")
        lineas.append(f"{indent}}};")

        # Continuar con el nodo de salida (rama No)
        if no_id:
            _recorrer(no_id, hijos_de, nodo_por_id, visitados, lineas, indent)
        return

    # ── Bucle for ─────────────────────────────────────────
    elif tipo == "for":
        d         = datos
        hijos     = hijos_de.get(nid, [])
        cuerpo_id = hijos[0][0] if hijos else None

        lineas.append(
            f"{indent}for ({d.get('tipo_var','int')} {d.get('var','i')} = {d.get('inicio','0')}; "
            f"{d.get('cond','i < 5')}; "
            f"{d.get('var','i')} = {d.get('inc','i + 1')}) {{"
        )
        if cuerpo_id:
            _recorrer(cuerpo_id, hijos_de, nodo_por_id, set(visitados), lineas, indent + "    ")
        else:
            lineas.append(f"{indent}    // vacío")
        lineas.append(f"{indent}}};")
        return

    # ── Continuar con el siguiente nodo en la secuencia ──
    hijos     = hijos_de.get(nid, [])
    siguiente = next(
        (d for d, l in hijos if l.lower() not in ("no","false","n","salir")),
        hijos[0][0] if hijos else None
    )
    if siguiente:
        _recorrer(siguiente, hijos_de, nodo_por_id, visitados, lineas, indent)


# =============================================================
# COMPILADOR — Integración con los módulos del proyecto
# =============================================================

def imprimir_ast(nodo):
    """
    Convierte el árbol AST del compilador en un diccionario
    serializable para mostrarlo en la interfaz.
    """
    if isinstance(nodo, lexico.NodoPrograma):
        return {
            "programa":  "Noname",
            "funciones": [imprimir_ast(f) for f in nodo.funciones],
            "main":      imprimir_ast(nodo.main),
        }
    if isinstance(nodo, lexico.NodoFuncion):
        return {
            "nombre":     nodo.nombre[1],
            "parametros": [imprimir_ast(p) for p in nodo.parametros],
            "cuerpo":     [imprimir_ast(c) for c in nodo.cuerpo],
        }
    if isinstance(nodo, lexico.NodoParametro):
        return {"id": nodo.nombre[1], "tipo": nodo.tipo[1]}
    if isinstance(nodo, lexico.NodoAsignacion):
        return {"tipo": "asignacion", "var": nodo.nombre[1], "expr": imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoReasignacion):
        return {"tipo": "reasignacion", "var": nodo.nombre[1], "expr": imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoOperacion):
        return {"op": nodo.operador[1], "izq": imprimir_ast(nodo.izquierda), "der": imprimir_ast(nodo.derecha)}
    if isinstance(nodo, lexico.NodoRetorno):
        return {"tipo": "return", "valor": imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoIdentificador):
        return nodo.nombre[1]
    if isinstance(nodo, lexico.NodoNumero):
        return {"Numero": nodo.valor}
    if isinstance(nodo, lexico.NodoString):
        return {"String": nodo.valor[1] if isinstance(nodo.valor, tuple) else nodo.valor}
    if isinstance(nodo, lexico.NodoLlamadaFuncion):
        return {"LlamadaFuncion": nodo.nombre_funcion, "args": [imprimir_ast(a) for a in nodo.argumentos]}
    if isinstance(nodo, lexico.NodoPrint):
        return {"tipo": "print", "expr": imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoPrintln):
        return {"tipo": "println", "expr": imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoIf):
        n = {"tipo": "if", "cond": imprimir_ast(nodo.condicion),
             "si": [imprimir_ast(c) for c in nodo.cuerpo_if]}
        if nodo.cuerpo_else:
            n["no"] = [imprimir_ast(c) for c in nodo.cuerpo_else]
        return n
    if isinstance(nodo, lexico.NodoWhile):
        return {"tipo": "while", "cond": imprimir_ast(nodo.condicion),
                "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo]}
    if isinstance(nodo, lexico.NodoFor):
        return {"tipo": "for", "inicio": imprimir_ast(nodo.inicio),
                "cond": imprimir_ast(nodo.condicion), "inc": imprimir_ast(nodo.incremento),
                "cuerpo": [imprimir_ast(c) for c in nodo.cuerpo]}
    return {}


def limpiar_asm(asm):
    """Elimina comentarios del ASM para una salida más limpia."""
    lineas = []
    for linea in asm.splitlines():
        sin_comentario = linea.split(";", 1)[0].rstrip()
        if sin_comentario:
            lineas.append(sin_comentario)
    return "\n".join(lineas)


def _wsl_path(p):
    """Convierte una ruta Windows a formato WSL (/mnt/c/...)."""
    r = Path(p).resolve()
    u = r.drive.rstrip(":").lower()
    partes = [x for x in r.parts[1:] if x not in ("\\", "/")]
    return f"/mnt/{u}/" + "/".join(partes)


def _wsl(args):
    """Ejecuta un comando dentro de WSL (Ubuntu)."""
    return subprocess.run(
        ["wsl", "-d", "Ubuntu", "-e"] + args,
        capture_output=True, text=True
    )


def ejecutar_asm(asm, nb="programa"):
    """
    Guarda el ASM en disco, lo ensambla con nasm,
    lo linkea con ld y ejecuta el binario resultante.
    Retorna (stdout, stderr, exito).
    """
    win = platform.system() == "Windows"

    # Guardar el archivo .asm
    with open(f"{nb}.asm", "w", encoding="utf-8") as f:
        f.write(asm)

    # ── Paso 1: ensamblar con nasm ────────────────────────
    if win:
        b  = _wsl_path(Path.cwd())
        rn = _wsl(["/usr/bin/nasm", "-f", "elf32", f"{b}/{nb}.asm", "-o", f"{b}/{nb}.o"])
    else:
        rn = subprocess.run(
            ["nasm", "-f", "elf32", f"{nb}.asm", "-o", f"{nb}.o"],
            capture_output=True, text=True
        )
    if rn.returncode != 0:
        return None, f"Error nasm:\n{rn.stderr}", False

    # ── Paso 2: linkear con ld ────────────────────────────
    if win:
        b  = _wsl_path(Path.cwd())
        rl = _wsl(["/usr/bin/ld", "-m", "elf_i386", f"{b}/{nb}.o", "-o", f"{b}/{nb}"])
    else:
        rl = subprocess.run(
            ["ld", "-m", "elf_i386", f"{nb}.o", "-o", nb],
            capture_output=True, text=True
        )
    if rl.returncode != 0:
        return None, f"Error ld:\n{rl.stderr}", False

    # ── Paso 3: ejecutar el binario ───────────────────────
    if win:
        b  = _wsl_path(Path.cwd())
        rr = _wsl([f"{b}/{nb}"])
    else:
        rr = subprocess.run([f"./{nb}"], capture_output=True, text=True)

    return rr.stdout, rr.stderr, rr.returncode == 0


def compilar_codigo(codigo):
    """
    Ejecuta las 4 fases del compilador sobre el código dado:
    1. Análisis léxico     → tokens
    2. Análisis sintáctico → AST
    3. Análisis semántico  → validación
    4. Generación de ASM   → código ensamblador
    5. Ensamblado y ejecución (si nasm está disponible)

    Retorna un diccionario con los resultados de cada fase.
    """
    r = dict(
        tokens=None, ast=None, asm=None,
        stdout=None, stderr=None,
        ejecutado=False, error=None, fase=None
    )

    # Fase 1 — Léxico
    try:
        toks      = lexico.identificar_tokens(codigo)
        r["tokens"] = toks
    except Exception as e:
        r["fase"] = "léxico"; r["error"] = str(e); return r

    # Fase 2 — Sintáctico
    try:
        arbol = sintactico_ast.Parser(toks).parsear()
    except Exception as e:
        r["fase"] = "sintáctico"; r["error"] = str(e); return r

    # Fase 3 — Semántico
    try:
        semantico.AnalizadorSemantico().analizar(arbol)
    except Exception as e:
        r["fase"] = "semántico"; r["error"] = str(e); return r

    # Guardar AST serializado
    r["ast"] = imprimir_ast(arbol)

    # Fase 4 — Generación de ASM
    try:
        asm_completo = arbol.generarCodigo()
        r["asm"]     = limpiar_asm(asm_completo)
    except Exception as e:
        r["fase"] = "generación ASM"; r["error"] = str(e); return r

    # Fase 5 — Ensamblado y ejecución
    try:
        so, se, ok     = ejecutar_asm(asm_completo)
        r["stdout"]    = so
        r["stderr"]    = se
        r["ejecutado"] = ok
    except FileNotFoundError:
        r["stderr"] = (
            "nasm/ld no encontrado.\n"
            "El ASM fue generado correctamente.\n"
            "Para ejecutar instala nasm en WSL:\n"
            "  sudo apt install nasm"
        )

    return r


# =============================================================
# DIÁLOGO PARA EDITAR UN NODO
# =============================================================

class DialogoNodo(tk.Toplevel):
    """
    Ventana modal que permite editar los campos de un nodo
    del diagrama (tipo de dato, nombre, condición, etc.)
    """

    def __init__(self, parent, tipo, datos):
        super().__init__(parent)
        self.title(f"Editar — {tipo}")
        self.resizable(False, False)
        self.configure(bg=BG2)
        self.grab_set()
        self.resultado = None

        bg, fg = TIPO_COLOR.get(tipo, (MUTED, "#fff"))

        # Cabecera coloreada con el nombre actual del nodo
        hdr = tk.Frame(self, bg=bg, pady=10)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=f"  ✏  {etiqueta_nodo(tipo, datos)}",
            bg=bg, fg=fg, font=("Segoe UI", 11, "bold")
        ).pack(side="left", padx=12)

        # Cuerpo con los campos editables
        body = tk.Frame(self, bg=BG2, padx=20, pady=10)
        body.pack(fill="x")

        campos = CAMPOS.get(tipo, [])
        self._vars = {}

        if not campos:
            tk.Label(
                body, text="Este nodo no tiene parámetros editables.",
                bg=BG2, fg=MUTED, font=("Segoe UI", 10)
            ).pack()

        for key, label, ph in campos:
            tk.Label(
                body, text=label, bg=BG2, fg=MUTED,
                font=("Segoe UI", 9, "bold"), anchor="w"
            ).pack(fill="x", pady=(8, 2))

            var   = tk.StringVar(value=datos.get(key, ph))
            entry = tk.Entry(
                body, textvariable=var,
                bg=BG3, fg=TEXT, font=("Courier New", 11),
                relief="flat", insertbackground=ACCENT, bd=4, width=32
            )
            entry.pack(fill="x", ipady=5)
            self._vars[key] = var

        # Botones de acción
        btns = tk.Frame(self, bg=BG2, pady=12, padx=20)
        btns.pack(fill="x")

        tk.Button(
            btns, text="Cancelar", bg=BG3, fg=MUTED,
            font=("Segoe UI", 10), relief="flat", padx=12, pady=5,
            cursor="hand2", command=self.destroy
        ).pack(side="right", padx=(4, 0))

        tk.Button(
            btns, text="Guardar", bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=12, pady=5,
            cursor="hand2", command=self._ok
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.wait_window()

    def _ok(self):
        """Guarda los valores del formulario y cierra el diálogo."""
        self.resultado = {k: v.get() for k, v in self._vars.items()}
        self.destroy()


# =============================================================
# CANVAS DEL DIAGRAMA DE FLUJO
# =============================================================

class DiagramaCanvas(tk.Frame):
    """
    Canvas interactivo principal del entorno.
    Permite al usuario:
      - Arrastrar instrucciones desde la paleta al canvas
      - Mover nodos libremente (modo Mover)
      - Conectar nodos con flechas (modo Conectar)
      - Editar nodos con doble clic
      - Eliminar nodos con la tecla Supr
    """

    def __init__(self, parent, on_codigo_change):
        super().__init__(parent, bg=BG)

        # Callback que se llama cada vez que el diagrama cambia
        self._on_codigo  = on_codigo_change

        # Estado interno
        self._nodos      = []       # Lista de dicts con info de cada nodo
        self._conexiones = []       # Lista de (src_id, dst_id, etiqueta)
        self._sel        = None     # Nodo actualmente seleccionado
        self._modo       = "mover"  # Modo actual: "mover" | "conectar"
        self._conn_src   = None     # Nodo origen al conectar
        self._drag_off   = (0, 0)   # Offset para arrastre suave
        self._ghost      = None     # Ventana fantasma al arrastrar desde paleta
        self._ghost_tipo = None     # Tipo del nodo siendo arrastrado
        self._next_id    = 1        # Contador de IDs de nodos
        self._prev_line  = None     # Línea de previsualización al conectar

        self._build()

    # ── CONSTRUCCIÓN DEL WIDGET ───────────────────────────

    def _build(self):
        """Construye el canvas con scrollbars y configura los eventos."""
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="both", expand=True)

        # Canvas principal
        self._cv = tk.Canvas(frm, bg="#fafaf8", highlightthickness=0)

        # Scrollbars
        vsb = ttk.Scrollbar(frm, orient="vertical",   command=self._cv.yview)
        hsb = ttk.Scrollbar(frm, orient="horizontal", command=self._cv.xview)
        self._cv.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            scrollregion=(-800, -800, 3000, 3000)
        )

        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        self._cv.pack(side="left", fill="both", expand=True)

        # Grid de fondo
        self._dibujar_grid()

        # Eventos del canvas
        self._cv.bind("<ButtonPress-1>",   self._on_press)
        self._cv.bind("<B1-Motion>",       self._on_drag)
        self._cv.bind("<ButtonRelease-1>", self._on_release)
        self._cv.bind("<Double-Button-1>", self._on_dbl)
        self._cv.bind("<ButtonPress-3>",   self._pan_start)
        self._cv.bind("<B3-Motion>",       self._pan_move)
        self._cv.bind("<MouseWheel>",      self._wheel)
        self._cv.bind("<Delete>",          lambda e: self._borrar_sel())
        self._cv.bind("<BackSpace>",       lambda e: self._borrar_sel())
        self._cv.focus_set()

    def _dibujar_grid(self):
        """Dibuja la cuadrícula de fondo del canvas."""
        for x in range(-800, 3001, 40):
            self._cv.create_line(x, -800, x, 3000, fill="#edebe6", width=1, tags="grid")
        for y in range(-800, 3001, 40):
            self._cv.create_line(-800, y, 3000, y, fill="#edebe6", width=1, tags="grid")
        self._cv.tag_lower("grid")

    # ── CONTROL DE MODO ───────────────────────────────────

    def set_modo(self, modo):
        """Cambia entre modo mover y modo conectar."""
        self._modo     = modo
        self._conn_src = None

        # Limpiar línea de previsualización
        if self._prev_line:
            self._cv.delete(self._prev_line)
            self._prev_line = None

        # Cambiar cursor según el modo
        self._cv.config(cursor="fleur" if modo == "mover" else "crosshair")

    # ── GESTIÓN DE NODOS ──────────────────────────────────

    def agregar_nodo(self, tipo, x=None, y=None):
        """
        Crea un nuevo nodo en la posición (x, y).
        Si no se especifica posición, lo coloca en el centro del canvas.
        """
        if x is None:
            x = self._cv.winfo_width()  // 2 + self._cv.canvasx(0)
            y = self._cv.winfo_height() // 2 + self._cv.canvasy(0)

        nid  = self._next_id
        self._next_id += 1

        nodo = {
            "id":    nid,
            "tipo":  tipo,
            "x":     int(x),
            "y":     int(y),
            "datos": defaults(tipo),
            "cids":  [],   # IDs de elementos canvas del nodo
        }
        self._nodos.append(nodo)
        self._dibujar_nodo(nodo)
        self._on_codigo()
        return nodo

    def redibujar_todo(self):
        """Redibuja todos los nodos del diagrama."""
        for n in self._nodos:
            self._dibujar_nodo(n)

    # ── DIBUJO DE NODOS ───────────────────────────────────

    def _dibujar_nodo(self, nodo):
        """
        Dibuja un nodo en el canvas según su tipo, posición
        y estado (seleccionado o no).
        """
        # Borrar elementos anteriores del nodo
        for cid in nodo["cids"]:
            self._cv.delete(cid)
        nodo["cids"] = []

        x, y   = nodo["x"], nodo["y"]
        tipo   = nodo["tipo"]
        bg, fg = TIPO_COLOR.get(tipo, (MUTED, "#fff"))
        forma  = TIPO_FORMA.get(tipo, "rect")
        sel    = nodo.get("sel", False)
        tag    = f"nodo_{nodo['id']}"
        w, h   = NW, NH
        ids    = []

        # Sombra del nodo
        ids.append(self._cv.create_rectangle(
            x - w//2 + 4, y - h//2 + 4,
            x + w//2 + 4, y + h//2 + 4,
            fill="#d0ccc4", outline="", tags=(tag, "sombra")
        ))

        # ── Forma principal según tipo ────────────────────
        borde = "#ffffff" if sel else bg
        ancho = 3 if sel else 0

        if forma == "oval":
            ids.append(self._cv.create_oval(
                x - w//2, y - h//2, x + w//2, y + h//2,
                fill=bg, outline=borde, width=ancho,
                tags=(tag, "cuerpo")
            ))

        elif forma == "diamond":
            hw, hh = w//2 + 10, h//2 + 10
            pts    = [x, y - hh, x + hw, y, x, y + hh, x - hw, y]
            ids.append(self._cv.create_polygon(
                pts, fill=bg, outline=borde, width=ancho,
                tags=(tag, "cuerpo")
            ))

        elif forma == "parall":
            off = 14
            pts = [
                x - w//2 + off, y - h//2,
                x + w//2 + off, y - h//2,
                x + w//2 - off, y + h//2,
                x - w//2 - off, y + h//2,
            ]
            ids.append(self._cv.create_polygon(
                pts, fill=bg, outline=borde, width=ancho,
                tags=(tag, "cuerpo")
            ))

        else:  # rect
            ids.append(self._cv.create_rectangle(
                x - w//2, y - h//2, x + w//2, y + h//2,
                fill=bg, outline=borde, width=ancho,
                tags=(tag, "cuerpo")
            ))

        # Texto del nodo (truncado si es muy largo)
        label = etiqueta_nodo(tipo, nodo["datos"])
        if len(label) > 20:
            label = label[:18] + "…"

        ids.append(self._cv.create_text(
            x, y, text=label, fill=fg,
            font=("Segoe UI", 9, "bold"),
            width=NW - 20, tags=(tag, "texto")
        ))

        nodo["cids"] = ids

        # Mantener orden visual: grid al fondo, sombras bajo nodos
        self._cv.tag_lower("sombra")
        self._cv.tag_lower("grid")

        # Redibujar conexiones para que queden sobre la grid
        self._redibujar_conexiones()

    def _redibujar_conexiones(self):
        """
        Redibuja todas las flechas de conexión entre nodos.
        Detecta flechas de retorno (cuando el destino está más
        arriba que el origen) y las dibuja por la izquierda con
        color y estilo diferente para mayor claridad visual.
        """
        self._cv.delete("conexion")
        por_id = {n["id"]: n for n in self._nodos}

        for src_id, dst_id, lbl in self._conexiones:
            s = por_id.get(src_id)
            d = por_id.get(dst_id)
            if not s or not d:
                continue

            extra_s = 12 if TIPO_FORMA.get(s["tipo"]) == "diamond" else 0
            extra_d = 12 if TIPO_FORMA.get(d["tipo"]) == "diamond" else 0

            x1, y1 = s["x"], s["y"] + NH//2 + extra_s
            x2, y2 = d["x"], d["y"] - NH//2 - extra_d

            # ── Detectar flecha de retorno (destino arriba del origen) ──
            es_retorno = y2 < y1 - 20

            if es_retorno:
                # Flecha de retorno: 4 segmentos en ángulo recto
                # Baja → izquierda → sube → derecha hasta el nodo destino
                margen = min(s["x"], d["x"]) - 80  # columna por la que sube

                # Segmento 1: baja del nodo origen
                self._cv.create_line(
                    x1, y1, x1, y1 + 20,
                    fill=ACCENT, width=2, tags="conexion"
                )
                # Segmento 2: va hacia la izquierda
                self._cv.create_line(
                    x1, y1 + 20, margen, y1 + 20,
                    fill=ACCENT, width=2, tags="conexion"
                )
                # Segmento 3: sube por la izquierda
                self._cv.create_line(
                    margen, y1 + 20, margen, y2,
                    fill=ACCENT, width=2, tags="conexion"
                )
                # Segmento 4: entra al nodo destino con flecha
                self._cv.create_line(
                    margen, y2, x2, y2,
                    arrow="last", arrowshape=(12, 14, 5),
                    fill=ACCENT, width=2, tags="conexion"
                )

                # Etiqueta en el segmento vertical izquierdo
                mid_y = (y1 + y2) // 2
                self._cv.create_rectangle(
                    margen - 16, mid_y - 9,
                    margen + 16, mid_y + 9,
                    fill=BG2, outline=ACCENT, width=1, tags="conexion"
                )
                self._cv.create_text(
                    margen, mid_y,
                    text=lbl if lbl else "↺",
                    fill=ACCENT, font=("Segoe UI", 8, "bold"),
                    tags="conexion"
                )

            else:
                # ── Flecha normal: codo vertical ──────────────────────
                my = (y1 + y2) // 2
                self._cv.create_line(
                    x1, y1, x1, my, x2, my, x2, y2,
                    arrow="last", arrowshape=(12, 14, 5),
                    fill=MUTED, width=2, smooth=False, tags="conexion"
                )

                # Etiqueta (Sí / No)
                if lbl:
                    # Colocar la etiqueta cerca del punto de bifurcación
                    lbl_x = (x1 + x2) // 2 + (30 if x2 > x1 else -30)
                    lbl_y = my - 12
                    # Fondo blanco para legibilidad
                    self._cv.create_rectangle(
                        lbl_x - 14, lbl_y - 9,
                        lbl_x + 14, lbl_y + 9,
                        fill=BG2, outline=BORDER, width=1, tags="conexion"
                    )
                    self._cv.create_text(
                        lbl_x, lbl_y,
                        text=lbl, fill=AMBER,
                        font=("Segoe UI", 8, "bold"), tags="conexion"
                    )

        self._cv.tag_lower("conexion")
        self._cv.tag_lower("grid")

    # ── EVENTOS DEL CANVAS ────────────────────────────────

    def _on_press(self, e):
        """Maneja el clic en el canvas según el modo activo."""
        cx, cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        nodo   = self._nodo_en(cx, cy)

        # ── Modo conectar ─────────────────────────────────
        if self._modo == "conectar":
            if nodo:
                if self._conn_src is None:
                    # Primer clic: seleccionar nodo origen
                    self._conn_src = nodo
                    self._seleccionar(nodo)
                else:
                    # Segundo clic: crear conexión hacia el destino
                    if nodo["id"] != self._conn_src["id"]:
                        lbl = ""
                        # Pedir etiqueta si el origen es una estructura de control
                        if self._conn_src["tipo"] in ("if", "while", "for"):
                            lbl = self._pedir_label()
                        self._conexiones.append((self._conn_src["id"], nodo["id"], lbl))
                        self._redibujar_conexiones()
                        self._on_codigo()

                    # Resetear estado de conexión
                    self._conn_src = None
                    if self._prev_line:
                        self._cv.delete(self._prev_line)
                        self._prev_line = None
                    self._deseleccionar()
            return

        # ── Modo mover ────────────────────────────────────
        if nodo:
            self._seleccionar(nodo)
            self._drag_off = (cx - nodo["x"], cy - nodo["y"])
        else:
            self._deseleccionar()

    def _on_drag(self, e):
        """Maneja el arrastre del ratón."""
        cx, cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)

        if self._modo == "conectar":
            # Dibujar línea de previsualización al conectar
            if self._conn_src:
                if self._prev_line:
                    self._cv.delete(self._prev_line)
                sx, sy = self._conn_src["x"], self._conn_src["y"] + NH//2
                self._prev_line = self._cv.create_line(
                    sx, sy, cx, cy,
                    fill=GREEN, width=2, dash=(6, 3),
                    arrow="last", arrowshape=(10, 12, 4),
                    tags="prev_line"
                )
            return

        # Mover el nodo seleccionado
        if self._sel:
            self._sel["x"] = int(cx - self._drag_off[0])
            self._sel["y"] = int(cy - self._drag_off[1])
            self._dibujar_nodo(self._sel)

    def _on_release(self, e):
        """Al soltar el ratón, notifica el cambio de código."""
        self._on_codigo()

    def _on_dbl(self, e):
        """Doble clic: abre el diálogo de edición del nodo."""
        cx, cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        nodo   = self._nodo_en(cx, cy)

        if nodo:
            dlg = DialogoNodo(self.winfo_toplevel(), nodo["tipo"], nodo["datos"])
            if dlg.resultado:
                nodo["datos"].update(dlg.resultado)
                self._dibujar_nodo(nodo)
                self._on_codigo()

    def _pan_start(self, e):
        """Inicia el paneo del canvas con clic derecho."""
        self._cv.scan_mark(e.x, e.y)

    def _pan_move(self, e):
        """Mueve la vista del canvas (paneo)."""
        self._cv.scan_dragto(e.x, e.y, gain=1)

    def _wheel(self, e):
        """Zoom in/out con la rueda del ratón."""
        factor = 1.1 if e.delta > 0 else 1 / 1.1
        cx, cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        self._cv.scale("all", cx, cy, factor, factor)
        self._cv.configure(scrollregion=self._cv.bbox("all"))

    # ── SELECCIÓN DE NODOS ────────────────────────────────

    def _seleccionar(self, nodo):
        """Selecciona un nodo y lo resalta visualmente."""
        self._deseleccionar()
        self._sel      = nodo
        nodo["sel"]    = True
        self._dibujar_nodo(nodo)

    def _deseleccionar(self):
        """Quita la selección del nodo actual."""
        if self._sel:
            self._sel["sel"] = False
            self._dibujar_nodo(self._sel)
            self._sel = None

    # ── ARRASTRE DESDE LA PALETA ──────────────────────────

    def iniciar_drag_paleta(self, tipo, x_root, y_root):
        """
        Inicia el arrastre de un bloque desde la paleta.
        Muestra una ventana fantasma que sigue al cursor.
        """
        self._ghost_tipo = tipo

        # Destruir fantasma anterior si existe
        if self._ghost:
            self._ghost.destroy()

        # Crear ventana fantasma
        g = tk.Toplevel(self)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.75)
        g.attributes("-topmost", True)

        bg, fg = TIPO_COLOR.get(tipo, (MUTED, "#fff"))
        tk.Label(
            g, text=f"  {etiqueta_nodo(tipo, defaults(tipo))}  ",
            bg=bg, fg=fg, font=("Segoe UI", 9, "bold"),
            relief="solid", bd=1, padx=8, pady=5
        ).pack()

        g.geometry(f"+{x_root + 10}+{y_root + 10}")
        self._ghost = g

        # Bindear movimiento y soltar al nivel de la ventana principal
        self.winfo_toplevel().bind("<Motion>",          self._mover_ghost)
        self.winfo_toplevel().bind("<ButtonRelease-1>", self._soltar_paleta)

    def _mover_ghost(self, e):
        """Mueve la ventana fantasma siguiendo el cursor."""
        if self._ghost:
            self._ghost.geometry(f"+{e.x_root + 10}+{e.y_root + 10}")

    def _soltar_paleta(self, e):
        """
        Al soltar el botón sobre el canvas, crea el nodo en esa posición.
        Si se soltó fuera del canvas, no hace nada.
        """
        # Limpiar bindings temporales
        self.winfo_toplevel().unbind("<Motion>")
        self.winfo_toplevel().unbind("<ButtonRelease-1>")

        if self._ghost:
            self._ghost.destroy()
            self._ghost = None

        if not self._ghost_tipo:
            return

        # Verificar si se soltó dentro del canvas
        cx0 = self._cv.winfo_rootx()
        cy0 = self._cv.winfo_rooty()
        cw  = self._cv.winfo_width()
        ch  = self._cv.winfo_height()

        if cx0 <= e.x_root <= cx0 + cw and cy0 <= e.y_root <= cy0 + ch:
            # Convertir coordenadas de pantalla a coordenadas del canvas
            cv_x = self._cv.canvasx(e.x_root - cx0)
            cv_y = self._cv.canvasy(e.y_root - cy0)
            self.agregar_nodo(self._ghost_tipo, cv_x, cv_y)

        self._ghost_tipo = None

    # ── UTILIDADES ────────────────────────────────────────

    def _nodo_en(self, cx, cy):
        """Devuelve el nodo que contiene el punto (cx, cy), o None."""
        for n in reversed(self._nodos):
            dx    = abs(cx - n["x"])
            dy    = abs(cy - n["y"])
            forma = TIPO_FORMA.get(n["tipo"], "rect")
            hw    = NW//2 + (10 if forma == "diamond" else 0)
            hh    = NH//2 + (10 if forma == "diamond" else 0)
            if dx <= hw and dy <= hh:
                return n
        return None

    def _borrar_sel(self):
        """Elimina el nodo seleccionado y sus conexiones."""
        if not self._sel:
            return
        nid = self._sel["id"]

        # Borrar elementos del canvas
        for cid in self._sel["cids"]:
            self._cv.delete(cid)

        # Eliminar de las listas internas
        self._nodos      = [n for n in self._nodos if n["id"] != nid]
        self._conexiones = [(s, d, l) for s, d, l in self._conexiones if s != nid and d != nid]
        self._sel        = None

        self._redibujar_conexiones()
        self._on_codigo()

    def borrar_conexion_sel(self):
        """Elimina la última conexión agregada."""
        if self._conexiones:
            self._conexiones.pop()
            self._redibujar_conexiones()
            self._on_codigo()

    def limpiar(self):
        """Elimina todos los nodos y conexiones del canvas."""
        self._cv.delete("all")
        self._nodos.clear()
        self._conexiones.clear()
        self._sel        = None
        self._conn_src   = None
        self._dibujar_grid()
        self._on_codigo()

    def _pedir_label(self):
        """
        Muestra un diálogo para ingresar la etiqueta de una flecha
        (usado al conectar desde nodos if/while/for).
        """
        dlg = tk.Toplevel(self)
        dlg.title("Etiqueta de la flecha")
        dlg.resizable(False, False)
        dlg.configure(bg=BG2)
        dlg.grab_set()
        result = [""]

        tk.Label(
            dlg, text="Etiqueta (ej: Sí, No, True, False…)",
            bg=BG2, fg=MUTED, font=("Segoe UI", 9)
        ).pack(padx=16, pady=(12, 4))

        var   = tk.StringVar(value="")
        entry = tk.Entry(
            dlg, textvariable=var,
            bg=BG3, fg=TEXT, font=("Courier New", 11),
            relief="flat", bd=4, width=22
        )
        entry.pack(padx=16, ipady=4)
        entry.focus_set()

        def ok(ev=None):
            result[0] = var.get()
            dlg.destroy()

        entry.bind("<Return>", ok)

        tk.Button(
            dlg, text="OK", bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=10, pady=4, cursor="hand2", command=ok
        ).pack(pady=10)

        dlg.wait_window()
        return result[0]

    def obtener_codigo(self):
        """Genera y devuelve el código C-like del diagrama actual."""
        return diagrama_a_codigo(self._nodos, self._conexiones)


# =============================================================
# PALETA LATERAL DE INSTRUCCIONES
# =============================================================

# Elementos de la paleta: (tipo, etiqueta_visible)
PALETA_ITEMS = [
    ("inicio",    "⬟  INICIO"),
    ("fin",       "⬟  FIN"),
    ("asignar",   "▭  int x = 0"),
    ("reasignar", "▭  x = expr"),
    ("print",     "▱  print(…)"),
    ("println",   "▱  println(…)"),
    ("if",        "◇  if (…)"),
    ("while",     "◇  while (…)"),
    ("for",       "◇  for (…)"),
    ("return",    "▭  return …"),
    ("funcion",   "▭  función"),
    ("llamada",   "▭  f(…)"),
]


class PaletaLateral(tk.Frame):
    """
    Panel lateral con los tipos de instrucciones disponibles.
    Cada botón se puede arrastrar al canvas para crear un nodo.
    """

    def __init__(self, parent, diagrama: DiagramaCanvas):
        super().__init__(parent, bg=BG2, width=162)
        self.pack_propagate(False)
        self._diag = diagrama
        self._build()

    def _build(self):
        """Construye la lista de botones de instrucciones."""
        # Título de la sección
        tk.Label(
            self, text="INSTRUCCIONES", bg=BG3, fg=MUTED,
            font=("Segoe UI", 8, "bold"), pady=7
        ).pack(fill="x")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Contenedor de tooltips (compartido entre botones)
        tip_ref = [None]

        for tipo, label in PALETA_ITEMS:
            bg, fg = TIPO_COLOR.get(tipo, (BG4, TEXT))

            btn = tk.Button(
                self, text=label, bg=bg, fg=fg,
                font=("Courier New", 9, "bold"),
                relief="flat", bd=0, pady=6, padx=8,
                anchor="w", cursor="hand2",
                activebackground=bg, activeforeground=fg
            )
            btn.pack(fill="x", padx=6, pady=2)

            # Iniciar arrastre al presionar el botón
            btn.bind(
                "<ButtonPress-1>",
                lambda e, t=tipo: self._diag.iniciar_drag_paleta(t, e.x_root, e.y_root)
            )

            # Tooltip al pasar el cursor
            def show(e, t=tipo, tr=tip_ref):
                if tr[0]:
                    tr[0].destroy()
                tip = tk.Toplevel(self)
                tip.overrideredirect(True)
                tip.attributes("-topmost", True)
                tk.Label(
                    tip, text="Arrastra al diagrama",
                    bg="#ffffcc", fg=TEXT, font=("Segoe UI", 8),
                    padx=5, pady=2, relief="solid", bd=1
                ).pack()
                tip.geometry(f"+{e.x_root + 16}+{e.y_root + 12}")
                tr[0] = tip

            def hide(e, tr=tip_ref):
                if tr[0]:
                    tr[0].destroy()
                    tr[0] = None

            btn.bind("<Enter>", show)
            btn.bind("<Leave>", hide)


# =============================================================
# VENTANA PRINCIPAL DEL IDE
# =============================================================

class CompiladorIDE(tk.Tk):
    """
    Ventana principal del entorno de programación visual.
    Integra el diagrama de flujo, la paleta de instrucciones
    y las pestañas de resultados (Código, Tokens, AST, ASM, Consola).
    """

    def __init__(self):
        super().__init__()
        self.title("CompiladorIDE — Diagrama de Flujo")
        self.geometry("1380x800")
        self.minsize(1000, 640)
        self.configure(bg=BG)

        self._build_ui()
        self._init_ejemplo()

    def _init_ejemplo(self):
        """Carga un diagrama de ejemplo al iniciar la aplicación."""
        cv = self._diagrama

        # Crear nodos del ejemplo
        n0 = cv.agregar_nodo("inicio",   400, 80)
        n1 = cv.agregar_nodo("asignar",  400, 190)
        n2 = cv.agregar_nodo("asignar",  400, 300)
        n3 = cv.agregar_nodo("println",  400, 410)
        n4 = cv.agregar_nodo("fin",      400, 510)

        # Configurar datos de los nodos
        n1["datos"].update({"tipo_var": "int", "nombre": "a", "valor": "5"})
        n2["datos"].update({"tipo_var": "int", "nombre": "b", "valor": "3"})
        n3["datos"].update({"expr": "a"})

        # Crear conexiones entre nodos
        cv._conexiones = [
            (n0["id"], n1["id"], ""),
            (n1["id"], n2["id"], ""),
            (n2["id"], n3["id"], ""),
            (n3["id"], n4["id"], ""),
        ]

        cv.redibujar_todo()

    # ── CONSTRUCCIÓN DE LA INTERFAZ ───────────────────────

    def _build_ui(self):
        """Construye todos los componentes de la interfaz."""
        self._build_topbar()
        self._build_modebar()
        self._build_body()
        self._build_statusbar()

    def _build_topbar(self):
        """Barra superior con logo, título y botones principales."""
        bar = tk.Frame(self, bg=BG2, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Logo
        tk.Frame(bar, bg=ACCENT, width=30, height=30).place(x=12, y=11)
        tk.Label(
            bar, text="⚙", bg=ACCENT, fg="white", font=("Segoe UI", 13)
        ).place(x=12, y=11, width=30, height=30)

        tk.Label(
            bar, text="  CompiladorIDE", bg=BG2, fg=ACCENT,
            font=("Segoe UI", 13, "bold")
        ).pack(side="left", padx=(50, 0))

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=12, pady=10)

        tk.Label(
            bar, text="Diagrama de flujo → Código → Tokens → AST → ASM",
            bg=BG2, fg=MUTED, font=("Courier New", 9)
        ).pack(side="left")

        # Botones de acción
        right = tk.Frame(bar, bg=BG2)
        right.pack(side="right", padx=12)

        self._btn_comp = tk.Button(
            right, text="▶  Compilar y Ejecutar",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._on_compilar
        )
        self._btn_comp.pack(side="right", padx=(6, 0))

        tk.Button(
            right, text="✕  Limpiar",
            bg=BG3, fg=MUTED,
            font=("Segoe UI", 10), relief="flat",
            padx=12, pady=6, cursor="hand2",
            command=self._on_limpiar
        ).pack(side="right")

    def _build_modebar(self):
        """Barra de modo con controles para mover, conectar y borrar."""
        bar = tk.Frame(self, bg=BG3, height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar, text="  Modo:", bg=BG3, fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", pady=6)

        # Botón modo Mover
        self._btn_mover = tk.Button(
            bar, text="✥ Mover nodos",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4,
            cursor="hand2",
            command=lambda: self._set_modo("mover")
        )
        self._btn_mover.pack(side="left", padx=(6, 2), pady=4)

        # Botón modo Conectar
        self._btn_conn = tk.Button(
            bar, text="→ Conectar con flecha",
            bg=BG4, fg=TEXT,
            font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4,
            cursor="hand2",
            command=lambda: self._set_modo("conectar")
        )
        self._btn_conn.pack(side="left", padx=2, pady=4)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=6)

        # Botón borrar nodo
        tk.Button(
            bar, text="🗑 Borrar nodo (Supr)",
            bg=BG4, fg=RED,
            font=("Segoe UI", 9), relief="flat",
            padx=10, pady=4, cursor="hand2",
            command=lambda: self._diagrama._borrar_sel()
        ).pack(side="left", padx=2, pady=4)

        # Botón quitar última flecha
        tk.Button(
            bar, text="✂ Quitar última flecha",
            bg=BG4, fg=MUTED,
            font=("Segoe UI", 9), relief="flat",
            padx=10, pady=4, cursor="hand2",
            command=lambda: self._diagrama.borrar_conexion_sel()
        ).pack(side="left", padx=2, pady=4)

        # Indicador del modo actual
        self._modo_lbl = tk.Label(
            bar, text="  ✥  Arrastra nodos libremente",
            bg=BG3, fg=ACCENT, font=("Segoe UI", 9, "bold")
        )
        self._modo_lbl.pack(side="right", padx=12)

    def _build_body(self):
        """Panel principal dividido en diagrama (izq) y resultados (der)."""
        paned = tk.PanedWindow(
            self, orient="horizontal",
            bg=BORDER, sashwidth=4, sashrelief="flat"
        )
        paned.pack(fill="both", expand=True)

        # ── Panel izquierdo: paleta + canvas ─────────────
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=340, width=580)

        # Crear diagrama primero (la paleta lo necesita como referencia)
        self._diagrama = DiagramaCanvas(left, self._on_codigo_change)
        paleta = PaletaLateral(left, self._diagrama)
        paleta.pack(side="left", fill="y")
        tk.Frame(left, bg=BORDER, width=1).pack(side="left", fill="y")
        self._diagrama.pack(side="left", fill="both", expand=True)

        # ── Panel derecho: pestañas de resultados ─────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=300)
        self._build_tabs(right)

    def _build_tabs(self, parent):
        """Construye las pestañas de resultados del compilador."""
        style = ttk.Style()
        style.configure("IDE.TNotebook",     background=BG2, borderwidth=0)
        style.configure("IDE.TNotebook.Tab", background=BG3, foreground=MUTED,
                        padding=[12, 6], font=("Segoe UI", 10, "bold"))
        style.map("IDE.TNotebook.Tab",
                  background=[("selected", BG2)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(parent, style="IDE.TNotebook")
        nb.pack(fill="both", expand=True)
        self._nb = nb

        # Pestaña 0: Código generado
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="📄 Código")
        self._cod_text = self._make_text(f)

        # Pestaña 1: Tokens
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="◆ Tokens")
        self._build_tokens_tab(f)

        # Pestaña 2: AST (JSON)
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="⬡ AST")
        self._ast_text = self._make_text(f)

        # Pestaña 3: ASM generado
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="⚙ ASM")
        self._asm_text = self._make_text(f)
        self._asm_text.tag_config("sec", foreground=PINK,  font=("Courier New", 11, "bold"))
        self._asm_text.tag_config("lbl", foreground=BLUE,  font=("Courier New", 11, "bold"))
        self._asm_text.tag_config("cmt", foreground=MUTED, font=("Courier New", 11, "italic"))

        # Pestaña 4: Consola de salida
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="▸ Consola")
        self._console = self._make_text(f)
        for tag, col in [
            ("ok",   GREEN),
            ("err",  RED),
            ("warn", AMBER),
            ("out",  TEAL),
            ("info", MUTED),
        ]:
            self._console.tag_config(tag, foreground=col)

    def _build_tokens_tab(self, parent):
        """Construye la tabla de tokens con colores por tipo."""
        style = ttk.Style()
        style.configure("Tok.Treeview",
                        background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=24,
                        font=("Courier New", 11))
        style.configure("Tok.Treeview.Heading",
                        background=BG3, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Tok.Treeview",
                  background=[("selected", "#d4d0f8")],
                  foreground=[("selected", ACCENT)])

        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="both", expand=True, padx=10, pady=8)

        self._tree = ttk.Treeview(
            frm, columns=("#", "Tipo", "Valor"),
            show="headings", style="Tok.Treeview"
        )
        self._tree.heading("#",     text="#")
        self._tree.heading("Tipo",  text="TIPO")
        self._tree.heading("Valor", text="VALOR")
        self._tree.column("#",     width=40,  anchor="center", stretch=False)
        self._tree.column("Tipo",  width=130, anchor="w",      stretch=False)
        self._tree.column("Valor", width=300, anchor="w")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Colores por tipo de token
        for tag, col in [
            ("KEYWORD",    ACCENT),
            ("IDENTIFIER", BLUE),
            ("NUMBER",     GREEN),
            ("STRING",     AMBER),
            ("OPERATOR",   ORANGE),
            ("DELIMITER",  TEAL),
            ("UNKNOWN",    RED),
        ]:
            self._tree.tag_configure(tag, foreground=col)

    def _build_statusbar(self):
        """Barra de estado inferior con indicador y contador de nodos."""
        bar = tk.Frame(self, bg=BG3, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._dot = tk.Label(
            bar, text="●", bg=BG3, fg=GREEN, font=("Segoe UI", 9)
        )
        self._dot.pack(side="left", padx=(10, 4))

        self._status = tk.Label(
            bar, text="Listo — arrastra instrucciones al diagrama",
            bg=BG3, fg=MUTED, font=("Segoe UI", 9)
        )
        self._status.pack(side="left")

        self._ncount = tk.Label(
            bar, text="0 nodos", bg=BG3, fg=MUTED, font=("Segoe UI", 9)
        )
        self._ncount.pack(side="right", padx=10)

    def _make_text(self, parent):
        """Crea un widget Text con scrollbars para mostrar resultados."""
        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="both", expand=True, padx=10, pady=8)

        txt = tk.Text(
            frm, bg=BG2, fg=TEXT, font=("Courier New", 11),
            relief="flat", bd=0, wrap="none",
            padx=10, pady=8, state="disabled",
            selectbackground="#d4d0f8"
        )

        vsb = ttk.Scrollbar(frm, orient="vertical",   command=txt.yview)
        hsb = ttk.Scrollbar(frm, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        txt.pack(side="left",   fill="both", expand=True)

        return txt

    # ── LÓGICA DEL IDE ────────────────────────────────────

    def _set_modo(self, modo):
        """Cambia el modo del diagrama y actualiza los botones."""
        self._diagrama.set_modo(modo)

        if modo == "mover":
            self._btn_mover.config(bg=ACCENT, fg="white")
            self._btn_conn.config(bg=BG4, fg=TEXT)
            self._modo_lbl.config(text="  ✥  Arrastra nodos libremente", fg=ACCENT)
        else:
            self._btn_mover.config(bg=BG4, fg=TEXT)
            self._btn_conn.config(bg=GREEN, fg="white")
            self._modo_lbl.config(
                text="  →  Clic en origen → clic en destino para conectar",
                fg=GREEN
            )

    def _on_codigo_change(self):
        """
        Callback que se ejecuta cada vez que el diagrama cambia.
        Actualiza el contador de nodos y el código en tiempo real.
        """
        n = len(self._diagrama._nodos)
        self._ncount.config(text=f"{n} nodo{'s' if n != 1 else ''}")

        codigo = self._diagrama.obtener_codigo()
        self._write(self._cod_text, codigo, clear=True)
        self._hl_codigo(self._cod_text)

    def _on_limpiar(self):
        """Limpia el diagrama y todos los paneles de resultados."""
        self._diagrama.limpiar()
        for w in (self._cod_text, self._ast_text, self._asm_text, self._console):
            self._write(w, "", clear=True)
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._set_status("", "Listo")

    def _on_compilar(self):
        """
        Inicia la compilación del diagrama en un hilo secundario
        para no bloquear la interfaz gráfica.
        """
        codigo = self._diagrama.obtener_codigo().strip()

        if not codigo or not self._diagrama._nodos:
            self._set_status("warn", "El diagrama está vacío")
            return

        # Deshabilitar botón mientras compila
        self._btn_comp.config(state="disabled", text="⏳ Compilando...")
        self._set_status("", "Compilando…")

        # Ejecutar compilación en hilo separado
        def hilo():
            resultado = compilar_codigo(codigo)
            # Mostrar resultados en el hilo principal de Tkinter
            self.after(0, lambda: self._mostrar(resultado))

        threading.Thread(target=hilo, daemon=True).start()

    def _mostrar(self, r):
        """
        Muestra los resultados de la compilación en las pestañas
        correspondientes y en la consola.
        """
        # Restaurar botón
        self._btn_comp.config(state="normal", text="▶  Compilar y Ejecutar")
        self._write(self._console, "", clear=True)

        # ── Error en alguna fase ──────────────────────────
        if r["error"]:
            fase = r["fase"] or "desconocida"
            msg  = r["error"]
            self._set_status("error", f"Error en fase {fase}: {msg}")
            self._write(
                self._ast_text,
                f"✕  Error en fase '{fase}':\n\n{msg}\n",
                clear=True
            )
            if r["tokens"]:
                self._render_tokens(r["tokens"])
            self._log(f"[ERROR {fase}] {msg}", "err")
            self._nb.select(4)  # Ir a consola
            return

        # ── Tokens ───────────────────────────────────────
        if r["tokens"]:
            self._render_tokens(r["tokens"])
            self._log(f"✓ Léxico: {len(r['tokens'])} tokens identificados", "ok")

        # ── AST ──────────────────────────────────────────
        if r["ast"]:
            ast_str = json.dumps(r["ast"], indent=2, ensure_ascii=False)
            self._write(self._ast_text, ast_str, clear=True)
            self._log("✓ Análisis sintáctico completado sin errores", "ok")
            self._log("✓ Análisis semántico completado sin errores", "ok")

        # ── ASM ──────────────────────────────────────────
        if r["asm"]:
            self._write(self._asm_text, r["asm"], clear=True)
            self._asm_colors(self._asm_text)
            self._log(f"✓ ASM generado — {len(r['asm'].splitlines())} líneas", "ok")

        # ── Salida del programa ───────────────────────────
        if r["stdout"]:
            self._log("─" * 38, "info")
            self._log("=== SALIDA DEL PROGRAMA ===", "info")
            for ln in r["stdout"].splitlines():
                self._log(ln, "out")
            self._log("─" * 38, "info")

        # ── Advertencias / mensajes ───────────────────────
        if r["stderr"]:
            for ln in r["stderr"].splitlines():
                self._log(ln, "warn")

        estado = "✓ Compilado y ejecutado" if r["ejecutado"] else "✓ Compilado (sin ejecución)"
        self._set_status("ok", estado)
        self._nb.select(4)  # Mostrar consola al terminar

    # ── UTILIDADES DE VISUALIZACIÓN ───────────────────────

    def _write(self, w, text, clear=False, tag=None):
        """Escribe texto en un widget Text (habilita/deshabilita edición)."""
        w.config(state="normal")
        if clear:
            w.delete("1.0", "end")
        w.insert("end", text, tag or "")
        w.config(state="disabled")

    def _log(self, msg, kind="info"):
        """Agrega una línea a la consola con el prefijo y color correspondiente."""
        prefijos = {"ok": "✓ ", "err": "✕ ", "warn": "! ", "out": "▸ ", "info": "  "}
        prefix   = prefijos.get(kind, "  ")
        self._write(self._console, prefix + msg + "\n", tag=kind)
        self._console.see("end")

    def _render_tokens(self, tokens):
        """Llena la tabla de tokens con los resultados del análisis léxico."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        for i, (tipo, valor) in enumerate(tokens, 1):
            self._tree.insert("", "end", values=(i, tipo, valor), tags=(tipo,))

    def _set_status(self, kind, text):
        """Actualiza el indicador de estado en la barra inferior."""
        color = {"ok": GREEN, "error": RED, "warn": AMBER}.get(kind, MUTED)
        self._dot.config(fg=color)
        self._status.config(text=text)

    def _hl_codigo(self, w):
        """Aplica syntax highlighting al código generado."""
        w.config(state="normal")

        # Limpiar tags anteriores
        for tag in ("kw", "str", "num", "cm"):
            w.tag_remove(tag, "1.0", "end")

        # Configurar colores
        w.tag_config("kw",  foreground=ACCENT, font=("Courier New", 11, "bold"))
        w.tag_config("str", foreground=AMBER)
        w.tag_config("num", foreground=GREEN)
        w.tag_config("cm",  foreground=MUTED, font=("Courier New", 11, "italic"))

        txt = w.get("1.0", "end-1c")

        def char_to_idx(pos):
            """Convierte posición de carácter a índice de Tkinter."""
            ls = txt[:pos].split("\n")
            return f"{len(ls)}.{len(ls[-1])}"

        # Aplicar patrones de coloreado
        patrones = [
            (r'//[^\n]*',                                                    "cm"),
            (r'"[^"]*"',                                                     "str"),
            (r'\b(int|float|void|if|else|while|for|return|print|println)\b', "kw"),
            (r'\b\d+\.?\d*\b',                                               "num"),
        ]
        for pat, tag in patrones:
            for m in re.finditer(pat, txt):
                w.tag_add(tag, char_to_idx(m.start()), char_to_idx(m.end()))

        w.config(state="disabled")

    def _asm_colors(self, w):
        """Aplica colores al código ASM según el tipo de línea."""
        w.config(state="normal")
        for i, line in enumerate(w.get("1.0", "end-1c").split("\n"), 1):
            s  = line.strip()
            st = f"{i}.0"
            en = f"{i}.{len(line)}"

            if s.startswith("section "):
                w.tag_add("sec", st, en)
            elif re.match(r'^[a-zA-Z_]\w*:', s):
                w.tag_add("lbl", st, en)
            elif s.startswith(";"):
                w.tag_add("cmt", st, en)

        w.config(state="disabled")


# =============================================================
# PUNTO DE ENTRADA
# =============================================================
if __name__ == "__main__":
    app = CompiladorIDE()
    app.mainloop()