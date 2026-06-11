FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go/soap/go.mod ./go.mod
COPY go/soap/main.go ./main.go
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o server .

FROM alpine:latest
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /app/server /server
EXPOSE 8004
CMD ["/server"]
