# The j value here should be *less* than the number of clients.
all:
	$(MAKE) -j 4 test

.PHONY: all

CLIENTS=client0 client1 client2 client3 client4 client5 client6 client7 client8 client9

$(CLIENTS):
	+../utils/client.py $@

test: $(CLIENTS)
	@true

.PHONY: test $(CLIENTS)
