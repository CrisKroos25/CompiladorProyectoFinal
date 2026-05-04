import re

# === Análisis Léxico ===
# Definir los patrones para los diferentes tipos de tokens
token_patron = {
    "KEYWORD":    r'\b(if|else|while|for|return|int|float|void|println|print)\b',
    "STRING":     r'"[^"]*"',
    "IDENTIFIER": r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',
    "NUMBER":     r'\b\d+(\.\d+)?\b',
    "OPERATOR":   r'[+\-*/=<>!]=?|&&|\|\|',
    "DELIMITER":  r'[();{},]',
    "WHITESPACE": r'\s+',
}

def identificar_tokens(texto):
    patron_general = '|'.join(
        f'(?P<{token}>{patron})'
        for token, patron in token_patron.items()
    )
    patron_regex = re.compile(patron_general)
    tokens_encontrados = []
    for match in patron_regex.finditer(texto):
        for token, valor in match.groupdict().items():
            if valor is not None and token != "WHITESPACE":
                tokens_encontrados.append((token, valor))
    return tokens_encontrados


# ==========================
# DEFINICIÓN DEL AST
# ==========================

class NodoAST():
    # Clase base para todos los nodos del AST

    def traducirPy(self):
        raise NotImplementedError("Metodo traducirPy() no implementado en este Nodo.")

    def traducirRuby(self):
        raise NotImplementedError("Metodo traducirRuby() no implementado en este Nodo.")

    def generarCodigo(self, ctx=None):
        raise NotImplementedError("Metodo generarCodigo() no implementado en este Nodo.")


# ==========================
# CONTEXTO DE COMPILACION
# ==========================
# El contexto viaja por todo el árbol para recolectar:
#   - cadenas literales (.data)
#   - variables enteras    (.bss)
# Así el NodoPrograma puede emitir las secciones correctas al final.

class ContextoCodigo:
    def __init__(self):
        self.strings   = {}   # label -> valor_string  (para .data)
        self.variables = []   # [(tipo, nombre)]        (para .bss)
        self.externs   = set() # nombres de funciones externas
        self._str_cnt  = 0

    def agregar_string(self, valor):
        """Registra una cadena literal y devuelve su etiqueta .data."""
        # Buscar si ya existe
        for lbl, val in self.strings.items():
            if val == valor:
                return lbl
        lbl = f"str_{self._str_cnt}"
        self._str_cnt += 1
        self.strings[lbl] = valor
        return lbl

    def agregar_variable(self, tipo, nombre):
        if (tipo, nombre) not in self.variables:
            self.variables.append((tipo, nombre))

    def agregar_extern(self, nombre):
        self.externs.add(nombre)

    def seccion_data(self):
        """Genera la sección .data con todas las cadenas y el caracter newline."""
        lineas = ["section .data"]
        lineas.append("    newline  db  0x0A          ; salto de linea")
        # NOTA: digbuf va en .bss porque es un buffer mutable (se escribe en runtime)
        for lbl, valor in self.strings.items():
            # valor tiene las comillas incluidas: "hola" -> hola
            contenido = valor[1:-1]  # quitar comillas
            escaped   = contenido.replace("\\n", "', 0x0A, '")
            lineas.append(f"    {lbl}  db  '{escaped}', 0")
            lineas.append(f"    {lbl}_len  equ  $ - {lbl} - 1")
        return "\n".join(lineas)

    def seccion_bss(self):
        """Genera la sección .bss con todas las variables enteras y el buffer mutable."""
        lineas = ["section .bss"]
        # digbuf va aquí porque es un buffer que se escribe en runtime (__int_to_str)
        lineas.append("    digbuf:  resb 12")
        for tipo, nombre in self.variables:
            if tipo == 'int':
                lineas.append(f"    {nombre}:  resd 1")
        return "\n".join(lineas)


