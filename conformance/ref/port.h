#ifndef DSP2_REF_PORT_H
#define DSP2_REF_PORT_H

#include <stdint.h>
#include <string.h>

typedef uint8_t uint8;
typedef uint16_t uint16;
typedef int16_t int16;
typedef uint32_t uint32;
typedef int32_t int32;
typedef uint8_t bool8;

#define TRUE 1
#define FALSE 0

struct SDSP2
{
    bool8  waiting4command;
    uint8  command;
    uint32 in_count;
    uint32 in_index;
    uint32 out_count;
    uint32 out_index;
    uint8  parameters[512];
    uint8  output[512];

    bool8  Op05HasLen;
    int32  Op05Len;
    uint8  Op05Transparent;

    bool8  Op06HasLen;
    int32  Op06Len;

    uint16 Op09Word1;
    uint16 Op09Word2;

    bool8  Op0DHasLen;
    int32  Op0DOutLen;
    int32  Op0DInLen;
};

extern struct SDSP2 DSP2;

void  DSP2SetByte (uint8, uint16);
uint8 DSP2GetByte (uint16);

#endif
