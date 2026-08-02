SHELL := /bin/sh
CC ?= clang
CFLAGS ?= -O2 -std=c17 -Wall -Wextra -Wpedantic -Werror
BUILD_DIR := build
TARGET := $(BUILD_DIR)/zoterochat-helper
SOURCE := src/zoterochat_helper.c
REMOTE_TARGET := $(BUILD_DIR)/qlab-remote
REMOTE_SOURCE := src/qlab_remote_helper.c
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Linux)
PTY_LIBS := -lutil
endif

.PHONY: all test remote-test universal linux-static clean

all: $(TARGET)

$(TARGET): $(SOURCE)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SOURCE) $(PTY_LIBS) -o $(TARGET)

$(REMOTE_TARGET): $(REMOTE_SOURCE) include/qlab_remote_protocol.h
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -Iinclude $(REMOTE_SOURCE) -o $(REMOTE_TARGET)

test: $(TARGET) remote-test
	HELPER="$(abspath $(TARGET))" python3 tests/test_helper.py

remote-test: $(REMOTE_TARGET)
	REMOTE_HELPER="$(abspath $(REMOTE_TARGET))" python3 tests/test_remote_helper.py

universal:
	./scripts/build-universal.sh

linux-static:
	./scripts/build-linux-static.sh

clean:
	rm -rf build dist
