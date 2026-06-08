# Trabalho 6 – Comparação de Tecnologias de Invocação de Serviços Remotos

> Implementação e benchmarking de um serviço de catálogo de músicas em **8 variações** — 4 protocolos × 2 linguagens — com testes de carga automatizados via Locust.

---

## Tecnologias

| # | Serviço | Protocolo | Linguagem | Porta | Framework |
|---|---------|-----------|-----------|-------|-----------|
| 1 | `go-rest` | REST / HTTP | Go | 8001 | `net/http` |
| 2 | `go-graphql` | GraphQL | Go | 8002 | `graph-gophers/graphql-go` |
| 3 | `go-grpc` | gRPC | Go | 8003 | `google.golang.org/grpc` |
| 4 | `go-soap` | SOAP 1.1 | Go | 8004 | `encoding/xml` |
| 5 | `python-rest` | REST / HTTP | Python | 8011 | Flask |
| 6 | `python-graphql` | GraphQL | Python | 8012 | Strawberry + Flask |
| 7 | `python-grpc` | gRPC | Python | 8013 | `grpcio` |
| 8 | `python-soap` | SOAP 1.1 | Python | 8014 | Spyne |

Todos os serviços compartilham um único **PostgreSQL** com o mesmo schema e os mesmos dados de seed.

---

## Modelo de Dados

```
users          songs                    playlists
─────────      ──────────────────────   ──────────────────
id             id                       id
name           title                    user_id  → users
email          artist                   name
created_at     album                    created_at
               year
               genre                    playlist_songs
               duration_seconds         ──────────────────
               created_at               playlist_id → playlists
                                        song_id     → songs
```

**Dados de seed:** 300 usuários · 500 músicas · 100 playlists · ~700 relações playlist–música

---

## Estrutura do Repositório

```
trabalho6/
├── docker-compose.yml       ← orquestra os 9 containers (8 serviços + DB)
├── init.sql                 ← schema + dados de seed
├── music.proto              ← contrato gRPC compartilhado
├── run_benchmarks.py        ← runner automatizado de testes + gráficos
│
├── go/
│   ├── rest/    main.go  go.mod  Dockerfile
│   ├── graphql/ main.go  go.mod  Dockerfile
│   ├── grpc/    main.go  go.mod  Dockerfile
│   └── soap/    main.go  go.mod  Dockerfile
│
├── python/
│   ├── rest/    app.py  requirements.txt  Dockerfile
│   ├── graphql/ app.py  requirements.txt  Dockerfile
│   ├── grpc/    app.py  requirements.txt  Dockerfile
│   └── soap/    app.py  requirements.txt  Dockerfile
│
├── locust/
│   ├── locustfile_rest.py
│   ├── locustfile_graphql.py
│   ├── locustfile_grpc.py
│   ├── locustfile_soap.py
│   └── requirements.txt
│
└── results/
    ├── all_results.csv
    ├── chart_rps.png
    ├── chart_p95.png
    └── chart_comparison_lines.png
```

---

## CRUD Implementado

Todos os 8 serviços expõem o conjunto completo de operações para as três entidades:

| Operação | REST | GraphQL | gRPC | SOAP |
|----------|------|---------|------|------|
| Listar todos | `GET /songs` | `query { songs { ... } }` | `ListSongs` | `<ListSongs/>` |
| Buscar por ID | `GET /songs/{id}` | `query { song(id: N) }` | `GetSong` | `<GetSong>` |
| Criar | `POST /songs` | `mutation { create_song(...) }` | `CreateSong` | `<CreateSong>` |
| Atualizar | `PUT /songs/{id}` | `mutation { update_song(...) }` | `UpdateSong` | `<UpdateSong>` |
| Deletar | `DELETE /songs/{id}` | `mutation { delete_song(id: N) }` | `DeleteSong` | `<DeleteSong>` |

Idem para **users** e **playlists** (+ operações `AddSongToPlaylist` / `RemoveSongFromPlaylist`).

---

## Como Executar

### 1. Subir todos os serviços

```bash
cd trabalho6
docker compose up --build -d
```

Aguarde ~2 min na primeira vez (build + espera do PostgreSQL ficar saudável).

### 2. Verificar se estão no ar

```bash
# REST e GraphQL (HTTP GET /health)
curl http://localhost:8001/health   # go-rest
curl http://localhost:8011/health   # python-rest

# gRPC e SOAP — verificar via TCP
nc -zv localhost 8003               # go-grpc
nc -zv localhost 8014               # python-soap
```

### 3. Rodar os testes de carga

```bash
# Na máquina host, com Python instalado:
pip install locust matplotlib pandas requests grpcio grpcio-tools

cd trabalho6
python run_benchmarks.py
```

O script testa os 8 serviços em 3 níveis de carga e salva gráficos e CSV em `results/`.

---

## Exemplos de API

### REST

```bash
# Listar músicas
curl http://localhost:8001/songs

# Buscar música por ID
curl http://localhost:8001/songs/42

# Criar música
curl -X POST http://localhost:8001/songs \
  -H "Content-Type: application/json" \
  -d '{"title":"Bohemian Rhapsody","artist":"Queen","album":"A Night at the Opera","year":1975,"genre":"Rock","duration_seconds":354}'

# Atualizar
curl -X PUT http://localhost:8001/songs/42 \
  -H "Content-Type: application/json" \
  -d '{"genre":"Classic Rock"}'

# Deletar
curl -X DELETE http://localhost:8001/songs/42
```

### GraphQL

