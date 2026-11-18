# Build and smoke-test the M4 renderer core (C99, no dependencies).
#
# Built in CI only (`make -C native smoke`), never at `pip install` time: the
# Python package has no compiler dependency (docs/architecture.md §5).

CC ?= cc
CFLAGS ?= -std=c99 -O2 -Wall -Wextra -pedantic

.PHONY: all smoke test clean

all: smoke

renderer.o: renderer.c renderer.h
	$(CC) $(CFLAGS) -c renderer.c -o renderer.o

smoke.o: smoke.c renderer.h
	$(CC) $(CFLAGS) -c smoke.c -o smoke.o

smoke: renderer.o smoke.o
	$(CC) $(CFLAGS) renderer.o smoke.o -o smoke

# Build and run the headless smoke binary (exit 0 = all golden checks pass).
test: smoke
	./smoke

clean:
	rm -f renderer.o smoke.o smoke
