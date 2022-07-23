FROM python:3.7-alpine
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

CMD ["/usr/local/bin/python","src/main.py","config.json"]

