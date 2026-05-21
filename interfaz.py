# interfaz.py — Coloca junto a lexico.py, sintactico_ast.py, semantico.py
# Ejecutar: python interfaz.py

import tkinter as tk
from tkinter import ttk, messagebox
import json, threading, re
from pathlib import Path

import lexico, sintactico_ast, semantico

# ══════════════════════════════════════════════════════════
# COLORES
# ══════════════════════════════════════════════════════════
BG     = "#f5f3ef"
BG2    = "#ffffff"
BG3    = "#eeebe5"
BG4    = "#e4e0d8"
BORDER = "#d8d4cc"
TEXT   = "#1a1815"
MUTED  = "#8c8580"
ACCENT = "#5a47e0"
GREEN  = "#1a8a4a"
RED    = "#c0392b"
AMBER  = "#b45309"
BLUE   = "#1d4ed8"
TEAL   = "#0d7377"
PINK   = "#9d174d"
ORANGE = "#c2410c"

# ── Colores por tipo de instrucción ──────────────────────
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

# ── Forma del nodo por tipo ───────────────────────────────
# "rect" | "diamond" | "oval" | "parall"
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

NW, NH = 160, 52   # ancho y alto base del nodo

# ══════════════════════════════════════════════════════════
# CAMPOS EDITABLES POR TIPO
# ══════════════════════════════════════════════════════════
CAMPOS = {
    "asignar":   [("tipo_var","Tipo","int"), ("nombre","Nombre","x"), ("valor","Valor","0")],
    "reasignar": [("nombre","Variable","x"), ("valor","Nuevo valor","x + 1")],
    "print":     [("expr","Expresión",'"Hola"')],
    "println":   [("expr","Expresión",'"Hola"')],
    "if":        [("cond","Condición","x > 0")],
    "while":     [("cond","Condición","x > 0")],
    "for":       [("tipo_var","Tipo","int"),("var","Variable","i"),
                  ("inicio","Inicio","0"),("cond","Condición","i < 5"),("inc","Incremento","i + 1")],
    "return":    [("expr","Valor de retorno","0")],
    "funcion":   [("tipo_ret","Tipo retorno","int"),("nombre","Nombre","miFun"),("params","Parámetros","int a, int b")],
    "llamada":   [("nombre","Función","miFun"),("args","Argumentos","")],
    "inicio":    [],
    "fin":       [],
}

def defaults(tipo):
    return {k: v for k, _, v in CAMPOS.get(tipo, [])}

def etiqueta_nodo(tipo, datos):
    d = datos
    if tipo == "inicio":    return "INICIO"
    if tipo == "fin":       return "FIN"
    if tipo == "asignar":   return f"{d.get('tipo_var','int')} {d.get('nombre','x')} = {d.get('valor','0')}"
    if tipo == "reasignar": return f"{d.get('nombre','x')} = {d.get('valor','...')}"
    if tipo == "print":     return f"print({d.get('expr','...')})"
    if tipo == "println":   return f"println({d.get('expr','...')})"
    if tipo == "if":        return f"if {d.get('cond','...')}"
    if tipo == "while":     return f"while {d.get('cond','...')}"
    if tipo == "for":       return f"for {d.get('var','i')}"
    if tipo == "return":    return f"return {d.get('expr','...')}"
    if tipo == "funcion":   return f"{d.get('tipo_ret','int')} {d.get('nombre','f')}()"
    if tipo == "llamada":   return f"{d.get('nombre','f')}({d.get('args','')})"
    return tipo

# ══════════════════════════════════════════════════════════
# GENERACIÓN DE CÓDIGO DESDE EL DIAGRAMA
# ══════════════════════════════════════════════════════════
def diagrama_a_codigo(nodos, conexiones):
    """
    Recorre el diagrama siguiendo las flechas desde INICIO hasta FIN
    y genera el código fuente C-like.
    Soporta: secuencia, if/else, while, for, funciones.
    """
    # Índices
    nodo_por_id  = {n["id"]: n for n in nodos}
    hijos_de     = {}   # id → [(id_destino, etiqueta)]
    padres_de    = {}   # id → [id_origen]
    for n in nodos:
        hijos_de[n["id"]]  = []
        padres_de[n["id"]] = []
    for src, dst, lbl in conexiones:
        hijos_de[src].append((dst, lbl))
        padres_de[dst].append(src)

    # Nodo inicial
    inicio = next((n for n in nodos if n["tipo"] == "inicio"), None)
    if not inicio:
        return "// Error: no hay nodo INICIO en el diagrama\n"

    visitados = set()
    lineas_func = []
    lineas_main = []

    # Primero extraer funciones (nodos tipo "funcion")
    for n in nodos:
        if n["tipo"] == "funcion":
            d = n["datos"]
            # Buscar cuerpo: nodos accesibles desde esta función que no sean main
            cuerpo = _cuerpo_funcion(n["id"], hijos_de, nodo_por_id, visitados)
            lineas_func.append(
                f"{d.get('tipo_ret','int')} {d.get('nombre','f')}({d.get('params','')}) {{\n"
                + cuerpo +
                f"\n}};"
            )
            visitados.add(n["id"])

    # Recorrer desde INICIO
    _recorrer(inicio["id"], hijos_de, nodo_por_id, visitados,
              lineas_main, indent="    ")

    body = "\n".join(lineas_main) or "    // vacío"
    main_bloque = f"int main() {{\n{body}\n}};"
    partes = lineas_func + [main_bloque]
    return "\n\n".join(partes)


def _cuerpo_funcion(fn_id, hijos_de, nodo_por_id, visitados):
    """Genera el cuerpo de una función siguiendo sus conexiones."""
    lineas = []
    vis_local = set(visitados)
    nodos_sig = [dst for dst, _ in hijos_de.get(fn_id, [])]
    for nid in nodos_sig:
        _recorrer(nid, hijos_de, nodo_por_id, vis_local, lineas, "    ")
    return "\n".join(lineas)


