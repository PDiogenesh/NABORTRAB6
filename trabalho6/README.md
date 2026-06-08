# Trabalho 6 – Comparação de Tecnologias de Invocação de Serviços Remotos

Sistema de streaming de música implementado em **8 versões** (4 tecnologias × 2 linguagens), com testes de carga automatizados.

## Arquitetura

| Serviço           | Tecnologia | Linguagem | Porta |
|-------------------|-----------|-----------|-------|
| `go-rest`         | REST       | Go        | 8001  |
| `go-graphql`      | GraphQL    | Go        | 8002  |
| `go-grpc`         | gRPC       | Go        | 8003  |
| `go-soap`         | SOAP       | Go        | 8004  |
| `python-rest`     | REST       | Python    | 8011  |
| `python-graphql`  | GraphQL    | Python    | 8012  |
| `python-grpc`     | gRPC       | Python    | 8013  |
| `python-soap`     | SOAP       | Python    | 8014  |

Todos os serviços compartilham um único PostgreSQL com:
- **300 usuários**
- **500 músicas** (nome, artista, álbum, ano, gênero, duração)
- **100 playlists** (cada uma com ~7 músicas)

## Estrutura de Diretórios

```
trabalho6/
├── docker-compose.yml
├── init.sql               ← schema + dados de seed
├── music.proto            ← contrato gRPC compartilhado
├── run_benchmarks.py      ← runner automatizado de testes + gráficos
├── go/
│   ├── rest/    (main.go, go.mod, Dockerfile)
│   ├── graphql/ (main.go, go.mod, Dockerfile)
│   ├── grpc/    (main.go, go.mod, Dockerfile)
│   └── soap/    (main.go, go.mod, Dockerfile)
├── python/
│   ├── rest/    (app.py, requirements.txt, Dockerfile)
│   ├── graphql/ (app.py, requirements.txt, Dockerfile)
│   ├── grpc/    (app.py, requirements.txt, Dockerfile)
│   └── soap/    (app.py, requirements.txt, Dockerfile)
└── locust/
    ├── locustfile_rest.py
    ├── locustfile_graphql.py
    ├── locustfile_soap.py
    ├── locustfile_grpc.py
    ├── requirements.txt
    └── Dockerfile
```

## Como Executar

### 1. Subir todos os serviços

```bash
cd trabalho6
docker compose up --build -d
```

Aguarde todos os containers ficarem saudáveis (≈ 2–3 min na primeira vez).

### 2. Verificar saúde dos serviços REST/GraphQL/SOAP

```bash
curl http://localhost:8001/health   # Go REST
curl http://localhost:8002/health   # Go GraphQL  (endpoint: /graphql)
curl http://localhost:8004/health   # Go SOAP
curl http://localhost:8011/health   # Python REST
curl http://localhost:8012/health   # Python GraphQL
curl http://localhost:8014/health   # Python SOAP (porta /soap)
```

### 3. Executar testes de carga automatizados

Na máquina host (com Python e locust instalados):

```bash
pip install locust matplotlib pandas requests
python run_benchmarks.py
```

Isso rodará 3 níveis de carga (50, 200, 500 usuários) em cada serviço e salvará gráficos em `./results/`.

### 4. Testes manuais via Locust UI

```bash
# REST Go
docker compose --profile locust run --rm locust \
  -f /locust/locustfile_rest.py --host http://go-rest:8001

# GraphQL Python
docker compose --profile locust run --rm locust \
  -f /locust/locustfile_graphql.py --host http://python-graphql:8012
```

Acesse `http://localhost:8089` para a interface do Locust.

## CRUD – Exemplos de uso

### REST (Go/Python)

```bash
# Listar músicas
curl http://localhost:8001/songs

# Buscar música
curl http://localhost:8001/songs/42

# Criar música
curl -X POST http://localhost:8001/songs \
  -H "Content-Type: application/json" \
  -d '{"title":"Stairway to Heaven","artist":"Led Zeppelin","album":"Led Zeppelin IV","year":1971,"genre":"Rock","duration_seconds":482}'

# Atualizar
curl -X PUT http://localhost:8001/songs/42 \
  -H "Content-Type: application/json" \
  -d '{"title":"Stairway to Heaven (Remaster)"}'

# Deletar
curl -X DELETE http://localhost:8001/songs/42
```

### GraphQL (Go/Python)

```bash
# Query
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ song(id: 1) { id title artist album year genre } }"}'

# Mutation
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { create_song(title:\"Test\",artist:\"Band\") { id title } }"}'
```

### SOAP (Go)

```bash
curl -X POST http://localhost:8004/soap \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body><GetSong><id>1</id></GetSong></soap:Body>
</soap:Envelope>'
```

### gRPC (Go/Python) – via grpcurl

```bash
# Instalar grpcurl: https://github.com/fullstorydev/grpcurl
grpcurl -plaintext -proto music.proto \
  -d '{"id": 1}' localhost:8003 music.MusicService/GetSong
```

## Níveis de Carga

| Nível  | Usuários | Spawn rate | Duração |
|--------|----------|-----------|---------|
| Baixo  | 50       | 10/s      | 60s     |
| Médio  | 200      | 20/s      | 60s     |
| Alto   | 500      | 50/s      | 60s     |

Os resultados são salvos em `results/` como CSV e PNG.
