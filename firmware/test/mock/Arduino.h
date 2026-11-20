// Stubs mínimos para verificar la sintaxis del sketch fuera del IDE (no simulan hardware).
#pragma once
#include <stdint.h>
#include <stddef.h>
enum { LOW = 0, HIGH = 1, INPUT = 0, OUTPUT = 1, SERIAL_8N1 = 0x06 };
enum { A0 = 100, A1, A2, A3, A4, A5, A6, A7, D0 = 0, D1, D2, D3, LED_D0 = 10, LED_D1, LED_D2, LED_D3 };
inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline int digitalRead(int) { return HIGH; }
inline unsigned long millis() { static unsigned long t = 0; return t += 7; }