# ==========================
# RUTINAS AUXILIARES NASM
# ==========================
# Estas rutinas se insertan UNA SOLA VEZ en la sección .text.
# - __int_to_str : convierte EAX (entero) a string en digbuf, devuelve ptr en ESI y len en ECX
# - __print_int  : llama __int_to_str y hace sys_write sin newline
# - __println_int: llama __int_to_str y hace sys_write + newline

RUTINAS_AUX = """
; -------------------------------------------------------
; __int_to_str: convierte EAX a decimal ASCII en digbuf
;   Entrada : EAX = entero a convertir
;   Salida  : ESI = puntero al primer digito en digbuf
;             ECX = longitud de la cadena
; -------------------------------------------------------
__int_to_str:
    push ebx
    push edx
    push edi
    mov  edi, digbuf        ; apuntar al buffer
    add  edi, 11            ; empezar por el final
    mov  byte [edi], 0      ; terminador nulo
    mov  ebx, 10            ; divisor decimal
    test eax, eax
    jnz  .convertir
    ; caso especial: eax == 0
    dec  edi
    mov  byte [edi], '0'
    jmp  .fin
.convertir:
    test eax, eax
    jz   .fin
    xor  edx, edx
    div  ebx                ; eax = cociente, edx = resto
    add  dl, '0'
    dec  edi
    mov  [edi], dl
    jmp  .convertir
.fin:
    mov  esi, edi           ; ESI = inicio del string
    mov  ecx, digbuf
    add  ecx, 11
    sub  ecx, esi           ; ECX = longitud
    pop  edi
    pop  edx
    pop  ebx
    ret

; -------------------------------------------------------
; __print_int: imprime EAX como entero decimal (sin newline)
;   Entrada : EAX = entero
; -------------------------------------------------------
__print_int:
    call __int_to_str       ; ESI = ptr, ECX = len
    mov  eax, 4             ; sys_write
    mov  ebx, 1             ; stdout
    ; ecx = ptr (usar esi)
    push ecx
    mov  ecx, esi
    pop  edx                ; edx = longitud
    int  0x80
    ret

; -------------------------------------------------------
; __println_int: imprime EAX como entero decimal + newline
;   Entrada : EAX = entero
; -------------------------------------------------------
__println_int:
    call __int_to_str       ; ESI = ptr, ECX = len
    mov  eax, 4
    mov  ebx, 1
    push ecx
    mov  ecx, esi
    pop  edx
    int  0x80
    ; imprimir newline
    mov  eax, 4
    mov  ebx, 1
    mov  ecx, newline
    mov  edx, 1
    int  0x80
    ret
"""


# ==========================
# NODO PROGRAMA
# ==========================

class NodoPrograma(NodoAST):
    def __init__(self, funciones, main):
        self.funciones = funciones
        self.main      = main

    def generarCodigo(self, ctx=None):
        ctx = ContextoCodigo()

        def recolectar_variables(instrucciones):
            """Recorre recursivamente bloques anidados para registrar todas las variables."""
            for inst in instrucciones:
                if isinstance(inst, NodoAsignacion):
                    ctx.agregar_variable(inst.tipo[1], inst.nombre[1])
                elif isinstance(inst, NodoIf):
                    recolectar_variables(inst.cuerpo_if)
                    if inst.cuerpo_else:
                        recolectar_variables(inst.cuerpo_else)
                elif isinstance(inst, NodoWhile):
                    recolectar_variables(inst.cuerpo)
                elif isinstance(inst, NodoFor):
                    # El inicio del for puede declarar una variable (ej: int k = 0)
                    recolectar_variables([inst.inicio])
                    recolectar_variables(inst.cuerpo)

        # --- Recolectar variables de funciones (cuerpo + parametros) ---
        for funcion in self.funciones:
            recolectar_variables(funcion.cuerpo)
            for param in funcion.parametros:
                ctx.agregar_variable(param.tipo[1], param.nombre[1])

        # --- Recolectar variables del main (incluyendo bloques anidados) ---
        recolectar_variables(self.main.cuerpo)

        # --- Generar código de funciones y main ---
        texto_funciones = []
        for funcion in self.funciones:
            texto_funciones.append(funcion.generarCodigo(ctx))

        texto_main = self.main.generarCodigo(ctx)

        # --- Ensamblar secciones ---
        seccion_data = ctx.seccion_data()
        seccion_bss  = ctx.seccion_bss()

        texto = []
        texto.append(seccion_data)
        texto.append("")
        texto.append(seccion_bss)
        texto.append("")
        texto.append("section .text")
        texto.append("global _start")
        for ext in sorted(ctx.externs):
            texto.append(f"extern {ext}")
        texto.append("")
        texto.append(RUTINAS_AUX)
        texto.append("")
        for tf in texto_funciones:
            texto.append(tf)
            texto.append("")
        texto.append("_start:")
        # El main ahora emite la syscall exit internamente (ver NodoFuncion.generarCodigo).
        # _start solo necesita saltar al cuerpo de main.
        texto.append(texto_main)

        return "\n".join(texto)

    def traducirPy(self):
        resultado = [f.traducirPy() for f in self.funciones]
        resultado.append(self.main.traducirPy())
        return "\n\n".join(resultado)

    def traducirRuby(self):
        resultado = [f.traducirRuby() for f in self.funciones]
        resultado.append(self.main.traducirRuby())
        return "\n\n".join(resultado)


