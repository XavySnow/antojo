#!/usr/bin/env bash
# Prepare build prerequisites only; do not create or replace the existing cluster.
set -euo pipefail

readonly PROJECT_ID="antojo-lab"
readonly REGION="us-central1"
readonly CLUSTER="antojo"
readonly REPOSITORY="antojo"
readonly BUILD_SA_NAME="antojo-cloud-build"
readonly BUILD_SA="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly SOURCE_BUCKET="${PROJECT_ID}-antojo-build-source"

command -v gcloud >/dev/null || { echo "Install the Google Cloud CLI first." >&2; exit 1; }
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

# APIs are capabilities, not running workloads. Enabling an enabled API is safe.
echo "Step 1/6: enable the build, registry, identity, storage and logging APIs."
gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com \
  iam.googleapis.com storage.googleapis.com logging.googleapis.com \
  --project="$PROJECT_ID" --quiet

# Keep images near the cluster to avoid unnecessary cross-region transfers.
echo "Step 2/6: ensure the regional Docker repository exists."
if ! gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>"$tmp_dir/repository-error"; then
  if ! grep -q 'NOT_FOUND' "$tmp_dir/repository-error"; then
    cat "$tmp_dir/repository-error" >&2
    exit 1
  fi
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker \
    --location="$REGION" --description="Antojo temporary trial lab images" \
    --project="$PROJECT_ID" --quiet
fi

# A KEEP rule alone deletes nothing. KEEP wins over DELETE, retaining five versions
# per image package. The one-day grace window protects images being rolled out.
echo "Step 3/6: apply cleanup (last five versions kept; older extras deleted after one day)."
cat > "$tmp_dir/cleanup.json" <<'JSON'
[
  {"name":"delete-old-extras","action":{"type":"Delete"},"condition":{"tagState":"any","olderThan":"86400s"}},
  {"name":"keep-last-five","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":5}}
]
JSON
gcloud artifacts repositories set-cleanup-policies "$REPOSITORY" \
  --location="$REGION" --policy="$tmp_dir/cleanup.json" --no-dry-run \
  --project="$PROJECT_ID" --quiet

# Do not use the Compute default identity for builds: that would give GKE nodes
# the writer permission too. Cloud Build uses this dedicated SA in cloudbuild.yaml.
echo "Step 4/6: prepare the dedicated build identity and repository-scoped writer role."
if ! gcloud iam service-accounts describe "$BUILD_SA" --project="$PROJECT_ID" \
  >/dev/null 2>"$tmp_dir/service-account-error"; then
  if ! grep -q 'NOT_FOUND' "$tmp_dir/service-account-error"; then
    cat "$tmp_dir/service-account-error" >&2
    exit 1
  fi
  gcloud iam service-accounts create "$BUILD_SA_NAME" \
    --display-name="Antojo Cloud Build (no deploy permissions)" --project="$PROJECT_ID"
fi
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
  --location="$REGION" --member="serviceAccount:${BUILD_SA}" \
  --role=roles/artifactregistry.writer --condition=None --project="$PROJECT_ID" --quiet
# Logs use Cloud Logging rather than a broadly writable logs bucket.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" --role=roles/logging.logWriter \
  --condition=None --quiet

# A private, dedicated staging bucket lets the build SA read uploaded sources
# without project-wide Storage permissions. Source archives expire after one day.
# Disable soft delete only on this disposable source bucket, not durable data.
echo "Step 5/6: prepare the private source staging bucket with one-day retention."
if ! gcloud storage buckets describe "gs://${SOURCE_BUCKET}" --project="$PROJECT_ID" \
  >/dev/null 2>"$tmp_dir/bucket-error"; then
  if ! grep -Eq 'NOT_FOUND|NotFoundException|404' "$tmp_dir/bucket-error"; then
    cat "$tmp_dir/bucket-error" >&2
    exit 1
  fi
  gcloud storage buckets create "gs://${SOURCE_BUCKET}" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention --soft-delete-duration=0 \
    --project="$PROJECT_ID"
fi
cat > "$tmp_dir/lifecycle.json" <<'JSON'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":1}}]}
JSON
gcloud storage buckets update "gs://${SOURCE_BUCKET}" \
  --lifecycle-file="$tmp_dir/lifecycle.json" --public-access-prevention \
  --uniform-bucket-level-access --clear-soft-delete \
  --project="$PROJECT_ID"
gcloud storage buckets add-iam-policy-binding "gs://${SOURCE_BUCKET}" \
  --member="serviceAccount:${BUILD_SA}" --role=roles/storage.objectViewer \
  --condition=None --project="$PROJECT_ID"

# Image pulls use the NODE Google SA, not a Pod's Kubernetes SA or Workload Identity.
# Discover actual node-pool identities; Autopilot may expose only nodeConfig.
echo "Step 6/6: grant node identities read-only access to this repository."
project_number="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
node_sas="$(gcloud container clusters describe "$CLUSTER" --location="$REGION" \
  --project="$PROJECT_ID" --flatten=nodePools --format='value(nodePools.config.serviceAccount)')"
if [[ -z "$node_sas" ]]; then
  node_sas="$(gcloud container clusters describe "$CLUSTER" --location="$REGION" \
    --project="$PROJECT_ID" --format='value(nodeConfig.serviceAccount)')"
fi
# Empty or 'default' means the project's Compute Engine default service account.
node_sas="${node_sas:-default}"
while IFS= read -r node_sa; do
  [[ "$node_sa" != "default" ]] || node_sa="${project_number}-compute@developer.gserviceaccount.com"
  [[ "$node_sa" == *@*.gserviceaccount.com ]] || { echo "Unexpected node SA: $node_sa" >&2; exit 1; }
  gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
    --location="$REGION" --member="serviceAccount:${node_sa}" \
    --role=roles/artifactregistry.reader --condition=None --project="$PROJECT_ID" --quiet
done < <(printf '%s\n' "$node_sas" | sort -u)

echo "Bootstrap complete. No cluster, Gemini service or application was deployed."
echo "Submitter needs iam.serviceAccounts.actAs on ${BUILD_SA} (Owner normally has it)."
echo "Next: bash scripts/build-and-deploy.sh"
