import { Check, Clock3, Heart, Languages, MapPin, ShieldCheck } from 'lucide-react'
import { money } from '../domain/selection'
import type { Profile, Recommendation } from '../domain/selection'
import { Artwork } from './Artwork'
import { Evidence } from './ContractorCard'

export function ProfileDetails({
  profile,
  recommendation,
  saved,
  onSave,
}: {
  profile: Profile
  recommendation?: Recommendation
  saved: boolean
  onSave: () => void
}) {
  return (
    <div className="profile-detail">
      <Artwork palette={profile.artwork} category={profile.category} name={profile.name} />
      <div className="profile-meta">
        <span>
          <MapPin size={15} />
          {profile.city}
        </span>
        <span>{profile.categories.join(' · ')}</span>
      </div>
      <div className="profile-price">
        <span>
          от <strong>{money(profile.price_from_kzt)}</strong>
        </span>
        <button className={`secondary-button ${saved ? 'saved' : ''}`} onClick={onSave}>
          <Heart size={16} fill={saved ? 'currentColor' : 'none'} />
          {saved ? 'В избранном' : 'Сохранить'}
        </button>
      </div>
      <p className="muted">Стартовая цена из каталога. Итоговая смета требует уточнения.</p>
      <h3>О подрядчике</h3>
      <p className="profile-description">{profile.description}</p>
      <div className="profile-facts">
        <div>
          <Languages size={19} />
          <span>
            <small>Языки</small>
            {profile.languages.join(', ')}
          </span>
        </div>
        <div>
          <Clock3 size={19} />
          <span>
            <small>Длительность</small>
            {profile.max_hours === null ? 'Неприменима к услуге' : `До ${profile.max_hours} часов`}
          </span>
        </div>
      </div>
      <h3>Форматы мероприятий</h3>
      <div className="profile-formats">
        {profile.event_formats.map((format) => (
          <span key={format}>
            <Check size={13} />
            {format}
          </span>
        ))}
      </div>
      {recommendation && (
        <>
          <h3>Почему в вашей подборке</h3>
          <p>{recommendation.explanation}</p>
          <Evidence card={recommendation} />
        </>
      )}
      {!recommendation && (
        <p className="profile-saved-note">
          Избранное сохраняет профиль. Доступность на новую дату нужно проверить повторным подбором.
        </p>
      )}
      <div className="provenance">
        <ShieldCheck size={18} />
        <div>
          <strong>
            {profile.origin === 'synthetic'
              ? 'Синтетический профиль из датасета'
              : profile.origin === 'demo'
                ? 'Демонстрационный профиль'
                : 'Анонимизированный профиль каталога'}
          </strong>
          <p>
            {profile.price_is_estimated ? 'Цена проставлена при подготовке датасета. ' : ''}
            {profile.city_is_estimated ? 'Город проставлен при подготовке датасета. ' : ''}
            Изображение — иллюстрация, не фотография подрядчика. Утверждения в описании принадлежат
            автору профиля.
          </p>
        </div>
      </div>
    </div>
  )
}
