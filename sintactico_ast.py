import lexico

# Analizador sintactico
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def obtener_token_actual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def coincidir(self, tipo_esperado):
        token_actual = self.obtener_token_actual()
        if token_actual and token_actual[0] == tipo_esperado:
            self.pos += 1
            return token_actual
        else:
            raise SyntaxError(f"Error sintactico: Se esperaba {tipo_esperado}, pero se encontro: {token_actual}")

    # ----------------------------------------
    # PUNTO DE ENTRADA
    # ----------------------------------------

    def parsear(self):
        funciones = []
        main = None
        while self.obtener_token_actual() is not None:
            nodo_funcion = self.funcion()
            if nodo_funcion.nombre[1] == 'main':
                main = nodo_funcion
            else:
                funciones.append(nodo_funcion)
        return lexico.NodoPrograma(funciones, main)

    # ----------------------------------------
    # FUNCION
    # ----------------------------------------

    def funcion(self):
        # Gramatica: tipo IDENTIFIER ( [parametros] ) { cuerpo }
        tipo_retorno   = self.coincidir('KEYWORD')          # tipo de retorno
        nombre_funcion = self.coincidir('IDENTIFIER')       # nombre
        self.coincidir('DELIMITER')                         # (

        if nombre_funcion[1] == 'main':
            parametros = []
        else:
            if self.obtener_token_actual() and self.obtener_token_actual()[1] == ')':
                parametros = []
            else:
                parametros = self.parametros()

        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # {
        cuerpo = self.cuerpo()
        self.coincidir('DELIMITER')                         # }

        # Consumir ; opcional despues de } (ej. };)
        if self.obtener_token_actual() and self.obtener_token_actual()[1] == ';':
            self.coincidir('DELIMITER')

        return lexico.NodoFuncion(tipo_retorno, nombre_funcion, parametros, cuerpo)

    # ----------------------------------------
    # PARAMETROS
    # ----------------------------------------

    def parametros(self):
        lista = []
        tipo   = self.coincidir('KEYWORD')
        nombre = self.coincidir('IDENTIFIER')
        lista.append(lexico.NodoParametro(tipo, nombre))
        while self.obtener_token_actual() and self.obtener_token_actual()[1] == ',':
            self.coincidir('DELIMITER')
            tipo   = self.coincidir('KEYWORD')
            nombre = self.coincidir('IDENTIFIER')
            lista.append(lexico.NodoParametro(tipo, nombre))
        return lista

    # ----------------------------------------
    # CUERPO
    # ----------------------------------------

    def cuerpo(self):
        instrucciones = []
        while self.obtener_token_actual() and self.obtener_token_actual()[1] != '}':
            token = self.obtener_token_actual()

            if token[1] == 'return':
                instrucciones.append(self.retorno())

            elif token[1] == 'if':
                instrucciones.append(self.instruccion_if())
                if self.obtener_token_actual() and self.obtener_token_actual()[1] == ';':
                    self.coincidir('DELIMITER')

            elif token[1] == 'while':
                instrucciones.append(self.instruccion_while())
                if self.obtener_token_actual() and self.obtener_token_actual()[1] == ';':
                    self.coincidir('DELIMITER')

            elif token[1] == 'for':
                instrucciones.append(self.instruccion_for())
                if self.obtener_token_actual() and self.obtener_token_actual()[1] == ';':
                    self.coincidir('DELIMITER')

            elif token[1] == 'print':
                instrucciones.append(self.instruccion_print())

            elif token[1] == 'println':
                instrucciones.append(self.instruccion_println())

            elif token[0] == 'KEYWORD':
                instrucciones.append(self.asignacion())

            elif token[0] == 'IDENTIFIER':
                instrucciones.append(self.instruccion_identificador())

            else:
                raise SyntaxError(f"Instruccion no valida: {token}")

        return instrucciones

    # ----------------------------------------
    # INSTRUCCIONES
    # ----------------------------------------

    def asignacion(self):
        # tipo IDENTIFIER = expresion ;
        tipo      = self.coincidir('KEYWORD')
        nombre    = self.coincidir('IDENTIFIER')
        self.coincidir('OPERATOR')                          # =
        expresion = self.expresion()
        self.coincidir('DELIMITER')                         # ;
        return lexico.NodoAsignacion(tipo, nombre, expresion)

    def instruccion_identificador(self):
        # Reasignacion (x = ...) o llamada a funcion (f(...))
        identificador = self.coincidir('IDENTIFIER')
        token_sig = self.obtener_token_actual()

        if token_sig and token_sig[1] == '(':
            self.coincidir('DELIMITER')                     # (
            argumentos = self.llamadaFuncion()
            self.coincidir('DELIMITER')                     # )
            self.coincidir('DELIMITER')                     # ;
            return lexico.NodoLlamadaFuncion(identificador[1], argumentos)

        elif token_sig and token_sig[0] == 'OPERATOR' and token_sig[1] == '=':
            self.coincidir('OPERATOR')                      # =
            expresion = self.expresion()
            self.coincidir('DELIMITER')                     # ;
            return lexico.NodoReasignacion(identificador, expresion)

        else:
            raise SyntaxError(f"Se esperaba '(' o '=' despues de identificador, pero se encontro: {token_sig}")

    def retorno(self):
        self.coincidir('KEYWORD')                           # return
        expresion = self.expresion()
        self.coincidir('DELIMITER')                         # ;
        return lexico.NodoRetorno(expresion)

    # ----------------------------------------
    # PRINT / PRINTLN
    # ----------------------------------------

    def instruccion_print(self):
        # print ( expresion ) ;
        self.coincidir('KEYWORD')                           # print
        self.coincidir('DELIMITER')                         # (
        expresion = self.expresion()
        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # ;
        return lexico.NodoPrint(expresion)

    def instruccion_println(self):
        # println ( expresion ) ;
        self.coincidir('KEYWORD')                           # println
        self.coincidir('DELIMITER')                         # (
        expresion = self.expresion()
        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # ;
        return lexico.NodoPrintln(expresion)

    # ----------------------------------------
    # IF / ELSE
    # ----------------------------------------

    def instruccion_if(self):
        # if ( condicion ) { cuerpo } [else { cuerpo }]
        self.coincidir('KEYWORD')                           # if
        self.coincidir('DELIMITER')                         # (
        condicion = self.expresion()
        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # {
        cuerpo_if = self.cuerpo()
        self.coincidir('DELIMITER')                         # }

        cuerpo_else = None
        if self.obtener_token_actual() and self.obtener_token_actual()[1] == 'else':
            self.coincidir('KEYWORD')                       # else
            self.coincidir('DELIMITER')                     # {
            cuerpo_else = self.cuerpo()
            self.coincidir('DELIMITER')                     # }

        return lexico.NodoIf(condicion, cuerpo_if, cuerpo_else)

    # ----------------------------------------
    # WHILE
    # ----------------------------------------

    def instruccion_while(self):
        # while ( condicion ) { cuerpo }
        self.coincidir('KEYWORD')                           # while
        self.coincidir('DELIMITER')                         # (
        condicion = self.expresion()
        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # {
        cuerpo = self.cuerpo()
        self.coincidir('DELIMITER')                         # }
        return lexico.NodoWhile(condicion, cuerpo)

    # ----------------------------------------
    # FOR
    # ----------------------------------------

    def instruccion_for(self):
        # for ( inicio ; condicion ; incremento ) { cuerpo }
        self.coincidir('KEYWORD')                           # for
        self.coincidir('DELIMITER')                         # (

        token = self.obtener_token_actual()
        if token[0] == 'KEYWORD':
            inicio = self.asignacion()                      # tipo id = expr ;
        elif token[0] == 'IDENTIFIER':
            identificador = self.coincidir('IDENTIFIER')
            self.coincidir('OPERATOR')                      # =
            expresion = self.expresion()
            self.coincidir('DELIMITER')                     # ;
            inicio = lexico.NodoReasignacion(identificador, expresion)
        else:
            raise SyntaxError(f"Se esperaba inicio de for, pero se encontro: {token}")

        condicion = self.expresion()
        self.coincidir('DELIMITER')                         # ;

        identificador = self.coincidir('IDENTIFIER')
        self.coincidir('OPERATOR')                          # =
        expresion_inc = self.expresion()
        incremento = lexico.NodoReasignacion(identificador, expresion_inc)

        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # {
        cuerpo = self.cuerpo()
        self.coincidir('DELIMITER')                         # }

        return lexico.NodoFor(inicio, condicion, incremento, cuerpo)

    # ----------------------------------------
    # EXPRESIONES Y TÉRMINOS
    # ----------------------------------------

    def expresion(self):
        izquierda = self.termino()
        while self.obtener_token_actual() and self.obtener_token_actual()[0] == 'OPERATOR':
            if self.obtener_token_actual()[1] == '=':
                break
            operador  = self.coincidir('OPERATOR')
            derecha   = self.termino()
            izquierda = lexico.NodoOperacion(izquierda, operador, derecha)
        return izquierda

    def termino(self):
        token = self.obtener_token_actual()

        if token[0] == 'NUMBER':
            return lexico.NodoNumero(self.coincidir('NUMBER'))

        elif token[0] == 'STRING':
            return lexico.NodoString(self.coincidir('STRING'))

        elif token[0] == 'IDENTIFIER':
            identificador = self.coincidir('IDENTIFIER')
            if self.obtener_token_actual() and self.obtener_token_actual()[1] == '(':
                self.coincidir('DELIMITER')                 # (
                argumentos = self.llamadaFuncion()
                self.coincidir('DELIMITER')                 # )
                return lexico.NodoLlamadaFuncion(identificador[1], argumentos)
            return lexico.NodoIdentificador(identificador)

        elif token[0] == 'KEYWORD' and token[1] in ('print', 'println'):
            if token[1] == 'print':
                self.coincidir('KEYWORD')
                self.coincidir('DELIMITER')
                expresion = self.expresion()
                self.coincidir('DELIMITER')
                return lexico.NodoPrint(expresion)
            else:
                self.coincidir('KEYWORD')
                self.coincidir('DELIMITER')
                expresion = self.expresion()
                self.coincidir('DELIMITER')
                return lexico.NodoPrintln(expresion)

        else:
            raise SyntaxError(f'Expresion no valida: {token}')

    def llamadaFuncion(self):
        argumentos = []
        if self.obtener_token_actual() and self.obtener_token_actual()[1] == ')':
            return argumentos
        sigue = True
        while sigue:
            sigue = False
            argumentos.append(self.expresion())
            if self.obtener_token_actual() and self.obtener_token_actual()[1] == ',':
                self.coincidir('DELIMITER')
                sigue = True
        return argumentos

    def llamadaComoInstruccion(self):
        identificador = self.coincidir('IDENTIFIER')
        self.coincidir('DELIMITER')                         # (
        argumentos = self.llamadaFuncion()
        self.coincidir('DELIMITER')                         # )
        self.coincidir('DELIMITER')                         # ;
        return lexico.NodoLlamadaFuncion(identificador[1], argumentos)