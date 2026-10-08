FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
# A imagem aplica envsubst em /etc/nginx/templates/*.template ao iniciar
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template
ENV PROXY_CONFIAVEL=127.0.0.1/32 NGINX_ENVSUBST_FILTER=^PROXY_CONFIAVEL$
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
