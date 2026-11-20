#pragma once
#include <stdint.h>
namespace mbed { class Watchdog { public: static Watchdog& get_instance() { static Watchdog w; return w; } bool start(uint32_t) { return true; } void kick() {} }; }