# ==========================
# NODO FUNCION
# ==========================

class NodoFuncion(NodoAST):
    def __init__(self, tipo, nombre, parametros, cuerpo):
        self.tipo       = tipo
        self.nombre     = nombre
        self.parametros = parametros
        self.cuerpo     = cuerpo

    def generarCodigo(self, ctx=None):
        es_main = self.nombre[1] == 'main'
        lineas  = [f"{self.nombre[1]}:"]

        if self.parametros:
            # Convencion cdecl: al entrar a la funcion el stack es:
            #   [esp]   = direccion de retorno  (push por call)
            #   [esp+4] = primer argumento
            #   [esp+8] = segundo argumento ...
            # Guardamos ebp como frame pointer para acceder a los args de forma estable.
            lineas.append("    push  ebp")
            lineas.append("    mov   ebp, esp")
            for i, param in enumerate(self.parametros):
                offset = 8 + i * 4  # ebp+8 = arg1, ebp+12 = arg2, etc.
                lineas.append(f"    mov   eax, [ebp+{offset}]   ; param \'{param.nombre[1]}\'")
                lineas.append(f"    mov  [{param.nombre[1]}], eax")

        for inst in self.cuerpo:
            lineas.append(inst.generarCodigo(ctx))

        if self.parametros:
            lineas.append("    pop   ebp")

        if es_main:
            # _start no tiene caller: usar ret aqui causaria segfault.
            # La syscall exit (eax=1) termina el proceso correctamente.
            lineas.append("    ; salida del proceso via syscall exit")
            lineas.append("    mov  eax, 1")
            lineas.append("    xor  ebx, ebx")
            lineas.append("    int  0x80")
        else:
            lineas.append("    ret")

        return "\n".join(lineas)

    def traducirPy(self):
        params = ", ".join(p.traducirPy() for p in self.parametros)
        lineas = []
        for c in self.cuerpo:
            try:    lineas.append(c.traducirPy(indent=1))
            except TypeError: lineas.append(c.traducirPy())
        return f"def {self.nombre[1]}({params}):\n    " + "\n    ".join(lineas)

    def traducirRuby(self):
        params = ", ".join(p.traducirRuby() for p in self.parametros)
        lineas = []
        for c in self.cuerpo:
            try:    lineas.append(c.traducirRuby(indent=1))
            except TypeError: lineas.append(c.traducirRuby())
        return f"def {self.nombre[1]}({params})\n    " + "\n    ".join(lineas) + "\nend"


# ==========================
# NODO LLAMADA A FUNCION
# ==========================

