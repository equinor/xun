FROM python:3.8-buster

RUN apt-get update
RUN apt-get install -y uuid-runtime
RUN apt-get install -y libgl1-mesa-glx

# Wikicloud requirements
RUN python3 -m pip install \
    numpy \
    opencv-python \
    pillow \
    requests \
    wordcloud

# xun
ADD /xun /src/xun
RUN python3 -m pip install /src/xun

RUN mkdir /data
VOLUME /data
WORKDIR /data

ENTRYPOINT \
    celery \
        --app=xun.functions.driver.celery \
        --broker=pyamqp://guest@rabbitmq// \
    worker \
        --loglevel=INFO \
        --concurrency=1 \
        --hostname xun-celery-`uuidgen` \
        --uid=nobody \
        --gid=nogroup
