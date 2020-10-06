build: xun-worker volumes
	docker-compose build
	touch build

.PHONY: volumes
volumes:
	make -C volumes

.PHONY: xun-worker
xun-worker:
	make -C xun-worker

run: build
	docker-compose up --scale xun-worker=4

rebuild-workers: xun-worker
	docker-compose up -d --build --scale xun-worker=4 xun-worker
