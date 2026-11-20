#pragma once
#include "Ethernet.h"
enum { COILS = 0, DISCRETE_INPUTS, HOLDING_REGISTERS, INPUT_REGISTERS };
struct ModbusRTUClientClass { int begin(unsigned long, uint16_t) { return 1; } void setTimeout(unsigned long) {} long holdingRegisterRead(int, int) { return -1; } };
static ModbusRTUClientClass ModbusRTUClient;
class ModbusTCPServer { public: int begin(int id = 0xff) { (void)id; return 1; } int configureInputRegisters(int, int) { return 1; } int configureHoldingRegisters(int, int) { return 1; }
  int inputRegisterWrite(int, uint16_t) { return 1; } long holdingRegisterRead(int) { return 0; } void accept(Client&) {} int poll() { return 0; } };
class ModbusTCPClient { public: ModbusTCPClient(Client&) {} int begin(IPAddress, uint16_t) { return 0; } int connected() { return 0; } void stop() {} void setTimeout(unsigned long) {}
  int beginTransmission(int, int, int) { return 1; } int write(unsigned int) { return 1; } int endTransmission() { return 1; } };
