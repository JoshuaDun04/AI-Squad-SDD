FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Gera conf.d/00-proxy-confiavel.conf a partir de PROXY_CONFIAVEL (lista de redes) ao iniciar
COPY --chmod=755 entrypoint/05-proxy-confiavel.sh /docker-entrypoint.d/05-proxy-confiavel.sh
ENV PROXY_CONFIAVEL=127.0.0.1/32
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
