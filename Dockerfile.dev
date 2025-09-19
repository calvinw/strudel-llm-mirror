FROM node:24

WORKDIR /app

RUN npm install pnpm --global

COPY pnpm-workspace.yaml ./
COPY package.json pnpm-lock.yaml ./
COPY packages/ ./packages/
COPY examples/ ./examples/
RUN mkdir -p website/public
COPY website/package.json ./website/

RUN pnpm install


COPY . .

EXPOSE 4321

CMD ["pnpm", "dev"]
