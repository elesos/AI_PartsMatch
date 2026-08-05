import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input } from '../components/ui'
import { useLocale } from '../contexts/LocaleContext'
import { downloadBatchTemplate, getCategories, getHotMachines, searchParts } from '../services/homeApi'
import { clearSearchHistory, readSearchHistory, saveSearchHistory } from '../services/searchHistory'
import type { Category, HotMachine, SearchHistoryItem, SearchMode } from '../types/home'
import { useTranslation } from 'react-i18next'

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { locale } = useLocale()
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('auto')
  const [error, setError] = useState('')
  const [searching, setSearching] = useState(false)
  const [history, setHistory] = useState<SearchHistoryItem[]>(readSearchHistory)
  const [categories, setCategories] = useState<Category[]>([])
  const [machines, setMachines] = useState<HotMachine[]>([])
  const [catalogueLoading, setCatalogueLoading] = useState(true)
  const [catalogueError, setCatalogueError] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const modes: { value: SearchMode; label: string; placeholder: string; hint: string }[] = (['auto', 'part_no', 'machine', 'engine'] as const).map(value => ({
    value, label: t(`home.modes.${value}.label`), placeholder: t(`home.modes.${value}.placeholder`), hint: t(`home.modes.${value}.hint`),
  }))
  const selectedMode = modes.find(item => item.value === mode) ?? modes[0]
  const messageOf = (reason: unknown) => reason instanceof Error ? reason.message : t('common.requestFailed')

  const loadCatalogue = useCallback(async () => {
    setCatalogueLoading(true)
    setCatalogueError(false)
    const [categoryResult, machineResult] = await Promise.allSettled([getCategories(), getHotMachines()])
    if (categoryResult.status === 'fulfilled') setCategories(categoryResult.value)
    if (machineResult.status === 'fulfilled') setMachines(machineResult.value)
    if (categoryResult.status === 'rejected' || machineResult.status === 'rejected') setCatalogueError(true)
    setCatalogueLoading(false)
  }, [])

  useEffect(() => { void Promise.resolve().then(loadCatalogue) }, [loadCatalogue])

  const runSearch = async (rawQuery = query, searchMode = mode) => {
    const normalized = rawQuery.trim()
    setQuery(rawQuery)
    setMode(searchMode)
    if (!normalized) {
      setError(t('home.required'))
      return
    }
    if (normalized.length > 500) {
      setError(t('home.tooLong'))
      return
    }
    setSearching(true)
    setError('')
    try {
      const result = await searchParts(normalized, searchMode, locale)
      setHistory(saveSearchHistory({ query: normalized, type: searchMode }))
      const params = new URLSearchParams({ q: normalized, type: searchMode, lang: locale })
      navigate(`/search?${params}`, { state: { prefetchedResult: result, query: normalized, type: searchMode, lang: locale } })
    } catch (requestError) {
      setError(messageOf(requestError))
    } finally { setSearching(false) }
  }

  const submit = (event: FormEvent) => { event.preventDefault(); void runSearch() }
  const selectMode = (nextMode: SearchMode) => { setMode(nextMode); setError('') }

  const downloadTemplate = async () => {
    setDownloading(true)
    setDownloadError('')
    try { await downloadBatchTemplate(locale) }
    catch (requestError) { setDownloadError(messageOf(requestError)) }
    finally { setDownloading(false) }
  }

  return <div className="home-page">
    <section className="search-workbench" aria-labelledby="home-title">
      <div className="workbench-copy">
        <p className="eyebrow">{t('home.eyebrow')}</p>
        <h1 id="home-title">{t('home.title1')}<br />{t('home.title2')}</h1>
        <p>{t('home.intro')}</p>
        {history.length > 0 && <div className="search-history" aria-label={t('home.recent')}>
          <div className="section-heading"><strong>{t('home.recent')}</strong><button type="button" onClick={() => { clearSearchHistory(); setHistory([]) }}>{t('home.clear')}</button></div>
          <ul>{history.map(item => <li key={`${item.type}:${item.query}`}><button type="button" onClick={() => void runSearch(item.query, item.type)} disabled={searching}><span>{item.query}</span><small>{modes.find(entry => entry.value === item.type)?.label}</small></button></li>)}</ul>
        </div>}
      </div>
      <form className="search-console" onSubmit={submit} noValidate>
        <div className="console-label"><span>{t('home.quick')}</span><code>INPUT / PART CLUE</code></div>
        <div className="search-tabs" role="tablist" aria-label={t('home.methods')}>
          {modes.map(item => <button key={item.value} type="button" role="tab" aria-selected={mode === item.value} aria-controls="search-panel" id={`search-tab-${item.value}`} onClick={() => selectMode(item.value)}>{item.label}</button>)}
        </div>
        <div id="search-panel" role="tabpanel" aria-labelledby={`search-tab-${mode}`}>
          <Input label={t('home.clue')} placeholder={selectedMode.placeholder} value={query} onChange={(event) => { setQuery(event.target.value); if (error) setError('') }} hint={selectedMode.hint} error={error} autoComplete="off" maxLength={501} />
          <Button type="submit" loading={searching}>{searching ? t('home.matching') : t('home.match')} <span aria-hidden="true">→</span></Button>
        </div>
        <div className="alternate-actions" aria-label={t('home.also')}>
          <span>{t('home.also')}</span>
          <button type="button" onClick={() => navigate('/upload')}>{t('home.photo')}</button>
          <button type="button" onClick={() => navigate('/upload?type=nameplate')}>{t('home.nameplate')}</button>
          <button type="button" onClick={() => navigate('/batch')}>{t('home.excel')}</button>
          <button type="button" onClick={() => navigate('/inquiry')}>{t('home.support')}</button>
        </div>
        <div className="template-action">
          <Button type="button" variant="secondary" loading={downloading} onClick={() => void downloadTemplate()}>{downloading ? t('home.downloading') : t('home.download')}</Button>
          {downloadError && <p role="alert">{downloadError}</p>}
        </div>
      </form>
    </section>

    <section className="quick-navigation" aria-labelledby="quick-title">
      <div className="quick-navigation__header"><div><p className="eyebrow">{t('home.catalogueEyebrow')}</p><h2 id="quick-title">{t('home.catalogueTitle')}</h2></div>{catalogueError && <button type="button" onClick={() => void loadCatalogue()}>{t('home.reload')}</button>}</div>
      {catalogueLoading && <p className="catalogue-status" role="status">{t('home.loadingShortcuts')}</p>}
      {catalogueError && <p className="catalogue-status catalogue-status--error" role="alert">{t('home.shortcutError')}</p>}
      {!catalogueLoading && <div className="quick-navigation__grid">
        <div><h3>{t('home.categories')}</h3>{categories.length ? <ul className="category-list">{categories.map(category => <li key={category.id}><button type="button" onClick={() => void runSearch(category.name, 'auto')}><span>{category.name}</span><small>{t('home.categoryItems', { count: category.part_count })}</small></button>{category.children.length > 0 && <div>{category.children.map(child => <button type="button" key={child.id} onClick={() => void runSearch(child.name, 'auto')}>{child.name}</button>)}</div>}</li>)}</ul> : <p className="empty-copy">{t('home.noCategories')}</p>}</div>
        <div><h3>{t('home.machines')}</h3>{machines.length ? <ul className="machine-list">{machines.map(machine => <li key={machine.id}><button type="button" onClick={() => void runSearch(`${machine.brand} ${machine.model}`, 'machine')}><strong>{machine.model}</strong><span>{machine.brand} · {t('home.fittings', { count: machine.part_count })}</span></button></li>)}</ul> : <p className="empty-copy">{t('home.noMachines')}</p>}</div>
      </div>}
    </section>
  </div>
}
