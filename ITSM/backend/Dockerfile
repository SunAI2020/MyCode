# ITSM 后端镜像：Python 3.13 + FastAPI + uvicorn
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用与迁移
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

# 单 worker（ENABLE_SCHEDULER 需单实例）；横向扩展请关闭调度器另起调度进程
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
