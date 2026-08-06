#define _GNU_SOURCE 1

#include "../include/qlab_remote_protocol.h"

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#define MAX_JSON_TOKENS 4096
#define MAX_CAPABILITIES 128
#define MAX_REQUEST_IDS 1024
#define MAX_DIRECTORY_ENTRIES 1024
#define MAX_PROBE_OUTPUT 4096
#define FIXED_PROCESS_TIMEOUT_MS 3000
#define MAX_SAFE_INTEGER 9007199254740991L
#define UUID_PUBLICATION_RETRIES 100
#define UUID_PUBLICATION_RETRY_NANOSECONDS 10000000L

typedef struct {
  char *data;
  size_t len;
  size_t cap;
} StrBuf;

static bool sb_reserve(StrBuf *buffer, size_t extra) {
  if (extra > SIZE_MAX - buffer->len - 1)
    return false;
  size_t required = buffer->len + extra + 1;
  if (required <= buffer->cap)
    return true;
  size_t capacity = buffer->cap ? buffer->cap : 256;
  while (capacity < required) {
    if (capacity > SIZE_MAX / 2) {
      capacity = required;
      break;
    }
    capacity *= 2;
  }
  char *next = realloc(buffer->data, capacity);
  if (!next)
    return false;
  buffer->data = next;
  buffer->cap = capacity;
  return true;
}

static bool sb_append_n(StrBuf *buffer, const void *value, size_t length) {
  if (!sb_reserve(buffer, length))
    return false;
  if (length)
    memcpy(buffer->data + buffer->len, value, length);
  buffer->len += length;
  buffer->data[buffer->len] = 0;
  return true;
}

static bool sb_append(StrBuf *buffer, const char *value) {
  return sb_append_n(buffer, value, strlen(value));
}

static bool sb_printf(StrBuf *buffer, const char *format, ...) {
  va_list arguments;
  va_start(arguments, format);
  va_list copy;
  va_copy(copy, arguments);
  int length = vsnprintf(NULL, 0, format, copy);
  va_end(copy);
  if (length < 0 || !sb_reserve(buffer, (size_t)length)) {
    va_end(arguments);
    return false;
  }
  vsnprintf(buffer->data + buffer->len, buffer->cap - buffer->len, format,
            arguments);
  va_end(arguments);
  buffer->len += (size_t)length;
  return true;
}

static bool sb_json_string_n(StrBuf *buffer, const char *value, size_t length) {
  if (!sb_append(buffer, "\""))
    return false;
  for (size_t index = 0; index < length; index++) {
    unsigned char byte = (unsigned char)value[index];
    switch (byte) {
    case '"':
      if (!sb_append(buffer, "\\\""))
        return false;
      break;
    case '\\':
      if (!sb_append(buffer, "\\\\"))
        return false;
      break;
    case '\b':
      if (!sb_append(buffer, "\\b"))
        return false;
      break;
    case '\f':
      if (!sb_append(buffer, "\\f"))
        return false;
      break;
    case '\n':
      if (!sb_append(buffer, "\\n"))
        return false;
      break;
    case '\r':
      if (!sb_append(buffer, "\\r"))
        return false;
      break;
    case '\t':
      if (!sb_append(buffer, "\\t"))
        return false;
      break;
    default:
      if (byte < 0x20) {
        if (!sb_printf(buffer, "\\u%04x", byte))
          return false;
      } else if (!sb_append_n(buffer, value + index, 1)) {
        return false;
      }
    }
  }
  return sb_append(buffer, "\"");
}

static bool sb_json_string(StrBuf *buffer, const char *value) {
  return sb_json_string_n(buffer, value, strlen(value));
}

static void sb_free(StrBuf *buffer) {
  free(buffer->data);
  memset(buffer, 0, sizeof(*buffer));
}

typedef enum {
  JSON_OBJECT,
  JSON_ARRAY,
  JSON_STRING,
  JSON_NUMBER,
  JSON_TRUE,
  JSON_FALSE,
  JSON_NULL
} JsonType;

typedef struct {
  JsonType type;
  size_t start;
  size_t end;
  int parent;
} JsonToken;

typedef struct {
  const char *source;
  size_t length;
  size_t position;
  JsonToken *tokens;
  int count;
  int capacity;
  const char *error;
} JsonParser;

static bool valid_utf8(const unsigned char *value, size_t length) {
  size_t index = 0;
  while (index < length) {
    unsigned char first = value[index++];
    if (first <= 0x7f)
      continue;
    size_t continuation;
    uint32_t codepoint;
    if (first >= 0xc2 && first <= 0xdf) {
      continuation = 1;
      codepoint = first & 0x1f;
    } else if (first >= 0xe0 && first <= 0xef) {
      continuation = 2;
      codepoint = first & 0x0f;
    } else if (first >= 0xf0 && first <= 0xf4) {
      continuation = 3;
      codepoint = first & 0x07;
    } else {
      return false;
    }
    if (length - index < continuation)
      return false;
    for (size_t offset = 0; offset < continuation; offset++) {
      unsigned char next = value[index++];
      if ((next & 0xc0) != 0x80)
        return false;
      codepoint = (codepoint << 6) | (next & 0x3f);
    }
    if ((continuation == 1 && codepoint < 0x80) ||
        (continuation == 2 && codepoint < 0x800) ||
        (continuation == 3 && codepoint < 0x10000) ||
        codepoint > 0x10ffff ||
        (codepoint >= 0xd800 && codepoint <= 0xdfff))
      return false;
  }
  return true;
}

static void json_skip_space(JsonParser *parser) {
  while (parser->position < parser->length &&
         strchr(" \t\r\n", parser->source[parser->position]))
    parser->position++;
}

static int json_add_token(JsonParser *parser, JsonType type, size_t start,
                          int parent) {
  if (parser->count >= parser->capacity) {
    parser->error = "too many JSON tokens";
    return -1;
  }
  int index = parser->count++;
  parser->tokens[index] =
      (JsonToken){.type = type, .start = start, .end = start, .parent = parent};
  return index;
}

static bool json_hex4(const char *value) {
  for (int index = 0; index < 4; index++)
    if (!isxdigit((unsigned char)value[index]))
      return false;
  return true;
}

static int json_parse_value(JsonParser *parser, int parent, int depth);

static int json_parse_string(JsonParser *parser, int parent) {
  size_t start = parser->position;
  int token = json_add_token(parser, JSON_STRING, start, parent);
  if (token < 0)
    return -1;
  parser->position++;
  while (parser->position < parser->length) {
    unsigned char byte = (unsigned char)parser->source[parser->position++];
    if (byte == '"') {
      parser->tokens[token].end = parser->position;
      return token;
    }
    if (byte < 0x20) {
      parser->error = "control character in JSON string";
      return -1;
    }
    if (byte == '\\') {
      if (parser->position >= parser->length) {
        parser->error = "truncated JSON escape";
        return -1;
      }
      char escape = parser->source[parser->position++];
      if (escape == 'u') {
        if (parser->length - parser->position < 4 ||
            !json_hex4(parser->source + parser->position)) {
          parser->error = "invalid JSON unicode escape";
          return -1;
        }
        parser->position += 4;
      } else if (!strchr("\"\\/bfnrt", escape)) {
        parser->error = "invalid JSON escape";
        return -1;
      }
    }
  }
  parser->error = "unterminated JSON string";
  return -1;
}

static int json_parse_value(JsonParser *parser, int parent, int depth) {
  if (depth > 32) {
    parser->error = "JSON nesting too deep";
    return -1;
  }
  json_skip_space(parser);
  if (parser->position >= parser->length) {
    parser->error = "expected JSON value";
    return -1;
  }
  size_t start = parser->position;
  char byte = parser->source[parser->position];
  if (byte == '"')
    return json_parse_string(parser, parent);
  if (byte == '{') {
    int token = json_add_token(parser, JSON_OBJECT, start, parent);
    if (token < 0)
      return -1;
    parser->position++;
    json_skip_space(parser);
    if (parser->position < parser->length &&
        parser->source[parser->position] == '}') {
      parser->tokens[token].end = ++parser->position;
      return token;
    }
    for (;;) {
      json_skip_space(parser);
      if (parser->position >= parser->length ||
          parser->source[parser->position] != '"') {
        parser->error = "expected JSON object key";
        return -1;
      }
      if (json_parse_string(parser, token) < 0)
        return -1;
      json_skip_space(parser);
      if (parser->position >= parser->length ||
          parser->source[parser->position++] != ':') {
        parser->error = "expected colon after JSON key";
        return -1;
      }
      if (json_parse_value(parser, token, depth + 1) < 0)
        return -1;
      json_skip_space(parser);
      if (parser->position >= parser->length) {
        parser->error = "unterminated JSON object";
        return -1;
      }
      char delimiter = parser->source[parser->position++];
      if (delimiter == '}') {
        parser->tokens[token].end = parser->position;
        return token;
      }
      if (delimiter != ',') {
        parser->error = "expected comma in JSON object";
        return -1;
      }
    }
  }
  if (byte == '[') {
    int token = json_add_token(parser, JSON_ARRAY, start, parent);
    if (token < 0)
      return -1;
    parser->position++;
    json_skip_space(parser);
    if (parser->position < parser->length &&
        parser->source[parser->position] == ']') {
      parser->tokens[token].end = ++parser->position;
      return token;
    }
    for (;;) {
      if (json_parse_value(parser, token, depth + 1) < 0)
        return -1;
      json_skip_space(parser);
      if (parser->position >= parser->length) {
        parser->error = "unterminated JSON array";
        return -1;
      }
      char delimiter = parser->source[parser->position++];
      if (delimiter == ']') {
        parser->tokens[token].end = parser->position;
        return token;
      }
      if (delimiter != ',') {
        parser->error = "expected comma in JSON array";
        return -1;
      }
    }
  }
  const char *literal = NULL;
  JsonType type = JSON_NULL;
  if (byte == 't') {
    literal = "true";
    type = JSON_TRUE;
  } else if (byte == 'f') {
    literal = "false";
    type = JSON_FALSE;
  } else if (byte == 'n') {
    literal = "null";
    type = JSON_NULL;
  }
  if (literal) {
    size_t length = strlen(literal);
    if (parser->length - parser->position < length ||
        memcmp(parser->source + parser->position, literal, length)) {
      parser->error = "invalid JSON literal";
      return -1;
    }
    int token = json_add_token(parser, type, start, parent);
    if (token < 0)
      return -1;
    parser->position += length;
    parser->tokens[token].end = parser->position;
    return token;
  }
  if (byte == '-' || isdigit((unsigned char)byte)) {
    size_t index = parser->position;
    if (parser->source[index] == '-')
      index++;
    if (index >= parser->length) {
      parser->error = "invalid JSON number";
      return -1;
    }
    if (parser->source[index] == '0')
      index++;
    else if (parser->source[index] >= '1' && parser->source[index] <= '9')
      while (index < parser->length &&
             isdigit((unsigned char)parser->source[index]))
        index++;
    else {
      parser->error = "invalid JSON number";
      return -1;
    }
    if (index < parser->length && parser->source[index] == '.') {
      index++;
      if (index >= parser->length ||
          !isdigit((unsigned char)parser->source[index])) {
        parser->error = "invalid JSON fraction";
        return -1;
      }
      while (index < parser->length &&
             isdigit((unsigned char)parser->source[index]))
        index++;
    }
    if (index < parser->length &&
        (parser->source[index] == 'e' || parser->source[index] == 'E')) {
      index++;
      if (index < parser->length &&
          (parser->source[index] == '+' || parser->source[index] == '-'))
        index++;
      if (index >= parser->length ||
          !isdigit((unsigned char)parser->source[index])) {
        parser->error = "invalid JSON exponent";
        return -1;
      }
      while (index < parser->length &&
             isdigit((unsigned char)parser->source[index]))
        index++;
    }
    int token = json_add_token(parser, JSON_NUMBER, start, parent);
    if (token < 0)
      return -1;
    parser->position = index;
    parser->tokens[token].end = index;
    return token;
  }
  parser->error = "invalid JSON value";
  return -1;
}

