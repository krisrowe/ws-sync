# Workstation Sync (WS-SYNC) Design

This document outlines the recommended strategy for storing and retrieving workstation configurations using a personal Google Cloud project as the central source of truth.

The core principle is to use a **Project Label** (e.g., `ws-sync=default`) to discover the globally unique **Project ID** on any new workstation. This is a robust and scalable method designed for automation.

---

## Recommended Strategy: Google Cloud Storage (GCS)

A straightforward, file-based approach that is flexible, cost-effective, and can be made highly secure. This strategy was chosen as the primary recommendation for several practical reasons:

1.  **File-Based Nature:** Many configurations are already stored in files (`.env`, `kubeconfig`, `.properties`). GCS allows you to manage these files as-is, without needing to parse them into a key-value model.
2.  **Cost Model:** GCS storage costs are extremely low (fractions of a cent per GB per month). For a personal use case with a few small files, the cost is effectively zero.
3.  **Billing Risk Mitigation:** Services with per-unit monthly costs (like Secret Manager's per-secret-version fee) introduce a dependency on an active billing account. Even for small amounts, this creates a risk that an expired credit card or a billing issue could lead to the project being suspended and the data becoming inaccessible. The GCS free tier and low storage costs make it much more resilient to these kinds of billing lifecycle issues.
4.  **Flexibility:** The bucket and object model allows for easy extension, such as using different folders for different profiles (`default/`, `work/`) within the same bucket.

### Securing the GCS Bucket for Sensitive Files

You can achieve a very high level of security, consistent with enterprise practices, by layering the following controls.

1.  **IAM (Identity and Access Management):** Ensure only your user account has access to the project. As confirmed in our audit, having a single `owner` binding for your user is the most secure starting point.
2.  **Uniform Bucket-Level Access:** This is a critical setting that disables object-level ACLs and ensures only bucket-level IAM policies are used. This simplifies security and prevents accidental public sharing. The setup script enables this with the `-b on` flag.
3.  **Public Access Prevention:** This bucket-level setting (`enforced` in our audit) provides a strong guarantee that no public access is allowed, regardless of other policies.
4.  **Customer-Managed Encryption Keys (CMEK) (Advanced):** For the highest level of control, you can use Cloud KMS to create your own encryption key. You then configure the GCS bucket to use this key. This means you have full control over the key, and if you disable it, no one (including Google) can decrypt the data. This is an advanced feature with its own cost and responsibility considerations (if you lose the key, the data is lost forever).

### Billing and Long-Term Availability

A key goal of this design is to ensure long-term data durability without requiring active billing management.

*   **Billing Account Requirement:** To use any GCP service, a project must be linked to an active billing account with a valid payment method. This is a fundamental requirement of the platform.

*   **"Always Free" Tier and Costs:** This solution generates a **$0.00** bill because its usage falls within the GCS "Always Free" tier. This tier, which resets monthly, includes generous allowances for storage (e.g., 5 GB-months), operations, and network egress that are far greater than what this solution requires. A "GB-month" is a unit of storage over time; storing 1 GB for a full month consumes 1 GB-month.

*   **The "Billing Dependency" Risk:** Even with zero cost, a dependency on the billing account remains. If the credit card on file expires, Google may eventually suspend the billing account and, in turn, the project. While the risk is low for a zero-charge project, this administrative dependency is a key difference compared to a consumer product like Google Drive.

### How to Verify Bucket Security

You can and should periodically audit your setup to confirm it remains secure. This guide provides the commands to verify that access is restricted exclusively to you.

**Step 1: Identify Your Project and Bucket**

First, find the exact Project ID and Bucket Name using the label you've assigned. This ensures you are checking the correct resources.

```bash
# Define the profile you want to check
PROFILE="default"
SYNC_LABEL="labels.ws-sync=${PROFILE}"

# Find the Project ID
PROJECT_ID=$(gcloud projects list --filter="${SYNC_LABEL}" --format="value(project_id)")
echo "Found Project ID: ${PROJECT_ID}"

# Find the Bucket URL
BUCKET_URL=$(gcloud storage buckets list --project="${PROJECT_ID}" --filter="${SYNC_LABEL}" --format="value(url)")
echo "Found Bucket: ${BUCKET_URL}"
```

**Step 2: Check Bucket-Level Settings**

Next, verify that the bucket itself is configured to prevent public access.

```bash
# Describe the bucket's configuration
gcloud storage buckets describe $BUCKET_URL
```

In the output, look for these two critical lines:
*   `uniformBucketLevelAccess: true`
*   `publicAccessPrevention: ENFORCED`

If both are set as shown, the bucket is properly configured to block public access and use only IAM for permissions.

**Step 3: Audit Project-Level IAM Permissions**

Finally, check who has access to the entire project. This is the most important step.

```bash
# Get the IAM policy for the project
gcloud projects get-iam-policy $PROJECT_ID
```

Review the `bindings` section of the output. For a completely private setup, you should **only** see your own user account, typically with the `roles/owner` role:

```yaml
bindings:
- members:
  - user:your-email@example.com
  role: roles/owner
```

If you see any other `members`, especially the special groups `allUsers` or `allAuthenticatedUsers`, it means other people or services can access your project.

## Implementation

The implementation of this design consists of two main scripts:

1.  **A one-time setup script:** Used to create and configure the GCP project and GCS bucket with the correct labels and security settings.
2.  **A sync script:** Used on new workstations to discover the correct resources and download the configuration files.

The complete, commented scripts and the detailed step-by-step usage instructions are maintained in the main user-facing guide.

**For the full implementation details, see: [README.md](./README.md)**

---
### Alternative Designs Considered

A detailed analysis of alternative solutions, including Google Secret Manager and Google Firestore, is maintained in a separate document. This includes the rationale for choosing GCS as the primary strategy and preserves the technical details of the other options. This separate analysis is valuable for periodic re-evaluation and to help developers quickly recall the findings and trade-offs of each approach, as these alternatives may be useful in future extensions of this solution.

For this detailed analysis, please see:
- [`ALT-DESIGN.md`](./ALT-DESIGN.md)

---
## Appendix: The "Consumer Durability" Backup Strategy

For users who wish to have a long-term, highly durable backup of their most critical configurations, independent of their GCP project's lifecycle, a "Consumer Durability" strategy can be employed.

### The Rationale for "Consumer Durability" (Personal Data Gravity)

This concept stems from the profound trust and reliance users place on their primary Google Account (Gmail, Google Drive, etc.).

1.  **High Personal Investment & Active Use:** Your primary Google Account is central to your daily digital life, making it highly unlikely to be neglected or lost. This creates a strong sense of "data gravity" and permanence.

2.  **Simpler Account Lifecycle:** A consumer Google Account has a simple, user-centric lifecycle. In contrast, a GCP setup is more complex (organizations, billing accounts, projects). A GCP project could be accidentally deleted or a billing account suspended, potentially jeopardizing the data within. A personal Google Drive feels more resilient to these administrative mishaps.

3.  **Perceived Product Longevity:** Core products like Gmail and Google Drive are perceived as "permanent" fixtures. For data that needs to "just exist" for years without active management, the perceived stability of Google Drive can be more appealing.

This strategy uses an operationally convenient tool (like GCS or Secret Manager) for day-to-day use, but maintains a periodic backup in a highly trusted, permanent location (Google Drive).

### Practical Implementation: GCS to Drive Backup

This script demonstrates how to back up a file from GCS to Google Drive. It requires a third-party CLI tool like `gdrive` to be installed and authenticated.

```bash
#!/bin/bash

# --- Configuration ---
PROFILE="default" # Your workstation sync profile
CONFIG_FILE_NAME="config.json" # The name of the file in GCS
LOCAL_TEMP_DIR="/tmp/ws-sync-backup" # Temporary directory for download
DRIVE_BACKUP_FOLDER="Workstation Backups" # Folder name in Google Drive
OUTPUT_FILE="${LOCAL_TEMP_DIR}/${CONFIG_FILE_NAME}"

# --- Authenticate and Discover GCS Source ---
gcloud auth login

SYNC_LABEL="labels.ws-sync=${PROFILE}"

echo "Discovering Project by label: ${SYNC_LABEL}..."
PROJECT_ID=$(gcloud projects list --filter="${SYNC_LABEL}" --format="value(project_id)")
if [ -z "$PROJECT_ID" ]; then echo "Error: Could not find project." && exit 1; fi

echo "Discovering GCS Bucket by label in project ${PROJECT_ID}..."
BUCKET_URL=$(gcloud storage buckets list --project="${PROJECT_ID}" --filter="${SYNC_LABEL}" --format="value(url)")
if [ -z "$BUCKET_URL" ]; then echo "Error: Could not find bucket." && exit 1; fi

# --- Step 1: Download from GCS to Local Workstation ---
mkdir -p "${LOCAL_TEMP_DIR}"
echo "Downloading ${CONFIG_FILE_NAME} from GCS..."
gsutil cp "${BUCKET_URL}${CONFIG_FILE_NAME}" "${OUTPUT_FILE}"
if [ $? -ne 0 ]; then echo "Error: GCS download failed." && rm -rf "${LOCAL_TEMP_DIR}" && exit 1; fi

# --- Step 2: Upload to Google Drive ---
echo "Uploading to Google Drive folder '${DRIVE_BACKUP_FOLDER}'..."

# Find the ID of the Drive folder. Create it if it doesn't exist.
# This assumes a 'gdrive' CLI tool is installed and authenticated.
DRIVE_FOLDER_ID=$(gdrive list --query "name = '${DRIVE_BACKUP_FOLDER}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false" --absolute --no-header | awk '{print $1}')

if [ -z "$DRIVE_FOLDER_ID" ]; then
  echo "Drive folder not found. Creating it..."
  DRIVE_FOLDER_ID=$(gdrive mkdir "${DRIVE_BACKUP_FOLDER}" | awk '{print $1}')
  if [ -z "$DRIVE_FOLDER_ID" ]; then echo "Error: Failed to create Drive folder." && rm -rf "${LOCAL_TEMP_DIR}" && exit 1; fi
fi

# Upload the file
gdrive upload --parent "${DRIVE_FOLDER_ID}" "${OUTPUT_FILE}"
if [ $? -ne 0 ]; then echo "Error: Drive upload failed." && rm -rf "${LOCAL_TEMP_DIR}" && exit 1; fi

echo "Backup successful!"

# --- Cleanup ---
rm -rf "${LOCAL_TEMP_DIR}"
```