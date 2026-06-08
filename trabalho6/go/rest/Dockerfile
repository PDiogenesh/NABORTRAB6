FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go/rest/go.mod ./go.mod
COPY go/rest/main.go ./main.go
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o server .

FROM alpine:latest
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /app/server /server
EXPOSE 8001
CMD ["/server"]
