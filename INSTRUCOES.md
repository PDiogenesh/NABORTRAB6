# Instruções de Execução e Teste - Trabalho 2

Este documento descreve como iniciar, configurar e testar o ambiente de múltiplas instâncias do WordPress balanceadas pelo Nginx.

## Requisitos
* Docker instalado na máquina.
* Docker Compose instalado (geralmente integrado com o Docker Desktop no Windows).

## Como Executar

1. **Subir os Contêineres:**
   No terminal, navegue até a pasta do projeto e execute o comando abaixo para iniciar todos os 5 contêineres em segundo plano:
   ```bash
   docker compose up -d
   ```

2. **Configuração Inicial do WordPress:**
   * Abra o navegador e acesse: `http://localhost/` (ou `http://127.0.0.1/`).
   * Você verá a tela de instalação clássica do WordPress. Isso é servido pelo Nginx que está balanceando e roteando as requisições para as instâncias do WordPress.
   * Conclua a instalação fornecendo o título do site, usuário administrador, senha e e-mail.
   * Como as três instâncias compartilham a mesma pasta no host (`./wordpress`) e se conectam ao mesmo banco de dados MySQL, qualquer alteração ou upload feito em qualquer uma das instâncias será refletido nas outras.

## Como Testar o Balanceamento de Carga

Depois de iniciar os contêineres, você pode comprovar que o Nginx está realizando o balanceamento de carga entre os três servidores de WordPress por meio do cabeçalho customizado `X-Upstream`.

1. Execute o seguinte comando no terminal (ou PowerShell) algumas vezes consecutivas:
   ```bash
   curl -I http://localhost/
   ```

2. Observe o cabeçalho `X-Upstream` na resposta HTTP. Ele deverá assumir três possíveis endereços IP diferentes, que representam os endereços IPs internos dos contêineres do WordPress (`wordpress1`, `wordpress2`, `wordpress3`) na rede interna do Docker.
   Exemplo de resposta:
   ```http
   HTTP/1.1 200 OK
   Server: nginx/1.19.0
   ...
   X-Upstream: 172.19.0.3:80
   ```

3. Você também pode verificar essa rotação abrindo a página no navegador, abrindo a ferramenta de desenvolvedor (F12), indo na aba **Rede (Network)**, recarregando a página e verificando o cabeçalho HTTP da resposta para a requisição principal.

## Comandos Úteis

* **Verificar o status dos contêineres:**
  ```bash
  docker compose ps
  ```

* **Visualizar logs das instâncias em tempo real:**
  ```bash
  docker compose logs -f
  ```

* **Parar os contêineres (mantendo os dados):**
  ```bash
  docker compose down
  ```

* **Parar os contêineres e remover os volumes (limpar dados):**
  ```bash
  docker compose down -v
  ```
