FROM node:20-alpine AS build

WORKDIR /frontend
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.25-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html

EXPOSE 80
