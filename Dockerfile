FROM python:3-slim

ENV HOME /home/punjab
ENV PATH=$PATH:/home/punjab:/home/punjab/.local/bin

WORKDIR $HOME

RUN apt-get update \
  && apt-get install -y gcc make libffi-dev libssl-dev\
  && useradd -ms /bin/bash punjab \
  && chown -R punjab:punjab /home/punjab

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

USER punjab

COPY --chown=punjab:punjab . .

RUN uv sync

# Default command

CMD uv run twistd --nodaemon --python=run.py
