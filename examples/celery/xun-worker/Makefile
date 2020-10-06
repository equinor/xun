all: xun

# We copy the xun repository into the container. This requires us to have a
# copy of the repository relative to the Dockerfile.
SRC_PATH := $(shell git rev-parse --show-toplevel)

.PHONY: xun
xun:
	rsync -auv --delete --filter=':- .gitignore' $(SRC_PATH) .
