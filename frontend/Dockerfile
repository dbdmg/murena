# Stage 1: Build dell'applicazione React
FROM node:20-alpine AS builder

WORKDIR /app

# Copia i file di dipendenze
COPY package.json package-lock.json ./
RUN npm ci

# Copia il codice sorgente
COPY . .

# Build Arguments
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Compila per la produzione (crea la cartella /dist)
RUN npm run build

# Stage 2: Serve con Nginx
FROM nginx:alpine

# Copia la configurazione custom di Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia i file compilati dallo stage precedente
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
