all:
	$(MAKE) -j 8 test-top

.PHONY: all
.DEFAULT_GOAL := all

CLIENTS=client0 client1 client2 client3 client4 client5 client6 client7 client8 client9

fail:
	sleep 1
	false

CLIENTS_BOT=$(addprefix bot,$(CLIENTS))
$(CLIENTS_BOT):
	+../utils/client.py $@

test-bot: $(CLIENTS_BOT) fail
	@true

CLIENTS_MID=$(addprefix mid,$(CLIENTS))
$(CLIENTS_MID):
	+../utils/proxy.py 0 $(MAKE) test-mid

test-mid: $(CLIENTS_BOT) fail
	@true

CLIENTS_TOP=$(addprefix top,$(CLIENTS))
$(CLIENTS_TOP):
	+../utils/proxy.py 0 $(MAKE) test-mid

test-top: $(CLIENTS_TOP)
	@true

.PHONY: test $(CLIENTS)
