#!/usr/bin/env python3
"""Regenerate templates/crd/rabbitmqclusters.rabbitmq.com.yaml from the
rabbitmq/cluster-operator release pinned in Chart.yaml.

Byte-exact, idempotent, and fails loudly: every problem raises, so a wrong CRD
is never written.  Stdlib + PyYAML only.

Usage: scripts/refresh-crd.py   (no arguments; runnable from any directory)
"""
import hashlib
import os
import re
import sys
import urllib.error
import urllib.request

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_YAML = os.path.join(ROOT, "Chart.yaml")
CRD_PATH = os.path.join(ROOT, "templates", "crd", "rabbitmqclusters.rabbitmq.com.yaml")

UPSTREAM = ("https://raw.githubusercontent.com/rabbitmq/cluster-operator/"
            "v{version}/config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml")

# The Chart.yaml pin key and the CRD marker key are deliberately different strings.
# Conflating them pins nothing and stamps nothing.
PIN_KEY = "rabbitmq-operator-version"
MARKER = "rabbitmq.com/operator-version"
RESOURCE_POLICY = "helm.sh/resource-policy"

# Chart-injected metadata. Upstream carries none of it; it must survive a refresh.
LABELS = {
    "app.kubernetes.io/component": "rabbitmq-operator",
    "app.kubernetes.io/name": "rabbitmq-cluster-operator",
    "app.kubernetes.io/part-of": "rabbitmq",
    "servicebinding.io/provisioned-service": "true",
}

CRD_NAME = "rabbitmqclusters.rabbitmq.com"
# The raw upstream CRD is ~293 kB (v2.6.0) to ~364 kB (v2.23.0). This floor exists
# only to reject a truncated/error body early; the kind/name check is the real guard.
MIN_BYTES = 100_000
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+].*)?$")


def normalise(raw):
    """' v2.6.0 ' -> '2.6.0'. Raises unless the result is a plain version."""
    version = str(raw).strip().lstrip("v").strip()
    if not SEMVER.match(version):
        raise SystemExit(f"refresh-crd: not a version: {raw!r}")
    return version


def read_pin(path=CHART_YAML):
    """Return the operator version pinned in Chart.yaml, without the leading 'v'."""
    with open(path, encoding="utf-8") as fh:
        chart = yaml.safe_load(fh)
    raw = (chart.get("annotations") or {}).get(PIN_KEY)
    if raw is None:
        raise SystemExit(f"refresh-crd: annotations.{PIN_KEY} missing from {path}")
    return normalise(raw)


def read_marker(path=CRD_PATH):
    """Return the operator version already stamped on the committed CRD, if any."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        crd = yaml.safe_load(fh) or {}
    raw = ((crd.get("metadata") or {}).get("annotations") or {}).get(MARKER)
    return None if raw is None else normalise(raw)


def fetch(version):
    """Download the CRD for `version`. Raises on any non-200 -- never returns a body."""
    url = UPSTREAM.format(version=version)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            if response.status != 200:
                raise SystemExit(f"refresh-crd: HTTP {response.status} for {url}")
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"refresh-crd: HTTP {exc.code} for {url}") from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"refresh-crd: cannot fetch {url}: {exc.reason}") from None
    if len(body) < MIN_BYTES:
        raise SystemExit(
            f"refresh-crd: {url} returned {len(body)} B, expected >= {MIN_BYTES} B")
    return body


def render(body, version):
    """Upstream bytes -> chart CRD bytes. sort_keys and width are load-bearing."""
    try:
        crd = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise SystemExit(f"refresh-crd: upstream CRD is not valid YAML: {exc}") from exc
    if not isinstance(crd, dict):
        raise SystemExit("refresh-crd: upstream CRD is not a YAML mapping")
    if crd.get("kind") != "CustomResourceDefinition":
        raise SystemExit(f"refresh-crd: upstream kind is {crd.get('kind')!r}, not a CRD")
    metadata = crd.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("name") != CRD_NAME:
        raise SystemExit(f"refresh-crd: upstream metadata.name is not {CRD_NAME}")
    if not isinstance(crd.get("spec"), dict):
        raise SystemExit("refresh-crd: upstream CRD has no spec")

    annotations = metadata.setdefault("annotations", {})
    annotations[RESOURCE_POLICY] = "keep"
    annotations[MARKER] = version
    metadata.setdefault("labels", {}).update(LABELS)

    # safe_dump already ends the document with a newline; do not append one.
    return yaml.safe_dump(crd, default_flow_style=False, sort_keys=True, width=80)


def write(path, text):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)  # never leave a half-written CRD behind


def main():
    version = read_pin()
    current = read_marker()
    if current == version:
        print(f"refresh-crd: {os.path.relpath(CRD_PATH, ROOT)} is already operator "
              f"{version}; nothing to do")
        return 0

    url = UPSTREAM.format(version=version)
    print(f"refresh-crd: {current or 'unstamped'} -> {version}")
    print(f"refresh-crd: fetching {url}")
    text = render(fetch(version), version)
    write(CRD_PATH, text)

    data = text.encode()
    print(f"refresh-crd: wrote {len(data)} B / {text.count(chr(10))} lines "
          f"sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