class NodoLlamadaFuncion(NodoAST):
    def __init__(self, nombref, argumentos):
        self.nombre_funcion = nombref
        self.argumentos     = argumentos

    def traducirPy(self):
        args = ", ".join(a.traducirPy() for a in self.argumentos)
        if self.nombre_funcion == "print":   return f"print({args}, end='')"
        if self.nombre_funcion == "println": return f"print({args})"
        return f"{self.nombre_funcion}({args})"

    def traducirRuby(self):
        args = ", ".join(a.traducirRuby() for a in self.argumentos)
        if self.nombre_funcion == "print":   return f"print {args}"
        if self.nombre_funcion == "println": return f"puts {args}"
        return f"{self.nombre_funcion}({args})"

    def generarCodigo(self, ctx=None):
        if self.nombre_funcion == 'printf':
            ctx.agregar_extern('printf')
            lineas = []
            for arg in reversed(self.argumentos):
                lineas.append(arg.generarCodigo(ctx))
                lineas.append("    push  eax")
            lineas.append(f"    call  {self.nombre_funcion}")
            lineas.append(f"    add   esp, {4 * len(self.argumentos)}")
            return "\n".join(lineas)
        else:
            # Funciones internas (convencion cdecl)
            lineas = []
            # Empujar argumentos en orden inverso (cdecl: el ultimo argumento primero)
            for arg in reversed(self.argumentos):
                lineas.append(arg.generarCodigo(ctx))
                lineas.append("    push  eax")
            lineas.append(f"    call  {self.nombre_funcion}")
            # El caller es responsable de limpiar el stack despues del call
            if self.argumentos:
                lineas.append(f"    add   esp, {4 * len(self.argumentos)}   ; limpiar {len(self.argumentos)} arg(s) del stack")
            return "\n".join(lineas)


# ==========================
# NODO PRINT
# ==========================

class NodoPrint(NodoAST):
    # print(expr) — imprime sin salto de linea
    def __init__(self, expresion):
        self.expresion = expresion

    def traducirPy(self):
        return f"print({self.expresion.traducirPy()}, end='')"

    def traducirRuby(self):
        return f"print {self.expresion.traducirRuby()}"

    def generarCodigo(self, ctx=None):
        """
        Si la expresion es un NodoString → sys_write directo de la cadena en .data
        Si la expresion es numerica/variable → llamar __print_int (entero a decimal)
        """
        lineas = []
        if isinstance(self.expresion, NodoString):
            # Registrar cadena en .data y hacer sys_write
            lbl = ctx.agregar_string(self.expresion.valor[1]
                                     if isinstance(self.expresion.valor, tuple)
                                     else self.expresion.valor)
            # Calcular longitud real (sin comillas, con newline escapado)
            contenido = (self.expresion.valor[1]
                         if isinstance(self.expresion.valor, tuple)
                         else self.expresion.valor)
            contenido = contenido[1:-1]  # quitar comillas
            longitud  = len(contenido.replace("\\n", "\n"))
            lineas.append(f"    ; print string '{contenido}'")
            lineas.append(f"    mov  eax, 4         ; sys_write")
            lineas.append(f"    mov  ebx, 1         ; stdout")
            lineas.append(f"    mov  ecx, {lbl}")
            lineas.append(f"    mov  edx, {longitud}")
            lineas.append(f"    int  0x80")
        else:
            # Expresion entera: evaluar en EAX, llamar __print_int
            lineas.append(self.expresion.generarCodigo(ctx))
            lineas.append("    ; print entero (sin newline)")
            lineas.append("    call __print_int")
        return "\n".join(lineas)


# ==========================
# NODO PRINTLN
# ==========================

