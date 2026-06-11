# ── Stage 1: generate protobuf code ──────────────────────────
FROM golang:1.21-alpine AS proto-gen

RUN apk add --no-cache protobuf protobuf-dev git

RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.31.0 && \
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0

WORKDIR /build
COPY music.proto .
# Output the generated files into musicpb/ directory, using "paths=source_relative"
RUN mkdir -p musicpb && \
    protoc \
      --go_out=musicpb \
      --go_opt=paths=source_relative \
      --go-grpc_out=musicpb \
      --go-grpc_opt=paths=source_relative \
      music.proto

# ── Stage 2: build binary ─────────────────────────────────────
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go/grpc/go.mod ./go.mod
COPY go/grpc/main.go ./main.go
COPY --from=proto-gen /build/musicpb ./musicpb

RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o server .

# ── Stage 3: minimal runtime ──────────────────────────────────
FROM alpine:latest
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /app/server /server
EXPOSE 8003
CMD ["/server"]
