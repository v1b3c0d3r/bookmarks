FROM ubuntu:24.04

WORKDIR /

RUN apt update && apt upgrade -y && apt install -y python3-pip
ADD requirements.txt requirements.txt
RUN pip3 install -r requirements.txt --break-system-packages

COPY static /static
COPY main.py main.py

EXPOSE 8000
VOLUME ["/data"]

ENTRYPOINT ["python3", "main.py"]

