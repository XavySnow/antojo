# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modified by the Antojo project, 2026: simplified and hardened lab packaging.

{{- define "antojo.labels" -}}
app.kubernetes.io/name: antojo
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end }}

{{- define "antojo.image" -}}
{{- $tag := default .root.Values.global.imageTag .service.image.tag -}}
{{- if eq $tag "latest" }}{{ fail "Mutable latest tags are forbidden" }}{{ end -}}
{{- printf "%s/%s:%s" .root.Values.global.imageRegistry .name $tag -}}
{{- end }}

{{- define "antojo.probe" -}}
{{- if eq .health "http" }}
httpGet:
  path: /_healthz
  port: {{ .port }}
  httpHeaders:
    - name: Cookie
      value: shop_session-id=health-probe
{{- else if eq .health "grpc" }}
grpc:
  port: {{ .port }}
{{- else }}
# Headless Locust has no server port: check its own process, not dependencies.
exec:
  command:
    - python
    - -c
    - "import glob; assert any(any(a.rsplit(b'/', 1)[-1] == b'locust' for a in open(p, 'rb').read().split(bytes([0]))[:2]) for p in glob.glob('/proc/[0-9]*/cmdline'))"
{{- end }}
{{- end }}
