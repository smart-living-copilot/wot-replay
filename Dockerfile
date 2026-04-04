FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY providers/ providers/
COPY td_generator.py replay_server.py cli.py ./

EXPOSE 9000

CMD ["python", "cli.py", "serve"]
