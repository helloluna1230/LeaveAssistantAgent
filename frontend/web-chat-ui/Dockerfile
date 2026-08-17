# Multi-stage: build the Vite site, then serve it + BFF proxy with Python.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY bff-requirements.txt .
RUN pip install --no-cache-dir -r bff-requirements.txt
COPY bff.py .
COPY --from=build /app/dist ./dist
ENV PORT=8080 STATIC_DIR=dist
EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn bff:app --host 0.0.0.0 --port ${PORT}"]