static bool json_parse(const char *source, size_t length, JsonToken *tokens,
                       int capacity, int *count) {
  if (!valid_utf8((const unsigned char *)source, length))
    return false;
  JsonParser parser = {.source = source,
                       .length = length,
                       .tokens = tokens,
                       .capacity = capacity};
  int root = json_parse_value(&parser, -1, 0);
  json_skip_space(&parser);
  if (root != 0 || parser.position != length)
    return false;
  *count = parser.count;
  return true;
}

static int token_next(const JsonToken *tokens, int count, int index) {
  if (index < 0 || index >= count)
    return count;
  size_t end = tokens[index].end;
  index++;
  while (index < count && tokens[index].start < end)
    index++;
  return index;
}

static bool token_string_equal(const char *source, const JsonToken *token,
                               const char *expected) {
  if (!token || token->type != JSON_STRING || token->end < token->start + 2)
    return false;
  size_t length = token->end - token->start - 2;
  return strlen(expected) == length &&
         !memcmp(source + token->start + 1, expected, length) &&
         !memchr(source + token->start + 1, '\\', length);
}

static int object_get(const char *source, const JsonToken *tokens, int count,
                      int object, const char *key) {
  if (object < 0 || object >= count || tokens[object].type != JSON_OBJECT)
    return -1;
  int index = object + 1;
  while (index + 1 < count && tokens[index].start < tokens[object].end) {
    int value = index + 1;
    if (token_string_equal(source, &tokens[index], key))
      return value;
    index = token_next(tokens, count, value);
  }
  return -1;
}

static bool object_has_exact_keys(const char *source, const JsonToken *tokens,
                                  int count, int object,
                                  const char *const *keys, size_t key_count) {
  if (object < 0 || object >= count || tokens[object].type != JSON_OBJECT ||
      key_count > 32)
    return false;
  bool seen[32] = {false};
  size_t fields = 0;
  int index = object + 1;
  while (index + 1 < count && tokens[index].start < tokens[object].end) {
    int value = index + 1;
    size_t match = key_count;
    for (size_t candidate = 0; candidate < key_count; candidate++)
      if (token_string_equal(source, &tokens[index], keys[candidate])) {
        match = candidate;
        break;
      }
    if (match == key_count || seen[match])
      return false;
    seen[match] = true;
    fields++;
    index = token_next(tokens, count, value);
  }
  return fields == key_count;
}

static unsigned hex_value(char value) {
  if (value >= '0' && value <= '9')
    return (unsigned)(value - '0');
  if (value >= 'a' && value <= 'f')
    return (unsigned)(value - 'a' + 10);
  return (unsigned)(value - 'A' + 10);
}

static bool sb_utf8(StrBuf *buffer, uint32_t codepoint) {
  unsigned char encoded[4];
  size_t length;
  if (codepoint <= 0x7f) {
    encoded[0] = (unsigned char)codepoint;
    length = 1;
  } else if (codepoint <= 0x7ff) {
    encoded[0] = 0xc0 | (codepoint >> 6);
    encoded[1] = 0x80 | (codepoint & 0x3f);
    length = 2;
  } else if (codepoint <= 0xffff) {
    encoded[0] = 0xe0 | (codepoint >> 12);
    encoded[1] = 0x80 | ((codepoint >> 6) & 0x3f);
    encoded[2] = 0x80 | (codepoint & 0x3f);
    length = 3;
  } else if (codepoint <= 0x10ffff) {
    encoded[0] = 0xf0 | (codepoint >> 18);
    encoded[1] = 0x80 | ((codepoint >> 12) & 0x3f);
    encoded[2] = 0x80 | ((codepoint >> 6) & 0x3f);
    encoded[3] = 0x80 | (codepoint & 0x3f);
    length = 4;
  } else {
    return false;
  }
  return sb_append_n(buffer, encoded, length);
}

static char *token_strdup(const char *source, const JsonToken *token,
                          size_t maximum) {
  if (!token || token->type != JSON_STRING || token->end < token->start + 2)
    return NULL;
  StrBuf result = {0};
  size_t index = token->start + 1;
  size_t end = token->end - 1;
  while (index < end) {
    unsigned char byte = (unsigned char)source[index++];
    if (byte != '\\') {
      if (!sb_append_n(&result, &byte, 1))
        goto failure;
    } else {
      char escape = source[index++];
      switch (escape) {
      case '"':
      case '\\':
      case '/':
        if (!sb_append_n(&result, &escape, 1))
          goto failure;
        break;
      case 'b':
        byte = '\b';
        if (!sb_append_n(&result, &byte, 1))
          goto failure;
        break;
      case 'f':
        byte = '\f';
        if (!sb_append_n(&result, &byte, 1))
          goto failure;
        break;
      case 'n':
        byte = '\n';
        if (!sb_append_n(&result, &byte, 1))
          goto failure;
        break;
      case 'r':
        byte = '\r';
        if (!sb_append_n(&result, &byte, 1))
          goto failure;
        break;
      case 't':
        byte = '\t';
        if (!sb_append_n(&result, &byte, 1))
          goto failure;
        break;
      case 'u': {
        uint32_t codepoint = (hex_value(source[index]) << 12) |
                             (hex_value(source[index + 1]) << 8) |
                             (hex_value(source[index + 2]) << 4) |
                             hex_value(source[index + 3]);
        index += 4;
        if (codepoint >= 0xd800 && codepoint <= 0xdbff && index + 6 <= end &&
            source[index] == '\\' && source[index + 1] == 'u') {
          uint32_t low = (hex_value(source[index + 2]) << 12) |
                         (hex_value(source[index + 3]) << 8) |
                         (hex_value(source[index + 4]) << 4) |
                         hex_value(source[index + 5]);
          if (low >= 0xdc00 && low <= 0xdfff) {
            codepoint = 0x10000 + ((codepoint - 0xd800) << 10) +
                        (low - 0xdc00);
            index += 6;
          }
        }
        if (codepoint == 0 ||
            (codepoint >= 0xd800 && codepoint <= 0xdfff) ||
            !sb_utf8(&result, codepoint))
          goto failure;
        break;
      }
      default:
        goto failure;
      }
    }
    if (result.len > maximum)
      goto failure;
  }
  if (!sb_reserve(&result, 0) || result.len > maximum)
    goto failure;
  return result.data;
failure:
  sb_free(&result);
  return NULL;
}

static bool token_long(const char *source, const JsonToken *token, long minimum,
                       long maximum, long *result) {
  if (!token || token->type != JSON_NUMBER || token->end - token->start >= 32)
    return false;
  char buffer[32];
  size_t length = token->end - token->start;
  memcpy(buffer, source + token->start, length);
  buffer[length] = 0;
  char *end = NULL;
  errno = 0;
  long value = strtol(buffer, &end, 10);
  if (errno || !end || *end || value < minimum || value > maximum)
    return false;
  *result = value;
  return true;
}

static int array_first(const JsonToken *tokens, int count, int array) {
  if (array < 0 || array >= count || tokens[array].type != JSON_ARRAY)
    return -1;
  int first = array + 1;
  return first < count && tokens[first].start < tokens[array].end ? first : -1;
}

static int array_next(const JsonToken *tokens, int count, int array,
                      int current) {
  int next = token_next(tokens, count, current);
  return next < count && tokens[next].start < tokens[array].end ? next : -1;
}

typedef struct {
  char *items[MAX_CAPABILITIES];
  size_t count;
  char *json;
} Capabilities;

static bool valid_id(const char *value) {
  size_t length = value ? strlen(value) : 0;
  if (!length || length > QLAB_REMOTE_MAX_ID_BYTES)
    return false;
  for (size_t index = 0; index < length; index++)
    if (!(isalnum((unsigned char)value[index]) ||
          strchr("._:-", value[index])))
      return false;
  return true;
}

static bool valid_uuid(const char *value) {
  if (!value || strlen(value) != 36)
    return false;
  for (size_t index = 0; index < 36; index++) {
    if (index == 8 || index == 13 || index == 18 || index == 23) {
      if (value[index] != '-')
        return false;
    } else if (!((value[index] >= '0' && value[index] <= '9') ||
                 (value[index] >= 'a' && value[index] <= 'f'))) {
      return false;
    }
  }
  return value[14] >= '1' && value[14] <= '5' &&
         strchr("89ab", value[19]) != NULL;
}

static void capabilities_free(Capabilities *capabilities) {
  for (size_t index = 0; index < capabilities->count; index++)
    free(capabilities->items[index]);
  free(capabilities->json);
  memset(capabilities, 0, sizeof(*capabilities));
}

