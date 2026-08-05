import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Badge, Button } from '../components/ui'
import { getTicketStatus } from '../services/inquiryApi'
import { loadInquirySuccess } from '../services/inquiryContext'
import { getRuntimeConfig } from '../services/runtimeConfig'
import type { TicketResult, TicketSuccessSnapshot } from '../types/inquiry'
import { useTranslation } from 'react-i18next'

const statusTone = (status: string) => status === 'matched' || status === 'in_cart' ? 'success' : status === 'need_info' ? 'warning' : status === 'closed' ? 'danger' : 'caution'

export function InquirySuccessPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const routeSnapshot = location.state as TicketSuccessSnapshot | null
  const recovered = routeSnapshot?.ticket?.ticket_no ? routeSnapshot : loadInquirySuccess()
  const [ticket, setTicket] = useState<TicketResult | null>(recovered?.ticket ?? null)
  const [lookupError, setLookupError] = useState('')
  const [checking, setChecking] = useState(false)
  const ticketNo = ticket?.ticket_no
  const contacts = getRuntimeConfig().supportContacts
  const links = [
    ['WhatsApp', contacts.whatsappUrl], ['Zalo', contacts.zaloUrl], ['Telegram', contacts.telegramUrl],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]))

  useEffect(() => {
    if (!ticketNo) return
    const controller = new AbortController()
    void getTicketStatus(ticketNo, controller.signal).then(setTicket).catch(() => undefined)
    return () => controller.abort()
  }, [ticketNo])

  const lookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setChecking(true); setLookupError('')
    const ticketNo = String(new FormData(event.currentTarget).get('ticket_no') ?? '').trim().toUpperCase()
    try { setTicket(await getTicketStatus(ticketNo)) }
    catch { setLookupError(t('inquirySuccess.notFound')) }
    finally { setChecking(false) }
  }

  return <div className="inquiry-success-page">
    <section className="success-ticket"><div className="success-ticket__stamp" aria-hidden="true">✓</div><p className="eyebrow">{t('inquirySuccess.accepted')}</p><h1>{ticket ? t('inquirySuccess.queue') : t('inquirySuccess.lookup')}</h1>{ticket && <><p className="success-ticket__number"><span>{t('inquirySuccess.ticketNo')}</span><strong>{ticket.ticket_no}</strong></p><Badge tone={statusTone(ticket.status)}>{t(`inquirySuccess.statuses.${ticket.status}`, { defaultValue: ticket.status })}</Badge><p className="success-ticket__hint">{t('inquirySuccess.hint')}</p></>}</section>
    <div className="success-grid"><section className="success-panel"><p className="eyebrow">{t('inquirySuccess.progress')}</p><h2>{t('inquirySuccess.view')}</h2><form className="ticket-status-form" onSubmit={(event) => void lookup(event)}><label>{t('inquirySuccess.fullNo')}<input name="ticket_no" required maxLength={44} defaultValue={ticket?.ticket_no ?? ''} placeholder="MT-20260805-…" /></label><Button type="submit" variant="secondary" loading={checking}>{t('inquirySuccess.check')}</Button></form>{lookupError && <p className="inquiry-error" role="alert">{lookupError}</p>}{ticket && <dl className="ticket-status-data"><div><dt>{t('inquirySuccess.current')}</dt><dd>{t(`inquirySuccess.statuses.${ticket.status}`, { defaultValue: ticket.status })}</dd></div><div><dt>{t('inquirySuccess.contact')}</dt><dd>{ticket.contact_info}</dd></div><div><dt>{t('inquirySuccess.matched')}</dt><dd>{ticket.resolved_parts.length ? ticket.resolved_parts.map(part => `${part.part_no} × ${part.quantity}`).join(', ') : t('inquirySuccess.waiting')}</dd></div></dl>}</section>
      <section className="success-panel"><p className="eyebrow">{t('inquirySuccess.support')}</p><h2>{t('inquirySuccess.contactUs')}</h2>{links.length > 0 || contacts.wechatLabel ? <div className="support-contacts">{links.map(([label, href]) => <a key={label} href={href} target="_blank" rel="noopener noreferrer">{label}<span>↗</span></a>)}{contacts.wechatLabel && <p><b>WeChat</b><span>{contacts.wechatLabel}</span></p>}</div> : <p className="support-fallback">{t('inquirySuccess.fallback')}</p>}</section></div>
    <footer className="success-actions"><Link className="button button--secondary" to="/">{t('inquirySuccess.home')}</Link><Link className="button button--primary" to="/cart">{t('inquirySuccess.cart')}</Link></footer>
  </div>
}
