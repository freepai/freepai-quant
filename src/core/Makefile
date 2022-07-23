install:
	pip install -r requirements.txt

build:
	docker build -t registry.us-west-1.aliyuncs.com/nextquant/quant:0.1.0 .

run:
	docker run -it --rm -p 8080:8080 registry.us-west-1.aliyuncs.com/nextquant/quant:0.1.0