def _recorrer(nid, hijos_de, nodo_por_id, visitados, lineas, indent):
    """Recorre recursivamente el grafo generando código."""
    if nid in visitados:
        return
    nodo = nodo_por_id.get(nid)
    if not nodo:
        return

    tipo  = nodo["tipo"]
    datos = nodo["datos"]
    visitados.add(nid)

    if tipo == "fin" or tipo == "inicio":
        pass  # no genera código

    elif tipo in ("asignar",):
        lineas.append(f"{indent}{datos.get('tipo_var','int')} {datos.get('nombre','x')} = {datos.get('valor','0')};")

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

    elif tipo == "if":
        cond = datos.get("cond", "true")
        hijos = hijos_de.get(nid, [])
        # Separar por etiqueta Sí/No o True/False o primera/segunda flecha
        si_nodo   = next((d for d, l in hijos if l.lower() in ("sí","si","true","s","yes","1")), None)
        no_nodo   = next((d for d, l in hijos if l.lower() in ("no","false","n","0")), None)
        if not si_nodo and hijos:
            si_nodo = hijos[0][0]
        if not no_nodo and len(hijos) > 1:
            no_nodo = hijos[1][0]

        lineas.append(f"{indent}if ({cond}) {{")
        vis_if = set(visitados)
        lineas_if = []
        if si_nodo:
            _recorrer(si_nodo, hijos_de, nodo_por_id, vis_if, lineas_if, indent+"    ")
        lineas.extend(lineas_if or [f"{indent}    // vacío"])
        if no_nodo:
            lineas.append(f"{indent}}} else {{")
            vis_else = set(visitados)
            lineas_else = []
            _recorrer(no_nodo, hijos_de, nodo_por_id, vis_else, lineas_else, indent+"    ")
            lineas.extend(lineas_else or [f"{indent}    // vacío"])
        lineas.append(f"{indent}}};")
        return  # no seguir con hijos normales

    elif tipo == "while":
        cond = datos.get("cond", "true")
        hijos = hijos_de.get(nid, [])
        cuerpo_id = next((d for d, l in hijos if l.lower() not in ("salir","no","false")), None)
        if not cuerpo_id and hijos:
            cuerpo_id = hijos[0][0]
        lineas.append(f"{indent}while ({cond}) {{")
        vis_w = set(visitados)
        lineas_w = []
        if cuerpo_id:
            _recorrer(cuerpo_id, hijos_de, nodo_por_id, vis_w, lineas_w, indent+"    ")
        lineas.extend(lineas_w or [f"{indent}    // vacío"])
        lineas.append(f"{indent}}};")
        return

    elif tipo == "for":
        d = datos
        lineas.append(
            f"{indent}for ({d.get('tipo_var','int')} {d.get('var','i')} = {d.get('inicio','0')}; "
            f"{d.get('cond','i < 5')}; {d.get('var','i')} = {d.get('inc','i + 1')}) {{"
        )
        hijos = hijos_de.get(nid, [])
        cuerpo_id = hijos[0][0] if hijos else None
        vis_f = set(visitados)
        lineas_f = []
        if cuerpo_id:
            _recorrer(cuerpo_id, hijos_de, nodo_por_id, vis_f, lineas_f, indent+"    ")
        lineas.extend(lineas_f or [f"{indent}    // vacío"])
        lineas.append(f"{indent}}};")
        return

    # Continuar con el siguiente nodo (primer hijo no etiquetado como "no")
    hijos = hijos_de.get(nid, [])
    siguiente = next((d for d, l in hijos if l.lower() not in ("no","false","n","salir")), None)
    if not siguiente and hijos:
        siguiente = hijos[0][0]
    if siguiente:
        _recorrer(siguiente, hijos_de, nodo_por_id, visitados, lineas, indent)


# ══════════════════════════════════════════════════════════
# COMPILADOR (usa los módulos Python del proyecto)
# ══════════════════════════════════════════════════════════
def imprimir_ast(nodo):
    if isinstance(nodo, lexico.NodoPrograma):
        return {"programa":"Noname","funciones":[imprimir_ast(f) for f in nodo.funciones],"main":imprimir_ast(nodo.main)}
    if isinstance(nodo, lexico.NodoFuncion):
        return {"nombre":nodo.nombre[1],"params":[imprimir_ast(p) for p in nodo.parametros],"cuerpo":[imprimir_ast(c) for c in nodo.cuerpo]}
    if isinstance(nodo, lexico.NodoParametro):    return {"id":nodo.nombre[1],"tipo":nodo.tipo[1]}
    if isinstance(nodo, lexico.NodoAsignacion):   return {"tipo":"asignacion","var":nodo.nombre[1],"expr":imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoReasignacion): return {"tipo":"reasignacion","var":nodo.nombre[1],"expr":imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoOperacion):    return {"op":nodo.operador[1],"izq":imprimir_ast(nodo.izquierda),"der":imprimir_ast(nodo.derecha)}
    if isinstance(nodo, lexico.NodoRetorno):      return {"tipo":"return","valor":imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoIdentificador):return nodo.nombre[1]
    if isinstance(nodo, lexico.NodoNumero):       return {"Numero":nodo.valor}
    if isinstance(nodo, lexico.NodoString):       return {"String":nodo.valor[1] if isinstance(nodo.valor,tuple) else nodo.valor}
    if isinstance(nodo, lexico.NodoLlamadaFuncion):return {"LlamadaFuncion":nodo.nombre_funcion,"args":[imprimir_ast(a) for a in nodo.argumentos]}
    if isinstance(nodo, lexico.NodoPrint):        return {"tipo":"print","expr":imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoPrintln):      return {"tipo":"println","expr":imprimir_ast(nodo.expresion)}
    if isinstance(nodo, lexico.NodoIf):
        n={"tipo":"if","cond":imprimir_ast(nodo.condicion),"si":[imprimir_ast(c) for c in nodo.cuerpo_if]}
        if nodo.cuerpo_else: n["no"]=[imprimir_ast(c) for c in nodo.cuerpo_else]
        return n
    if isinstance(nodo, lexico.NodoWhile): return {"tipo":"while","cond":imprimir_ast(nodo.condicion),"cuerpo":[imprimir_ast(c) for c in nodo.cuerpo]}
    if isinstance(nodo, lexico.NodoFor):   return {"tipo":"for","inicio":imprimir_ast(nodo.inicio),"cond":imprimir_ast(nodo.condicion),"inc":imprimir_ast(nodo.incremento),"cuerpo":[imprimir_ast(c) for c in nodo.cuerpo]}
    return {}

