export type ConfidenceTone = 'success' | 'warning' | 'caution' | 'danger'

export const confidenceTone = (confidence: number): ConfidenceTone => {
  if (confidence >= 90) return 'success'
  if (confidence >= 70) return 'warning'
  if (confidence >= 40) return 'caution'
  return 'danger'
}
