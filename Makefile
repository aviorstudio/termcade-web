.DEFAULT_GOAL := help
.PHONY: help install lint test build check dev stop clean
BUN ?= bun
help:
	@echo 'make check    Install frozen dependencies, type-check, build and check static output'
	@echo 'make dev      Start the foreground Astro development server'
install:
	$(BUN) install --frozen-lockfile
lint:
	@echo "lint: unsupported: no source lint or type-check gate is configured"
build: install
	$(BUN) run build
test:
	bash scripts/test-site.sh
check: build
	$(MAKE) test
dev:
	$(BUN) run dev
stop:
	@echo 'stop: unsupported: press Ctrl-C in the foreground dev terminal'
clean:
	$(BUN) -e 'const fs = require("node:fs"); for (const path of ["dist", ".astro"]) fs.rmSync(path, { recursive: true, force: true });'
