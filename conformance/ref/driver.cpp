#include <cstdio>
#include <cstring>
#include <vector>

#include "port.h"

struct SDSP2 DSP2;

static bool read_exact(void *dest, size_t size) {
    return fread(dest, 1, size, stdin) == size;
}

static bool read_u32(uint32_t *out) {
    unsigned char raw[4];
    if (!read_exact(raw, sizeof(raw))) {
        return false;
    }
    *out = (uint32_t)raw[0] | ((uint32_t)raw[1] << 8) | ((uint32_t)raw[2] << 16) |
           ((uint32_t)raw[3] << 24);
    return true;
}

static void reset_chip(const unsigned char *ram, uint8 transparent) {
    memset(&DSP2, 0, sizeof(DSP2));
    DSP2.waiting4command = TRUE;
    DSP2.Op05Transparent = transparent;
    memcpy(DSP2.parameters, ram, sizeof(DSP2.parameters));
}

int main(void) {
    uint32_t exchanges = 0;
    if (!read_u32(&exchanges)) {
        return 1;
    }

    for (uint32_t index = 0; index < exchanges; index++) {
        unsigned char ram[512];
        if (!read_exact(ram, sizeof(ram))) {
            return 1;
        }

        unsigned char transparent = 0;
        if (!read_exact(&transparent, 1)) {
            return 1;
        }

        uint32_t steps = 0;
        if (!read_u32(&steps)) {
            return 1;
        }

        reset_chip(ram, (uint8)transparent);

        std::vector<unsigned char> answered;
        for (uint32_t step = 0; step < steps; step++) {
            unsigned char kind = 0;
            unsigned char value = 0;
            if (!read_exact(&kind, 1) || !read_exact(&value, 1)) {
                return 1;
            }
            if (kind == 'w') {
                DSP2SetByte((uint8)value, 0x6000);
            } else {
                answered.push_back((unsigned char)DSP2GetByte(0x6000));
            }
        }

        uint32_t produced = (uint32_t)answered.size();
        unsigned char header[4] = {
            (unsigned char)(produced & 0xFF),
            (unsigned char)((produced >> 8) & 0xFF),
            (unsigned char)((produced >> 16) & 0xFF),
            (unsigned char)((produced >> 24) & 0xFF),
        };
        if (fwrite(header, 1, sizeof(header), stdout) != sizeof(header)) {
            return 1;
        }
        if (produced != 0 &&
            fwrite(answered.data(), 1, produced, stdout) != produced) {
            return 1;
        }
    }
    return 0;
}
