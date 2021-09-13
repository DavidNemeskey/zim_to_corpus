# Using the oldest working release so that we are compatible with as many
# releases as possible (compiling on a newer release would make us end up
# with glibc tokens that don't exist on older releases)
FROM ubuntu:18.10

# To make sure tzdata (or other packages) don't ask questions
# See https://serverfault.com/questions/949991/
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Budapest

# This is only needed for unsupported releases, such as 18.10
RUN cat /etc/apt/sources.list | sed -e "s/archive/old-releases/" -e "s/security/old-releases/" > xxx && mv xxx /etc/apt/sources.list
RUN apt update

# Install git so that we can obtain libzim
RUN apt install -y git
# Build tools
RUN apt install -y build-essential meson pkg-config
# libzim dependencies
RUN apt install -y liblzma-dev libicu-dev libzstd-dev uuid-dev
# zim_to_dir dependencies
RUN apt install -y zlib1g-dev

# Clone the repositories we need
RUN git clone --depth 1 --branch 6.3.2 https://github.com/openzim/libzim.git
RUN git clone --depth 1 --branch docker --recursive https://github.com/DavidNemeskey/zim_to_corpus.git

# Compile and install libzim
WORKDIR "/libzim"
RUN meson . build -Dwith_xapian=false --default-library=static
RUN ninja -C build
RUN ninja -C build install

# Compile zim_to_dir
WORKDIR "/zim_to_corpus/src"
RUN make
RUN cp zim_to_dir /

ENTRYPOINT ["/zim_to_dir"]
