FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    build-essential \
    git \
    curl \
    wget \
    nano \
    vim

RUN python3 -m pip install ollama --break-system-packages

# copy project into container
WORKDIR /workspace
COPY main.py /main.py

RUN mkdir -p life soul play

CMD [ "python3", "-u", "/main.py" ]