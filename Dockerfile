# Ruteo en un contenedor: la app compilada y el backend (gateway + optimizador) en una sola imagen.
# docker build -t ruteo . && docker run -p 8000:8000 --env-file backend/.env -v ruteo-datos:/datos ruteo
# Necesita GOOGLE_CLIENT_ID (login con Google) o, solo para probar en un equipo propio, SIN_LOGIN=1.

FROM node:22-slim AS app
WORKDIR /ruteo/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# La app llama a la API en la misma dirección que la sirve
RUN REACT_APP_API_URL=/api npm run build

FROM python:3.12-slim
WORKDIR /ruteo
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY servidor.sh ./
COPY --from=app /ruteo/frontend/build frontend/build
# Lo que se edita o se aprende en la app va en /datos: móntalo como volumen para no perderlo
ENV ASIGNACION_CONFIG_PATH=/datos/asignacion.json \
    RESULTADOS_PATH=/datos/sugerencias.json \
    GEOCACHE_PATH=/datos/geocache.json \
    PYTHON=python \
    PORT=8000 \
    TZ=America/Bogota \
    ALLOWED_HOSTS='["*"]'
VOLUME /datos
EXPOSE 8000
CMD ["./servidor.sh"]
