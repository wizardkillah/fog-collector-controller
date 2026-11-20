#pragma once
#include <stdint.h>
class IPAddress { public: IPAddress() {} IPAddress(uint8_t, uint8_t, uint8_t, uint8_t) {} };
class Client { public: virtual ~Client() {} virtual int connected() { return 0; } virtual void stop() {} explicit operator bool() const { return false; } };
class EthernetClient : public Client {};
class EthernetServer { public: EthernetServer(uint16_t) {} void begin() {} EthernetClient available() { return EthernetClient(); } };
struct EthernetClass { int begin(IPAddress, IPAddress, IPAddress, IPAddress) { return 1; } };
static EthernetClass Ethernet;
