
TESTS=\
	00-simple-client \
	01-multiples-clients-less \
	01-multiples-clients-more \
	02-simple-server \
	03-simple-server-multiple-client \
	04-proxy \


$(TESTS):
	cd $@; for i in 0 1 2 3 4 5; do make || exit 1; done

.PHONY: $(TESTS)

all: $(TESTS)
	@true

.DEFAULT_GOAL := all
