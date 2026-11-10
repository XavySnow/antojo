#!/usr/bin/env bash
# Build on Cloud Build, then install one auditable SHA-tagged Helm release.
set -euo pipefail

readonly PROJECT_ID="antojo-lab"
readonly REGION="us-central1"
readonly CLUSTER="antojo"
readonly NAMESPACE="antojo"
readonly CONTEXT="gke_${PROJECT_ID}_${REGION}_${CLUSTER}"
readonly SOURCE_BUCKET="${PROJECT_ID}-antojo-build-source"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
cd "$ROOT"
for tool in git gcloud helm kubectl; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done

# Refuse uncommitted build inputs so the tag truthfully identifies the source.
echo "Step 1/5: validate committed build inputs and render the chart locally."
if ! git diff --quiet HEAD -- services cloudbuild.yaml charts/antojo scripts .gcloudignore || \
  [[ -n "$(git ls-files --others --exclude-standard -- services cloudbuild.yaml charts/antojo scripts .gcloudignore)" ]]; then
  echo "Commit or stash changes to build/deployment inputs before building a SHA tag." >&2
  exit 1
fi
TAG="$(git rev-parse --short HEAD)"
readonly TAG
helm lint charts/antojo --set-string "global.imageTag=${TAG}"
helm template antojo charts/antojo --namespace "$NAMESPACE" \
  --set-string "global.imageTag=${TAG}" >/dev/null

# Refresh credentials for the EXISTING cluster. Explicit context avoids a wrong-cluster install.
echo "Step 2/5: select the existing GKE cluster (no cluster creation)."
gcloud container clusters get-credentials "$CLUSTER" --location="$REGION" --project="$PROJECT_ID"
kubectl --context="$CONTEXT" cluster-info

# The remote builder is amd64 even on an ARM Mac. A single SHA links all 11 images.
# The staging bucket is the private bucket prepared by bootstrap-lab.sh.
echo "Step 3/5: build and push all eleven images remotely (billable)."
gcloud builds submit --project="$PROJECT_ID" --region="$REGION" \
  --config cloudbuild.yaml --substitutions="_TAG=${TAG}" \
  --gcs-source-staging-dir="gs://${SOURCE_BUCKET}/source" .

# Wait for readiness, not merely API acceptance. On failure --atomic rolls back
# an upgrade (or uninstalls a failed first install); inspect the printed diagnostics.
echo "Step 4/5: upgrade/install the Helm release and wait for healthy Pods."
if ! helm upgrade --install antojo charts/antojo --namespace "$NAMESPACE" \
  --create-namespace --kube-context "$CONTEXT" --set-string "global.imageTag=${TAG}" \
  --atomic --wait --timeout=20m; then
  kubectl --context="$CONTEXT" get pods,events -n "$NAMESPACE" || true
  echo "Helm failed. A failed first install may have been removed by --atomic." >&2
  exit 1
fi
deployments="$(kubectl --context="$CONTEXT" get deployments -n "$NAMESPACE" \
  -l app.kubernetes.io/instance=antojo -o name)"
[[ -n "$deployments" ]] || { echo "No release Deployments found." >&2; exit 1; }
while IFS= read -r deployment; do
  kubectl --context="$CONTEXT" rollout status "$deployment" -n "$NAMESPACE" --timeout=5m
done <<< "$deployments"

# Helm waits for the LoadBalancer address; print it only when it is actually present.
echo "Step 5/5: print the frontend's public HTTP address."
frontend_address="$(kubectl --context="$CONTEXT" get svc frontend-external -n "$NAMESPACE" \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
if [[ -z "$frontend_address" ]]; then
  frontend_address="$(kubectl --context="$CONTEXT" get svc frontend-external -n "$NAMESPACE" \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
fi
if [[ -z "$frontend_address" ]]; then
  echo "Address is still pending; inspect: kubectl --context=$CONTEXT get svc -n $NAMESPACE" >&2
  exit 1
fi
printf 'Antojo (%s): http://%s\n' "$TAG" "$frontend_address"
echo "HTTP lab only: use fake data. Load generator is off by default. Tear down by Nov 17."
