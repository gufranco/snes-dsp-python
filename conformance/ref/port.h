#ifndef DSPREF_PORT_H
#define DSPREF_PORT_H

#include <stdint.h>
#include <string.h>

typedef uint8_t uint8;
typedef int8_t int8;
typedef uint16_t uint16;
typedef int16_t int16;
typedef uint32_t uint32;
typedef int32_t int32;
typedef uint8_t bool8;

#define TRUE 1
#define FALSE 0

#define READ_WORD(s)      (*(uint8 *) (s) | (*((uint8 *) (s) + 1) << 8))
#define READ_3WORD(s)     (*(uint8 *) (s) | (*((uint8 *) (s) + 1) << 8) | (*((uint8 *) (s) + 2) << 16))
#define READ_DWORD(s)     (*(uint8 *) (s) | (*((uint8 *) (s) + 1) << 8) | (*((uint8 *) (s) + 2) << 16) | (*((uint8 *) (s) + 3) << 24))
#define WRITE_WORD(s, d)  *(uint8 *) (s) = (uint8) (d), *((uint8 *) (s) + 1) = (uint8) ((d) >> 8)
#define WRITE_3WORD(s, d) *(uint8 *) (s) = (uint8) (d), *((uint8 *) (s) + 1) = (uint8) ((d) >> 8), *((uint8 *) (s) + 2) = (uint8) ((d) >> 16)
#define WRITE_DWORD(s, d) *(uint8 *) (s) = (uint8) (d), *((uint8 *) (s) + 1) = (uint8) ((d) >> 8), *((uint8 *) (s) + 2) = (uint8) ((d) >> 16), *((uint8 *) (s) + 3) = (uint8) ((d) >> 24)

#include "dsp.h"

#endif
