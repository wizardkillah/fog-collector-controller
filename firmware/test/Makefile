CXX ?= g++
CXXFLAGS ?= -std=c++11 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined

test: test_core
	./test_core

test_core: test_core.cpp ../opta_niebla/niebla_core.cpp ../opta_niebla/niebla_core.h
	$(CXX) $(CXXFLAGS) -o $@ test_core.cpp ../opta_niebla/niebla_core.cpp

clean:
	rm -f test_core

.PHONY: test clean

# Verificación de sintaxis del sketch con stubs (no reemplaza compilar en el IDE).
sintaxis:
	cp ../opta_niebla/opta_niebla.ino /tmp/opta_niebla_sketch.cpp
	$(CXX) -std=c++11 -Wall -Wextra -Werror -fsyntax-only -Imock -I../opta_niebla /tmp/opta_niebla_sketch.cpp
	$(CXX) -std=c++11 -Wall -Wextra -Werror -fsyntax-only -Imock -I../opta_niebla -DROL_PLC=1 /tmp/opta_niebla_sketch.cpp
	@echo "sintaxis OK (principal y secundario)"

.PHONY: sintaxis
