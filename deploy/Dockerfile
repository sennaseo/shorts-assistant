# 빌드 컨텍스트는 리포 루트: docker build -f deploy/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIPELINE_HOST=0.0.0.0 PIPELINE_PORT=8787

# ffmpeg: moviepy 렌더링 · fonts-nanum: 자막 한글 (video_renderer 가 /usr/share/fonts/truetype/nanum 을 찾는다)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline_server.py pipeline_ui.html image_ui.html ./
COPY modules/ modules/
COPY assets/ assets/

RUN useradd --create-home --uid 1000 app && mkdir -p /app/outputs && chown -R app:app /app
USER app

EXPOSE 8787
CMD ["python", "pipeline_server.py"]
