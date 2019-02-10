
NUMBERS=$(shell python3 -c "print(*range(20))")

SUBCHILDREN=$(addprefix out/subtask, $(NUMBERS))
$(SUBCHILDREN):
	@echo $$PID $$(pwd) - subchild $@ MAKE='$(MAKE)' MAKEFLAGS='$(MAKEFLAGS)'
	@sleep 1
	@touch $@

subchildren: $(SUBCHILDREN)
	@true

CHILDREN=$(addprefix out/task, $(NUMBERS))
$(CHILDREN):
	mkdir $@.children
	cp Makefile ./$@.children/
	cd $@.children; mkdir -p logs; mkdir -p out
	+./test.py ./user.py $@
	#$(MAKE) -C $@.children subchildren
	touch $@

USERS=$(addprefix out/user, $(NUMBERS))
$(USERS):
	+./user.py $@
	touch $@

out/user: $(USERS)
	touch out/user

user: out/user
	@true

.PHONY: all


all: $(CHILDREN)
	@true

.PHONY: all

clean:
	rm -rf out
	mkdir -p out
	rm -rf logs
	mkdir -p logs

.PHONY: clean