def limpiar_asm(asm):
    return "\n".join(l.split(";",1)[0].rstrip() for l in asm.splitlines() if l.split(";",1)[0].rstrip())

def _wsl(args):
    return subprocess.run(["wsl","-d","Ubuntu","-e"]+args, capture_output=True, text=True)
def _wsl_path(p):
    r=Path(p).resolve(); u=r.drive.rstrip(":").lower()
    return f"/mnt/{u}/"+"/" .join(x for x in r.parts[1:] if x not in("\\","/"))

def compilar_codigo(codigo):
    r=dict(tokens=None,ast=None,asm=None,stdout=None,stderr=None,ejecutado=False,error=None,fase=None)
    try: toks=lexico.identificar_tokens(codigo); r["tokens"]=toks
    except Exception as e: r["fase"]="léxico"; r["error"]=str(e); return r
    try: arbol=sintactico_ast.Parser(toks).parsear()
    except Exception as e: r["fase"]="sintáctico"; r["error"]=str(e); return r
    try: semantico.AnalizadorSemantico().analizar(arbol)
    except Exception as e: r["fase"]="semántico"; r["error"]=str(e); return r
    r["ast"]=imprimir_ast(arbol)
    try: asm_c=arbol.generarCodigo(); r["asm"]=limpiar_asm(asm_c)
    except Exception as e: r["fase"]="ASM"; r["error"]=str(e); return r
    # Ejecución deshabilitada — nasm no disponible en este equipo
    r["stderr"] = "ASM generado correctamente. Ejecución no disponible (nasm no instalado)."
    return r


# ══════════════════════════════════════════════════════════
# DIÁLOGO PARA EDITAR UN NODO
# ══════════════════════════════════════════════════════════
class DialogoNodo(tk.Toplevel):
    def __init__(self, parent, tipo, datos):
        super().__init__(parent)
        self.title(f"Editar — {tipo}")
        self.resizable(False, False)
        self.configure(bg=BG2)
        self.grab_set()
        self.resultado = None
        bg, fg = TIPO_COLOR.get(tipo, (MUTED, "#fff"))

        # Cabecera coloreada
        hdr = tk.Frame(self, bg=bg, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"  ✏  {etiqueta_nodo(tipo, datos)}",
                 bg=bg, fg=fg, font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)

        body = tk.Frame(self, bg=BG2, padx=20, pady=10)
        body.pack(fill="x")

        campos = CAMPOS.get(tipo, [])
        self._vars = {}
        if not campos:
            tk.Label(body, text="Este nodo no tiene parámetros.",
                     bg=BG2, fg=MUTED, font=("Segoe UI", 10)).pack()
        for key, label, ph in campos:
            tk.Label(body, text=label, bg=BG2, fg=MUTED,
                     font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(8,2))
            var = tk.StringVar(value=datos.get(key, ph))
            e = tk.Entry(body, textvariable=var, bg=BG3, fg=TEXT,
                         font=("Courier New", 11), relief="flat",
                         insertbackground=ACCENT, bd=4, width=32)
            e.pack(fill="x", ipady=5)
            self._vars[key] = var

        btns = tk.Frame(self, bg=BG2, pady=12, padx=20)
        btns.pack(fill="x")
        tk.Button(btns, text="Cancelar", bg=BG3, fg=MUTED, relief="flat",
                  font=("Segoe UI", 10), padx=12, pady=5,
                  cursor="hand2", command=self.destroy).pack(side="right", padx=(4,0))
        tk.Button(btns, text="Guardar", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=12, pady=5,
                  cursor="hand2", command=self._ok).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.wait_window()

    def _ok(self):
        self.resultado = {k: v.get() for k, v in self._vars.items()}
        self.destroy()


