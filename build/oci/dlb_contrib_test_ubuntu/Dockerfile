# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2022 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Build the image (in the root of this repository):
#
#   podman build -t ghcr.io/dlu-ch/dlb_contrib_test_ubuntu .
#
# Use the image (in the root of the repository of 'dlb':
#
#   podman run -it -v=.:/home/tester/dlb --cap-add SYS_PTRACE ghcr.io/dlu-ch/dlb_contrib_test_ubuntu

# https://hub.docker.com/_/ubuntu
# approx. 80 MB (05.07.2022)
FROM --platform=linux/amd64 docker.io/library/ubuntu:rolling
LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:rolling"

ENV OCI_IMAGE_TITLE="dlb_contrib_test_ubuntu"
LABEL org.opencontainers.image.title="${OCI_IMAGE_TITLE}"

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        dash \
        coreutils \
        binutils \
        gcc \
        g++ \
        libc6-dev \
        make \
        strace \
        doxygen \
        python2-minimal \
        python3 \
        git \
        pkg-config \
        texlive-binaries \
        texlive-base \
        texlive-latex-base

# approx. 822 MB so far (05.07.2022)

RUN apt-get install --no-install-recommends --yes \
        ca-certificates \
        curl \
        lbzip2
COPY install-doxypress.bash /tmp
RUN /tmp/install-doxypress.bash && rm /tmp/install-doxypress.bash

RUN useradd --create-home --shell /bin/bash --uid 1001 tester
WORKDIR /home/tester
COPY Dockerfile Dockerfile
USER tester
