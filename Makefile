ctrace-parse: ctrace-parse.c DLTrace.h
	gcc ctrace-parse.c -o ctrace-parse

.PHONY: clean
clean:
	rm -f ctrace-parse
