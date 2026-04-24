import type { ObjectDetection, ObjectState } from "@/contracts/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toObjectDetection(value: unknown): ObjectDetection | null {
  if (!isRecord(value)) return null;

  const className = value.class_name;
  const confidence = value.confidence;
  const bbox = value.bbox;

  if (typeof className !== "string") return null;
  if (typeof confidence !== "number") return null;
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  if (!bbox.every((coord) => typeof coord === "number")) return null;

  const classId = typeof value.class_id === "number" ? value.class_id : undefined;

  return {
    class_name: className,
    class_id: classId,
    confidence,
    bbox: [bbox[0], bbox[1], bbox[2], bbox[3]],
  };
}

function getRawDetections(data: Record<string, unknown>): unknown[] {
  if (Array.isArray(data.detected_objects)) return data.detected_objects;
  if (Array.isArray(data.objects)) return data.objects;
  return [];
}

function isObjectStatus(value: unknown): value is ObjectState["status"] {
  return value === "active" || value === "inactive" || value === "loading";
}

export function extractObjectDetections(data: Record<string, unknown>): ObjectDetection[] {
  return getRawDetections(data)
    .map(toObjectDetection)
    .filter((item): item is ObjectDetection => item !== null);
}

export function normalizeObjectState(data: Record<string, unknown>): ObjectState | null {
  if (!Array.isArray(data.detected_objects) && !Array.isArray(data.objects)) {
    return null;
  }

  const detectedObjects = extractObjectDetections(data);
  const active = typeof data.active === "boolean" ? data.active : detectedObjects.length > 0;
  const status = isObjectStatus(data.status) ? data.status : active ? "active" : "inactive";
  const stamp = typeof data.stamp === "number" ? data.stamp : Date.now() / 1000;

  return {
    stamp,
    active,
    detected_objects: detectedObjects,
    status,
  };
}
