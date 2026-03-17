# Frontend Dockerfile
FROM node:20-alpine as build

WORKDIR /app

# Accept build arguments
ARG BACKEND_HOST
ARG BACKEND_PORT
ARG FRONTEND_HOST
ARG FRONTEND_PORT
ARG PRODUCTION

# Copy package files
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Create .env file from build args for Vite (in current directory)
RUN echo "BACKEND_HOST=${BACKEND_HOST}" > .env && \
    echo "BACKEND_PORT=${BACKEND_PORT}" >> .env && \
    echo "FRONTEND_HOST=${FRONTEND_HOST}" >> .env && \
    echo "FRONTEND_PORT=${FRONTEND_PORT}" >> .env && \
    echo "PRODUCTION=${PRODUCTION}" >> .env && \
    echo "=== Build configuration ===" && \
    cat .env && \
    echo "=========================="

# Build with production mode
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
