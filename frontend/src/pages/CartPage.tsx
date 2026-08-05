import { useCallback, useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { PartImageView, valueText } from '../components/PartMedia'
import { ErrorState, LoadingState } from '../components/status/AsyncState'
import { Badge, Button, Input, Modal } from '../components/ui'
import { useCartSummary } from '../contexts/CartSummaryContext'
import { deleteCartItem, getCart, submitCart, updateCartQuantity } from '../services/cartApi'
import { showToast } from '../stores/toast'
import type { CartDetails, CartItem, CommunicationTool, InquiryPayload, InquiryResult } from '../types/cart'
import { useTranslation } from 'react-i18next'

const emptyCart: CartDetails = { total_items: 0, total_quantity: 0, total_amount: 0, need_confirm_count: 0, items: [] }
const matchTones: Record<CartItem['match_status'], 'success' | 'warning' | 'caution' | 'danger'> = {
  exact: 'success', high: 'success', multiple: 'warning', insufficient: 'caution', not_found: 'danger',
}
const toolLabels: Record<CommunicationTool, string> = {
  wechat: '微信 / WeChat', whatsapp: 'WhatsApp', zalo: 'Zalo', telegram: 'Telegram', phone: '电话', email: '电子邮箱', other: '其他',
}

function QuantityEditor({ item, onSaved }: { item: CartItem; onSaved: (quantity: number) => void }) {
  const { t } = useTranslation()
  const [value, setValue] = useState(String(item.quantity))
  const [pending, setPending] = useState(false)

  const save = async (candidate: number) => {
    const quantity = Math.max(1, Math.floor(candidate || 1))
    setValue(String(quantity))
    if (quantity === item.quantity || pending) return
    setPending(true)
    try {
      await updateCartQuantity(item.id, quantity)
      onSaved(quantity)
      showToast(t('cart.saved'), 'success')
    } catch (error) {
      setValue(String(item.quantity))
      showToast(error instanceof Error ? error.message : t('cart.saveFailed'), 'error')
    } finally { setPending(false) }
  }
  const step = (delta: number) => void save(Math.max(1, item.quantity + delta))
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur() }
  }
  return <div className="quantity-editor" aria-label={`${item.name} ${t('cart.quantity')}`}>
    <button type="button" aria-label={t('cart.decrease')} disabled={pending || item.quantity <= 1} onClick={() => step(-1)}>−</button>
    <input aria-label={t('cart.quantity')} type="number" inputMode="numeric" min="1" value={value} disabled={pending}
      onChange={(event) => setValue(event.target.value)} onKeyDown={onKeyDown}
      onBlur={() => void save(Number(value))} />
    <button type="button" aria-label={t('cart.increase')} disabled={pending} onClick={() => step(1)}>+</button>
    <span className="quantity-status" role="status">{pending ? t('cart.saving') : ''}</span>
  </div>
}

function EmptyCart() {
  const { t } = useTranslation()
  return <section className="cart-empty">
    <div className="cart-empty__part" aria-hidden="true"><i /><i /><i /><span>0</span></div>
    <p className="eyebrow">{t('cart.emptyCode')}</p><h2>{t('cart.emptyTitle')}</h2>
    <p>{t('cart.emptyText')}</p>
    <Link className="button button--primary" to="/">{t('cart.search')}</Link>
  </section>
}