class NodoPrintln(NodoAST):
    # println(expr) — imprime con salto de linea
    def __init__(self, expresion):
        self.expresion = expresion

    def traducirPy(self):
        return f"print({self.expresion.traducirPy()})"

    def traducirRuby(self):
        return f"puts {self.expresion.traducirRuby()}"

    def generarCodigo(self, ctx=None):
        """
        Si la expresion es un NodoString → sys_write de cadena + sys_write de newline
        Si la expresion es numerica/variable → llamar __println_int
        """
        lineas = []
        if isinstance(self.expresion, NodoString):
            lbl = ctx.agregar_string(self.expresion.valor[1]
                                     if isinstance(self.expresion.valor, tuple)
                                     else self.expresion.valor)
            contenido = (self.expresion.valor[1]
                         if isinstance(self.expresion.valor, tuple)
                         else self.expresion.valor)
            contenido = contenido[1:-1]
            longitud  = len(contenido.replace("\\n", "\n"))
            lineas.append(f"    ; println string '{contenido}'")
            lineas.append(f"    mov  eax, 4         ; sys_write")
            lineas.append(f"    mov  ebx, 1         ; stdout")
            lineas.append(f"    mov  ecx, {lbl}")
            lineas.append(f"    mov  edx, {longitud}")
            lineas.append(f"    int  0x80")
            lineas.append(f"    ; newline")
            lineas.append(f"    mov  eax, 4")
            lineas.append(f"    mov  ebx, 1")
            lineas.append(f"    mov  ecx, newline")
            lineas.append(f"    mov  edx, 1")
            lineas.append(f"    int  0x80")
        else:
            lineas.append(self.expresion.generarCodigo(ctx))
            lineas.append("    ; println entero (con newline)")
            lineas.append("    call __println_int")
        return "\n".join(lineas)


# ==========================
# NODO IF / ELSE
# ==========================

class NodoIf(NodoAST):
    def __init__(self, condicion, cuerpo_if, cuerpo_else=None):
        self.condicion   = condicion
        self.cuerpo_if   = cuerpo_if
        self.cuerpo_else = cuerpo_else

    def generarCodigo(self, ctx=None):
        etq_else = f"else_{id(self)}"
        etq_fin  = f"fin_if_{id(self)}"
        lineas   = []
        lineas.append(self.condicion.generarCodigo(ctx))
        lineas.append("    cmp  eax, 0")
        lineas.append(f"    je   {etq_else if self.cuerpo_else else etq_fin}")
        for inst in self.cuerpo_if:
            lineas.append(inst.generarCodigo(ctx))
        if self.cuerpo_else:
            lineas.append(f"    jmp  {etq_fin}")
            lineas.append(f"{etq_else}:")
            for inst in self.cuerpo_else:
                lineas.append(inst.generarCodigo(ctx))
        lineas.append(f"{etq_fin}:")
        return "\n".join(lineas)

    def traducirPy(self, indent=0):
        tab = "    " * indent
        cond = self.condicion.traducirPy()
        ci   = f"\n{tab}    ".join(c.traducirPy() for c in self.cuerpo_if)
        res  = f"if {cond}:\n{tab}    {ci}"
        if self.cuerpo_else:
            ce  = f"\n{tab}    ".join(c.traducirPy() for c in self.cuerpo_else)
            res += f"\n{tab}else:\n{tab}    {ce}"
        return res

    def traducirRuby(self, indent=0):
        tab = "    " * indent
        cond = self.condicion.traducirRuby()
        ci   = f"\n{tab}    ".join(c.traducirRuby() for c in self.cuerpo_if)
        res  = f"if {cond}\n{tab}    {ci}"
        if self.cuerpo_else:
            ce  = f"\n{tab}    ".join(c.traducirRuby() for c in self.cuerpo_else)
            res += f"\n{tab}else\n{tab}    {ce}"
        return res + f"\n{tab}end"


# ==========================
# NODO WHILE
# ==========================