# ══════════════════════════════════════════════════════════
# CANVAS — DIAGRAMA DE FLUJO
# ══════════════════════════════════════════════════════════
class DiagramaCanvas(tk.Frame):
    """
    Canvas interactivo donde el usuario arrastra instrucciones desde
    la paleta, las conecta con flechas y luego compila el diagrama.
    """
    def __init__(self, parent, on_codigo_change):
        super().__init__(parent, bg=BG)
        self._on_codigo = on_codigo_change
        self._nodos      = []          # lista de dicts
        self._conexiones = []          # (src_id, dst_id, etiqueta)
        self._sel        = None        # nodo seleccionado
        self._modo       = "mover"     # "mover" | "conectar"
        self._conn_src   = None
        self._drag_off   = (0, 0)
        self._ghost      = None        # ventana fantasma al arrastrar desde paleta
        self._ghost_tipo = None
        self._next_id    = 1
        self._prev_line  = None
        self._build()

    # ── CONSTRUCCIÓN ─────────────────────────────────────
    def _build(self):
        # Canvas con scrollbars
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="both", expand=True)

        self._cv = tk.Canvas(frm, bg="#fafaf8", highlightthickness=0)
        vsb = ttk.Scrollbar(frm, orient="vertical",   command=self._cv.yview)
        hsb = ttk.Scrollbar(frm, orient="horizontal", command=self._cv.xview)
        self._cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set,
                            scrollregion=(-800, -800, 3000, 3000))
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        self._cv.pack(side="left", fill="both", expand=True)

        self._dibujar_grid()

        # Eventos
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
        for x in range(-800, 3001, 40):
            self._cv.create_line(x,-800,x,3000, fill="#edebe6", width=1, tags="grid")
        for y in range(-800, 3001, 40):
            self._cv.create_line(-800,y,3000,y, fill="#edebe6", width=1, tags="grid")
        self._cv.tag_lower("grid")

    # ── MODO ─────────────────────────────────────────────
    def set_modo(self, modo):
        self._modo = modo
        self._conn_src = None
        if self._prev_line:
            self._cv.delete(self._prev_line); self._prev_line = None
        cur = "fleur" if modo == "mover" else "crosshair"
        self._cv.config(cursor=cur)

    # ── AGREGAR NODO ─────────────────────────────────────
    def agregar_nodo(self, tipo, x=None, y=None):
        """Crea un nodo en (x,y) o en el centro del canvas."""
        if x is None:
            x = self._cv.winfo_width()  // 2 + self._cv.canvasx(0)
            y = self._cv.winfo_height() // 2 + self._cv.canvasy(0)
        nid = self._next_id; self._next_id += 1
        nodo = {"id": nid, "tipo": tipo, "x": int(x), "y": int(y),
                "datos": defaults(tipo), "cids": []}
        self._nodos.append(nodo)
        self._dibujar_nodo(nodo)
        self._on_codigo()
        return nodo

    # ── DIBUJO ───────────────────────────────────────────
    def _dibujar_nodo(self, nodo):
        for cid in nodo["cids"]: self._cv.delete(cid)
        nodo["cids"] = []

        x, y   = nodo["x"], nodo["y"]
        tipo   = nodo["tipo"]
        bg, fg = TIPO_COLOR.get(tipo, (MUTED, "#fff"))
        forma  = TIPO_FORMA.get(tipo, "rect")
        sel    = nodo.get("sel", False)
        tag    = f"nodo_{nodo['id']}"
        w, h   = NW, NH
        ids    = []

        # Sombra
        ids.append(self._cv.create_rectangle(
            x-w//2+4, y-h//2+4, x+w//2+4, y+h//2+4,
            fill="#d0ccc4", outline="", tags=(tag,"sombra")))

        # Forma principal
        if forma == "oval":
            ids.append(self._cv.create_oval(
                x-w//2, y-h//2, x+w//2, y+h//2,
                fill=bg, outline="#ffffff" if sel else bg, width=3 if sel else 0,
                tags=(tag,"cuerpo")))
        elif forma == "diamond":
            hw, hh = w//2+10, h//2+10
            pts = [x, y-hh, x+hw, y, x, y+hh, x-hw, y]
            ids.append(self._cv.create_polygon(
                pts, fill=bg, outline="#ffffff" if sel else bg, width=3 if sel else 0,
                tags=(tag,"cuerpo")))
            h = hh*2  # para que el texto se centre bien
        elif forma == "parall":
            off = 14
            pts = [x-w//2+off, y-h//2, x+w//2+off, y-h//2,
                   x+w//2-off, y+h//2, x-w//2-off, y+h//2]
            ids.append(self._cv.create_polygon(
                pts, fill=bg, outline="#ffffff" if sel else bg, width=3 if sel else 0,
                tags=(tag,"cuerpo")))
        else:  # rect
            r = 8
            ids.append(self._cv.create_rectangle(
                x-w//2, y-h//2, x+w//2, y+h//2,
                fill=bg, outline="#ffffff" if sel else bg, width=3 if sel else 0,
                tags=(tag,"cuerpo")))

        # Texto
        label = etiqueta_nodo(tipo, nodo["datos"])
        if len(label) > 20: label = label[:18]+"…"
        ids.append(self._cv.create_text(
            x, y, text=label, fill=fg,
            font=("Segoe UI", 9, "bold"),
            width=NW - 20, tags=(tag,"texto")))

        nodo["cids"] = ids
        self._cv.tag_lower("sombra")
        self._cv.tag_lower("grid")
        self._redibujar_conexiones()

    def _redibujar_conexiones(self):
        self._cv.delete("conexion")
        por_id = {n["id"]: n for n in self._nodos}
        for src_id, dst_id, lbl in self._conexiones:
            s = por_id.get(src_id); d = por_id.get(dst_id)
            if not s or not d: continue
            x1,y1 = s["x"], s["y"] + NH//2 + (12 if TIPO_FORMA.get(s["tipo"])=="diamond" else 0)
            x2,y2 = d["x"], d["y"] - NH//2 - (12 if TIPO_FORMA.get(d["tipo"])=="diamond" else 0)
            # Línea con codo
            my = (y1+y2)//2
            self._cv.create_line(
                x1,y1, x1,my, x2,my, x2,y2,
                arrow="last", arrowshape=(12,14,5),
                fill=MUTED, width=2, smooth=False, tags="conexion")
            # Etiqueta
            if lbl:
                self._cv.create_text(
                    (x1+x2)//2 + 8, my - 10, text=lbl,
                    fill=AMBER, font=("Segoe UI", 8, "bold"), tags="conexion")
        self._cv.tag_lower("conexion")
        self._cv.tag_lower("grid")

    def redibujar_todo(self):
        for n in self._nodos: self._dibujar_nodo(n)

    # ── EVENTOS DEL CANVAS ───────────────────────────────
    def _on_press(self, e):
        cx,cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        nodo  = self._nodo_en(cx, cy)

        if self._modo == "conectar":
            if nodo:
                if self._conn_src is None:
                    self._conn_src = nodo
                    self._seleccionar(nodo)
                else:
                    if nodo["id"] != self._conn_src["id"]:
                        lbl = ""
                        if self._conn_src["tipo"] in ("if","while","for"):
                            lbl = self._pedir_label()
                        self._conexiones.append((self._conn_src["id"], nodo["id"], lbl))
                        self._redibujar_conexiones()
                        self._on_codigo()
                    self._conn_src = None
                    if self._prev_line: self._cv.delete(self._prev_line); self._prev_line=None
                    self._deseleccionar()
            return

        # Modo mover
        if nodo:
            self._seleccionar(nodo)
            self._drag_off = (cx - nodo["x"], cy - nodo["y"])
        else:
            self._deseleccionar()

    def _on_drag(self, e):
        cx,cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        if self._modo == "conectar":
            if self._conn_src:
                if self._prev_line: self._cv.delete(self._prev_line)
                sx,sy = self._conn_src["x"], self._conn_src["y"] + NH//2
                self._prev_line = self._cv.create_line(
                    sx,sy,cx,cy, fill=GREEN, width=2, dash=(6,3),
                    arrow="last", arrowshape=(10,12,4), tags="prev_line")
            return
        if self._sel:
            self._sel["x"] = int(cx - self._drag_off[0])
            self._sel["y"] = int(cy - self._drag_off[1])
            self._dibujar_nodo(self._sel)

    def _on_release(self, e):
        self._on_codigo()

    def _on_dbl(self, e):
        cx,cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        nodo  = self._nodo_en(cx, cy)
        if nodo:
            dlg = DialogoNodo(self.winfo_toplevel(), nodo["tipo"], nodo["datos"])
            if dlg.resultado:
                nodo["datos"].update(dlg.resultado)
                self._dibujar_nodo(nodo)
                self._on_codigo()

    def _pan_start(self, e): self._cv.scan_mark(e.x, e.y)
    def _pan_move(self,  e): self._cv.scan_dragto(e.x, e.y, gain=1)

    def _wheel(self, e):
        f = 1.1 if e.delta > 0 else 1/1.1
        cx,cy = self._cv.canvasx(e.x), self._cv.canvasy(e.y)
        self._cv.scale("all", cx, cy, f, f)
        self._cv.configure(scrollregion=self._cv.bbox("all"))

    # ── SELECCIÓN ────────────────────────────────────────
    def _seleccionar(self, nodo):
        self._deseleccionar()
        self._sel = nodo
        nodo["sel"] = True
        self._dibujar_nodo(nodo)

    def _deseleccionar(self):
        if self._sel:
            self._sel["sel"] = False
            self._dibujar_nodo(self._sel)
            self._sel = None

    # ── DRAG DESDE PALETA ────────────────────────────────
    def iniciar_drag_paleta(self, tipo, x_root, y_root):
        self._ghost_tipo = tipo
        if self._ghost: self._ghost.destroy()
        g = tk.Toplevel(self)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.7)
        g.attributes("-topmost", True)
        bg, fg = TIPO_COLOR.get(tipo, (MUTED,"#fff"))
        tk.Label(g, text=f"  {etiqueta_nodo(tipo,defaults(tipo))}  ",
                 bg=bg, fg=fg, font=("Segoe UI", 9, "bold"),
                 relief="solid", bd=1, padx=8, pady=5).pack()
        g.geometry(f"+{x_root+10}+{y_root+10}")
        self._ghost = g
        self.winfo_toplevel().bind("<Motion>", self._mover_ghost)
        self.winfo_toplevel().bind("<ButtonRelease-1>", self._soltar_paleta)

    def _mover_ghost(self, e):
        if self._ghost:
            self._ghost.geometry(f"+{e.x_root+10}+{e.y_root+10}")

    def _soltar_paleta(self, e):
        self.winfo_toplevel().unbind("<Motion>")
        self.winfo_toplevel().unbind("<ButtonRelease-1>")
        if self._ghost: self._ghost.destroy(); self._ghost=None
        if not self._ghost_tipo: return
        # Convertir posición pantalla → canvas
        cv_x = self._cv.canvasx(e.x_root - self._cv.winfo_rootx())
        cv_y = self._cv.canvasy(e.y_root - self._cv.winfo_rooty())
        # Solo agregar si se soltó sobre el canvas
        cx0 = self._cv.winfo_rootx(); cy0 = self._cv.winfo_rooty()
        cw  = self._cv.winfo_width(); ch  = self._cv.winfo_height()
        if cx0 <= e.x_root <= cx0+cw and cy0 <= e.y_root <= cy0+ch:
            self.agregar_nodo(self._ghost_tipo, cv_x, cv_y)
        self._ghost_tipo = None

    # ── UTILIDADES ───────────────────────────────────────
    def _nodo_en(self, cx, cy):
        for n in reversed(self._nodos):
            dx = abs(cx - n["x"]); dy = abs(cy - n["y"])
            forma = TIPO_FORMA.get(n["tipo"],"rect")
            hw = NW//2 + (10 if forma=="diamond" else 0)
            hh = NH//2 + (10 if forma=="diamond" else 0)
            if dx <= hw and dy <= hh:
                return n
        return None

    def _borrar_sel(self):
        if not self._sel: return
        nid = self._sel["id"]
        for cid in self._sel["cids"]: self._cv.delete(cid)
        self._nodos = [n for n in self._nodos if n["id"] != nid]
        self._conexiones = [(s,d,l) for s,d,l in self._conexiones if s!=nid and d!=nid]
        self._sel = None
        self._redibujar_conexiones()
        self._on_codigo()

    def borrar_conexion_sel(self):
        """Borra la última conexión (simplificado)."""
        if self._conexiones:
            self._conexiones.pop()
            self._redibujar_conexiones()
            self._on_codigo()

    def limpiar(self):
        self._cv.delete("all")
        self._nodos.clear()
        self._conexiones.clear()
        self._sel = None; self._conn_src = None
        self._dibujar_grid()
        self._on_codigo()

    def _pedir_label(self):
        dlg = tk.Toplevel(self)
        dlg.title("Etiqueta de la flecha")
        dlg.resizable(False,False)
        dlg.configure(bg=BG2)
        dlg.grab_set()
        result = [""]
        tk.Label(dlg, text="Etiqueta (ej: Sí, No, True…)",
                 bg=BG2, fg=MUTED, font=("Segoe UI",9)).pack(padx=16, pady=(12,4))
        var = tk.StringVar(value="")
        e = tk.Entry(dlg, textvariable=var, bg=BG3, fg=TEXT,
                     font=("Courier New",11), relief="flat", bd=4, width=20)
        e.pack(padx=16, ipady=4); e.focus_set()
        def ok(ev=None): result[0]=var.get(); dlg.destroy()
        e.bind("<Return>", ok)
        tk.Button(dlg, text="OK", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI",10,"bold"), padx=10, pady=4,
                  cursor="hand2", command=ok).pack(pady=10)
        dlg.wait_window()
        return result[0]

    def obtener_codigo(self):
        return diagrama_a_codigo(self._nodos, self._conexiones)


