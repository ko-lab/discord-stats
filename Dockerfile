FROM ghcr.io/astral-sh/uv:debian

RUN mkdir -p /app/static
ADD pyproject.toml uv.lock crawl.py report.py /app/
WORKDIR /app
RUN uv sync

EXPOSE 8000
CMD ["uv", "run", "streamlit", "run", "--browser.gatherUsageStats", "false", "--server.address", "0.0.0.0", "--server.port", "8000", "./report.py"]
