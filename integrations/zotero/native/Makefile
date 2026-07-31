SHELL := /bin/sh
CC ?= clang
CFLAGS ?= -O2 -std=c17 -Wall -Wextra -Wpedantic -Werror
BUILD_DIR := build
TARGET := $(BUILD_DIR)/zoterochat-helper
SOURCE := src/zoterochat_helper.c
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Linux)
PTY_LIBS := -lutil
endif

.PHONY: all test universal clean

all: $(TARGET)

$(TARGET): $(SOURCE)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SOURCE) $(PTY_LIBS) -o $(TARGET)

test: $(TARGET)
	HELPER="$(abspath $(TARGET))" python3 tests/test_helper.py

universal:
	./scripts/build-universal.sh

clean:
	rm -rf build dist
