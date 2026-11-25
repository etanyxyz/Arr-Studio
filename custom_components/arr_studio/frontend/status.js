/**
 * Arr Studio frontend - queue item phase.
 *
 * Maps the arr queue record's `status` (QueueStatus) and `state`
 * (TrackedDownloadState) fields to a UI phase with a display label:
 *
 *   blocked  - download finished, import is blocked (needs attention)
 *   failed   - download or import failed
 *   import   - import in progress
 *   wait     - download finished, waiting for import
 *   done     - import finished
 *   download - download in progress
 *   other    - anything else (queued, paused, delay, ...)
 *
 * Both fields may be absent or unknown; the fallback shows the raw status.
 */

const STATUS_LABEL = {
  downloadclientunavailable: "Client unavailable",
  fallback: "Fallback",
};

export function queuePhase(item) {
  const status = String((item && item.status) || "unknown").toLowerCase();
  const state = String((item && item.state) || "").toLowerCase();
  if (state === "importblocked") {
    return { phase: "blocked", label: "Import blocked" };
  }
  if (state === "failed" || state === "failedpending") {
    return { phase: "failed", label: "Import failed" };
  }
  if (state === "importing") {
    return { phase: "import", label: "Importing" };
  }
  if (state === "imported") {
    return { phase: "done", label: "Imported" };
  }
  if (state === "importpending") {
    return { phase: "wait", label: "Waiting for import" };
  }
  if (status === "failed") {
    return { phase: "failed", label: "Download failed" };
  }
  if (status === "completed") {
    return { phase: "wait", label: "Waiting for import" };
  }
  if (state === "downloading" || status === "downloading") {
    return { phase: "download", label: "Downloading" };
  }
  const label = STATUS_LABEL[status] || status.charAt(0).toUpperCase() + status.slice(1);
  return { phase: "other", label };
}
