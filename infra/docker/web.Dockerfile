FROM node:24-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN pnpm install --filter @project-assistant/web...
COPY apps/web apps/web
COPY packages/api-client packages/api-client
ARG VITE_API_URL=/api/v1
ARG VITE_AUTH_MODE=local
ENV VITE_API_URL=$VITE_API_URL VITE_AUTH_MODE=$VITE_AUTH_MODE
RUN pnpm --filter @project-assistant/web build

FROM nginx:1.29-alpine
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
