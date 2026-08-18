FROM debian:bookworm-slim AS build

ARG SNES9X_REF=1.63
ARG DSP2_SHA256=

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth=1 --branch "${SNES9X_REF}" \
        https://github.com/snes9xgit/snes9x.git /src/snes9x

WORKDIR /ref

RUN cp /src/snes9x/dsp2.cpp /ref/ \
    && sha256sum /ref/dsp2.cpp

COPY port.h snes9x.h memmap.h driver.cpp /ref/

RUN g++ -O2 -Wall -Wextra -I/ref -o /ref/dsp2ref /ref/driver.cpp /ref/dsp2.cpp

FROM debian:bookworm-slim

COPY --from=build /ref/dsp2ref /usr/local/bin/dsp2ref

RUN useradd --create-home --uid 1000 builder
USER builder
WORKDIR /work

ENTRYPOINT ["dsp2ref"]
