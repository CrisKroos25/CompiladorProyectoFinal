section .data
    newline  db  0x0A          ; salto de linea
    str_0  db  'Inicio del programa', 0
    str_0_len  equ  $ - str_0 - 1
    str_1  db  'Resultado de suma(3,4): ', 0
    str_1_len  equ  $ - str_1 - 1
    str_2  db  'x es mayor que 5', 0
    str_2_len  equ  $ - str_2 - 1
    str_3  db  'x es menor o igual a 5', 0
    str_3_len  equ  $ - str_3 - 1

section .bss
    digbuf:  resb 12
    c:  resd 1
    a:  resd 1
    b:  resd 1
    resultado:  resd 1
    x:  resd 1

section .text
global _start


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


suma:
    push  ebp
    mov   ebp, esp
    mov   eax, [ebp+8]   ; param 'a'
    mov  [a], eax
    mov   eax, [ebp+12]   ; param 'b'
    mov  [b], eax
    mov  eax, [a]
    push  eax
    mov  eax, [b]
    mov   ebx, eax
    pop   eax
    add   eax, ebx
    mov  [c], eax
    mov  eax, [c]
    pop   ebp
    ret

_start:
main:
    ; println string 'Inicio del programa'
    mov  eax, 4         ; sys_write
    mov  ebx, 1         ; stdout
    mov  ecx, str_0
    mov  edx, 19
    int  0x80
    ; newline
    mov  eax, 4
    mov  ebx, 1
    mov  ecx, newline
    mov  edx, 1
    int  0x80
    mov  eax, 4
    push  eax
    mov  eax, 3
    push  eax
    call  suma
    add   esp, 8   ; limpiar 2 arg(s) del stack
    mov  [resultado], eax
    ; print string 'Resultado de suma(3,4): '
    mov  eax, 4         ; sys_write
    mov  ebx, 1         ; stdout
    mov  ecx, str_1
    mov  edx, 24
    int  0x80
    mov  eax, [resultado]
    ; println entero (con newline)
    call __println_int
    mov  eax, 10
    mov  [x], eax
    mov  eax, [x]
    push  eax
    mov  eax, 5
    mov   ebx, eax
    pop   eax
    cmp   eax, ebx
    mov   eax, 0
    jg   cmp_t_2866880701264
    jmp   cmp_e_2866880701264
cmp_t_2866880701264:
    mov   eax, 1
cmp_e_2866880701264:
    cmp  eax, 0
    je   else_2866880992592
    ; println string 'x es mayor que 5'
    mov  eax, 4         ; sys_write
    mov  ebx, 1         ; stdout
    mov  ecx, str_2
    mov  edx, 16
    int  0x80
    ; newline
    mov  eax, 4
    mov  ebx, 1
    mov  ecx, newline
    mov  edx, 1
    int  0x80
    jmp  fin_if_2866880992592
else_2866880992592:
    ; println string 'x es menor o igual a 5'
    mov  eax, 4         ; sys_write
    mov  ebx, 1         ; stdout
    mov  ecx, str_3
    mov  edx, 22
    int  0x80
    ; newline
    mov  eax, 4
    mov  ebx, 1
    mov  ecx, newline
    mov  edx, 1
    int  0x80
fin_if_2866880992592:
    ; salida del proceso via syscall exit
    mov  eax, 1
    xor  ebx, ebx
    int  0x80