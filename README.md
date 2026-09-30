# rabbitmq-crd-chart

Helm chart for the RabbitMQ CRDs. Installs the RabbitMQ Cluster Operator CRD (`rabbitmqclusters.rabbitmq.com`).

CRDs live in `templates/crd/`, so they are installed on `helm install`, are idempotent on re-install, and are never deleted on `helm uninstall`.

## Usage

```bash
helm install crds oci://ghcr.io/vshn/rabbitmq-crd-chart/rabbitmq-crd --version 0.0.1
```

## CRD source

`templates/crd/rabbitmqclusters.rabbitmq.com.yaml` is generated, not hand-maintained. `scripts/refresh-crd.py` downloads `https://raw.githubusercontent.com/rabbitmq/cluster-operator/v<version>/config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml` for the version pinned in `Chart.yaml` (`annotations.rabbitmq-operator-version`), stamps it back as the `rabbitmq.com/operator-version` annotation, and re-applies the chart metadata Helm needs — `helm.sh/resource-policy: keep` plus the four `app.kubernetes.io/*` and `servicebinding.io/*` labels, none of which upstream carries.

The render is deterministic (`yaml.safe_dump(sort_keys=True, width=80)`), so regenerating the same version is byte-identical. Never hand-edit or hand-merge this file; change the pin and regenerate.

Renovate watches the pin, and the `Refresh CRD` workflow regenerates the CRD on the Renovate branch and commits it into the same pull request, so an operator bump arrives as one reviewable PR with no manual step. To publish, label the PR `bump:patch` and merge — `projectsyn/pr-label-tag-action` then tags the next patch release and dispatches the `Publish Helm Chart` workflow.

Locally, with Python 3 and PyYAML 6.0.1:

```bash
pip install pyyaml==6.0.1 && scripts/refresh-crd.py
```

It takes no arguments, runs from any directory, is idempotent — a no-op that makes no network request when the CRD already carries the pinned version — and fails loudly rather than writing a bad file.

Renovate cannot run that script itself. Its `postUpgradeTasks` need `allowedCommands`, which is `globalOnly: true` with an empty default, so the validator rejects it from repo config; `allowShellExecutorForPostUpgradeCommands` defaults to `false`, so the hosted app has no shell to run a script with. Every operator bump therefore shows a red `renovate/artifacts` check. That is expected, and it is why the refresh lives in a GitHub Actions workflow instead.

## Release

Tag `v<version>` to publish the chart to GHCR. The chart version is derived from the tag.
