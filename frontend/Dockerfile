FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install
COPY . .
RUN yarn build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app ./
EXPOSE 3000
CMD ["yarn", "start"]
