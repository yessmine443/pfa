# ── Stage 1: Build Angular app ──────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (better cache)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build for production
COPY . .
RUN npx ng build --configuration production

# ── Stage 2: Serve with Nginx ──────────────────────────────────
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built Angular app from build stage
COPY --from=build /app/dist/sparky/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
