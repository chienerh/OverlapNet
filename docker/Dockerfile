FROM tensorflow/tensorflow:2.4.1-gpu

RUN pip install keras

RUN pip install -U scikit-learn

RUN pip install -U matplotlib

RUN pip install tqdm

USER root
RUN apt-get update \
    && apt-get install -y vim \
    && apt-get install git
