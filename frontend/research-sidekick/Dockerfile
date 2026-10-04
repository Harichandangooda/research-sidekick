FROM node:22.16.0-alpine AS build
WORKDIR /app
COPY frontend/research-sidekick/package*.json ./
RUN npm ci
COPY frontend/research-sidekick/ ./
ARG REACT_APP_API_BASE_URL=/api
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
RUN npm run build

FROM nginx:1.28.0-alpine
COPY frontend/research-sidekick/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