# ══════════════════════════════════════════════════════════
# PALETA LATERAL
# ══════════════════════════════════════════════════════════
PALETA_ITEMS = [
    ("inicio",    "⬟ INICIO"),
    ("fin",       "⬟ FIN"),
    ("asignar",   "▭ int x = 0"),
    ("reasignar", "▭ x = expr"),
    ("print",     "▱ print(…)"),
    ("println",   "▱ println(…)"),
    ("if",        "◇ if (…)"),
    ("while",     "◇ while (…)"),
    ("for",       "◇ for (…)"),
    ("return",    "▭ return …"),
    ("funcion",   "▭ función"),
    ("llamada",   "▭ f(…)"),
]

class PaletaLateral(tk.Frame):
    def __init__(self, parent, diagrama: DiagramaCanvas):
        super().__init__(parent, bg=BG2, width=160)
        self.pack_propagate(False)
        self._diag = diagrama
        self._build()

    def _build(self):
        tk.Label(self, text="INSTRUCCIONES", bg=BG3, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), pady=7).pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        tip_ventana = [None]

        for tipo, label in PALETA_ITEMS:
            bg, fg = TIPO_COLOR.get(tipo, (BG4, TEXT))
            btn = tk.Button(
                self, text=label, bg=bg, fg=fg,
                font=("Courier New", 9, "bold"),
                relief="flat", bd=0, pady=6, padx=8,
                anchor="w", cursor="hand2",
                activebackground=bg, activeforeground=fg)
            btn.pack(fill="x", padx=6, pady=2)

            # Arrastrar al canvas
            btn.bind("<ButtonPress-1>",
                     lambda e, t=tipo: self._diag.iniciar_drag_paleta(t, e.x_root, e.y_root))
            # Tooltip
            def show_tip(e, t=tipo, b=btn, tv=tip_ventana):
                if tv[0]: tv[0].destroy()
                tip = tk.Toplevel(b)
                tip.overrideredirect(True)
                tip.attributes("-topmost", True)
                tk.Label(tip, text=f"Arrastra al diagrama",
                         bg="#ffffcc", fg=TEXT, font=("Segoe UI",8),
                         padx=5, pady=2, relief="solid", bd=1).pack()
                tip.geometry(f"+{e.x_root+16}+{e.y_root+12}")
                tv[0] = tip
            def hide_tip(e, tv=tip_ventana):
                if tv[0]: tv[0].destroy(); tv[0]=None
            btn.bind("<Enter>", show_tip)
            btn.bind("<Leave>", hide_tip)


