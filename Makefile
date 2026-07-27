.DEFAULT_GOAL := dev

.PHONY: dev
dev: node_modules/.package-lock.json
	npm run dev

node_modules/.package-lock.json: package-lock.json
	npm ci