class NodoWhile(NodoAST):
    def __init__(self, condicion, cuerpo):
        self.condicion = condicion
        self.cuerpo    = cuerpo

    def generarCodigo(self, ctx=None):
        etq_ini = f"ini_while_{id(self)}"
        etq_fin = f"fin_while_{id(self)}"
        lineas  = []
        lineas.append(f"{etq_ini}:")
        lineas.append(self.condicion.generarCodigo(ctx))
        lineas.append("    cmp  eax, 0")
        lineas.append(f"    je   {etq_fin}")
        for inst in self.cuerpo:
            lineas.append(inst.generarCodigo(ctx))
        lineas.append(f"    jmp  {etq_ini}")
        lineas.append(f"{etq_fin}:")
        return "\n".join(lineas)

    def traducirPy(self, indent=0):
        tab  = "    " * indent
        cond = self.condicion.traducirPy()
        cuerpo = f"\n{tab}    ".join(c.traducirPy() for c in self.cuerpo)
        return f"while {cond}:\n{tab}    {cuerpo}"

    def traducirRuby(self, indent=0):
        tab  = "    " * indent
        cond = self.condicion.traducirRuby()
        cuerpo = f"\n{tab}    ".join(c.traducirRuby() for c in self.cuerpo)
        return f"while {cond}\n{tab}    {cuerpo}\n{tab}end"


# ==========================
# NODO FOR
# ==========================

class NodoFor(NodoAST):
    def __init__(self, inicio, condicion, incremento, cuerpo):
        self.inicio     = inicio
        self.condicion  = condicion
        self.incremento = incremento
        self.cuerpo     = cuerpo

    def generarCodigo(self, ctx=None):
        etq_ini = f"ini_for_{id(self)}"
        etq_fin = f"fin_for_{id(self)}"
        lineas  = []
        lineas.append(self.inicio.generarCodigo(ctx))
        lineas.append(f"{etq_ini}:")
        lineas.append(self.condicion.generarCodigo(ctx))
        lineas.append("    cmp  eax, 0")
        lineas.append(f"    je   {etq_fin}")
        for inst in self.cuerpo:
            lineas.append(inst.generarCodigo(ctx))
        lineas.append(self.incremento.generarCodigo(ctx))
        lineas.append(f"    jmp  {etq_ini}")
        lineas.append(f"{etq_fin}:")
        return "\n".join(lineas)

    def traducirPy(self, indent=0):
        tab  = "    " * indent
        ini  = self.inicio.traducirPy()
        cond = self.condicion.traducirPy()
        inc  = self.incremento.traducirPy()
        cuerpo = f"\n{tab}    ".join(c.traducirPy() for c in self.cuerpo)
        return f"{ini}\n{tab}while {cond}:\n{tab}    {cuerpo}\n{tab}    {inc}"

    def traducirRuby(self, indent=0):
        tab  = "    " * indent
        ini  = self.inicio.traducirRuby()
        cond = self.condicion.traducirRuby()
        inc  = self.incremento.traducirRuby()
        cuerpo = f"\n{tab}    ".join(c.traducirRuby() for c in self.cuerpo)
        return f"{ini}\n{tab}while {cond}\n{tab}    {cuerpo}\n{tab}    {inc}\n{tab}end"


# ==========================
# NODOS BÁSICOS
# ==========================

class NodoParametro(NodoAST):
    def __init__(self, tipo, nombre):
        self.tipo   = tipo
        self.nombre = nombre

    def traducirPy(self):  return self.nombre[1]
    def traducirRuby(self): return self.nombre[1]


class NodoAsignacion(NodoAST):
    # int x = expr
    def __init__(self, tipo, nombre, expresion):
        self.tipo     = tipo
        self.nombre   = nombre
        self.expresion = expresion

    def generarCodigo(self, ctx=None):
        lineas = [self.expresion.generarCodigo(ctx)]
        lineas.append(f"    mov  [{self.nombre[1]}], eax")
        return "\n".join(lineas)

    def traducirPy(self):   return f"{self.nombre[1]} = {self.expresion.traducirPy()}"
    def traducirRuby(self): return f"{self.nombre[1]} = {self.expresion.traducirRuby()}"