# ══════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════
class CompiladorIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CompiladorIDE — Diagrama de Flujo")
        self.geometry("1380x800")
        self.minsize(1000, 640)
        self.configure(bg=BG)
        self._build_ui()
        # Diagrama inicial de ejemplo
        self._init_ejemplo()

    def _init_ejemplo(self):
        cv = self._diagrama
        n0 = cv.agregar_nodo("inicio",   400, 80)
        n1 = cv.agregar_nodo("asignar",  400, 190)
        n2 = cv.agregar_nodo("asignar",  400, 300)
        n3 = cv.agregar_nodo("println",  400, 410)
        n4 = cv.agregar_nodo("fin",      400, 510)
        n1["datos"].update({"tipo_var":"int","nombre":"x","valor":"10"})
        n2["datos"].update({"tipo_var":"int","nombre":"y","valor":"20"})
        n3["datos"].update({"expr":"x"})
        cv._conexiones = [
            (n0["id"], n1["id"], ""),
            (n1["id"], n2["id"], ""),
            (n2["id"], n3["id"], ""),
            (n3["id"], n4["id"], ""),
        ]
        cv.redibujar_todo()

    # ── UI ───────────────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()
        self._build_modebar()
        self._build_body()
        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG2, height=52)
        bar.pack(fill="x"); bar.pack_propagate(False)

        tk.Frame(bar, bg=ACCENT, width=30, height=30).place(x=12, y=11)
        tk.Label(bar, text="⚙", bg=ACCENT, fg="white",
                 font=("Segoe UI",13)).place(x=12, y=11, width=30, height=30)
        tk.Label(bar, text="  CompiladorIDE", bg=BG2, fg=ACCENT,
                 font=("Segoe UI",13,"bold")).pack(side="left", padx=(50,0))
        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=12, pady=10)
        tk.Label(bar, text="Diagrama de flujo → Código → ASM",
                 bg=BG2, fg=MUTED, font=("Courier New",9)).pack(side="left")

        right = tk.Frame(bar, bg=BG2)
        right.pack(side="right", padx=12)
        self._btn_comp = tk.Button(right, text="▶  Compilar y Ejecutar",
                                    bg=ACCENT, fg="white",
                                    font=("Segoe UI",10,"bold"),
                                    relief="flat", padx=16, pady=6,
                                    cursor="hand2", command=self._on_compilar)
        self._btn_comp.pack(side="right", padx=(6,0))
        tk.Button(right, text="✕  Limpiar", bg=BG3, fg=MUTED,
                  font=("Segoe UI",10), relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._on_limpiar).pack(side="right")

    def _build_modebar(self):
        bar = tk.Frame(self, bg=BG3, height=36)
        bar.pack(fill="x"); bar.pack_propagate(False)

        tk.Label(bar, text="  Modo:", bg=BG3, fg=MUTED,
                 font=("Segoe UI",9,"bold")).pack(side="left", pady=6)

        self._btn_mover = tk.Button(
            bar, text="✥ Mover nodos", bg=ACCENT, fg="white",
            font=("Segoe UI",9,"bold"), relief="flat", padx=10, pady=4,
            cursor="hand2", command=lambda: self._set_modo("mover"))
        self._btn_mover.pack(side="left", padx=(6,2), pady=4)

        self._btn_conn = tk.Button(
            bar, text="→ Conectar con flecha", bg=BG4, fg=TEXT,
            font=("Segoe UI",9,"bold"), relief="flat", padx=10, pady=4,
            cursor="hand2", command=lambda: self._set_modo("conectar"))
        self._btn_conn.pack(side="left", padx=2, pady=4)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=6)

        tk.Button(bar, text="🗑 Borrar nodo (Supr)", bg=BG4, fg=RED,
                  font=("Segoe UI",9), relief="flat", padx=10, pady=4,
                  cursor="hand2",
                  command=lambda: self._diagrama._borrar_sel()).pack(side="left", padx=2, pady=4)

        tk.Button(bar, text="✂ Quitar última flecha", bg=BG4, fg=MUTED,
                  font=("Segoe UI",9), relief="flat", padx=10, pady=4,
                  cursor="hand2",
                  command=lambda: self._diagrama.borrar_conexion_sel()).pack(side="left", padx=2, pady=4)

        self._modo_lbl = tk.Label(bar, text="  ✥  Arrastra nodos libremente",
                                   bg=BG3, fg=ACCENT, font=("Segoe UI",9,"bold"))
        self._modo_lbl.pack(side="right", padx=12)

    def _build_body(self):
        paned = tk.PanedWindow(self, orient="horizontal", bg=BORDER,
                                sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # Izquierda: paleta + diagrama
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=340, width=560)

        self._diagrama = DiagramaCanvas(left, self._on_codigo_change)
        paleta = PaletaLateral(left, self._diagrama)
        paleta.pack(side="left", fill="y")
        tk.Frame(left, bg=BORDER, width=1).pack(side="left", fill="y")
        self._diagrama.pack(side="left", fill="both", expand=True)

        # Derecha: pestañas
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=300)
        self._build_tabs(right)

    def _build_tabs(self, parent):
        style = ttk.Style()
        style.configure("IDE.TNotebook",     background=BG2, borderwidth=0)
        style.configure("IDE.TNotebook.Tab", background=BG3, foreground=MUTED,
                        padding=[12,6], font=("Segoe UI",10,"bold"))
        style.map("IDE.TNotebook.Tab",
                  background=[("selected",BG2)],
                  foreground=[("selected",ACCENT)])

        nb = ttk.Notebook(parent, style="IDE.TNotebook")
        nb.pack(fill="both", expand=True)
        self._nb = nb

        # Código generado
        f = tk.Frame(nb, bg=BG); nb.add(f, text="📄 Código")
        self._cod_text = self._make_text(f)

        # Tokens
        f = tk.Frame(nb, bg=BG); nb.add(f, text="◆ Tokens")
        self._build_tokens_tab(f)

        # AST visual
        f = tk.Frame(nb, bg=BG); nb.add(f, text="⬡ AST")
        self._ast_text = self._make_text(f)

        # ASM
        f = tk.Frame(nb, bg=BG); nb.add(f, text="⚙ ASM")
        self._asm_text = self._make_text(f)
        self._asm_text.tag_config("sec", foreground=PINK,  font=("Courier New",11,"bold"))
        self._asm_text.tag_config("lbl", foreground=BLUE,  font=("Courier New",11,"bold"))
        self._asm_text.tag_config("cmt", foreground=MUTED, font=("Courier New",11,"italic"))

        # Consola
        f = tk.Frame(nb, bg=BG); nb.add(f, text="▸ Consola")
        self._console = self._make_text(f)
        for tag,col in [("ok",GREEN),("err",RED),("warn",AMBER),("out",TEAL),("info",MUTED)]:
            self._console.tag_config(tag, foreground=col)

    def _build_tokens_tab(self, parent):
        style = ttk.Style()
        style.configure("Tok.Treeview", background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=24, font=("Courier New",11))
        style.configure("Tok.Treeview.Heading", background=BG3, foreground=MUTED,
                        font=("Segoe UI",9,"bold"), relief="flat")
        style.map("Tok.Treeview",
                  background=[("selected","#d4d0f8")],
                  foreground=[("selected",ACCENT)])
        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="both", expand=True, padx=10, pady=8)
        self._tree = ttk.Treeview(frm, columns=("#","Tipo","Valor"),
                                   show="headings", style="Tok.Treeview")
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
        for tag,col in [("KEYWORD",ACCENT),("IDENTIFIER",BLUE),("NUMBER",GREEN),
                         ("STRING",AMBER),("OPERATOR",ORANGE),("DELIMITER",TEAL),("UNKNOWN",RED)]:
            self._tree.tag_configure(tag, foreground=col)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG3, height=26)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        self._dot = tk.Label(bar, text="●", bg=BG3, fg=GREEN, font=("Segoe UI",9))
        self._dot.pack(side="left", padx=(10,4))
        self._status = tk.Label(bar, text="Listo — arrastra instrucciones al diagrama",
                                 bg=BG3, fg=MUTED, font=("Segoe UI",9))
        self._status.pack(side="left")
        self._ncount = tk.Label(bar, text="0 nodos", bg=BG3, fg=MUTED, font=("Segoe UI",9))
        self._ncount.pack(side="right", padx=10)

    def _make_text(self, parent):
        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="both", expand=True, padx=10, pady=8)
        txt = tk.Text(frm, bg=BG2, fg=TEXT, font=("Courier New",11),
                      relief="flat", bd=0, wrap="none", padx=10, pady=8,
                      state="disabled", selectbackground="#d4d0f8")
        vsb = ttk.Scrollbar(frm, orient="vertical",   command=txt.yview)
        hsb = ttk.Scrollbar(frm, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        txt.pack(side="left",   fill="both", expand=True)
        return txt

    # ── LÓGICA ───────────────────────────────────────────
    def _set_modo(self, modo):
        self._diagrama.set_modo(modo)
        if modo == "mover":
            self._btn_mover.config(bg=ACCENT, fg="white")
            self._btn_conn.config(bg=BG4, fg=TEXT)
            self._modo_lbl.config(text="  ✥  Arrastra nodos libremente", fg=ACCENT)
        else:
            self._btn_mover.config(bg=BG4, fg=TEXT)
            self._btn_conn.config(bg=GREEN, fg="white")
            self._modo_lbl.config(
                text="  →  Clic en origen → clic en destino para conectar", fg=GREEN)

    def _on_codigo_change(self):
        n = len(self._diagrama._nodos)
        self._ncount.config(text=f"{n} nodo{'s' if n!=1 else ''}")
        codigo = self._diagrama.obtener_codigo()
        self._write(self._cod_text, codigo, clear=True)
        self._hl_codigo(self._cod_text)

    def _on_limpiar(self):
        self._diagrama.limpiar()
        for w in (self._cod_text, self._ast_text, self._asm_text, self._console):
            self._write(w, "", clear=True)
        for item in self._tree.get_children(): self._tree.delete(item)
        self._set_status("", "Listo")

    def _on_compilar(self):
        codigo = self._diagrama.obtener_codigo().strip()
        if not codigo or not self._diagrama._nodos:
            self._set_status("warn", "El diagrama está vacío"); return
        self._btn_comp.config(state="disabled", text="⏳ Compilando...")
        self._set_status("", "Compilando...")
        threading.Thread(target=lambda: self.after(0, self._mostrar(compilar_codigo(codigo))),
                         daemon=True).start()

    def _mostrar(self, r):
        self._btn_comp.config(state="normal", text="▶  Compilar y Ejecutar")
        self._write(self._console, "", clear=True)

        if r["error"]:
            fase, msg = r["fase"] or "?", r["error"]
            self._set_status("error", f"Error {fase}: {msg}")
            self._write(self._ast_text, f"✕  Error en fase '{fase}':\n\n{msg}\n", clear=True)
            if r["tokens"]: self._render_tokens(r["tokens"])
            self._log(f"[ERROR {fase}] {msg}", "err")
            self._nb.select(4)
            return

        if r["tokens"]:
            self._render_tokens(r["tokens"])
            self._log(f"✓ Léxico: {len(r['tokens'])} tokens", "ok")
        if r["ast"]:
            self._write(self._ast_text, json.dumps(r["ast"],indent=2,ensure_ascii=False), clear=True)
            self._log("✓ Sintáctico y semántico sin errores", "ok")
        if r["asm"]:
            self._write(self._asm_text, r["asm"], clear=True)
            self._asm_colors(self._asm_text)
            self._log(f"✓ ASM generado ({len(r['asm'].splitlines())} líneas)", "ok")
        if r["stdout"]:
            self._log("─"*36, "info")
            self._log("=== SALIDA DEL PROGRAMA ===", "info")
            for ln in r["stdout"].splitlines(): self._log(ln, "out")
            self._log("─"*36, "info")
        if r["stderr"]:
            self._log(f"! {r['stderr']}", "warn")

        self._set_status("ok", "✓ Compilado" + (" y ejecutado" if r["ejecutado"] else " (sin ejecución)"))
        self._nb.select(4)

    # ── UTILIDADES ───────────────────────────────────────
    def _write(self, w, text, clear=False, tag=None):
        w.config(state="normal")
        if clear: w.delete("1.0","end")
        w.insert("end", text, tag or "")
        w.config(state="disabled")

    def _log(self, msg, kind="info"):
        prefix = {"ok":"✓ ","err":"✕ ","warn":"! ","out":"▸ ","info":"  "}.get(kind,"  ")
        self._write(self._console, prefix+msg+"\n", tag=kind)
        self._console.see("end")

    def _render_tokens(self, tokens):
        for item in self._tree.get_children(): self._tree.delete(item)
        for i,(tipo,valor) in enumerate(tokens,1):
            self._tree.insert("","end", values=(i,tipo,valor), tags=(tipo,))

    def _set_status(self, kind, text):
        c = {"ok":GREEN,"error":RED,"warn":AMBER}.get(kind, MUTED)
        self._dot.config(fg=c); self._status.config(text=text)

    def _hl_codigo(self, w):
        w.config(state="normal")
        for tag in ("kw","str","num","cm"):
            w.tag_remove(tag,"1.0","end")
        w.tag_config("kw",  foreground=ACCENT, font=("Courier New",11,"bold"))
        w.tag_config("str", foreground=AMBER)
        w.tag_config("num", foreground=GREEN)
        w.tag_config("cm",  foreground=MUTED, font=("Courier New",11,"italic"))
        txt = w.get("1.0","end-1c")
        def idx(pos):
            ls = txt[:pos].split("\n")
            return f"{len(ls)}.{len(ls[-1])}"
        for pat,tag in [(r'//[^\n]*',"cm"),(r'"[^"]*"',"str"),
                         (r'\b(int|float|void|if|else|while|for|return|print|println)\b',"kw"),
                         (r'\b\d+\.?\d*\b',"num")]:
            for m in re.finditer(pat, txt):
                w.tag_add(tag, idx(m.start()), idx(m.end()))
        w.config(state="disabled")

    def _asm_colors(self, w):
        w.config(state="normal")
        for i,line in enumerate(w.get("1.0","end-1c").split("\n"),1):
            s=line.strip(); st=f"{i}.0"; en=f"{i}.{len(line)}"
            if s.startswith("section "): w.tag_add("sec",st,en)
            elif re.match(r'^[a-zA-Z_]\w*:',s): w.tag_add("lbl",st,en)
            elif s.startswith(";"): w.tag_add("cmt",st,en)
        w.config(state="disabled")


# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = CompiladorIDE()
    app.mainloop()