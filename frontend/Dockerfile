# Build stage
# Node must satisfy Angular 22's engine constraint: ^22.22.3 || ^24.15.0 || >=26.
# node:18-alpine fails the build with "The Angular CLI requires a minimum Node.js
# version of v22.22.3 or v24.15.0 or v26.0.0."
FROM node:24-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies. `npm ci` installs exactly what package-lock.json pins, instead of
# re-resolving like `npm install` does — the image then matches what was tested locally.
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built application
COPY --from=builder /app/dist/release-notes-agent/browser /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]