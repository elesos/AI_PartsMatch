import { useState } from 'react'
import { useCartSummary } from '../contexts/CartSummaryContext'
import { addDirectPart, addMatchedPart } from '../services/resultsApi'
import { showToast } from '../stores/toast'
import type { MatchStatus } from '../types/home'
import { Button, Modal } from './ui'
import { useTranslation } from 'react-i18next'

interface Props {
  partId: string
  queryId?: string | null
  confidence?: number
  matchStatus?: MatchStatus
  safetyRisk?: boolean
  needManual?: boolean
  disabled?: boolean
  disabledReason?: string
}

const apiMatchStatus = (status: MatchStatus): Exclude<MatchStatus, 'low'> => status === 'low' ? 'insufficient' : status

export function AddToCartButton({ partId, queryId, confidence, matchStatus = 'exact', safetyRisk = false, needManual = false, disabled, disabledReason }: Props) {
  const { t } = useTranslation()
  const [pending, setPending] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const { refresh } = useCartSummary()
  const needsConfirm = (confidence != null && confidence < .7) || safetyRisk || needManual || matchStatus === 'insufficient' || matchStatus === 'not_found'

  const add = async () => {
    if (pending) return
    setPending(true)
    try {
      if (confidence != null) await addMatchedPart({ part_id: partId, query_id: queryId, match_status: apiMatchStatus(matchStatus), confidence })
      else await addDirectPart(partId)
      showToast(t('cartAction.added'), 'success')
      await refresh()
      setConfirming(false)
    } catch (error) {
      showToast(error instanceof Error ? error.message : t('cartAction.failed'), 'error')
    } finally { setPending(false) }
  }

  return <>
    <Button onClick={() => needsConfirm ? setConfirming(true) : void add()} disabled={disabled} loading={pending} title={disabled ? disabledReason : undefined}>{pending ? t('cartAction.adding') : t('cartAction.add')}</Button>
    <Modal open={confirming} onClose={() => { if (!pending) setConfirming(false) }} title={t('cartAction.confirmTitle')} footer={<><Button variant="secondary" onClick={() => setConfirming(false)} disabled={pending}>{t('cartAction.keepOut')}</Button><Button onClick={() => void add()} loading={pending}>{t('cartAction.confirmAdd')}</Button></>}>
      <p>{t('cartAction.riskText')}</p>
    </Modal>
  </>
}