```bash
# Query
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ song(id: 1) { id title artist album year genre duration_seconds } }"}'

# Mutation – criar
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { create_song(title:\"Test\", artist:\"Band\", year:2024, duration_seconds:200) { id title } }"}'

# Mutation – atualizar
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { update_song(id:1, genre:\"Jazz\") { id title genre } }"}'
```

### gRPC

```bash
# Usando grpcurl (https://github.com/fullstorydev/grpcurl)
grpcurl -plaintext -proto music.proto \
  -d '{"id": 1}' localhost:8003 music.MusicService/GetSong

grpcurl -plaintext -proto music.proto \
  -d '{"title":"New Song","artist":"Artist","year":2024,"duration_seconds":180}' \
  localhost:8003 music.MusicService/CreateSong
```

### SOAP

```bash
# GetSong (Go SOAP – porta 8004)
curl -X POST http://localhost:8004/soap \
  -H "Content-Type: text/xml; charset=utf-8" \
  -d '<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://music.example.com/soap">
  <soap:Body>
    <tns:GetSong><tns:id>1</tns:id></tns:GetSong>
  </soap:Body>
</soap:Envelope>'
```

---

## Testes de Carga

### Metodologia

- **Ferramenta:** [Locust](https://locust.io/) em modo headless
- **Workload:** leitura intensiva — `GetSong` (5×), `ListSongs` (3×), `GetUser` (3×), `ListUsers` (2×), `GetPlaylist` (3×), `ListPlaylists` (2×), `GetPlaylistSongs` (2×)
- **Protocolos:** REST/GraphQL/SOAP via `HttpUser`; gRPC via cliente nativo `grpc.insecure_channel`

### Níveis de carga

| Nível | Usuários simultâneos | Taxa de spawn | Duração |
|-------|---------------------|---------------|---------|
| Low | 50 | 10/s | 15s |
| Medium | 200 | 20/s | 15s |
| High | 500 | 50/s | 15s |

---

## Resultados

### Throughput – Requisições por segundo (maior = melhor)

![Throughput por nível de carga](results/chart_rps.png)

### Latência p95 em ms (menor = melhor)

![p95 Latency por nível de carga](results/chart_p95.png)

### Evolução com o aumento de concorrência

![Throughput e Latência vs Concorrência](results/chart_comparison_lines.png)

---

### Tabela completa de resultados

| Serviço | RPS (50u) | p95 (50u) | RPS (200u) | p95 (200u) | RPS (500u) | p95 (500u) |
|---------|-----------|-----------|------------|------------|------------|------------|
| go-rest | 141 | 12ms | 434 | 25ms | **635** | 420ms |
| go-grpc | 140 | 25ms | 438 | 51ms | **677** | 510ms |
| go-graphql | 123 | 56ms | 388 | 70ms | 553 | 440ms |
| go-soap | 124 | 56ms | 378 | 95ms | 559 | 490ms |
| python-rest | 137 | 19ms | 424 | 69ms | 444 | 1000ms |
| python-grpc | 138 | 16ms | 397 | 140ms | 426 | 1200ms |
| python-graphql | 119 | 72ms | 375 | 140ms | 394 | 1100ms |
| python-soap | 7 | 7000ms | 7 | 10000ms | 7 | 12000ms |

---

## Análise e Conclusões

### Go supera Python em todos os protocolos

Go compila para binário nativo e usa goroutines de custo baixíssimo para atender requisições concorrentes. Python possui o GIL (*Global Interpreter Lock*), que limita o paralelismo real mesmo com múltiplas threads. Isso se reflete em ~35% mais throughput e latência 2–3× menor nos serviços Go.

### REST apresenta a melhor eficiência por protocolo

REST com JSON tem o menor overhead de serialização entre os protocolos testados. GraphQL e SOAP realizam parsing mais pesado (AST de query vs. XML envelope), enquanto gRPC adiciona negociação HTTP/2 e serialização protobuf — trade-offs que só compensam em cenários de contratos ricos ou payloads muito grandes.

### gRPC se destaca em Go; fica atrás em Python

`go-grpc` atingiu **677 RPS** (o maior entre todos a 500 usuários). O runtime de Go aproveita bem o multiplexing HTTP/2. Já `python-grpc` sofre com o GIL no processamento dos frames, ficando abaixo do `python-rest`.

### python-soap — gargalo arquitetural por design

O Spyne em modo `wsgiref.simple_server` é **single-threaded**: uma requisição bloqueia completamente as demais. Resultado: ~7 RPS independente da carga (vs. ~559 RPS do `go-soap`). Em produção, seria necessário um servidor WSGI multi-worker (Gunicorn/uWSGI), o que eliminaria o gargalo. O `go-soap` usa goroutines e não tem esse problema.

### Ranking final (500 usuários simultâneos)

```
🥇  go-grpc        677 RPS   p95 =  510ms
🥈  go-rest        635 RPS   p95 =  420ms
🥉  go-soap        559 RPS   p95 =  490ms
4   go-graphql     553 RPS   p95 =  440ms
5   python-rest    444 RPS   p95 = 1000ms
6   python-grpc    426 RPS   p95 = 1200ms
7   python-graphql 394 RPS   p95 = 1100ms
⚠   python-soap      7 RPS   p95 = 12000ms  ← server single-threaded
```

---

## Dependências

- Docker + Docker Compose
- Python 3.10+ (para rodar `run_benchmarks.py` no host)
- `pip install locust matplotlib pandas requests grpcio grpcio-tools`
