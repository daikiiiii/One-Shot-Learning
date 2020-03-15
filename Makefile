TARGET  = estimate
CC      = clang
OPT     =
CFLAGS  = -g -std=c99 -Wall -Wvla -Werror -fsanitize=address $(if $(findstring clang,$(CC)),-fsanitize=undefined) $(OPT)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) $^ -o $@

clean:
	rm -f $(TARGET) *.o *.a *.dylib *.dSYM
