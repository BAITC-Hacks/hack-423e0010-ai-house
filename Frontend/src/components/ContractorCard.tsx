import { ArrowUpRight, Check, ChevronDown, Heart, MapPin, Scale, Sparkles } from 'lucide-react'
import { dateLabel, money } from '../domain/selection'
import type { Recommendation } from '../domain/selection'
import { Artwork } from './Artwork'

export function Evidence({ card }: { card: Recommendation }) {
  return (
    <details className="evidence">
      <summary>
        На чём основан выбор <ChevronDown size={15} />
      </summary>
      <dl>
        {card.evidence.map((fact, index) => (
          <div key={`${fact.label}-${index}`}>
            <dt>{fact.label}</dt>
            <dd>
              {fact.value}
              <small>{fact.source}</small>
            </dd>
          </div>
        ))}
      </dl>
    </details>
  )
}
export function ContractorCard({
  card,
  index,
  saved,
  compared,
  onSave,
  onCompare,
  onProfile,
}: {
  card: Recommendation
  index: number
  saved: boolean
  compared: boolean
  onSave: () => void
  onCompare: () => void
  onProfile: () => void
}) {
  const profile = card.contractor
  return (
    <article className="contractor-card" style={{ animationDelay: `${index * 70}ms` }}>
      <div className="card-visual">
        <Artwork palette={profile.artwork} name={profile.name} category={profile.category} />
        <span className="card-category">{profile.category}</span>
        <button
          className={`favorite-button ${saved ? 'is-saved' : ''}`}
          aria-label={`${saved ? 'Убрать из избранного' : 'В избранное'}: ${profile.name}`}
          aria-pressed={saved}
          onClick={onSave}
        >
          <Heart size={18} fill={saved ? 'currentColor' : 'none'} />
        </button>
      </div>
      <div className="card-content">
        <div className="card-location">
          <MapPin size={12} />
          {profile.city}
          <span>•</span>
          <span>
            {profile.origin === 'demo'
              ? 'Демо-профиль'
              : profile.origin === 'synthetic'
                ? 'Синтетический профиль'
                : 'Из каталога'}
          </span>
        </div>
        <button className="profile-title" onClick={onProfile}>
          <h3>{profile.name}</h3>
          <ArrowUpRight size={18} />
        </button>
        <p className="specialty">{profile.specialty}</p>
        <div className="price-row">
          <span>
            от <strong>{money(profile.price_from_kzt)}</strong>
          </span>
          <span className="availability">
            <span />
            {dateLabel(card.available_on)}
          </span>
        </div>
        {(profile.price_is_estimated || profile.city_is_estimated) && (
          <p className="source-warning">
            {[
              profile.price_is_estimated && 'Цена заполнена при подготовке данных',
              profile.city_is_estimated && 'Город заполнен при подготовке данных',
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}
        <div className="why-match">
          <div className="why-label">
            <Sparkles size={14} />
            <span>Почему в подборке</span>
          </div>
          <p>{card.explanation}</p>
        </div>
        <div className="match-tags">
          <span>
            <Check size={12} />В бюджете
          </span>
          <span>
            <Check size={12} />
            {profile.event_formats.includes('корпоратив') &&
            card.evidence.some((e) => e.label === 'Формат' && e.value === 'корпоратив')
              ? 'Корпоратив'
              : card.evidence.find((e) => e.label === 'Формат')?.value}
          </span>
        </div>
        <Evidence card={card} />
        <div className="card-actions">
          <button className="text-button" onClick={onProfile}>
            Открыть профиль <ArrowUpRight size={15} />
          </button>
          <button
            className={`compare-button ${compared ? 'is-active' : ''}`}
            aria-pressed={compared}
            onClick={onCompare}
            aria-label={`${compared ? 'Убрать из сравнения' : 'Сравнить'}: ${profile.name}`}
          >
            {compared ? <Check size={16} /> : <Scale size={16} />}
          </button>
        </div>
      </div>
    </article>
  )
}
