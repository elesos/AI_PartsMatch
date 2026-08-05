import { useTranslation } from 'react-i18next'

export function PartNumberRail() {
  const { t } = useTranslation()
  return <div className="part-rail" aria-label={t('layout.railLabel')}>
    <span className="part-rail__label">{t('layout.rail')}</span>
    <div className="part-rail__track" aria-hidden="true">
      <code>{t('layout.oem')}</code><i /><code>{t('layout.machinePosition')}</code><i /><code>{t('layout.nameplate')}</code><i /><code>{t('layout.cross')}</code>
    </div>
  </div>
}
