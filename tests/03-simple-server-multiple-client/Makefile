all:
	+../utils/multiserver.py $(MAKE) test

.PHONY: all

CLIENTS=client0 client1 client2 client3 client4 client5 client6 client7 client8 client9

$(CLIENTS):
	@echo "$$PPID - $@ start - $(MAKEFLAGS)"
	@sleep 1
	@echo "$$PPID - $@ end - $(MAKEFLAGS)"

test: $(CLIENTS)
	@true

.PHONY: test $(CLIENTS)
