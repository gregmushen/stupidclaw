FROM python:3.11-slim

WORKDIR /opt/tgbot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt/tgbot

ENV PYTHONPATH=/opt

CMD ["python", "-m", "tgbot.bot"]
