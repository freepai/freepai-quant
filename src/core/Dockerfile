FROM python:3.7

# Install dependencies
RUN python -m pip install --upgrade pip

WORKDIR /opt/nextquant

COPY . .

# Install next quant
RUN pip install .