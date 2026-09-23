import {
  ArrowRight,
  CalendarCheck2,
  Check,
  CircleHelp,
  CircleSlash2,
  FolderSearch,
  Info,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react'
import { dateLabel, money, plural, reasonLabels } from '../domain/selection'
import type { Recommendation, SelectionRequest, SelectionResponse } from '../domain/selection'
import { ContractorCard } from './ContractorCard'

export function Results({
  result,
  loading,
  error,
  stale,
  savedIds,
  comparedIds,
  onSave,
  onCompare,
  onProfile,
  onRetry,
  onEdit,
  onAlternative,
  demo,
}: {
  result: SelectionResponse | null
  loading: boolean
  error: string | null
  stale: boolean
  savedIds: string[]
  comparedIds: string[]
  onSave: (card: Recommendation) => void
  onCompare: (id: string) => void
  onProfile: (card: Recommendation) => void
  onRetry: () => void
  onEdit: () => void
  onAlternative: (patch: Partial<SelectionRequest>) => void
  demo: boolean
}) {
  return (
    <section className="results-column" aria-labelledby="results-heading" aria-busy={loading}>
      <div className="results-heading">
        <div>
          <span className="section-eyebrow">ПОДБОР С ОБЪЯСНЕНИЕМ</span>
          <h2 id="results-heading">
            Ваша короткая подборка
            {result?.status === 'MATCHED' && !loading && (
              <span className="result-count">{result.recommendations.length}</span>
            )}
          </h2>
        </div>
        <span className="limit-label">До 3 вариантов</span>
      </div>
      <p className="results-intro">
        Только подходящие по условиям. И понятные причины для каждого.
      </p>
      {loading ? (
        <>
          <div className="search-progress" role="status">
            <span className="spinner" />
            Проверяем календарь, бюджет и условия…
          </div>
          <div className="cards-grid">
            {[0, 1, 2].map((n) => (
              <div className="skeleton-card" key={n}>
                <div />
                <span />
                <span />
                <p />
                <p />
              </div>
            ))}
          </div>
        </>
      ) : error ? (
        <div className="empty-state error-state" role="alert">
          <div className="empty-symbol">
            <RefreshCw size={30} />
          </div>
          <span className="state-label">ТЕХНИЧЕСКАЯ ОШИБКА</span>
          <h3>Не удалось завершить подбор</h3>
          <p>{error}</p>
          <p className="empty-note">Это не означает, что подходящих подрядчиков нет.</p>
          <button className="primary-button" onClick={onRetry}>
            <RefreshCw size={16} />
            Повторить попытку
          </button>
        </div>
      ) : !result ? (
        <div className="empty-state">
          <div className="empty-symbol">
            <Search size={32} />
          </div>
          <span className="state-label">ВСЁ НАЧИНАЕТСЯ С ВАШИХ ПЛАНОВ</span>
          <h3>Расскажите о мероприятии</h3>
          <p>
            Укажите условия в форме — покажем до трёх подрядчиков и объясним, почему они подходят.
          </p>
          <button className="primary-button" onClick={onEdit}>
            Заполнить параметры <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <>
          <div className="request-summary">
            <span>{result.request.city}</span>
            <span>{dateLabel(result.request.event_date)}</span>
            <span>{result.request.category}</span>
            <span>{result.request.event_format}</span>
            <span>до {money(result.request.budget_kzt)}</span>
            {result.request.language && <span>{result.request.language}</span>}
            {result.request.duration_hours !== null && (
              <span>{result.request.duration_hours} ч</span>
            )}
          </div>
          {stale && (
            <div className="stale-notice" role="status">
              <Info size={18} />
              <p>Условия изменены. Ниже — предыдущая подборка.</p>
              <button onClick={onRetry}>
                Обновить <RefreshCw size={14} />
              </button>
            </div>
          )}
          {result.status === 'MATCHED' ? (
            <>
              <div className="matched-status">
                <span>
                  <span className="status-dot" />
                  Подобрали {result.recommendations.length}{' '}
                  {plural(result.recommendations.length, ['вариант', 'варианта', 'вариантов'])}
                </span>
                <span>
                  <CalendarCheck2 size={14} />
                  Свободны по календарю на {dateLabel(result.request.event_date)}
                </span>
              </div>
              {result.eligible_count < 3 && (
                <div className="limited-notice">
                  <Info size={19} />
                  <div>
                    <strong>
                      Подходящих {result.eligible_count === 1 ? 'только один' : 'только два'} —
                      показываем сколько есть
                    </strong>
                    <p>
                      В этой категории и городе {result.catalog_count}{' '}
                      {plural(result.catalog_count, ['профиль', 'профиля', 'профилей'])}.
                      {result.exclusions.length
                        ? ` Не прошли условия: ${result.exclusions.map((item) => `${reasonLabels[item.code].toLowerCase()} — ${item.count}`).join('; ')}.`
                        : ' Все доступные профили уже в подборке.'}{' '}
                      Не добавляем варианты, которые вам не подходят.
                    </p>
                  </div>
                </div>
              )}
              <div className="cards-grid">
                {result.recommendations.map((card, index) => (
                  <ContractorCard
                    key={card.contractor.id}
                    card={card}
                    index={index}
                    saved={savedIds.includes(card.contractor.id)}
                    compared={comparedIds.includes(card.contractor.id)}
                    onSave={() => onSave(card)}
                    onCompare={() => onCompare(card.contractor.id)}
                    onProfile={() => onProfile(card)}
                  />
                ))}
              </div>
              <div className="result-disclaimer">
                <Info size={15} />
                <p>
                  Указана стартовая цена. Итоговая стоимость зависит от деталей заказа.
                  <br />
                  Доступность проверена по календарю каталога, бронирование не оформляется.
                </p>
              </div>
              <details className="selection-summary">
                <summary>
                  <SlidersHorizontal size={15} />
                  Как сократили список
                  <span>
                    {result.catalog_count} → {result.eligible_count} →{' '}
                    {result.recommendations.length}
                  </span>
                </summary>
                <div>
                  <p>
                    В городе и категории: <strong>{result.catalog_count}</strong>. После строгих
                    условий: <strong>{result.eligible_count}</strong>. В подборке:{' '}
                    <strong>{result.recommendations.length}</strong>.
                  </p>
                  {result.exclusions.length > 0 && (
                    <ul>
                      {result.exclusions.map((item) => (
                        <li key={item.code}>
                          {reasonLabels[item.code]}
                          <strong>{item.count}</strong>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="muted">
                    Каждый исключённый профиль учтён один раз — по первому неподходящему условию.{' '}
                    {result.request.preferences
                      ? demo
                        ? 'Пожелания в демо сопоставляются по ключевым словам, затем учитываются цена и ID.'
                        : 'Порядок и объяснения получены от сервиса подбора.'
                      : 'Без пожеланий порядок определяется ценой «от», затем стабильным ID.'}
                  </p>
                </div>
              </details>
            </>
          ) : (
            <div
              className={`empty-state ${result.status === 'CATEGORY_ABSENT' ? 'category-absent' : 'no-match'}`}
            >
              <div className="empty-symbol">
                {result.status === 'CATEGORY_ABSENT' ? (
                  <FolderSearch size={34} />
                ) : (
                  <CircleSlash2 size={32} />
                )}
              </div>
              <span className="state-label">
                {result.status === 'CATEGORY_ABSENT'
                  ? 'КАТЕГОРИИ НЕТ В КАТАЛОГЕ'
                  : 'КАНДИДАТЫ ЕСТЬ, НО НЕ ПОДХОДЯТ'}
              </span>
              <h3>
                {result.status === 'CATEGORY_ABSENT'
                  ? 'Пока нет такой категории в этом городе'
                  : 'Никто не прошёл все условия'}
              </h3>
              <p>
                {result.status === 'CATEGORY_ABSENT'
                  ? `В каталоге нет профилей категории «${result.request.category}» для города ${result.request.city}. Попробуйте другую категорию или город.`
                  : `Проверили ${result.catalog_count} ${plural(result.catalog_count, ['профиль', 'профиля', 'профилей'])} в категории «${result.request.category}», но ни один не соответствует вашему запросу.`}
              </p>
              {result.exclusions.length > 0 && (
                <div className="exclusion-list">
                  {result.exclusions.map((item) => (
                    <div key={item.code}>
                      <span>{reasonLabels[item.code]}</span>
                      <strong>{item.count}</strong>
                    </div>
                  ))}
                  <small>Каждый профиль учтён по первому неподходящему условию.</small>
                </div>
              )}
              {result.alternatives.length > 0 && (
                <div className="alternatives">
                  <h4>Небольшое изменение — новые варианты</h4>
                  <p>Проверили эти условия на том же каталоге:</p>
                  {result.alternatives.map((alternative, index) => (
                    <button key={index} onClick={() => onAlternative(alternative.patch)}>
                      <span>
                        {alternative.label}
                        <small>
                          {alternative.match_count}{' '}
                          {plural(alternative.match_count, [
                            'подходящий профиль',
                            'подходящих профиля',
                            'подходящих профилей',
                          ])}
                        </small>
                      </span>
                      <ArrowRight size={17} />
                    </button>
                  ))}
                </div>
              )}
              <button className="secondary-button" onClick={onEdit}>
                <SlidersHorizontal size={16} />
                Изменить параметры
              </button>
            </div>
          )}
        </>
      )}
      <div className="trust-strip">
        <div>
          <ShieldCheck size={22} />
          <span>
            <strong>Сначала условия</strong>
            <small>Дата, бюджет и формат</small>
          </span>
        </div>
        <div>
          <Sparkles size={22} />
          <span>
            <strong>Затем ваши пожелания</strong>
            <small>Внимание к деталям запроса</small>
          </span>
        </div>
        <div>
          <CircleHelp size={22} />
          <span>
            <strong>Всегда с объяснением</strong>
            <small>Факты из профиля и календаря</small>
          </span>
        </div>
      </div>
      <div className="editorial-note">
        <span className="editorial-mark">“</span>
        <div>
          <h3>Хороший выбор начинается с понимания.</h3>
          <p>
            Мы помогаем заметить различия между подходящими людьми — чтобы последнее слово всегда
            оставалось за вами.
          </p>
        </div>
        <Check size={24} />
      </div>
    </section>
  )
}
