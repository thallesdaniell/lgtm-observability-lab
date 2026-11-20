# LGTM Observability Lab

Uma API de pedidos demonstrativa envia logs, métricas e traces correlacionados para uma stack local com Grafana, Loki, Tempo e Mimir. Explore o comportamento de requisições bem-sucedidas e falhas pelo Grafana.

![Fluxo da telemetria](docs/flow.svg)

## Executar

Requisitos: Docker e Docker Compose, com memória e espaço disponíveis para a imagem Grafana LGTM.

```sh
docker compose up -d
curl http://localhost:8088/health
curl http://localhost:8088/order
curl 'http://localhost:8088/order?fail=true'
```

`/health` responde `200`. `/order` retorna `200` e um `trace_id`; `?fail=true` simula uma falha e retorna `500` com seu `trace_id`. As requisições geram um log, um span e atualizam o contador. Aguarde a inicialização da stack antes de enviar requisições.

Abra [Grafana](http://localhost:3300) com `admin` / `admin`. No **Explore**:

| Sinal | Datasource | Consulta ou ação |
|---|---|---|
| Logs | Loki | `{service_name="lgtm-demo"}` |
| Traces | Tempo | Busque pelo `trace_id` retornado pela API. |
| Métricas | Mimir | `demo_orders_total` |

O log inclui o mesmo trace ID do span, permitindo seguir a operação entre Loki e Tempo. Para acompanhar a aplicação, execute `docker compose logs -f app`.

## Fluxo

1. O cliente faz uma requisição à API local de demonstração.
2. A API envia logs e traces ao OpenTelemetry Collector da imagem LGTM e métricas ao Alloy, ambos por OTLP/HTTP.
3. O Collector encaminha logs ao Loki e traces ao Tempo; o Alloy converte as métricas e envia ao Mimir por Prometheus remote write.
4. O Grafana consulta os três backends para exploração.

O Mimir roda em modo monolítico com armazenamento local e multi-tenancy desabilitada para facilitar o aprendizado. O datasource Mimir é provisionado automaticamente no Grafana e usa consultas PromQL.

### Alternativa com Prometheus

A imagem `grafana/otel-lgtm` continua executando um Prometheus interno, mas as métricas da API seguem para o Mimir. Em `alloy.alloy` há uma configuração comentada de `remote_write` para um Prometheus separado. Para usá-la, é necessário provisionar esse serviço com `--web.enable-remote-write-receiver`, descomentar o bloco e alterar `forward_to` no exporter. O Prometheus interno da imagem não é configurado por esse bloco.

## Validação local

Com Docker Compose, `/order` retornou `200`, e a consulta `demo_orders_total` no datasource Mimir retornou a métrica enviada pelo Alloy. Na configuração anterior, também foram validados o log e o trace de erro com o mesmo ID; repita a consulta dos três sinais após subir a stack.

## Segurança e limitações

- O lab é local e não foi preparado para produção: usa HTTP e credenciais Grafana de demonstração.
- As portas publicadas ficam restritas a `127.0.0.1`.
- A API usa uma implementação mínima de OTLP em Python para tornar os dados visíveis; não representa a instrumentação recomendada para aplicações de produção, onde um SDK OpenTelemetry é mais apropriado.
- A exportação é síncrona e a API retorna `503` se o collector estiver indisponível.
- A tag `latest` da imagem pode mudar; fixe uma versão para resultados reproduzíveis.
- A configuração do Mimir é para uma única instância local; não demonstra escalabilidade, alta disponibilidade ou armazenamento de objetos.
- `docker compose down` encerra o lab e preserva o volume; `docker compose down -v` também apaga os dados.

Referências: [Grafana Docker OpenTelemetry LGTM](https://grafana.com/docs/opentelemetry/docker-lgtm/) e [projeto da imagem](https://github.com/grafana/docker-otel-lgtm).
