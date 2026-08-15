# Dockerfile：把项目打包成 Docker 镜像
#
# 构建镜像:   docker build -t ai-agent-test-platform .
# 运行容器:   docker run -p 8000:8000 --env-file .env ai-agent-test-platform
# 访问:       http://localhost:8000

# ---- 第 1 层：基础镜像 ----
# 用官方 Python 3.13 slim 版（比完整版小很多，够用）
FROM python:3.13-slim

# ---- 第 2 层：工作目录 ----
# 容器内的项目目录，后续指令都在这个目录下执行
WORKDIR /app

# ---- 第 3 层：安装依赖 ----
# 先只复制 requirements.txt，利用 Docker 的层缓存
# 只要 requirements.txt 没变，这层就缓存命中，不用重新下载依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 第 4 层：复制项目代码 ----
# 把所有代码复制进镜像（.dockerignore 排除了 .env、.venv 等）
COPY . .

# ---- 第 5 层：暴露端口 ----
# 声明容器监听 8000 端口（文档性质，还需要 docker run -p 映射）
EXPOSE 8000

# ---- 第 6 层：启动命令 ----
# 容器启动时运行 uvicorn 启动 Web 服务
# host=0.0.0.0 确保容器外部能访问（不能只监听 127.0.0.1）
CMD ["uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
