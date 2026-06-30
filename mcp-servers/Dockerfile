FROM node:20-slim

WORKDIR /app

# Copy dependency manifests first (layer caching)
COPY package.json tsconfig.json ./
RUN npm install

# Copy all server source code
COPY . .
RUN npm run build

# Each MCP server is started by overriding CMD in the K8s deployment.
# Default: start the Azure Tools MCP server on port 3004.
EXPOSE 3000 3001 3002 3003 3004

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD node -e "const http = require('http'); http.get('http://localhost:' + (process.env.PORT || '3004') + '/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); }).on('error', () => process.exit(1));" || exit 1

CMD ["npm", "run", "start:azure-tools"]
