FROM continuumio/miniconda3:4.10.3
MAINTAINER Mingxun Wang "mwang87@gmail.com"

RUN apt-get update && apt-get install -y build-essential

COPY requirements.txt .
RUN pip install -r requirements.txt

# Installing mamba
RUN conda install -c conda-forge mamba

# installing nextflow
RUN mamba install -c bioconda nextflow

COPY . /app
WORKDIR /app
