#!/usr/bin/env python3
"""Regenerate templates/crd/rabbitmqclusters.rabbitmq.com.yaml from upstream.

The upstream source version is the `rabbitmq-operator-version` annotation in
Chart.yaml. The transform below is byte-exact against the committed CRD: it
re-injects the chart-specific metadata and re-emits with PyYAML 6.0.1
(safe_dump width=80, sort_keys=True). Changing either breaks the golden check.
"""
import pathlib
import re
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHART = ROOT / "Chart.yaml"
OUT = ROOT / "templates/crd/rabbitmqclusters.rabbitmq.com.yaml"
UPSTREAM = (
    "https://raw.githubusercontent.com/rabbitmq/cluster-operator/"
    "v{version}/config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml"
)
LABELS = {
    "app.kubernetes.io/component": "rabbitmq-operator",
    "app.kubernetes.io/name": "rabbitmq-cluster-operator",
    "app.kubernetes.io/part-of": "rabbitmq",
    "servicebinding.io/provisioned-service": "true",
}


def pinned_version() -> str:
    match = re.search(
        r'rabbitmq-operator-version:\s*"?([^"\n]+)"?', CHART.read_text()
    )
    if not match:
        sys.exit("no rabbitmq-operator-version annotation in Chart.yaml")
    return match.group(1)


def main() -> None:
    version = pinned_version()
    tag = version.removeprefix("v")  # git tags are v-prefixed, the pin is not
    if OUT.exists():
        current = yaml.safe_load(OUT.read_text())
        marker = current["metadata"]["annotations"].get("rabbitmq.com/operator-version")
        if marker == version:
            print(f"CRD already at {version}, nothing to do")
            return
    with urllib.request.urlopen(UPSTREAM.format(version=tag), timeout=60) as resp:
        crd = yaml.safe_load(resp.read())
    metadata = crd["metadata"]
    metadata["annotations"]["helm.sh/resource-policy"] = "keep"
    metadata["annotations"]["rabbitmq.com/operator-version"] = version
    metadata["labels"] = LABELS
    with OUT.open("w") as handle:
        yaml.safe_dump(crd, handle, default_flow_style=False, sort_keys=True, width=80)
    print(f"refreshed CRD from cluster-operator v{tag} (pinned {version})")


if __name__ == "__main__":
    main()
