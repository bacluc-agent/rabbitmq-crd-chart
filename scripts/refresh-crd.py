#!/usr/bin/env python3
"""Refresh templates/crd/rabbitmqclusters.rabbitmq.com.yaml from the
rabbitmq/cluster-operator tag pinned in Chart.yaml.

Usage: scripts/refresh-crd.py [--check]
"""
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHART = ROOT / "Chart.yaml"
CRD = ROOT / "templates" / "crd" / "rabbitmqclusters.rabbitmq.com.yaml"
PIN_KEY = "rabbitmq-operator-version"
RESOURCE_POLICY = "helm.sh/resource-policy"
LABELS = {
    "app.kubernetes.io/component": "rabbitmq-operator",
    "app.kubernetes.io/name": "rabbitmq-cluster-operator",
    "app.kubernetes.io/part-of": "rabbitmq",
    "servicebinding.io/provisioned-service": "'true'",
}
CRD_NAME = "rabbitmqclusters.rabbitmq.com"
MIN_BYTES = 100_000
URL = ("https://raw.githubusercontent.com/rabbitmq/cluster-operator/"
       "v{version}/config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml")
UA = "rabbitmq-crd-chart-refresh/1.0"


def die(message):
    print(f"refresh-crd: {message}", file=sys.stderr)
    raise SystemExit(2)


def read_text(path, label):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        die(f"{label} not found: {path}")
    except (OSError, UnicodeDecodeError) as exc:
        die(f"cannot read {label}: {exc}")


def indent(line):
    return len(line) - len(line.lstrip(" "))


def ignorable(line):
    return not line.strip() or line.lstrip().startswith("#")


def scalar(raw, where):
    raw = raw.strip()
    if not raw:
        die(f"{where} is empty")
    if raw[0] in "'\"":
        quote = raw[0]
        out = []
        index = 1
        while index < len(raw):
            char = raw[index]
            if quote == "'" and char == "'":
                if raw[index + 1:index + 2] == "'":
                    out.append("'")
                    index += 2
                    continue
                index += 1
                break
            if quote == '"' and char == "\\":
                if index + 1 >= len(raw):
                    die(f"{where} has an unterminated escape")
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(
                    raw[index + 1], raw[index + 1]))
                index += 2
                continue
            if quote == '"' and char == '"':
                index += 1
                break
            out.append(char)
            index += 1
        else:
            die(f"{where} has an unterminated quoted scalar")
        tail = raw[index:].strip()
        if tail and not tail.startswith("#"):
            die(f"{where} has trailing content after the quoted scalar")
        value = "".join(out)
    else:
        value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
        if not value or value.startswith("#"):
            die(f"{where} is empty")
        if value[0] in "[{|>&*!?" or value.startswith("- ") or value in (
                "~", "null", "Null", "NULL"):
            die(f"{where} is not a scalar: {raw!r}")
    if not value:
        die(f"{where} is empty")
    return value


def split_entry(line, at):
    key, separator, rest = line[at:].partition(":")
    if not separator:
        return None, None
    key = key.strip()
    if key[:1] in "'\"":
        key = scalar(key, "mapping key")
    return key, rest.strip()


def find(lines, key, at, start=0, end=None):
    end = len(lines) if end is None else end
    for index in range(start, end):
        line = lines[index]
        if ignorable(line) or indent(line) != at:
            continue
        found, rest = split_entry(line, at)
        if found == key:
            return index, rest
    return None, None


def block_end(lines, header, at):
    end = header + 1
    for index in range(header + 1, len(lines)):
        line = lines[index]
        if ignorable(line):
            continue
        if indent(line) <= at:
            break
        end = index + 1
    return end


def child_indent(lines, start, end, fallback):
    for index in range(start, end):
        if not ignorable(lines[index]):
            return indent(lines[index])
    return fallback


def normalise(raw, where):
    version = raw[1:] if raw.startswith("v") else raw
    if not version:
        die(f"{where} is empty after stripping a leading v")
    return version


def chart_pin():
    lines = read_text(CHART, "Chart.yaml").split("\n")
    header, rest = find(lines, "annotations", 0)
    if header is None:
        die(f"annotations.{PIN_KEY} missing from {CHART}")
    if rest:
        die(f"annotations in {CHART} is not a block mapping")
    end = block_end(lines, header, 0)
    children = child_indent(lines, header + 1, end, 2)
    values = []
    for index in range(header + 1, end):
        line = lines[index]
        if ignorable(line) or indent(line) != children:
            continue
        key, raw = split_entry(line, children)
        if key == PIN_KEY:
            values.append(scalar(raw, f"annotations.{PIN_KEY} in {CHART}"))
    if len(values) != 1:
        die(f"annotations.{PIN_KEY} appears {len(values)} times in {CHART}")
    return normalise(values[0], f"annotations.{PIN_KEY} in {CHART}")


def read_marker(text):
    lines = text.split("\n")
    metadata, metadata_rest = find(lines, "metadata", 0)
    if metadata is None or metadata_rest:
        die(f"metadata is missing from {CRD}")
    metadata_end = block_end(lines, metadata, 0)
    children = child_indent(lines, metadata + 1, metadata_end, 2)
    annotations, _ = find(lines, "annotations", children, metadata + 1, metadata_end)
    if annotations is None:
        die(f"annotations.{PIN_KEY} missing from {CRD}")
    end = block_end(lines, annotations, children)
    annotation_indent = child_indent(lines, annotations + 1, end, children + 2)
    values = []
    for index in range(annotations + 1, end):
        line = lines[index]
        if ignorable(line) or indent(line) != annotation_indent:
            continue
        key, raw = split_entry(line, annotation_indent)
        if key == PIN_KEY:
            values.append(scalar(raw, f"annotations.{PIN_KEY} in {CRD}"))
    if len(values) != 1:
        die(f"annotations.{PIN_KEY} appears {len(values)} times in {CRD}")
    return normalise(values[0], f"annotations.{PIN_KEY} in {CRD}")


