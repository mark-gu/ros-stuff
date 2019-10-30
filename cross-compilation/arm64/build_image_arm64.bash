#!/bin/bash

install_docker() {
  apt-get remove docker docker-engine docker.io
  apt-get update
  apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common

  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

  apt-key fingerprint 0EBFCD88

  sudo add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) \
  stable"

  apt-get update
  apt-get install -y docker-ce
}

build_qemu() {
  # Install dependencies
  apt-get update
  apt-get install -y binfmt-support git libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev

  # Make build and download directories
  mkdir -p "$WORK_DIR/qemu/build"
  mkdir -p "$WORK_DIR/qemu/download"
  mkdir -p "$WORK_DIR/qemu/src"

  # Download and extract qemu
  QEMU_VERSION=3.0.0
  wget "https://download.qemu.org/qemu-$QEMU_VERSION.tar.xz" -P "$WORK_DIR/qemu/download"
  tar -xf "$WORK_DIR/qemu/download/qemu-$QEMU_VERSION.tar.xz" -C "$WORK_DIR/qemu/src" --strip 1

  # Build qemu
  cd "$WORK_DIR/qemu/build"
  ../src/configure --static --enable-user --disable-system --target-list=aarch64-linux-user
  make -j4

  # Set kernel to redirect AARCH64 executables to qemu
  echo "package qemu-aarch64-static
interpreter /usr/bin/qemu-aarch64-static
magic \x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xb7\x00
mask \xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff
credential no" > /usr/share/binfmts/qemu-aarch64-static

  update-binfmts --importdir /usr/share/binfmts --import qemu-aarch64-static
  cp "$WORK_DIR/qemu/build/aarch64-linux-user/qemu-aarch64" "$WORK_DIR/qemu-aarch64-static"

  # Clean up the build files
  rm -rf "$WORK_DIR/qemu"
}

set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root"
  exit 1
fi

WORK_DIR=$(pwd)

if [ ! -f "$WORK_DIR/Dockerfile.xenial" ]; then
  echo "Must be run in the same folder as a Dockerfile"
  exit 1
fi

if [ ! -x "$(command -v docker)" ]; then
  echo "Docker is not installed. Installing..."
  install_docker
fi

if [ ! -f "$WORK_DIR/qemu-aarch64-static" ]; then
  echo "Building qemu..."
  build_qemu $WORK_DIR
fi

# Build the Docker image
UBUNTU_VERSION=`lsb_release -cs`
if [ $UBUNTU_VERSION = 'xenial' ]; then
  ROS_VERSION="kinetic"
else
  ROS_VERSION="melodic"
fi

docker build -t ros-cross-compile:arm64 --build-arg ROS_VERSION=${ROS_VERSION} --build-arg UBUNTU_VERSION=${UBUNTU_VERSION} -f ${WORK_DIR}/Dockerfile.${UBUNTU_VERSION} "${WORK_DIR}"
