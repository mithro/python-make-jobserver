# The j value here should be *greater* than the number of clients.
all:
	$(MAKE) -j 20 test

.PHONY: all

CLIENTS=client0 client1 client2 client3 client4 client5

$(CLIENTS):
	+../utils/client.py $@

test: $(CLIENTS)
	@true

.PHONY: test $(CLIENTS)
