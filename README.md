# rabbitmq-crd-chart

Helm chart for the RabbitMQ CRDs. Installs the RabbitMQ Cluster Operator CRD (`rabbitmqclusters.rabbitmq.com`).

CRDs live in `templates/crd/`, so they are installed on `helm install`, are idempotent on re-install, and are never deleted on `helm uninstall`.

## Usage

```bash
helm install crds oci://ghcr.io/vshn/rabbitmq-crd-chart/rabbitmq-crd --version 0.0.1
```

## CRD updates

`Chart.yaml` pins the RabbitMQ Cluster Operator version in `annotations.rabbitmq-operator-version`. Renovate bumps that pin. On a pull request, the `Refresh CRD` workflow regenerates `templates/crd/rabbitmqclusters.rabbitmq.com.yaml` from the matching upstream tag and commits it into the same PR.

Run `python3 scripts/refresh-crd.py` locally to refresh the CRD, and `python3 scripts/refresh-crd.py --check` to verify offline that it matches the pin. Both need only Python 3 and its standard library.

## Release

Tag `v<version>` to publish the chart to GHCR. The chart version is derived from the tag.
