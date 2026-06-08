# Etapa 1: build de la app
FROM node:18 AS build

# Definir directorio de trabajo
WORKDIR /app

# Copiar package.json y package-lock.json
COPY package*.json ./

# Instalar dependencias
RUN npm install

# Copiar el resto del código
COPY . .

# Construir la aplicación
RUN npm run build

# Etapa 2: servidor web
FROM nginx:alpine

# Copiar el build de React al servidor nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copiar configuración de Nginx (opcional si quieres manejar rutas)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer el puerto
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]