static bool capabilities_parse(const char *source, const JsonToken *tokens,
                               int count, int token, Capabilities *result) {
  if (token < 0 || tokens[token].type != JSON_ARRAY)
    return false;
  StrBuf encoded = {0};
  if (!sb_append(&encoded, "["))
    return false;
  int item = array_first(tokens, count, token);
  while (item >= 0) {
    if (result->count >= MAX_CAPABILITIES)
      goto failure;
    char *capability = token_strdup(source, &tokens[item],
                                    QLAB_REMOTE_MAX_ID_BYTES);
    if (!capability || !valid_id(capability)) {
      free(capability);
      goto failure;
    }
    for (size_t prior = 0; prior < result->count; prior++)
      if (!strcmp(result->items[prior], capability)) {
        free(capability);
        goto failure;
      }
    if ((result->count && !sb_append(&encoded, ",")) ||
        !sb_json_string(&encoded, capability)) {
      free(capability);
      goto failure;
    }
    result->items[result->count++] = capability;
    item = array_next(tokens, count, token, item);
  }
  if (!sb_append(&encoded, "]"))
    goto failure;
  result->json = encoded.data;
  return true;
failure:
  sb_free(&encoded);
  capabilities_free(result);
  return false;
}

static bool capabilities_equal(const Capabilities *left,
                               const Capabilities *right) {
  if (left->count != right->count)
    return false;
  for (size_t index = 0; index < left->count; index++)
    if (strcmp(left->items[index], right->items[index]))
      return false;
  return true;
}

static bool capabilities_match_mode(const Capabilities *capabilities,
                                    HelperMode mode) {
  static const char *const browse[] = {"browse", "codex-probe"};
  static const char *const setup[] = {"codex-device-auth-pty"};
  static const char *const agent[] = {"codex-app-server"};
  const char *const *expected = NULL;
  size_t count = 0;
  switch (mode) {
  case MODE_BROWSE:
    expected = browse;
    count = sizeof(browse) / sizeof(browse[0]);
    break;
  case MODE_REPOSITORY_HANDSHAKE:
    break;
  case MODE_SETUP_AUTH:
    expected = setup;
    count = sizeof(setup) / sizeof(setup[0]);
    break;
  case MODE_AGENT:
    expected = agent;
    count = sizeof(agent) / sizeof(agent[0]);
    break;
  }
  if (capabilities->count != count)
    return false;
  for (size_t index = 0; index < count; index++)
    if (strcmp(capabilities->items[index], expected[index]))
      return false;
  return true;
}

typedef enum {
  FRAME_OK,
  FRAME_EOF,
  FRAME_TRUNCATED,
  FRAME_TOO_LARGE,
  FRAME_IO_ERROR
} FrameReadResult;

static FrameReadResult read_jsonl_frame(FILE *stream, char **frame,
                                        size_t *length) {
  char *buffer = malloc(QLAB_REMOTE_MAX_FRAME_BYTES);
  if (!buffer)
    return FRAME_IO_ERROR;
  size_t used = 0;
  for (;;) {
    int byte = fgetc(stream);
    if (byte == EOF) {
      free(buffer);
      if (ferror(stream))
        return FRAME_IO_ERROR;
      return used ? FRAME_TRUNCATED : FRAME_EOF;
    }
    if (byte == '\n') {
      buffer[used] = 0;
      *frame = buffer;
      *length = used;
      return FRAME_OK;
    }
    if (byte == 0) {
      free(buffer);
      return FRAME_TRUNCATED;
    }
    if (used >= QLAB_REMOTE_MAX_FRAME_BYTES - 1) {
      free(buffer);
      return FRAME_TOO_LARGE;
    }
    buffer[used++] = (char)byte;
  }
}

static bool emit_frame(StrBuf *frame) {
  bool success = frame->len + 1 <= QLAB_REMOTE_MAX_FRAME_BYTES &&
                 fwrite(frame->data, 1, frame->len, stdout) == frame->len &&
                 fputc('\n', stdout) != EOF && fflush(stdout) == 0;
  sb_free(frame);
  return success;
}

static bool write_all(int descriptor, const void *bytes, size_t length) {
  const unsigned char *cursor = bytes;
  while (length) {
    ssize_t written = write(descriptor, cursor, length);
    if (written < 0) {
      if (errno == EINTR)
        continue;
      return false;
    }
    cursor += (size_t)written;
    length -= (size_t)written;
  }
  return true;
}

static uint64_t monotonic_milliseconds(void) {
  struct timespec value;
  if (clock_gettime(CLOCK_MONOTONIC, &value) < 0)
    return 0;
  return (uint64_t)value.tv_sec * 1000U + (uint64_t)value.tv_nsec / 1000000U;
}

static bool random_bytes(unsigned char *output, size_t length) {
  int descriptor = open("/dev/urandom", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (descriptor < 0)
    return false;
  size_t offset = 0;
  while (offset < length) {
    ssize_t amount = read(descriptor, output + offset, length - offset);
    if (amount < 0 && errno == EINTR)
      continue;
    if (amount <= 0) {
      close(descriptor);
      return false;
    }
    offset += (size_t)amount;
  }
  return close(descriptor) == 0;
}

static bool generate_uuid(char output[37]) {
  unsigned char bytes[16];
  if (!random_bytes(bytes, sizeof(bytes)))
    return false;
  bytes[6] = (unsigned char)((bytes[6] & 0x0f) | 0x40);
  bytes[8] = (unsigned char)((bytes[8] & 0x3f) | 0x80);
  int length = snprintf(
      output, 37,
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6],
      bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12],
      bytes[13], bytes[14], bytes[15]);
  return length == 36 && valid_uuid(output);
}

static bool path_has_traversal(const char *path) {
  const char *cursor = path;
  while (*cursor) {
    while (*cursor == '/')
      cursor++;
    const char *start = cursor;
    while (*cursor && *cursor != '/')
      cursor++;
    size_t length = (size_t)(cursor - start);
    if ((length == 1 && start[0] == '.') ||
        (length == 2 && start[0] == '.' && start[1] == '.'))
      return true;
  }
  return false;
}

static bool normalize_absolute_path(const char *path, char output[PATH_MAX]) {
  if (!path || path[0] != '/' || path_has_traversal(path) ||
      strchr(path, '\r') || strchr(path, '\n') || strlen(path) >= PATH_MAX)
    return false;
  size_t used = 0;
  output[used++] = '/';
  const char *cursor = path;
  while (*cursor == '/')
    cursor++;
  while (*cursor) {
    const char *start = cursor;
    while (*cursor && *cursor != '/')
      cursor++;
    size_t length = (size_t)(cursor - start);
    if (length) {
      if ((used > 1 && used + 1 >= PATH_MAX) || used + length >= PATH_MAX)
        return false;
      if (used > 1)
        output[used++] = '/';
      memcpy(output + used, start, length);
      used += length;
    }
    while (*cursor == '/')
      cursor++;
  }
  output[used] = 0;
  return true;
}

