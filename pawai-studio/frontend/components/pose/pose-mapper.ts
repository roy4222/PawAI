const POSE_LABELS: Record<string, string> = {
  standing: '站立',
  sitting: '坐著',
  crouching: '蹲下',
  bending: '彎腰',
  hands_on_hips: '手插腰',
  kneeling_one_knee: '單膝跪地',
  fallen: '跌倒',
  unknown: '未知',
}

const POSE_EMOJI: Record<string, string> = {
  standing: '🧍',
  sitting: '🪑',
  crouching: '🏋️',
  bending: '🙇',
  hands_on_hips: '🦸',
  kneeling_one_knee: '🧎',
  fallen: '⚠️',
  unknown: '🧍',
}

export function normalizePoseKey(pose: string | null | undefined): string {
  return (pose ?? '')
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
    .replace(/_+/g, '_')
}

export function getPoseLabel(pose: string | null | undefined): string {
  const key = normalizePoseKey(pose)
  if (!key) return '尚未偵測'

  const mapped = POSE_LABELS[key]
  if (mapped) return mapped

  const raw = (pose ?? '').trim()
  return raw ? `未知姿勢（${raw}）` : '尚未偵測'
}

export function getPoseEmoji(pose: string | null | undefined): string {
  const key = normalizePoseKey(pose)
  if (!key) return '🧍'
  return POSE_EMOJI[key] ?? '🧍'
}

export function getPoseStyle(pose: string | null | undefined): string {
  const key = normalizePoseKey(pose)
  if (key === 'fallen') return 'text-red-400'
  if (
    key === 'crouching' ||
    key === 'bending' ||
    key === 'kneeling_one_knee'
  ) {
    return 'text-amber-300'
  }
  return 'text-emerald-300'
}

export function isFallenPose(pose: string | null | undefined): boolean {
  return normalizePoseKey(pose) === 'fallen'
}
