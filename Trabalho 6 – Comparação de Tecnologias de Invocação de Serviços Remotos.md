# Comparação de Tecnologias de

# Invocação de Serviços Remotos

## Computação Distribuída

## Prof. Nabor C. Mendonça


## Introdução

Serviços remotos são serviços de software expostos por meio da Internet, os
quais podem ser acessados via mecanismos de invocação remota. Serviços web,
em particular, que são serviços remotos acessados via protocolos padrão da web,
se tornaram extremamente populares nos últimos anos, por permitirem a
comunicação entre programas independentemente de plataforma de execução e
linguagem de programação.

Entre as tecnologias de invocação de serviços remotas mais utilizadas estão
**SOAP** [1], **REST** [2][3], **GraphQL** [4] e **gRPC** [5]. Por atenderem requisitos muito
similares, essas tecnologias podem, em muitas situações, ser utilizadas como
alternativas umas às outras, o que torna a escolha por uma delas uma importante
questão no projeto da arquitetura de aplicações distribuídas [6][7].


## Instruções

Organizados em grupos de 2-3 alunos, vocês deverão:

1. Pesquisar na Internet sobre a **origem** , **principais características** , e
    **vantagens e desvantagens** de cada uma dessas quatro tecnologias.
2. Comparar e ilustrar as principais similaridades e diferenças entre essas
    tecnologias por meio da especificação e implementação de **um serviço de**
    **streaming de músicas** utilizando cada uma das tecnologias.
3. Realizar **testes de carga** comparando as diferentes tecnologias, sob
    diferentes cargas de trabalho.


## Entregável

Apresentação de slides **,** compartilhada no Google Drive, contendo:

1. Identificação dos membros de cada equipe.
2. Descrição da origem, características, e vantagens e desvantagens de cada
    tecnologia de invocação remota, incluindo exemplos de código em um
    mesma linguagem de programação, a ser escolhida pela equipe
3. Análise crítica das quatro tecnologias tendo como base a experiência de
    cada equipe na implementação do serviço de streaming de músicas na
    linguagem escolhida e os resultados dos testes de carga.
4. Gráficos ilustrando os resultados dos testes de carga.


## Serviço de Streaming de Músicas

O serviço a ser implementado deve permitir o gerenciamento (criação, consulta,
alteração, e remoção) de três tipos de recursos: **usuários** , **músicas** , e **playlists** ,
os quais devem estar relacionados de acordo com o diagrama abaixo:


## Serviço de Streaming de Músicas

Seguem alguns exemplos de consultas que as aplicações clientes do serviço de
streaming de músicas deverão poder realizar a partir da invocação das operações
oferecidas pelo serviço:

```
● Listar os dados de todos os usuários do serviço
● Listar os dados de todas as músicas mantidas pelo serviço
● Listar os dados de todas as playlists de um determinado usuário
● Listar os dados de todas as músicas de uma determinada playlist
● Listar os dados de todas as playlists que contêm uma determinada música
```

## Referências

1. W3C, "SOAP Version 1.2 Part 1: Messaging Framework (Second Edition)".
    https://www.w3.org/TR/soap12/
2. Fielding, R. T. Architectural Styles and the Design of Network-Based Software
    Architectures. Doctoral Dissertation, University of California, Irvine, 2000.
    https://www.ics.uci.edu/~fielding/pubs/dissertation/top.htm
3. "REST API Tutorial". https://restfulapi.net/
4. "GraphQL: A query language for your API". https://graphql.org/
5. "gRPC: A high performance, open source universal RPC framework".
    https://grpc.io/
6. Stowe, M. "XML, SOAP, JSON, REST, GraphQL?".
    https://www.slideshare.net/mikestowe/xml-soap-json-rest-graphql
7. Brito, G., Valente, M. T. "REST vs GraphQL: A Controlled Experiment", In
    Proc. of the Int. Conf. Software Architecture (ICSA), 2020.
    https://www.researchgate.net/publication/339413273_REST_vs_GraphQL_A_
    Controlled_Experiment


