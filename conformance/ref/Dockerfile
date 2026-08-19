FROM debian:bookworm-slim AS build

ARG SNES9X_REF=1.63

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth=1 --branch "${SNES9X_REF}" \
        https://github.com/snes9xgit/snes9x.git /src/snes9x

WORKDIR /ref

RUN cp /src/snes9x/dsp.h /src/snes9x/dsp1.cpp /src/snes9x/dsp2.cpp \
        /src/snes9x/dsp3.cpp /src/snes9x/dsp4.cpp /ref/ \
    && sha256sum /ref/dsp.h /ref/dsp1.cpp /ref/dsp2.cpp /ref/dsp3.cpp /ref/dsp4.cpp

COPY port.h snes9x.h memmap.h driver.cpp /ref/

RUN g++ -O2 -w -I/ref -o /ref/dspref \
        /ref/driver.cpp /ref/dsp1.cpp /ref/dsp2.cpp /ref/dsp3.cpp /ref/dsp4.cpp

FROM debian:bookworm-slim

COPY --from=build /ref/dspref /usr/local/bin/dspref

RUN useradd --create-home --uid 1000 builder
USER builder
WORKDIR /work

ENTRYPOINT ["dspref"]
