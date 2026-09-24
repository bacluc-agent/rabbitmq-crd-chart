# rabbitmq-crd-chart

Helm chart for the RabbitMQ CRDs (rabbitmq.com group). Installs the RabbitMQ
Cluster Operator CRD (`rabbitmqclusters.rabbitmq.com`).

CRDs live in `templates/crd/`, so they are installed on `helm install`, are idempotent
on re-install, and are never deleted on `helm uninstall`.

## Usage

```bash
helm install crds oci://ghcr.io/bacluc-agent/rabbitmq-crd-chart/rabbitmq-crd --version 0.0.1
```

## Release

Tag `v<version>` to publish the chart to GHCR. The chart version is derived
from the tag.