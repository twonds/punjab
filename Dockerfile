FROM python:3-slim

ENV HOME /home/punjab
ENV PATH=$PATH:/home/punjab:/home/punjab/.local/bin

WORKDIR $HOME

RUN apt-get update \
  && apt-get install -y gcc make libffi-dev libssl-dev\
  && useradd -ms /bin/bash punjab \
  && chown -R punjab:punjab /home/punjab


USER punjab

COPY --chown=punjab:punjab *.* ./

COPY --chown=punjab:punjab . .


RUN pip install --user -U -r requirements.txt
RUN python setup.py install --force --user

# Default command

CMD twistd --nodaemon --python=run.py
