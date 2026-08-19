#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "port.h"

struct SDSP0 DSP0;
struct SDSP1 DSP1;
struct SDSP2 DSP2;
struct SDSP3 DSP3;
struct SDSP4 DSP4;

void DSP3_Reset(void);

typedef void (*Setter)(uint8, uint16);
typedef uint8 (*Getter)(uint16);
typedef void (*Resetter)(const unsigned char *);

static const uint16 PORT = 0x6000;

static void reset_dsp1(const unsigned char *ram) {
    memset(&DSP1, 0, sizeof(DSP1));
    DSP1.waiting4command = TRUE;
    DSP1.first_parameter = TRUE;
    memcpy(DSP1.parameters, ram, sizeof(DSP1.parameters));
}

static void reset_dsp2(const unsigned char *ram) {
    memset(&DSP2, 0, sizeof(DSP2));
    DSP2.waiting4command = TRUE;
    memcpy(DSP2.parameters, ram, sizeof(DSP2.parameters));
}

static void reset_dsp3(const unsigned char *ram) {
    memset(&DSP3, 0, sizeof(DSP3));
    DSP3_Reset();
    (void)ram;
}

static void reset_dsp4(const unsigned char *ram) {
    memset(&DSP4, 0, sizeof(DSP4));
    DSP4.waiting4command = TRUE;
    memcpy(DSP4.parameters, ram, sizeof(DSP4.parameters));
}

struct Chip {
    const char *name;
    Setter set;
    Getter get;
    Resetter reset;
};

static const Chip CHIPS[] = {
    {"dsp1", DSP1SetByte, DSP1GetByte, reset_dsp1},
    {"dsp2", DSP2SetByte, DSP2GetByte, reset_dsp2},
    {"dsp3", DSP3SetByte, DSP3GetByte, reset_dsp3},
    {"dsp4", DSP4SetByte, DSP4GetByte, reset_dsp4},
};

static const Chip *find(const char *name) {
    for (size_t i = 0; i < sizeof(CHIPS) / sizeof(CHIPS[0]); i++) {
        if (std::string(CHIPS[i].name) == name) {
            return &CHIPS[i];
        }
    }
    return NULL;
}

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

static bool write_u32(uint32_t value) {
    unsigned char raw[4] = {
        (unsigned char)(value & 0xFF),
        (unsigned char)((value >> 8) & 0xFF),
        (unsigned char)((value >> 16) & 0xFF),
        (unsigned char)((value >> 24) & 0xFF),
    };
    return fwrite(raw, 1, sizeof(raw), stdout) == sizeof(raw);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: dspref <dsp1|dsp2|dsp3|dsp4>\n");
        return 2;
    }

    const Chip *chip = find(argv[1]);
    if (chip == NULL) {
        fprintf(stderr, "%s is not a chip this driver carries\n", argv[1]);
        return 2;
    }

    uint32_t exchanges = 0;
    if (!read_u32(&exchanges)) {
        return 1;
    }

    for (uint32_t index = 0; index < exchanges; index++) {
        unsigned char ram[512];
        if (!read_exact(ram, sizeof(ram))) {
            return 1;
        }

        uint32_t steps = 0;
        if (!read_u32(&steps)) {
            return 1;
        }

        chip->reset(ram);

        std::vector<unsigned char> answered;
        for (uint32_t step = 0; step < steps; step++) {
            unsigned char kind = 0;
            unsigned char value = 0;
            if (!read_exact(&kind, 1) || !read_exact(&value, 1)) {
                return 1;
            }
            if (kind == 'w') {
                chip->set((uint8)value, PORT);
            } else {
                answered.push_back((unsigned char)chip->get(PORT));
            }
        }

        if (!write_u32((uint32_t)answered.size())) {
            return 1;
        }
        if (!answered.empty() &&
            fwrite(answered.data(), 1, answered.size(), stdout) != answered.size()) {
            return 1;
        }
    }
    return 0;
}
