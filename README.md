# rabbitmq-crd-chart

Helm chart for the RabbitMQ CRDs (rabbitmq.com group). Installs the RabbitMQ
Cluster Operator CRD (`rabbitmqclusters.rabbitmq.com`).

CRDs live in `templates/crd/`, so they are installed on `helm install`, are idempotent
on re-install, and are never deleted on `helm uninstall`.

## Usage

```bash
helm install crds oci://ghcr.io/bacluc-agent/rabbitmq-crd-chart/rabbitmq-crd --version 0.0.1
```

## CRD source

`templates/crd/rabbitmqclusters.rabbitmq.com.yaml` is generated from
[rabbitmq/cluster-operator](https://github.com/rabbitmq/cluster-operator)
`config/crd/bases/`, at the version pinned in the `rabbitmq-operator-version`
annotation in `Chart.yaml`. Do not edit it by hand.

Renovate tracks that annotation and opens a PR when a new operator version is
released; the `Refresh CRD` workflow then regenerates the CRD on that branch.
To refresh manually: bump the annotation and run `scripts/refresh-crd.py`
(needs PyYAML 6.0.1 — the dumper is part of the committed file's exact bytes).

Two pieces of chart-specific metadata are re-applied on every refresh and must
not be lost: the `helm.sh/resource-policy: keep` annotation, which keeps the CRD
after `helm uninstall`, and the four `metadata.labels`.

## Release

Label the merged PR `bump:patch` to publish. The release automation derives the
next chart version from the existing `v*` tags and dispatches
`Publish Helm Chart`, which pushes `v<version>` to GHCR.