export function CartPage() {
  const { t, i18n } = useTranslation()
  const [cart, setCart] = useState<CartDetails>(emptyCart)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState<CartItem | null>(null)
  const [deletePending, setDeletePending] = useState(false)
  const [inquiryOpen, setInquiryOpen] = useState(false)
  const [submitPending, setSubmitPending] = useState(false)
  const [submitted, setSubmitted] = useState<InquiryResult | null>(null)
  const { sync } = useCartSummary()
  const money = (amount: number) => new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'CNY' }).format(amount)
  const fitmentText = (item: CartItem) => item.fitments.length ? item.fitments.map((fitment) => [fitment.brand, fitment.model, fitment.engine_model].filter(Boolean).join(' ')).join('; ') : t('cart.noFitment')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { const result = await getCart(); setCart(result); sync(result) }
    catch (loadError) { setError(loadError instanceof Error ? loadError.message : t('common.loadError')) }
    finally { setLoading(false) }
  }, [sync, t])
  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const applyItems = (items: CartItem[]) => {
    const next = {
      items,
      total_items: items.length,
      total_quantity: items.reduce((total, item) => total + item.quantity, 0),
      total_amount: Number(items.reduce((total, item) => total + item.subtotal, 0).toFixed(2)),
      need_confirm_count: items.filter((item) => item.need_confirm).length,
    }
    setCart(next); sync(next)
  }
  const quantitySaved = (id: string, quantity: number) => applyItems(cart.items.map((item) =>
    item.id === id ? { ...item, quantity, subtotal: Number((item.unit_price * quantity).toFixed(2)) } : item))
  const remove = async () => {
    if (!deleting || deletePending) return
    setDeletePending(true)
    try {
      await deleteCartItem(deleting.id)
      applyItems(cart.items.filter((item) => item.id !== deleting.id))
      setDeleting(null); showToast(t('cart.removed'), 'success')
    } catch (deleteError) { showToast(deleteError instanceof Error ? deleteError.message : t('cart.removeFailed'), 'error') }
    finally { setDeletePending(false) }
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitPending || submitted) return
    const form = new FormData(event.currentTarget)
    const payload: InquiryPayload = {
      contact_name: String(form.get('contact_name') ?? '').trim(),
      country: String(form.get('country') ?? '').trim() || null,
      contact_method: String(form.get('contact_method') ?? '').trim(),
      communication_tool: String(form.get('communication_tool')) as CommunicationTool,
      note: String(form.get('note') ?? '').trim() || null,
    }
    if (!payload.contact_name || !payload.contact_method) return
    setSubmitPending(true)
    try { setSubmitted(await submitCart(payload)); showToast(t('cart.submitted'), 'success') }
    catch (submitError) { showToast(submitError instanceof Error ? submitError.message : t('common.requestFailed'), 'error') }
    finally { setSubmitPending(false) }
  }
  const closeInquiry = () => { if (!submitPending) { setInquiryOpen(false); setSubmitted(null) } }

  if (loading) return <LoadingState />
  if (error) return <ErrorState description={error} onRetry={() => void load()} />
  return <div className={`cart-page ${cart.items.length ? 'cart-page--with-summary' : ''}`}>
    <header className="cart-heading">
      <div><p className="eyebrow">{t('cart.eyebrow')}</p><h1>{t('cart.title')}</h1><p className="page-lead">{t('cart.intro')}</p></div>
      <div className="cart-heading__count"><b>{cart.total_quantity}</b><span>{t('cart.pending')}</span></div>
    </header>
    {!cart.items.length ? <EmptyCart /> : <>
      <section className="cart-list" aria-label={t('cart.list')}>
        {cart.items.map((item) => <article className="cart-item" key={item.id}>
          <PartImageView image={item.image ?? undefined} alt={item.name} className="cart-item__image" />
          <div className="cart-item__identity">
            <div className="cart-item__title"><div><p className="eyebrow">{valueText(item.brand)} / {valueText(item.category)}</p><h2>{item.name}</h2></div>
              <div className="cart-item__badges"><Badge tone={matchTones[item.match_status]}>{t(`cart.statuses.${item.match_status}`)}</Badge>{item.need_confirm && <Badge tone="caution">{t('cart.statuses.confirm')}</Badge>}</div>
            </div>
            <dl className="cart-identifiers"><div><dt>PART NUMBER</dt><dd>{item.part_no}</dd></div><div><dt>OEM</dt><dd>{valueText(item.oem)}</dd></div><div><dt>{t('detail.device')}</dt><dd>{fitmentText(item)}</dd></div></dl>
          </div>
          <div className="cart-item__commerce">
            <div><span>{t('cart.unitPrice')}</span><strong>{money(item.unit_price)}</strong></div>
            <QuantityEditor item={item} onSaved={(quantity) => quantitySaved(item.id, quantity)} />
            <div><span>{t('cart.subtotal')}</span><strong>{money(item.subtotal)}</strong></div>
            <Button variant="ghost" className="cart-remove" onClick={() => setDeleting(item)}>{t('cart.remove')}</Button>
          </div>
        </article>)}
      </section>
      <aside className="cart-summary" aria-label={t('cart.summary')}>
        <div className="cart-summary__safety"><span aria-hidden="true">!</span><p><strong>{t('cart.safety')}</strong>{cart.need_confirm_count ? t('cart.confirmCount', { count: cart.need_confirm_count }) : ''}{t('cart.safetyText')}</p></div>
        <dl><div><dt>{t('cart.total')}</dt><dd>{cart.total_quantity}</dd></div><div><dt>{t('cart.estimated')}</dt><dd>{money(cart.total_amount)}</dd></div></dl>
        <div className="cart-summary__action"><Button onClick={() => setInquiryOpen(true)}>{t('cart.submit')}</Button><small>{t('cart.noPaymentShort')}</small></div>
      </aside>
    </>}
    <Modal open={Boolean(deleting)} onClose={() => { if (!deletePending) setDeleting(null) }} title={t('cart.removeTitle')} footer={<><Button variant="secondary" disabled={deletePending} onClick={() => setDeleting(null)}>{t('cart.keep')}</Button><Button variant="danger" loading={deletePending} onClick={() => void remove()}>{t('cart.confirmRemove')}</Button></>}>
      <p>{t('cart.removeText', { name: deleting?.name })}</p>
    </Modal>
    <Modal open={inquiryOpen} onClose={closeInquiry} title={submitted ? t('cart.submitted') : t('cart.submit')} footer={submitted ? <Button onClick={closeInquiry}>{t('common.done')}</Button> : undefined}>
      {submitted ? <div className="inquiry-success" role="status"><span aria-hidden="true">✓</span><p>{t('cart.orderNo')}</p><strong>{submitted.order_no}</strong><small>{t('cart.orderStatus', { status: submitted.status })}</small></div> : <form className="inquiry-form" onSubmit={submit}>
        <div className="payment-notice"><strong>{t('cart.quoteOnly')}</strong><span>{t('cart.noPayment')}</span></div>
        <Input label={t('cart.contact')} name="contact_name" required maxLength={100} autoComplete="name" />
        <Input label={t('cart.country')} name="country" maxLength={100} autoComplete="country-name" hint={t('cart.countryHint')} />
        <label className="field"><span className="field__label">{t('cart.tool')}</span><select className="field__control" name="communication_tool" defaultValue="wechat">{Object.entries(toolLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <Input label={t('cart.contactMethod')} name="contact_method" required maxLength={255} hint={t('cart.contactHint')} />
        <label className="field"><span className="field__label">{t('cart.note')}</span><textarea className="field__control inquiry-form__note" name="note" maxLength={2000} rows={4} placeholder={t('cart.notePlaceholder')} /></label>
        <Button type="submit" loading={submitPending}>{t('cart.submit')}</Button>
      </form>}
    </Modal>
  </div>
}