class NodoReasignacion(NodoAST):
    # x = expr  (sin tipo)
    def __init__(self, nombre, expresion):
        self.nombre    = nombre
        self.expresion = expresion

    def generarCodigo(self, ctx=None):
        lineas = [self.expresion.generarCodigo(ctx)]
        lineas.append(f"    mov  [{self.nombre[1]}], eax")
        return "\n".join(lineas)

    def traducirPy(self):   return f"{self.nombre[1]} = {self.expresion.traducirPy()}"
    def traducirRuby(self): return f"{self.nombre[1]} = {self.expresion.traducirRuby()}"


class NodoOperacion(NodoAST):
    def __init__(self, izquierda, operador, derecha):
        self.izquierda = izquierda
        self.operador  = operador
        self.derecha   = derecha

    def generarCodigo(self, ctx=None):
        lineas = []
        lineas.append(self.izquierda.generarCodigo(ctx))
        lineas.append("    push  eax")
        lineas.append(self.derecha.generarCodigo(ctx))
        lineas.append("    mov   ebx, eax")
        lineas.append("    pop   eax")
        op = self.operador[1]
        if   op == '+': lineas.append("    add   eax, ebx")
        elif op == '-': lineas.append("    sub   eax, ebx")
        elif op == '*': lineas.append("    imul  eax, ebx")
        elif op in ('<', '>', '<=', '>=', '==', '!='):
            salto = {'<':'jl', '>':'jg', '<=':'jle', '>=':'jge', '==':'je', '!=':'jne'}[op]
            etq_t = f"cmp_t_{id(self)}"
            etq_e = f"cmp_e_{id(self)}"
            lineas.append("    cmp   eax, ebx")
            lineas.append("    mov   eax, 0")
            lineas.append(f"    {salto}   {etq_t}")
            lineas.append(f"    jmp   {etq_e}")
            lineas.append(f"{etq_t}:")
            lineas.append("    mov   eax, 1")
            lineas.append(f"{etq_e}:")
        return "\n".join(lineas)

    def traducirPy(self):
        return f"{self.izquierda.traducirPy()} {self.operador[1]} {self.derecha.traducirPy()}"

    def traducirRuby(self):
        return f"{self.izquierda.traducirRuby()} {self.operador[1]} {self.derecha.traducirRuby()}"


class NodoRetorno(NodoAST):
    def __init__(self, expresion):
        self.expresion = expresion

    def generarCodigo(self, ctx=None):
        return self.expresion.generarCodigo(ctx)

    def traducirPy(self):   return f"return {self.expresion.traducirPy()}"
    def traducirRuby(self): return f"return {self.expresion.traducirRuby()}"


class NodoIdentificador(NodoAST):
    def __init__(self, nombre):
        self.nombre = nombre

    def generarCodigo(self, ctx=None):
        return f"    mov  eax, [{self.nombre[1]}]"

    def traducirPy(self):   return self.nombre[1]
    def traducirRuby(self): return self.nombre[1]


class NodoNumero(NodoAST):
    def __init__(self, valor):
        self.valor = valor

    def generarCodigo(self, ctx=None):
        v = self.valor[1] if isinstance(self.valor, tuple) else str(self.valor)
        return f"    mov  eax, {v}"

    def traducirPy(self):
        return str(self.valor[1]) if isinstance(self.valor, tuple) else str(self.valor)

    def traducirRuby(self):
        return str(self.valor[1]) if isinstance(self.valor, tuple) else str(self.valor)


class NodoString(NodoAST):
    def __init__(self, valor):
        self.valor = valor   # token (STRING, '"texto"')

    def generarCodigo(self, ctx=None):
        # Las cadenas solas no generan código inline; se manejan en NodoPrint/NodoPrintln
        lbl = ctx.agregar_string(self.valor[1] if isinstance(self.valor, tuple) else self.valor)
        return f"    ; referencia string {lbl}"

    def traducirPy(self):
        return self.valor[1] if isinstance(self.valor, tuple) else self.valor

    def traducirRuby(self):
        return self.valor[1] if isinstance(self.valor, tuple) else self.valor