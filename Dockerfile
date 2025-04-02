FROM ubuntu:22.04
LABEL maintainer="Mingxun Wang mwang87@gmail.com"

RUN apt-get update && apt-get install -y build-essential libarchive-dev wget vim unzip zip curl

# Install Mamba
ENV CONDA_DIR /opt/conda
RUN wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O ~/miniforge.sh && /bin/bash ~/miniforge.sh -b -p /opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH

# Adding to bashrc
RUN echo "export PATH=$CONDA_DIR:$PATH" >> ~/.bashrc

# Set default Python version via Conda
RUN mamba install -n base python=3.10

# Install Java
RUN apt-get update && \
    apt-get install -y openjdk-21-jdk && \
    apt-get install -y ant && \
    apt-get clean;

# installing nextflow
ENV NXF_VER=24.10.3
RUN wget -qO- https://github.com/nextflow-io/nextflow/releases/download/v$NXF_VER/nextflow-$NXF_VER-dist | bash && chmod +x nextflow && mv nextflow /usr/local/bin

COPY requirements.txt .
COPY conda_env.yml .
# Required of numba, but 
RUN mamba env update -f conda_env.yml -n base 

COPY . /app
WORKDIR /app
