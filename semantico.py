# -------------- Análisis semántico ----------------
class TablaSimbolos:
    def __init__(self):
        self.tabla = {}
        self.ambito_actual = 'global'

    def declarar(self, nombre, tipo, ambito=None):
        if ambito is None:
            ambito = self.ambito_actual
        if ambito not in self.tabla:
            self.tabla[ambito] = {}
        if nombre in self.tabla[ambito]:
            raise Exception(f'Error semántico: {nombre} ya está declarado en el ámbito {ambito}')
        self.tabla[ambito][nombre] = {'tipo': tipo}

    def buscar(self, nombre, ambito=None):
        if ambito is None:
            ambito = self.ambito_actual
        if ambito in self.tabla and nombre in self.tabla[ambito]:
            return self.tabla[ambito][nombre]
        if ambito != 'global':
            return self.buscar(nombre, 'global')
        raise Exception(f'Error semántico: {nombre} no está definido')

    def entrar_ambito(self, nuevo_ambito):
        self.ambito_actual = nuevo_ambito

    def salir_ambito(self):
        if self.ambito_actual != 'global':
            self.ambito_actual = 'global'  # Simplificado, asumir solo global y función

class AnalizadorSemantico:
    def __init__(self):
        self.tabla_simbolos = TablaSimbolos()
        # Declarar funciones externas
        self.tabla_simbolos.declarar('printf', 'int')

    def analizar(self, nodo):
        metodo = f'visitar_{type(nodo).__name__}'
        if hasattr(self, metodo):
            return getattr(self, metodo)(nodo)
        else:
            raise Exception(f'No se ha implementado el análisis semántico para {type(nodo).__name__}')

    def visitar_NodoPrograma(self, nodo):
        for funcion in nodo.funciones:
            self.analizar(funcion)
        self.analizar(nodo.main)

    def visitar_NodoFuncion(self, nodo):
        self.tabla_simbolos.declarar(nodo.nombre[1], nodo.tipo[1])
        self.tabla_simbolos.entrar_ambito(nodo.nombre[1])
        for param in nodo.parametros:
            self.tabla_simbolos.declarar(param.nombre[1], param.tipo[1])
        for instruccion in nodo.cuerpo:
            self.analizar(instruccion)
        self.tabla_simbolos.salir_ambito()

    def visitar_NodoAsignacion(self, nodo):
        tipo_expresion = self.analizar(nodo.expresion)
        self.tabla_simbolos.declarar(nodo.nombre[1], tipo_expresion)

    def visitar_NodoReasignacion(self, nodo):
        tipo_expresion = self.analizar(nodo.expresion)
        simbolo = self.tabla_simbolos.buscar(nodo.nombre[1])
        if simbolo['tipo'] != tipo_expresion:
            raise Exception(f'Error semántico: No se puede asignar {tipo_expresion} a {simbolo["tipo"]}')

    def visitar_NodoOperacion(self, nodo):
        tipo_izq = self.analizar(nodo.izquierda)
        tipo_der = self.analizar(nodo.derecha)
        if tipo_izq != tipo_der:
            raise Exception(f'Error semántico: Operación entre tipos incompatibles {tipo_izq} y {tipo_der}')
        return tipo_izq

    def visitar_NodoNumero(self, nodo):
        return 'float' if '.' in str(nodo.valor) else 'int'

    def visitar_NodoString(self, nodo):
        return 'string'

    def visitar_NodoIdentificador(self, nodo):
        simbolo = self.tabla_simbolos.buscar(nodo.nombre[1])
        return simbolo['tipo']

    def visitar_NodoLlamadaFuncion(self, nodo):
        simbolo = self.tabla_simbolos.buscar(nodo.nombre_funcion)
        return simbolo['tipo']

    def visitar_NodoRetorno(self, nodo):
        return self.analizar(nodo.expresion)

    def visitar_NodoPrint(self, nodo):
        self.analizar(nodo.expresion)

    def visitar_NodoPrintln(self, nodo):
        self.analizar(nodo.expresion)

    def visitar_NodoIf(self, nodo):
        self.analizar(nodo.condicion)
        for inst in nodo.cuerpo_if:
            self.analizar(inst)
        if nodo.cuerpo_else:
            for inst in nodo.cuerpo_else:
                self.analizar(inst)

    def visitar_NodoWhile(self, nodo):
        self.analizar(nodo.condicion)
        for inst in nodo.cuerpo:
            self.analizar(inst)

    def visitar_NodoFor(self, nodo):
        self.analizar(nodo.inicio)
        self.analizar(nodo.condicion)
        self.analizar(nodo.incremento)
        for inst in nodo.cuerpo:
            self.analizar(inst)