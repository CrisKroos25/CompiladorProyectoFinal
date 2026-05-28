section .data
    newline  db  0x0A          ; salto de linea

section .bss
    digbuf:  resb 12
    a:  resd 1
    b:  resd 1
    x:  resd 1
    y:  resd 1
    resultado:  resd 1

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


maximo:
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
    cmp   eax, ebx
    mov   eax, 0
    jg   cmp_t_1516359112400
    jmp   cmp_e_1516359112400
cmp_t_1516359112400:
    mov   eax, 1
cmp_e_1516359112400:
    cmp  eax, 0
    je   else_1516316138128
    mov  eax, [a]
    jmp  fin_if_1516316138128
else_1516316138128:
    mov  eax, [b]
fin_if_1516316138128:
    pop   ebp
    ret

_start:
main:
    mov  eax, 8
    mov  [x], eax
    mov  eax, 3
    mov  [y], eax
    mov  eax, [y]
    push  eax
    mov  eax, [x]
    push  eax
    call  maximo
    add   esp, 8   ; limpiar 2 arg(s) del stack
    mov  [resultado], eax
    mov  eax, [resultado]
    ; println entero (con newline)
    call __println_int
    ; salida del proceso via syscall exit
    mov  eax, 1
    xor  ebx, ebx
    int  0x80