FROM python:3.11-slim

WORKDIR /app
COPY dist ./dist
COPY server.py ./

ENV DASHBOARD_PORT=80
ENV DASHBOARD_BACKEND_URL=http://football-data-mcp:8910

EXPOSE 80
CMD ["python", "server.py"]
