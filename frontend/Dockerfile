# syntax=docker/dockerfile:1

# --- Development: Vite dev server with HMR -------------------------------
FROM node:22-alpine AS dev
# UID/GID match the host user so that files npm writes into the bind-mounted
# source (package-lock.json, caches) stay owned correctly on the host.
ARG UID=1000
ARG GID=1000
ENV HOME=/home/app
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund || npm install --legacy-peer-deps --no-audit --no-fund
COPY . .
RUN mkdir -p "$HOME" && chown "$UID:$GID" "$HOME"
USER $UID:$GID
EXPOSE 5173
CMD ["npm", "run", "dev"]

# --- Build: static assets -------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund || npm install --legacy-peer-deps --no-audit --no-fund
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Production: static assets behind nginx -------------------------------
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
