FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
# 国内构建走 npmmirror（lock 里的 resolved URL 指向 npmjs 官方源，需一并替换），可用 --build-arg NPM_REGISTRY 覆盖
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN sed -i "s|https://registry.npmjs.org|${NPM_REGISTRY}|g" package-lock.json \
    && npm ci --registry=${NPM_REGISTRY}
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev:h5", "--", "--host", "0.0.0.0"]
