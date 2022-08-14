FROM docker.io/freepai/quant:0.1.0

WORKDIR /app

COPY . .

ENTRYPOINT ["python3"]
CMD ["/app/src/main.py", "/app/config.json"]
