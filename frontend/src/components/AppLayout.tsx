import { NavLink, Outlet } from 'react-router-dom'
import { PartNumberRail } from './PartNumberRail'
import { CartSummaryProvider, useCartSummary } from '../contexts/CartSummaryContext'
import { LocaleProvider, useLocale } from '../contexts/LocaleContext'
import { useTranslation } from 'react-i18next'

const navClass = ({ isActive }: { isActive: boolean }) => isActive ? 'nav-link nav-link--active' : 'nav-link'

const languageNames = { zh: '中文', en: 'English', vi: 'Tiếng Việt' }

function LayoutContent() {
  const { summary: cart } = useCartSummary()
  const { locale, changing, setLocale } = useLocale()
  const { t } = useTranslation()
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">{t('layout.skip')}</a>
    <header className="site-header">
      <div className="header-bar page-width">
        <NavLink className="brand" to="/" aria-label={t('layout.home')}>
          <svg className="brand__mark" viewBox="0 0 40 40" aria-hidden="true"><path d="M6 8h28v24H6z" /><path d="M12 14h16M12 20h10M12 26h13" /></svg>
          <span><b>PARTS<span>MATCH</span></b><small>{t('layout.tagline')}</small></span>
        </NavLink>
        <nav className="main-nav" aria-label={t('layout.nav')}>
          <NavLink className={navClass} to="/upload">{t('layout.image')}</NavLink>
          <NavLink className={navClass} to="/batch">{t('layout.batch')}</NavLink>
          <NavLink className={navClass} to="/inquiry">{t('layout.inquiry')}</NavLink>
        </nav>
        <div className="header-actions">
          <label className="language-select"><span className="sr-only">{t('layout.language')}</span><select value={locale} disabled={changing} aria-label={t('layout.language')} aria-busy={changing} onChange={(event) => void setLocale(event.target.value as keyof typeof languageNames)}>{Object.entries(languageNames).map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select></label>
          <NavLink className="cart-link" to="/cart"><span aria-hidden="true">▤</span> {t('layout.cart')} <span className="cart-count" aria-label={t('layout.cartCount', { count: cart.total_quantity })}>{cart.total_quantity > 99 ? '99+' : cart.total_quantity}</span></NavLink>
        </div>
      </div>
      <div className="page-width"><PartNumberRail /></div>
    </header>
    <main id="main-content" className="main-content page-width"><Outlet /></main>
    <footer className="site-footer">
      <div className="page-width footer-grid">
        <div><strong>{t('layout.clue')}</strong><p>{t('layout.clueText')}</p></div>
        <NavLink className="support-link" to="/inquiry">{t('layout.support')} <span aria-hidden="true">→</span></NavLink>
        <small>{t('layout.copyright')}</small>
      </div>
    </footer>
  </div>
}

export function AppLayout() {
  return <LocaleProvider><CartSummaryProvider><LayoutContent /></CartSummaryProvider></LocaleProvider>
}
