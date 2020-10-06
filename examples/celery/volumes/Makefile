all: rabbitmq redis xun-worker

# Ensures the existance of folders used for volumes in the containers.

rabbitmq:
	mkdir -p rabbitmq/data
	mkdir -p rabbitmq/etc
	mkdir -p rabbitmq/logs

redis:
	mkdir -p redis/data
	mkdir -p redis/etc

xun-worker:
	mkdir -p xun-worker/data