static int open_absolute_directory_nofollow(const char *path) {
  char normalized[PATH_MAX];
  if (!normalize_absolute_path(path, normalized))
    return -1;
  int descriptor = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (descriptor < 0)
    return -1;
  char copy[PATH_MAX];
  memcpy(copy, normalized, strlen(normalized) + 1);
  char *save = NULL;
  char *component = strtok_r(copy + 1, "/", &save);
  while (component) {
    int next = openat(descriptor, component,
                      O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    close(descriptor);
    if (next < 0)
      return -1;
    descriptor = next;
    component = strtok_r(NULL, "/", &save);
  }
  return descriptor;
}

static bool validate_owned_directory(int descriptor, mode_t mode,
                                     bool exact_mode) {
  struct stat status;
  if (fstat(descriptor, &status) < 0 || !S_ISDIR(status.st_mode) ||
      status.st_uid != geteuid())
    return false;
  mode_t permissions = status.st_mode & 0777;
  return exact_mode ? permissions == mode : (permissions & 0077) == 0;
}

static bool ensure_private_directory_at(int parent, const char *name,
                                        int *output) {
  bool created = false;
  mode_t previous_umask = umask(0);
  int mkdir_result = mkdirat(parent, name, 0700);
  int mkdir_error = errno;
  (void)umask(previous_umask);
  errno = mkdir_error;
  if (mkdir_result == 0) {
    created = true;
  } else if (errno != EEXIST) {
    return false;
  }
  int descriptor = openat(parent, name,
                          O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (descriptor < 0)
    return false;
  bool valid = validate_owned_directory(descriptor, 0700, true);
  if (created && (fchmod(descriptor, 0700) < 0 || fsync(parent) < 0))
    valid = false;
  if (!valid) {
    close(descriptor);
    return false;
  }
  *output = descriptor;
  return true;
}

typedef enum {
  UUID_READ_VALID,
  UUID_READ_MISSING,
  UUID_READ_INCOMPLETE,
  UUID_READ_INVALID
} UuidReadResult;

static UuidReadResult read_uuid_file_at(int directory, const char *name,
                                        bool require_exact_mode,
                                        char output[37]) {
  int descriptor = openat(directory, name,
                          O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
  if (descriptor < 0)
    return errno == ENOENT ? UUID_READ_MISSING : UUID_READ_INVALID;
  struct stat status;
  if (fstat(descriptor, &status) < 0 || !S_ISREG(status.st_mode) ||
      status.st_uid != geteuid()) {
    close(descriptor);
    return UUID_READ_INVALID;
  }
  mode_t permissions = status.st_mode & 0777;
  bool private_mode = require_exact_mode
                          ? permissions == 0600
                          : (permissions & 0077) == 0 &&
                                (permissions & 0400) != 0;
  if (!private_mode) {
    close(descriptor);
    return UUID_READ_INVALID;
  }
  char buffer[39];
  size_t used = 0;
  for (;;) {
    ssize_t amount = read(descriptor, buffer + used, sizeof(buffer) - used);
    if (amount < 0 && errno == EINTR)
      continue;
    if (amount < 0) {
      close(descriptor);
      return UUID_READ_INVALID;
    }
    if (amount == 0)
      break;
    used += (size_t)amount;
    if (used == sizeof(buffer)) {
      close(descriptor);
      return UUID_READ_INVALID;
    }
  }
  if (close(descriptor) < 0)
    return UUID_READ_INVALID;
  if (used < 36)
    return UUID_READ_INCOMPLETE;
  if (used == 37 && buffer[36] == '\n')
    used--;
  if (used != 36)
    return UUID_READ_INVALID;
  buffer[used] = 0;
  if (!valid_uuid(buffer))
    return UUID_READ_INVALID;
  memcpy(output, buffer, 37);
  return UUID_READ_VALID;
}

static bool wait_for_uuid_publication_at(int directory, const char *name,
                                         bool require_exact_mode,
                                         char output[37]) {
  for (int attempt = 0; attempt < UUID_PUBLICATION_RETRIES; attempt++) {
    UuidReadResult result =
        read_uuid_file_at(directory, name, require_exact_mode, output);
    if (result == UUID_READ_VALID)
      return true;
    if (result != UUID_READ_INCOMPLETE)
      return false;
    struct timespec delay = {.tv_sec = 0,
                             .tv_nsec = UUID_PUBLICATION_RETRY_NANOSECONDS};
    while (nanosleep(&delay, &delay) < 0 && errno == EINTR) {
    }
  }
  return false;
}

static bool load_or_create_uuid_at(int directory, const char *name,
                                   bool require_exact_mode, char output[37]) {
  UuidReadResult existing =
      read_uuid_file_at(directory, name, require_exact_mode, output);
  if (existing == UUID_READ_VALID)
    return true;
  if (existing == UUID_READ_INCOMPLETE)
    return wait_for_uuid_publication_at(directory, name, require_exact_mode,
                                        output);
  if (existing != UUID_READ_MISSING)
    return false;
  char candidate[37];
  if (!generate_uuid(candidate))
    return false;
  int descriptor = openat(directory, name,
                          O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
                          0600);
  if (descriptor < 0) {
    if (errno == EEXIST)
      return wait_for_uuid_publication_at(directory, name, require_exact_mode,
                                          output);
    return false;
  }
  char line[38];
  memcpy(line, candidate, 36);
  line[36] = '\n';
  line[37] = 0;
  bool success = fchmod(descriptor, 0600) == 0 &&
                 write_all(descriptor, line, 37) && fsync(descriptor) == 0;
  if (close(descriptor) < 0)
    success = false;
  if (success && fsync(directory) < 0)
    success = false;
  if (!success)
    return false;
  memcpy(output, candidate, 37);
  return true;
}

static bool canonical_login_home(char output[PATH_MAX]) {
  const char *home = getenv("HOME");
  if (!home || home[0] != '/' || !realpath(home, output))
    return false;
  int descriptor = open_absolute_directory_nofollow(output);
  if (descriptor < 0)
    return false;
  close(descriptor);
  return true;
}

static bool load_or_create_host_instance_id(const char *state_dir,
                                            char output[37]) {
  char home[PATH_MAX];
  if (!canonical_login_home(home))
    return false;
  int home_descriptor = open_absolute_directory_nofollow(home);
  if (home_descriptor < 0)
    return false;
  int qlab_descriptor = -1;
  int state_descriptor = -1;
  bool success = ensure_private_directory_at(home_descriptor, ".qlab",
                                             &qlab_descriptor) &&
                 ensure_private_directory_at(qlab_descriptor, state_dir,
                                             &state_descriptor) &&
                 load_or_create_uuid_at(state_descriptor, "host-instance-id",
                                        true, output);
  if (state_descriptor >= 0)
    close(state_descriptor);
  if (qlab_descriptor >= 0)
    close(qlab_descriptor);
  close(home_descriptor);
  return success;
}

typedef struct {
  char *output;
  size_t length;
  int exit_code;
  bool timed_out;
  bool overflowed;
} ProcessResult;

static void process_result_free(ProcessResult *result) {
  free(result->output);
  memset(result, 0, sizeof(*result));
}

static bool run_fixed_process(char *const argv[], size_t maximum_output,
                              int timeout_ms, ProcessResult *result) {
  int pipe_descriptors[2];
  if (pipe(pipe_descriptors) < 0)
    return false;
  int flags = fcntl(pipe_descriptors[0], F_GETFL);
  if (flags < 0 || fcntl(pipe_descriptors[0], F_SETFL, flags | O_NONBLOCK) < 0) {
    close(pipe_descriptors[0]);
    close(pipe_descriptors[1]);
    return false;
  }
  pid_t child = fork();
  if (child < 0) {
    close(pipe_descriptors[0]);
    close(pipe_descriptors[1]);
    return false;
  }
  if (child == 0) {
    close(pipe_descriptors[0]);
    (void)setpgid(0, 0);
    if (dup2(pipe_descriptors[1], STDOUT_FILENO) < 0)
      _exit(126);
    if (pipe_descriptors[1] != STDOUT_FILENO)
      close(pipe_descriptors[1]);
    int null_descriptor = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (null_descriptor < 0 || dup2(null_descriptor, STDIN_FILENO) < 0 ||
        dup2(null_descriptor, STDERR_FILENO) < 0)
      _exit(126);
    if (null_descriptor != STDIN_FILENO && null_descriptor != STDERR_FILENO)
      close(null_descriptor);
    execvp(argv[0], argv);
    _exit(errno == ENOENT ? 127 : 126);
  }
  close(pipe_descriptors[1]);
  result->output = malloc(maximum_output + 1);
  if (!result->output) {
    close(pipe_descriptors[0]);
    kill(-child, SIGKILL);
    kill(child, SIGKILL);
    (void)waitpid(child, NULL, 0);
    return false;
  }
  uint64_t deadline = monotonic_milliseconds() + (uint64_t)timeout_ms;
  bool pipe_open = true;
  bool child_exited = false;
  int status = 0;
  while (pipe_open || !child_exited) {
    uint64_t now = monotonic_milliseconds();
    if (now >= deadline) {
      result->timed_out = true;
      kill(-child, SIGKILL);
      kill(child, SIGKILL);
      break;
    }
    if (pipe_open) {
      struct pollfd descriptor = {.fd = pipe_descriptors[0], .events = POLLIN};
      int wait = (int)(deadline - now);
      if (wait > 50)
        wait = 50;
      int ready = poll(&descriptor, 1, wait);
      if (ready < 0 && errno != EINTR)
        break;
      if (ready > 0 && (descriptor.revents & (POLLIN | POLLHUP))) {
        char chunk[1024];
        for (;;) {
          ssize_t amount = read(pipe_descriptors[0], chunk, sizeof(chunk));
          if (amount > 0) {
            if ((size_t)amount > maximum_output - result->length) {
              result->overflowed = true;
              kill(-child, SIGKILL);
              kill(child, SIGKILL);
              pipe_open = false;
              close(pipe_descriptors[0]);
              break;
            }
            memcpy(result->output + result->length, chunk, (size_t)amount);
            result->length += (size_t)amount;
          } else if (amount == 0) {
            pipe_open = false;
            close(pipe_descriptors[0]);
            break;
          } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
            break;
          } else if (errno != EINTR) {
            pipe_open = false;
            close(pipe_descriptors[0]);
            break;
          }
        }
      }
    }
    if (!child_exited) {
      pid_t waited = waitpid(child, &status, WNOHANG);
      if (waited == child)
        child_exited = true;
      else if (waited < 0 && errno != EINTR)
        break;
    }
  }
  if (pipe_open)
    close(pipe_descriptors[0]);
  if (!child_exited) {
    while (waitpid(child, &status, 0) < 0 && errno == EINTR) {
    }
    child_exited = true;
  }
  result->output[result->length] = 0;
  result->exit_code = child_exited && WIFEXITED(status) ? WEXITSTATUS(status) : -1;
  return true;
}

static bool parse_single_path_line(const ProcessResult *process,
                                   char output[PATH_MAX]) {
  if (process->exit_code != 0 || process->timed_out || process->overflowed ||
      !process->length || process->length >= PATH_MAX)
    return false;
  size_t length = process->length;
  if (process->output[length - 1] == '\n')
    length--;
  if (!length || length >= PATH_MAX ||
      memchr(process->output, '\n', length) ||
      memchr(process->output, '\r', process->length) ||
      memchr(process->output, 0, process->length) ||
      !valid_utf8((const unsigned char *)process->output, length))
    return false;
  memcpy(output, process->output, length);
  output[length] = 0;
  return true;
}

static bool resolve_relative_path(const char *root, const char *raw,
                                  char output[PATH_MAX]) {
  char combined[PATH_MAX];
  if (raw[0] == '/')
    return normalize_absolute_path(raw, output);
  if (path_has_traversal(raw) || strchr(raw, '\r') || strchr(raw, '\n'))
    return false;
  int length = snprintf(combined, sizeof(combined), "%s/%s", root, raw);
  return length > 0 && (size_t)length < sizeof(combined) &&
         normalize_absolute_path(combined, output);
}

static bool resolve_repository_uuid(const char *canonical_root,
                                    char output_uuid[37]) {
  char *const private_arguments[] = {
      "git", "-C", (char *)canonical_root, "rev-parse", "--git-path",
      "qlab/repository-id", NULL};
  char *const common_arguments[] = {
      "git", "-C", (char *)canonical_root, "rev-parse",
      "--path-format=absolute", "--git-common-dir", NULL};
  ProcessResult private_result = {0};
  ProcessResult common_result = {0};
  char raw_private[PATH_MAX];
  char raw_common[PATH_MAX];
  bool valid = run_fixed_process(private_arguments, PATH_MAX,
                                 FIXED_PROCESS_TIMEOUT_MS, &private_result) &&
               parse_single_path_line(&private_result, raw_private) &&
               run_fixed_process(common_arguments, PATH_MAX,
                                 FIXED_PROCESS_TIMEOUT_MS, &common_result) &&
               parse_single_path_line(&common_result, raw_common);
  process_result_free(&private_result);
  process_result_free(&common_result);
  if (!valid || raw_common[0] != '/')
    return false;

  char private_path[PATH_MAX];
  char common_path[PATH_MAX];
  if (!resolve_relative_path(canonical_root, raw_private, private_path) ||
      !normalize_absolute_path(raw_common, common_path))
    return false;
  char expected[PATH_MAX];
  int expected_length = snprintf(expected, sizeof(expected),
                                 "%s/qlab/repository-id", common_path);
  if (expected_length <= 0 || (size_t)expected_length >= sizeof(expected) ||
      strcmp(private_path, expected))
    return false;

  int common_descriptor = open_absolute_directory_nofollow(common_path);
  if (common_descriptor < 0)
    return false;
  int qlab_descriptor = -1;
  bool success = ensure_private_directory_at(common_descriptor, "qlab",
                                             &qlab_descriptor) &&
                 load_or_create_uuid_at(qlab_descriptor, "repository-id",
                                        false, output_uuid);
  if (qlab_descriptor >= 0)
    close(qlab_descriptor);
  close(common_descriptor);
  return success;
}

typedef struct {
  char request_id[QLAB_REMOTE_MAX_ID_BYTES + 1];
  char activation_id[QLAB_REMOTE_MAX_ID_BYTES + 1];
  char mode[32];
  char *candidate_root;
  bool has_expected_host;
  char expected_host[37];
  Capabilities capabilities;
} ActivationHello;

typedef struct {
  char request_id[QLAB_REMOTE_MAX_ID_BYTES + 1];
  char target_id[QLAB_REMOTE_MAX_ID_BYTES + 1];
  long target_epoch;
  char *canonical_root;
  char expected_host[37];
  char expected_repository_uuid[37];
  char expected_repository_id[QLAB_REMOTE_MAX_ID_BYTES + 1];
  Capabilities capabilities;
} BoundHello;

static void activation_hello_free(ActivationHello *hello) {
  free(hello->candidate_root);
  capabilities_free(&hello->capabilities);
  memset(hello, 0, sizeof(*hello));
}

static void bound_hello_free(BoundHello *hello) {
  free(hello->canonical_root);
  capabilities_free(&hello->capabilities);
  memset(hello, 0, sizeof(*hello));
}

static bool copy_checked_string(const char *source, const JsonToken *token,
                                char *output, size_t capacity,
                                bool (*validator)(const char *)) {
  char *value = token_strdup(source, token, capacity - 1);
  if (!value || (validator && !validator(value))) {
    free(value);
    return false;
  }
  memcpy(output, value, strlen(value) + 1);
  free(value);
  return true;
}

static const char *activation_mode_name(HelperMode mode) {
  switch (mode) {
  case MODE_BROWSE:
    return "browse";
  case MODE_REPOSITORY_HANDSHAKE:
    return "repository-handshake";
  case MODE_SETUP_AUTH:
    return "setup-auth";
  case MODE_AGENT:
    break;
  }
  return NULL;
}

static bool parse_activation_hello(const char *source, size_t length,
                                   HelperMode command_mode,
                                   ActivationHello *hello) {
  JsonToken *tokens = calloc(MAX_JSON_TOKENS, sizeof(*tokens));
  int count = 0;
  static const char *const keys[] = {
      "kind",          "phase",          "requestId",
      "protocolVersion", "helperVersion", "activationId",
      "mode",          "candidateRoot",  "expectedHostInstanceId",
      "requestedCapabilities"};
  bool valid = tokens && json_parse(source, length, tokens, MAX_JSON_TOKENS,
                                    &count) &&
               object_has_exact_keys(source, tokens, count, 0, keys,
                                     sizeof(keys) / sizeof(keys[0]));
  if (!valid) {
    free(tokens);
    return false;
  }
  int kind = object_get(source, tokens, count, 0, "kind");
  int phase = object_get(source, tokens, count, 0, "phase");
  int request = object_get(source, tokens, count, 0, "requestId");
  int protocol = object_get(source, tokens, count, 0, "protocolVersion");
  int version = object_get(source, tokens, count, 0, "helperVersion");
  int activation = object_get(source, tokens, count, 0, "activationId");
  int mode = object_get(source, tokens, count, 0, "mode");
  int candidate = object_get(source, tokens, count, 0, "candidateRoot");
  int expected = object_get(source, tokens, count, 0, "expectedHostInstanceId");
  int capabilities = object_get(source, tokens, count, 0,
                                "requestedCapabilities");
  long protocol_value = 0;
  char version_value[QLAB_REMOTE_MAX_ID_BYTES + 1];
  const char *required_mode = activation_mode_name(command_mode);
  valid = required_mode && token_string_equal(source, &tokens[kind], "hello") &&
          token_string_equal(source, &tokens[phase], "activation") &&
          token_long(source, &tokens[protocol], 1, 1, &protocol_value) &&
          copy_checked_string(source, &tokens[request], hello->request_id,
                              sizeof(hello->request_id), valid_id) &&
          copy_checked_string(source, &tokens[activation], hello->activation_id,
                              sizeof(hello->activation_id), valid_id) &&
          copy_checked_string(source, &tokens[version], version_value,
                              sizeof(version_value), valid_id) &&
          !strcmp(version_value, QLAB_REMOTE_HELPER_VERSION) &&
          token_string_equal(source, &tokens[mode], required_mode) &&
          capabilities_parse(source, tokens, count, capabilities,
                             &hello->capabilities) &&
          capabilities_match_mode(&hello->capabilities, command_mode);
  if (!valid) {
    free(tokens);
    activation_hello_free(hello);
    return false;
  }
  memcpy(hello->mode, required_mode, strlen(required_mode) + 1);
  if (command_mode == MODE_REPOSITORY_HANDSHAKE) {
    hello->candidate_root = token_strdup(source, &tokens[candidate], PATH_MAX - 1);
    valid = hello->candidate_root && hello->candidate_root[0] == '/' &&
            !path_has_traversal(hello->candidate_root) &&
            !strchr(hello->candidate_root, '\r') &&
            !strchr(hello->candidate_root, '\n');
  } else {
    valid = tokens[candidate].type == JSON_NULL;
  }
  if (tokens[expected].type == JSON_NULL) {
    hello->has_expected_host = false;
  } else {
    hello->has_expected_host = copy_checked_string(
        source, &tokens[expected], hello->expected_host,
        sizeof(hello->expected_host), valid_uuid);
    valid = valid && hello->has_expected_host;
  }
  free(tokens);
  if (!valid)
    activation_hello_free(hello);
  return valid;
}

static bool parse_bound_hello(const char *source, size_t length,
                              BoundHello *hello) {
  JsonToken *tokens = calloc(MAX_JSON_TOKENS, sizeof(*tokens));
  int count = 0;
  static const char *const keys[] = {
      "kind",          "phase",        "requestId",
      "protocolVersion", "helperVersion", "mode",
      "targetId",      "targetEpoch",  "canonicalRoot",
      "expectedHostInstanceId", "expectedRepositoryUuid",
      "expectedRepositoryId", "requestedCapabilities"};
  bool valid = tokens && json_parse(source, length, tokens, MAX_JSON_TOKENS,
                                    &count) &&
               object_has_exact_keys(source, tokens, count, 0, keys,
                                     sizeof(keys) / sizeof(keys[0]));
  if (!valid) {
    free(tokens);
    return false;
  }
  int kind = object_get(source, tokens, count, 0, "kind");
  int phase = object_get(source, tokens, count, 0, "phase");
  int request = object_get(source, tokens, count, 0, "requestId");
  int protocol = object_get(source, tokens, count, 0, "protocolVersion");
  int version = object_get(source, tokens, count, 0, "helperVersion");
  int mode = object_get(source, tokens, count, 0, "mode");
  int target = object_get(source, tokens, count, 0, "targetId");
  int epoch = object_get(source, tokens, count, 0, "targetEpoch");
  int root = object_get(source, tokens, count, 0, "canonicalRoot");
  int host = object_get(source, tokens, count, 0, "expectedHostInstanceId");
  int repository_uuid = object_get(source, tokens, count, 0,
                                   "expectedRepositoryUuid");
  int repository_id = object_get(source, tokens, count, 0,
                                 "expectedRepositoryId");
  int capabilities = object_get(source, tokens, count, 0,
                                "requestedCapabilities");
  long protocol_value = 0;
  char version_value[QLAB_REMOTE_MAX_ID_BYTES + 1];
  valid = token_string_equal(source, &tokens[kind], "hello") &&
          token_string_equal(source, &tokens[phase], "bound") &&
          token_string_equal(source, &tokens[mode], "agent") &&
          token_long(source, &tokens[protocol], 1, 1, &protocol_value) &&
          token_long(source, &tokens[epoch], 0, MAX_SAFE_INTEGER,
                     &hello->target_epoch) &&
          copy_checked_string(source, &tokens[request], hello->request_id,
                              sizeof(hello->request_id), valid_id) &&
          copy_checked_string(source, &tokens[target], hello->target_id,
                              sizeof(hello->target_id), valid_id) &&
          copy_checked_string(source, &tokens[version], version_value,
                              sizeof(version_value), valid_id) &&
          !strcmp(version_value, QLAB_REMOTE_HELPER_VERSION) &&
          copy_checked_string(source, &tokens[host], hello->expected_host,
                              sizeof(hello->expected_host), valid_uuid) &&
          copy_checked_string(source, &tokens[repository_uuid],
                              hello->expected_repository_uuid,
                              sizeof(hello->expected_repository_uuid),
                              valid_uuid) &&
          copy_checked_string(source, &tokens[repository_id],
                              hello->expected_repository_id,
                              sizeof(hello->expected_repository_id), valid_id) &&
          capabilities_parse(source, tokens, count, capabilities,
                             &hello->capabilities) &&
          capabilities_match_mode(&hello->capabilities, MODE_AGENT);
  hello->canonical_root = token_strdup(source, &tokens[root], PATH_MAX - 1);
  valid = valid && hello->canonical_root && hello->canonical_root[0] == '/' &&
          !path_has_traversal(hello->canonical_root) &&
          !strchr(hello->canonical_root, '\r') &&
          !strchr(hello->canonical_root, '\n');
  free(tokens);
  if (!valid)
    bound_hello_free(hello);
  return valid;
}

static bool canonicalize_directory(const char *input, bool require_equal,
                                   char output[PATH_MAX]) {
  if (!input || input[0] != '/' || path_has_traversal(input) ||
      strchr(input, '\r') || strchr(input, '\n') || !realpath(input, output))
    return false;
  if (require_equal && strcmp(input, output))
    return false;
  int descriptor = open_absolute_directory_nofollow(output);
  if (descriptor < 0)
    return false;
  close(descriptor);
  return true;
}

static bool emit_activation_server_hello(const ActivationHello *hello,
                                         const char *host_uuid,
                                         const char *canonical_root,
                                         const char *repository_uuid) {
  StrBuf frame = {0};
  bool success = sb_append(&frame, "{\"kind\":\"hello\",\"phase\":\"activation\",\"requestId\":") &&
                 sb_json_string(&frame, hello->request_id) &&
                 sb_append(&frame, ",\"protocolVersion\":1,\"helperVersion\":") &&
                 sb_json_string(&frame, QLAB_REMOTE_HELPER_VERSION) &&
                 sb_append(&frame, ",\"activationId\":") &&
                 sb_json_string(&frame, hello->activation_id) &&
                 sb_append(&frame, ",\"mode\":") &&
                 sb_json_string(&frame, hello->mode) &&
                 sb_append(&frame, ",\"hostInstanceId\":") &&
                 sb_json_string(&frame, host_uuid) &&
                 sb_append(&frame, ",\"canonicalRoot\":") &&
                 (canonical_root ? sb_json_string(&frame, canonical_root)
                                 : sb_append(&frame, "null")) &&
                 sb_append(&frame, ",\"repositoryUuid\":") &&
                 (repository_uuid ? sb_json_string(&frame, repository_uuid)
                                  : sb_append(&frame, "null")) &&
                 sb_append(&frame, ",\"capabilities\":") &&
                 sb_append(&frame, hello->capabilities.json) &&
                 sb_append(&frame, "}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static bool emit_bound_server_hello(const BoundHello *hello,
                                    const char *host_uuid,
                                    const char *repository_uuid,
                                    const char *helper_instance_uuid) {
  StrBuf frame = {0};
  bool success = sb_append(&frame, "{\"kind\":\"hello\",\"phase\":\"bound\",\"requestId\":") &&
                 sb_json_string(&frame, hello->request_id) &&
                 sb_append(&frame, ",\"protocolVersion\":1,\"helperVersion\":") &&
                 sb_json_string(&frame, QLAB_REMOTE_HELPER_VERSION) &&
                 sb_append(&frame, ",\"mode\":\"agent\",\"targetId\":") &&
                 sb_json_string(&frame, hello->target_id) &&
                 sb_printf(&frame, ",\"targetEpoch\":%ld,\"canonicalRoot\":",
                           hello->target_epoch) &&
                 sb_json_string(&frame, hello->canonical_root) &&
                 sb_append(&frame, ",\"hostInstanceId\":") &&
                 sb_json_string(&frame, host_uuid) &&
                 sb_append(&frame, ",\"repositoryUuid\":") &&
                 sb_json_string(&frame, repository_uuid) &&
                 sb_append(&frame, ",\"repositoryId\":") &&
                 sb_json_string(&frame, hello->expected_repository_id) &&
                 sb_append(&frame, ",\"helperInstanceId\":") &&
                 sb_json_string(&frame, helper_instance_uuid) &&
                 sb_append(&frame, ",\"capabilities\":") &&
                 sb_append(&frame, hello->capabilities.json) &&
                 sb_append(&frame, "}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static bool append_activation_context(StrBuf *frame,
                                      const ActivationHello *hello,
                                      const char *host_uuid) {
  return sb_append(frame, "\"protocolVersion\":1,\"helperVersion\":") &&
         sb_json_string(frame, QLAB_REMOTE_HELPER_VERSION) &&
         sb_append(frame, ",\"activationId\":") &&
         sb_json_string(frame, hello->activation_id) &&
         sb_append(frame, ",\"hostInstanceId\":") &&
         sb_json_string(frame, host_uuid) &&
         sb_append(frame, ",\"capabilities\":") &&
         sb_append(frame, hello->capabilities.json);
}

static const char *protocol_error_name(ProtocolErrorCode code) {
  switch (code) {
  case PROTOCOL_INVALID_REQUEST:
    return "INVALID_REQUEST";
  case PROTOCOL_METHOD_NOT_ALLOWED:
    return "METHOD_NOT_ALLOWED";
  case PROTOCOL_DUPLICATE_ID:
    return "DUPLICATE_ID";
  }
  return "INVALID_REQUEST";
}

static bool emit_activation_protocol_error(const ActivationHello *hello,
                                           const char *host_uuid,
                                           const char *request_id,
                                           ProtocolErrorCode code,
                                           const char *message) {
  StrBuf frame = {0};
  bool success = sb_append(&frame, "{") &&
                 append_activation_context(&frame, hello, host_uuid) &&
                 sb_append(&frame, ",\"kind\":\"protocol-error\",\"requestId\":") &&
                 (request_id ? sb_json_string(&frame, request_id)
                             : sb_append(&frame, "null")) &&
                 sb_append(&frame, ",\"code\":") &&
                 sb_json_string(&frame, protocol_error_name(code)) &&
                 sb_append(&frame, ",\"message\":") &&
                 sb_json_string(&frame, message) && sb_append(&frame, "}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static bool emit_activation_result_prefix(StrBuf *frame,
                                          const ActivationHello *hello,
                                          const char *host_uuid,
                                          const char *request_id,
                                          const char *method) {
  return sb_append(frame, "{") &&
         append_activation_context(frame, hello, host_uuid) &&
         sb_append(frame, ",\"kind\":\"response\",\"id\":") &&
         sb_json_string(frame, request_id) &&
         sb_append(frame, ",\"method\":") && sb_json_string(frame, method);
}

static bool emit_activation_error(const ActivationHello *hello,
                                  const char *host_uuid,
                                  const char *request_id,
                                  const char *method, const char *code,
                                  const char *message) {
  StrBuf frame = {0};
  bool success = emit_activation_result_prefix(&frame, hello, host_uuid,
                                               request_id, method) &&
                 sb_append(&frame, ",\"error\":{\"code\":") &&
                 sb_json_string(&frame, code) &&
                 sb_append(&frame, ",\"message\":") &&
                 sb_json_string(&frame, message) && sb_append(&frame, "}}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static bool parse_request_id_if_trustworthy(const char *source,
                                            const JsonToken *tokens,
                                            int count, char output[129]) {
  int token = object_get(source, tokens, count, 0, "id");
  return token >= 0 && copy_checked_string(source, &tokens[token], output, 129,
                                           valid_id);
}

static bool request_id_seen(char ids[MAX_REQUEST_IDS][129], size_t count,
                            const char *candidate) {
  for (size_t index = 0; index < count; index++)
    if (!strcmp(ids[index], candidate))
      return true;
  return false;
}

static bool validate_request_context(const char *source,
                                     const JsonToken *tokens, int count,
                                     const ActivationHello *hello,
                                     const char *host_uuid) {
  long protocol = 0;
  char version[129];
  char activation[129];
  char host[37];
  Capabilities capabilities = {0};
  int protocol_token = object_get(source, tokens, count, 0, "protocolVersion");
  int version_token = object_get(source, tokens, count, 0, "helperVersion");
  int activation_token = object_get(source, tokens, count, 0, "activationId");
  int host_token = object_get(source, tokens, count, 0, "hostInstanceId");
  int capabilities_token = object_get(source, tokens, count, 0, "capabilities");
  bool valid = token_long(source, &tokens[protocol_token], 1, 1, &protocol) &&
               copy_checked_string(source, &tokens[version_token], version,
                                   sizeof(version), valid_id) &&
               copy_checked_string(source, &tokens[activation_token], activation,
                                   sizeof(activation), valid_id) &&
               copy_checked_string(source, &tokens[host_token], host,
                                   sizeof(host), valid_uuid) &&
               capabilities_parse(source, tokens, count, capabilities_token,
                                  &capabilities) &&
               !strcmp(version, QLAB_REMOTE_HELPER_VERSION) &&
               !strcmp(activation, hello->activation_id) &&
               !strcmp(host, host_uuid) &&
               capabilities_equal(&capabilities, &hello->capabilities);
  capabilities_free(&capabilities);
  return valid;
}

static bool params_empty(const char *source, const JsonToken *tokens, int count,
                         int token) {
  static const char *const keys[] = {NULL};
  return object_has_exact_keys(source, tokens, count, token, keys, 0);
}

static bool parse_one_path_param(const char *source, const JsonToken *tokens,
                                 int count, int token, const char *key,
                                 char output[PATH_MAX]) {
  const char *keys[] = {key};
  if (!object_has_exact_keys(source, tokens, count, token, keys, 1))
    return false;
  int value_token = object_get(source, tokens, count, token, key);
  char *value = token_strdup(source, &tokens[value_token], PATH_MAX - 1);
  bool valid = value && value[0] == '/' && !path_has_traversal(value) &&
               !strchr(value, '\r') && !strchr(value, '\n');
  if (valid)
    memcpy(output, value, strlen(value) + 1);
  free(value);
  return valid;
}

static bool emit_path_result(const ActivationHello *hello,
                             const char *host_uuid, const char *request_id,
                             const char *method, const char *path) {
  StrBuf frame = {0};
  bool success = emit_activation_result_prefix(&frame, hello, host_uuid,
                                               request_id, method) &&
                 sb_append(&frame, ",\"result\":{\"path\":") &&
                 sb_json_string(&frame, path) && sb_append(&frame, "}}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static int compare_strings(const void *left, const void *right) {
  const char *const *left_string = left;
  const char *const *right_string = right;
  return strcmp(*left_string, *right_string);
}

static bool emit_directory_result(const ActivationHello *hello,
                                  const char *host_uuid,
                                  const char *request_id,
                                  const char *directory) {
  int descriptor = open_absolute_directory_nofollow(directory);
  if (descriptor < 0)
    return emit_activation_error(hello, host_uuid, request_id,
                                 "browse.listDirectories", "PATH_REJECTED",
                                 "Directory path is not safely accessible");
  DIR *stream = fdopendir(dup(descriptor));
  if (!stream) {
    close(descriptor);
    return emit_activation_error(hello, host_uuid, request_id,
                                 "browse.listDirectories", "INTERNAL",
                                 "Directory enumeration failed");
  }
  char *names[MAX_DIRECTORY_ENTRIES];
  size_t count = 0;
  bool overflowed = false;
  struct dirent *entry;
  errno = 0;
  while ((entry = readdir(stream)) != NULL) {
    if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
      continue;
    struct stat status;
    if (fstatat(descriptor, entry->d_name, &status, AT_SYMLINK_NOFOLLOW) < 0 ||
        !S_ISDIR(status.st_mode))
      continue;
    size_t length = strlen(entry->d_name);
    if (!length || length > 255 ||
        !valid_utf8((const unsigned char *)entry->d_name, length))
      continue;
    if (count == MAX_DIRECTORY_ENTRIES) {
      overflowed = true;
      break;
    }
    names[count] = strdup(entry->d_name);
    if (!names[count]) {
      overflowed = true;
      break;
    }
    count++;
  }
  bool read_failed = errno != 0;
  closedir(stream);
  close(descriptor);
  if (overflowed || read_failed) {
    for (size_t index = 0; index < count; index++)
      free(names[index]);
    return emit_activation_error(hello, host_uuid, request_id,
                                 "browse.listDirectories", "INTERNAL",
                                 "Directory enumeration exceeded its bound");
  }
  qsort(names, count, sizeof(names[0]), compare_strings);
  StrBuf frame = {0};
  bool success = emit_activation_result_prefix(
                     &frame, hello, host_uuid, request_id,
                     "browse.listDirectories") &&
                 sb_append(&frame, ",\"result\":{\"entries\":[");
  for (size_t index = 0; success && index < count; index++) {
    char path[PATH_MAX];
    int length = !strcmp(directory, "/")
                     ? snprintf(path, sizeof(path), "/%s", names[index])
                     : snprintf(path, sizeof(path), "%s/%s", directory,
                                names[index]);
    success = length > 0 && (size_t)length < sizeof(path) &&
              (!index || sb_append(&frame, ",")) &&
              sb_append(&frame, "{\"name\":") &&
              sb_json_string(&frame, names[index]) &&
              sb_append(&frame, ",\"path\":") && sb_json_string(&frame, path) &&
              sb_append(&frame, ",\"kind\":\"directory\"}");
  }
  for (size_t index = 0; index < count; index++)
    free(names[index]);
  success = success && sb_append(&frame, "]}}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static bool parse_version_line(const ProcessResult *process, char output[64],
                               unsigned long parts[3]) {
  if (process->exit_code != 0 || process->timed_out || process->overflowed ||
      !process->length || process->length >= 128)
    return false;
  size_t length = process->length;
  if (process->output[length - 1] == '\n')
    length--;
  if (!length || memchr(process->output, '\n', length) ||
      memchr(process->output, '\r', process->length) ||
      memchr(process->output, 0, process->length))
    return false;
  const char *prefix = NULL;
  size_t prefix_length = 0;
  if (length > strlen("codex-cli ") &&
      !memcmp(process->output, "codex-cli ", strlen("codex-cli "))) {
    prefix = "codex-cli ";
    prefix_length = strlen(prefix);
  } else if (length > strlen("codex ") &&
             !memcmp(process->output, "codex ", strlen("codex "))) {
    prefix = "codex ";
    prefix_length = strlen(prefix);
  }
  if (!prefix || length - prefix_length >= 64)
    return false;
  memcpy(output, process->output + prefix_length, length - prefix_length);
  output[length - prefix_length] = 0;
  const char *cursor = output;
  for (int component = 0; component < 3; component++) {
    const char *start = cursor;
    if (!isdigit((unsigned char)*cursor))
      return false;
    if (*cursor == '0' && isdigit((unsigned char)cursor[1]))
      return false;
    errno = 0;
    char *end = NULL;
    unsigned long value = strtoul(cursor, &end, 10);
    if (errno || !end || end == start)
      return false;
    parts[component] = value;
    if (component < 2) {
      if (*end != '.')
        return false;
      cursor = end + 1;
    } else if (*end) {
      return false;
    }
  }
  return true;
}

static int compare_version_parts(const unsigned long left[3],
                                 const unsigned long right[3]) {
  for (int index = 0; index < 3; index++) {
    if (left[index] < right[index])
      return -1;
    if (left[index] > right[index])
      return 1;
  }
  return 0;
}

static bool emit_probe_result(const ActivationHello *hello,
                              const char *host_uuid, const char *request_id) {
  char *const version_arguments[] = {"codex", "--version", NULL};
  ProcessResult version_result = {0};
  if (!run_fixed_process(version_arguments, MAX_PROBE_OUTPUT,
                         FIXED_PROCESS_TIMEOUT_MS, &version_result))
    return emit_activation_error(hello, host_uuid, request_id, "codex.probe",
                                 "PROBE_FAILED", "Codex version probe failed");
  if (version_result.exit_code == 127 && version_result.length == 0 &&
      !version_result.timed_out && !version_result.overflowed) {
    process_result_free(&version_result);
    StrBuf frame = {0};
    bool success = emit_activation_result_prefix(&frame, hello, host_uuid,
                                                 request_id, "codex.probe") &&
                   sb_append(&frame, ",\"result\":{\"state\":\"missing\"}}");
    if (!success) {
      sb_free(&frame);
      return false;
    }
    return emit_frame(&frame);
  }
  char version[64];
  unsigned long found[3];
  if (!parse_version_line(&version_result, version, found)) {
    process_result_free(&version_result);
    return emit_activation_error(hello, host_uuid, request_id, "codex.probe",
                                 "PROBE_FAILED", "Codex returned an invalid version");
  }
  process_result_free(&version_result);
  const unsigned long minimum[3] = {0, 146, 0};
  if (compare_version_parts(found, minimum) < 0) {
    StrBuf frame = {0};
    bool success = emit_activation_result_prefix(&frame, hello, host_uuid,
                                                 request_id, "codex.probe") &&
                   sb_append(&frame, ",\"result\":{\"state\":\"incompatible\",\"foundVersion\":") &&
                   sb_json_string(&frame, version) &&
                   sb_append(&frame, ",\"minimumVersion\":") &&
                   sb_json_string(&frame, QLAB_REMOTE_MINIMUM_CODEX_VERSION) &&
                   sb_append(&frame, "}}");
    if (!success) {
      sb_free(&frame);
      return false;
    }
    return emit_frame(&frame);
  }
  char *const login_arguments[] = {"codex", "login", "status", NULL};
  ProcessResult login_result = {0};
  if (!run_fixed_process(login_arguments, MAX_PROBE_OUTPUT,
                         FIXED_PROCESS_TIMEOUT_MS, &login_result))
    return emit_activation_error(hello, host_uuid, request_id, "codex.probe",
                                 "PROBE_FAILED", "Codex login probe failed");
  const char *state = NULL;
  if (!login_result.timed_out && !login_result.overflowed &&
      login_result.exit_code == 0)
    state = "ready";
  else if (!login_result.timed_out && !login_result.overflowed &&
           login_result.exit_code == 1)
    state = "unauthenticated";
  process_result_free(&login_result);
  if (!state)
    return emit_activation_error(hello, host_uuid, request_id, "codex.probe",
                                 "PROBE_FAILED", "Codex login probe failed");
  StrBuf frame = {0};
  bool success = emit_activation_result_prefix(&frame, hello, host_uuid,
                                               request_id, "codex.probe") &&
                 sb_append(&frame, ",\"result\":{\"state\":") &&
                 sb_json_string(&frame, state) &&
                 sb_append(&frame, ",\"version\":") &&
                 sb_json_string(&frame, version) && sb_append(&frame, "}}");
  if (!success) {
    sb_free(&frame);
    return false;
  }
  return emit_frame(&frame);
}

static int run_browse(const ActivationHello *hello, const char *host_uuid) {
  char ids[MAX_REQUEST_IDS][129];
  size_t id_count = 0;
  for (;;) {
    char *source = NULL;
    size_t length = 0;
    FrameReadResult read_result = read_jsonl_frame(stdin, &source, &length);
    if (read_result == FRAME_EOF)
      return 0;
    if (read_result != FRAME_OK) {
      (void)emit_activation_protocol_error(
          hello, host_uuid, NULL, PROTOCOL_INVALID_REQUEST,
          read_result == FRAME_TOO_LARGE ? "JSONL frame exceeds 8 MiB"
                                         : "Incomplete JSONL request");
      return QLAB_REMOTE_IDENTITY_EXIT;
    }
    JsonToken *tokens = calloc(MAX_JSON_TOKENS, sizeof(*tokens));
    int count = 0;
    char trusted_id[129] = {0};
    bool parsed = tokens && json_parse(source, length, tokens, MAX_JSON_TOKENS,
                                       &count);
    if (parsed)
      (void)parse_request_id_if_trustworthy(source, tokens, count, trusted_id);
    static const char *const keys[] = {
        "protocolVersion", "helperVersion", "activationId", "hostInstanceId",
        "capabilities", "kind", "id", "method", "params"};
    bool structurally_valid =
        parsed && object_has_exact_keys(source, tokens, count, 0, keys,
                                        sizeof(keys) / sizeof(keys[0])) &&
        validate_request_context(source, tokens, count, hello, host_uuid);
    int kind = parsed ? object_get(source, tokens, count, 0, "kind") : -1;
    int method_token = parsed ? object_get(source, tokens, count, 0, "method") : -1;
    int params = parsed ? object_get(source, tokens, count, 0, "params") : -1;
    structurally_valid = structurally_valid && kind >= 0 &&
                         token_string_equal(source, &tokens[kind], "request") &&
                         trusted_id[0] && method_token >= 0;
    char *method = structurally_valid
                       ? token_strdup(source, &tokens[method_token], 64)
                       : NULL;
    if (!structurally_valid || !method) {
      (void)emit_activation_protocol_error(
          hello, host_uuid, trusted_id[0] ? trusted_id : NULL,
          PROTOCOL_INVALID_REQUEST, "Malformed activation request");
      free(method);
      free(tokens);
      free(source);
      return QLAB_REMOTE_IDENTITY_EXIT;
    }
    if (request_id_seen(ids, id_count, trusted_id)) {
      (void)emit_activation_protocol_error(hello, host_uuid, trusted_id,
                                           PROTOCOL_DUPLICATE_ID,
                                           "Request ID was already used");
      free(method);
      free(tokens);
      free(source);
      return QLAB_REMOTE_IDENTITY_EXIT;
    }
    if (id_count == MAX_REQUEST_IDS) {
      (void)emit_activation_protocol_error(hello, host_uuid, trusted_id,
                                           PROTOCOL_INVALID_REQUEST,
                                           "Request ID limit exceeded");
      free(method);
      free(tokens);
      free(source);
      return QLAB_REMOTE_IDENTITY_EXIT;
    }
    memcpy(ids[id_count++], trusted_id, strlen(trusted_id) + 1);

    bool known = !strcmp(method, "browse.home") ||
                 !strcmp(method, "browse.listDirectories") ||
                 !strcmp(method, "browse.canonicalize") ||
                 !strcmp(method, "codex.probe");
    if (!known) {
      (void)emit_activation_protocol_error(hello, host_uuid, trusted_id,
                                           PROTOCOL_METHOD_NOT_ALLOWED,
                                           "Activation method is not allowed");
      free(method);
      free(tokens);
      free(source);
      return QLAB_REMOTE_IDENTITY_EXIT;
    }
    char path[PATH_MAX];
    bool params_valid = false;
    if (!strcmp(method, "browse.home") || !strcmp(method, "codex.probe"))
      params_valid = params_empty(source, tokens, count, params);
    else if (!strcmp(method, "browse.listDirectories"))
      params_valid = parse_one_path_param(source, tokens, count, params, "path",
                                          path);
    else
      params_valid = parse_one_path_param(source, tokens, count, params, "input",
                                          path);
    if (!params_valid) {
      (void)emit_activation_protocol_error(hello, host_uuid, trusted_id,
                                           PROTOCOL_INVALID_REQUEST,
                                           "Activation method params are invalid");
      free(method);
      free(tokens);
      free(source);
      return QLAB_REMOTE_IDENTITY_EXIT;
    }

    bool emitted = false;
    if (!strcmp(method, "browse.home")) {
      char home[PATH_MAX];
      emitted = canonical_login_home(home) &&
                emit_path_result(hello, host_uuid, trusted_id, method, home);
    } else if (!strcmp(method, "browse.listDirectories")) {
      char canonical[PATH_MAX];
      if (!canonicalize_directory(path, true, canonical))
        emitted = emit_activation_error(
            hello, host_uuid, trusted_id, method, "PATH_REJECTED",
            "Directory is not canonical or safely accessible");
      else
        emitted = emit_directory_result(hello, host_uuid, trusted_id, canonical);
    } else if (!strcmp(method, "browse.canonicalize")) {
      char canonical[PATH_MAX];
      if (!canonicalize_directory(path, false, canonical))
        emitted = emit_activation_error(
            hello, host_uuid, trusted_id, method, "PATH_REJECTED",
            "Input is not an accessible directory");
      else
        emitted = emit_path_result(hello, host_uuid, trusted_id, method,
                                   canonical);
    } else {
      emitted = emit_probe_result(hello, host_uuid, trusted_id);
    }
    free(method);
    free(tokens);
    free(source);
    if (!emitted)
      return QLAB_REMOTE_IDENTITY_EXIT;
  }
}

static bool configure_setup_terminal(void) {
  struct termios terminal;
  if (tcgetattr(STDIN_FILENO, &terminal) < 0)
    return false;
  cfmakeraw(&terminal);
  terminal.c_lflag &= (tcflag_t)~ECHO;
  terminal.c_cc[VMIN] = 1;
  terminal.c_cc[VTIME] = 0;
  if (tcsetattr(STDIN_FILENO, TCSANOW, &terminal) < 0)
    return false;
  struct termios verified;
  if (tcgetattr(STDIN_FILENO, &verified) < 0)
    return false;
  return !(verified.c_lflag & (ECHO | ICANON)) && !(verified.c_oflag & OPOST);
}

static int run_setup_auth(const ActivationHello *hello, const char *host_uuid) {
  if (!emit_activation_server_hello(hello, host_uuid, NULL, NULL))
    return QLAB_REMOTE_IDENTITY_EXIT;
  StrBuf frame = {0};
  bool success = sb_append(&frame, "{\"kind\":\"setup-ready\",\"requestId\":") &&
                 sb_json_string(&frame, hello->request_id) &&
                 sb_append(&frame, ",\"protocolVersion\":1,\"helperVersion\":") &&
                 sb_json_string(&frame, QLAB_REMOTE_HELPER_VERSION) &&
                 sb_append(&frame, ",\"activationId\":") &&
                 sb_json_string(&frame, hello->activation_id) &&
                 sb_append(&frame, ",\"hostInstanceId\":") &&
                 sb_json_string(&frame, host_uuid) &&
                 sb_append(&frame, ",\"capability\":\"codex-device-auth-pty\"}");
  if (!success || !emit_frame(&frame)) {
    if (!success)
      sb_free(&frame);
    return QLAB_REMOTE_IDENTITY_EXIT;
  }
  char *const arguments[] = {"codex", "login", "--device-auth", NULL};
  execvp(arguments[0], arguments);
  return 127;
}

static int run_agent(const BoundHello *hello, const char *host_uuid,
                     const char *repository_uuid) {
  char helper_instance[37];
  if (!generate_uuid(helper_instance))
    return QLAB_REMOTE_IDENTITY_EXIT;
  int gate[2];
  if (pipe(gate) < 0)
    return QLAB_REMOTE_IDENTITY_EXIT;
  pid_t child = fork();
  if (child < 0) {
    close(gate[0]);
    close(gate[1]);
    return QLAB_REMOTE_IDENTITY_EXIT;
  }
  if (child == 0) {
    close(gate[1]);
    unsigned char byte;
    ssize_t amount;
    do {
      amount = read(gate[0], &byte, 1);
    } while (amount < 0 && errno == EINTR);
    close(gate[0]);
    if (amount != 1)
      _exit(126);
    int null_descriptor = open("/dev/null", O_WRONLY | O_CLOEXEC);
    if (null_descriptor >= 0) {
      if (dup2(null_descriptor, STDERR_FILENO) < 0)
        _exit(126);
      if (null_descriptor != STDERR_FILENO)
        close(null_descriptor);
    }
    char *const arguments[] = {"codex", "app-server", "--stdio", NULL};
    execvp(arguments[0], arguments);
    _exit(127);
  }
  close(gate[0]);
  bool emitted = emit_bound_server_hello(hello, host_uuid, repository_uuid,
                                         helper_instance);
  if (emitted) {
    StrBuf frame = {0};
    emitted = sb_append(&frame, "{\"protocolVersion\":1,\"helperVersion\":") &&
              sb_json_string(&frame, QLAB_REMOTE_HELPER_VERSION) &&
              sb_append(&frame, ",\"targetId\":") &&
              sb_json_string(&frame, hello->target_id) &&
              sb_printf(&frame, ",\"targetEpoch\":%ld,\"hostInstanceId\":",
                        hello->target_epoch) &&
              sb_json_string(&frame, host_uuid) &&
              sb_append(&frame, ",\"repositoryId\":") &&
              sb_json_string(&frame, hello->expected_repository_id) &&
              sb_append(&frame, ",\"capabilities\":") &&
              sb_append(&frame, hello->capabilities.json) &&
              sb_append(&frame, ",\"kind\":\"stream-ready\",\"requestId\":") &&
              sb_json_string(&frame, hello->request_id) &&
              sb_append(&frame, ",\"stream\":\"codex-jsonl\"}");
    if (emitted)
      emitted = emit_frame(&frame);
    else
      sb_free(&frame);
  }
  if (!emitted || !write_all(gate[1], "x", 1)) {
    close(gate[1]);
    kill(child, SIGKILL);
    (void)waitpid(child, NULL, 0);
    return QLAB_REMOTE_IDENTITY_EXIT;
  }
  close(gate[1]);
  int status;
  while (waitpid(child, &status, 0) < 0) {
    if (errno != EINTR)
      return QLAB_REMOTE_IDENTITY_EXIT;
  }
  return WIFEXITED(status) ? WEXITSTATUS(status) : QLAB_REMOTE_IDENTITY_EXIT;
}

static int run_channel(HelperMode mode) {
  if (mode == MODE_SETUP_AUTH && !configure_setup_terminal())
    return QLAB_REMOTE_IDENTITY_EXIT;
  char *source = NULL;
  size_t length = 0;
  FrameReadResult read_result = read_jsonl_frame(stdin, &source, &length);
  if (read_result != FRAME_OK)
    return QLAB_REMOTE_IDENTITY_EXIT;

  if (mode == MODE_AGENT) {
    BoundHello hello = {0};
    bool parsed = parse_bound_hello(source, length, &hello);
    free(source);
    if (!parsed)
      return QLAB_REMOTE_IDENTITY_EXIT;
    char host_uuid[37];
    char canonical_root[PATH_MAX];
    char repository_uuid[37];
    bool valid = load_or_create_host_instance_id("state", host_uuid) &&
                 !strcmp(host_uuid, hello.expected_host) &&
                 canonicalize_directory(hello.canonical_root, true,
                                        canonical_root) &&
                 resolve_repository_uuid(canonical_root, repository_uuid) &&
                 !strcmp(repository_uuid, hello.expected_repository_uuid);
    int result = valid ? run_agent(&hello, host_uuid, repository_uuid)
                       : QLAB_REMOTE_IDENTITY_EXIT;
    bound_hello_free(&hello);
    return result;
  }

  ActivationHello hello = {0};
  bool parsed = parse_activation_hello(source, length, mode, &hello);
  free(source);
  if (!parsed)
    return QLAB_REMOTE_IDENTITY_EXIT;
  char host_uuid[37];
  if (!load_or_create_host_instance_id("state", host_uuid) ||
      (hello.has_expected_host && strcmp(host_uuid, hello.expected_host))) {
    activation_hello_free(&hello);
    return QLAB_REMOTE_IDENTITY_EXIT;
  }
  int result = 0;
  if (mode == MODE_REPOSITORY_HANDSHAKE) {
    char canonical_root[PATH_MAX];
    char repository_uuid[37];
    if (!canonicalize_directory(hello.candidate_root, false, canonical_root) ||
        !resolve_repository_uuid(canonical_root, repository_uuid) ||
        !emit_activation_server_hello(&hello, host_uuid, canonical_root,
                                      repository_uuid))
      result = QLAB_REMOTE_IDENTITY_EXIT;
  } else if (mode == MODE_BROWSE) {
    if (!emit_activation_server_hello(&hello, host_uuid, NULL, NULL))
      result = QLAB_REMOTE_IDENTITY_EXIT;
    else
      result = run_browse(&hello, host_uuid);
  } else {
    result = run_setup_auth(&hello, host_uuid);
  }
  activation_hello_free(&hello);
  return result;
}

int main(int argc, char **argv) {
  (void)setvbuf(stdout, NULL, _IONBF, 0);
  if (argc == 2 && !strcmp(argv[1], "browse")) {
    return run_channel(MODE_BROWSE);
  }
  if (argc == 2 && !strcmp(argv[1], "repository-handshake")) {
    return run_channel(MODE_REPOSITORY_HANDSHAKE);
  }
  if (argc == 2 && !strcmp(argv[1], "agent")) {
    (void)setvbuf(stdin, NULL, _IONBF, 0);
    return run_channel(MODE_AGENT);
  }
  if (argc == 3 && !strcmp(argv[1], "setup") &&
      !strcmp(argv[2], "codex-device-auth")) {
    (void)setvbuf(stdin, NULL, _IONBF, 0);
    return run_channel(MODE_SETUP_AUTH);
  }
  return 64;
}