def fetch(version):
    url = URL.format(version=version)
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            body = response.read()
    except urllib.error.HTTPError as exc:
        die(f"HTTP {exc.code} for {url}")
    except Exception as exc:
        die(f"cannot fetch {url}: {exc}")
    if status != 200:
        die(f"HTTP {status} for {url}")
    if len(body) < MIN_BYTES:
        die(f"{url} returned {len(body)} B, expected >= {MIN_BYTES} B")
    return body


def decode(body):
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        die(f"upstream is not UTF-8: {exc}")
    if "\r" in text:
        if text.replace("\r\n", "").count("\r"):
            die("upstream contains a bare CR")
        text = text.replace("\r\n", "\n")
    return text


def replace_header(lines, header, key, at):
    _found, rest = split_entry(lines[header], at)
    if rest and rest not in ("{}", "~", "null", "Null", "NULL"):
        die(f"{key} is not a block mapping")
    lines[header] = " " * at + f"{key}:"


def upsert(lines, header, at, wanted):
    end = block_end(lines, header, at)
    children = child_indent(lines, header + 1, end, at + 2)
    seen = set()
    body = []
    for index in range(header + 1, end):
        line = lines[index]
        if not ignorable(line) and indent(line) == children:
            key, _rest = split_entry(line, children)
            if key in wanted:
                if key in seen:
                    continue
                seen.add(key)
                body.append(" " * children + f"{key}: {wanted[key]}")
                continue
        body.append(line)
    missing = [" " * children + f"{key}: {value}"
               for key, value in wanted.items() if key not in seen]
    if missing:
        position = len(body)
        while position and not body[position - 1].strip():
            position -= 1
        body[position:position] = missing
    return lines[:header + 1] + body + lines[end:]


def insert_block(lines, at, level, key, wanted):
    block = [" " * level + f"{key}:"] + [
        " " * (level + 2) + f"{name}: {value}" for name, value in wanted.items()]
    return lines[:at] + block + lines[at:]


def transform(text, version):
    lines = text.split("\n")
    try:
        start = lines.index("apiVersion: apiextensions.k8s.io/v1")
    except ValueError:
        die("upstream has no top-level apiVersion: apiextensions.k8s.io/v1")
    lines = lines[start:]

    kind, kind_rest = find(lines, "kind", 0)
    if kind is None or scalar(kind_rest, "upstream kind") != "CustomResourceDefinition":
        die(f"upstream kind is {kind_rest!r}, not a CustomResourceDefinition")

    metadata, metadata_rest = find(lines, "metadata", 0)
    if metadata is None or metadata_rest:
        die("upstream has no top-level metadata mapping")
    metadata_end = block_end(lines, metadata, 0)
    children = child_indent(lines, metadata + 1, metadata_end, 2)
    name, name_rest = find(lines, "name", children, metadata + 1, metadata_end)
    if name is None or scalar(name_rest, "upstream metadata.name") != CRD_NAME:
        die(f"upstream metadata.name is not {CRD_NAME}")

    annotations_wanted = {PIN_KEY: f'"{version}"', RESOURCE_POLICY: "keep"}
    annotations, _ = find(lines, "annotations", children, metadata + 1, metadata_end)
    if annotations is None:
        lines = insert_block(lines, metadata + 1, children, "annotations", annotations_wanted)
    else:
        replace_header(lines, annotations, "annotations", children)
        lines = upsert(lines, annotations, children, annotations_wanted)

    metadata_end = block_end(lines, metadata, 0)
    labels, _ = find(lines, "labels", children, metadata + 1, metadata_end)
    if labels is None:
        annotations, _ = find(lines, "annotations", children, metadata + 1, metadata_end)
        at = block_end(lines, annotations, children) if annotations is not None else metadata + 1
        lines = insert_block(lines, at, children, "labels", LABELS)
    else:
        replace_header(lines, labels, "labels", children)
        lines = upsert(lines, labels, children, LABELS)

    result = "\n".join(lines)
    return result if result.endswith("\n") else result + "\n"


def write_atomic(data):
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".refresh-crd-", suffix=".tmp", dir=CRD.parent)
    except OSError as exc:
        die(f"cannot create a temp file next to {CRD}: {exc}")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, CRD)
    except OSError as exc:
        die(f"cannot write {CRD}: {exc}")
    finally:
        if os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


def regenerate():
    version = chart_pin()
    new = transform(decode(fetch(version)), version).encode("utf-8")
    try:
        old = CRD.read_bytes()
    except FileNotFoundError:
        old = None
    except OSError as exc:
        die(f"cannot read {CRD}: {exc}")
    if old == new:
        print(f"up to date (v{version})")
        return 0
    write_atomic(new)
    print(f"updated {CRD.relative_to(ROOT).as_posix()} -> v{version}")
    return 0


def check():
    version = chart_pin()
    marker = read_marker(read_text(CRD, "CRD"))
    if marker == version:
        print(f"ok (v{version})")
        return 0
    print(f"refresh-crd: Chart.yaml pins {version} but CRD declares {marker}",
          file=sys.stderr)
    return 1


def main(argv):
    if not argv:
        return regenerate()
    if argv == ["--check"]:
        return check()
    die("usage: refresh-crd.py [--check]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
