all:
	$(MAKE) -j 8 test-top

.PHONY: all

CLIENTS=client0 client1 client2 client3 client4 client5 client6 client7 client8 client9

CLIENTS_BOT=$(addprefix bot,$(CLIENTS))
$(CLIENTS_BOT):
	+../utils/client.py $@

test-bot: $(CLIENTS_BOT)
	@true

CLIENTS_TOP=$(addprefix top,$(CLIENTS))
$(CLIENTS_TOP):
	+../utils/proxy.py $(MAKE) test-bot

test-top: $(CLIENTS_TOP)
	@true

.PHONY: test $(CLIENTS)
