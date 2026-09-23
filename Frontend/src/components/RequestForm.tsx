import {
  ArrowRight,
  CalendarDays,
  ChevronDown,
  Clock3,
  Globe2,
  MapPin,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  Wallet,
} from 'lucide-react'
import type { FormEvent } from 'react'
import { CALENDAR, CATEGORIES, CITIES, EVENT_FORMATS, LANGUAGES } from '../domain/selection'
import type { FieldErrors, FormValues } from '../domain/selection'

export function RequestForm({
  form,
  errors,
  loading,
  onChange,
  onSubmit,
  onReset,
  onHelp,
}: {
  form: FormValues
  errors: FieldErrors
  loading: boolean
  onChange: (patch: Partial<FormValues>) => void
  onSubmit: (event: FormEvent) => void
  onReset: () => void
  onHelp: () => void
}) {
  return (
    <aside className="form-column">
      <form className="request-form" onSubmit={onSubmit} noValidate aria-label="Параметры подбора">
        <div className="form-heading">
          <div>
            <span className="section-eyebrow">НАЧНЁМ С ГЛАВНОГО</span>
            <h2>Ваше мероприятие</h2>
          </div>
          <SlidersHorizontal size={20} />
        </div>
        <div className="form-fields">
          <div className="field">
            <label htmlFor="city">
              Город <span>*</span>
            </label>
            <div className="input-wrap">
              <MapPin size={17} />
              <select
                id="city"
                value={form.city}
                onChange={(e) => onChange({ city: e.target.value as FormValues['city'] })}
              >
                {CITIES.map((city) => (
                  <option key={city}>{city}</option>
                ))}
              </select>
              <ChevronDown className="select-chevron" size={15} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="event-date">
              Дата мероприятия <span>*</span>
            </label>
            <div className={`input-wrap ${errors.event_date ? 'input-invalid' : ''}`}>
              <CalendarDays size={17} />
              <input
                id="event-date"
                type="date"
                required
                min={CALENDAR.start}
                max={CALENDAR.end}
                value={form.event_date}
                onChange={(e) => onChange({ event_date: e.target.value })}
                aria-invalid={!!errors.event_date}
                aria-describedby="date-hint"
              />
            </div>
            <small id="date-hint" className={errors.event_date ? 'field-error' : 'field-hint'}>
              {errors.event_date ?? 'Календарь: 23 сен — 31 дек 2026'}
            </small>
          </div>
          <fieldset className="event-field">
            <legend>
              Тип мероприятия <span>*</span>
            </legend>
            <div className="event-options">
              {EVENT_FORMATS.map((format) => (
                <label key={format} className={form.event_format === format ? 'selected' : ''}>
                  <input
                    type="radio"
                    name="event-format"
                    value={format}
                    checked={form.event_format === format}
                    onChange={() => onChange({ event_format: format })}
                  />
                  <span>{format.charAt(0).toUpperCase() + format.slice(1)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="field">
            <label htmlFor="category">
              Кого ищем <span>*</span>
            </label>
            <div className="input-wrap category-select">
              <select
                id="category"
                value={form.category}
                onChange={(e) => onChange({ category: e.target.value as FormValues['category'] })}
              >
                {CATEGORIES.map((category) => (
                  <option key={category}>{category}</option>
                ))}
              </select>
              <ChevronDown className="select-chevron" size={15} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="budget">
              Бюджет на подрядчика <span>*</span>
            </label>
            <div className={`input-wrap ${errors.budget_kzt ? 'input-invalid' : ''}`}>
              <Wallet size={17} />
              <input
                id="budget"
                type="text"
                inputMode="numeric"
                required
                value={form.budget_kzt.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}
                onChange={(e) => onChange({ budget_kzt: e.target.value.replace(/\s/g, '') })}
                aria-invalid={!!errors.budget_kzt}
                aria-describedby="budget-hint"
              />
              <span className="input-unit">₸</span>
            </div>
            <small id="budget-hint" className={errors.budget_kzt ? 'field-error' : 'field-hint'}>
              {errors.budget_kzt ?? 'Максимальная сумма за одну услугу'}
            </small>
            <div className="budget-options">
              {[
                [300000, '300 тыс.'],
                [500000, '500 тыс.'],
                [1000000, '1 млн'],
              ].map(([amount, label]) => (
                <button
                  key={amount}
                  type="button"
                  className={form.budget_kzt === String(amount) ? 'selected' : ''}
                  onClick={() => onChange({ budget_kzt: String(amount) })}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="optional-heading">
            <span>Чуть больше деталей</span>
            <small>необязательно</small>
          </div>
          <div className="two-fields">
            <div className="field">
              <label htmlFor="duration">Длительность</label>
              <div className={`input-wrap ${errors.duration_hours ? 'input-invalid' : ''}`}>
                <Clock3 size={16} />
                <input
                  id="duration"
                  type="number"
                  min="0.5"
                  max="24"
                  step="0.5"
                  value={form.duration_hours}
                  placeholder="Любая"
                  onChange={(e) => onChange({ duration_hours: e.target.value })}
                  aria-invalid={!!errors.duration_hours}
                  aria-describedby={errors.duration_hours ? 'duration-error' : undefined}
                />
                <span className="input-unit">ч</span>
              </div>
            </div>
            <div className="field">
              <label htmlFor="language">Язык</label>
              <div className="input-wrap">
                <select
                  id="language"
                  value={form.language ?? ''}
                  onChange={(e) =>
                    onChange({ language: (e.target.value || null) as FormValues['language'] })
                  }
                >
                  <option value="">Любой</option>
                  {LANGUAGES.map((language) => (
                    <option key={language} value={language}>
                      {language.charAt(0).toUpperCase() + language.slice(1)}
                    </option>
                  ))}
                </select>
                <ChevronDown className="select-chevron" size={14} />
              </div>
            </div>
          </div>
          {errors.duration_hours && (
            <small id="duration-error" className="field-error">
              {errors.duration_hours}
            </small>
          )}
          <div className="field">
            <div className="label-row">
              <label htmlFor="preferences">Что для вас важно?</label>
              <button
                type="button"
                className="subtle-icon"
                onClick={onHelp}
                aria-label="Помочь сформулировать пожелания"
              >
                <Sparkles size={15} />
              </button>
            </div>
            <textarea
              id="preferences"
              rows={3}
              maxLength={500}
              placeholder="Например, интеллигентный юмор и спокойная подача…"
              value={form.preferences}
              onChange={(e) => onChange({ preferences: e.target.value })}
            />
            <div className="textarea-meta">
              <span>Поможет найти близких по стилю</span>
              <span>{form.preferences.length}/500</span>
            </div>
          </div>
          <button type="submit" className="primary-button search-button" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" />
                Подбираем варианты…
              </>
            ) : (
              <>
                <Sparkles size={17} />
                Подобрать подрядчиков
                <ArrowRight size={17} />
              </>
            )}
          </button>
          <button type="button" className="reset-button" onClick={onReset} disabled={loading}>
            <RotateCcw size={13} />
            Сбросить параметры
          </button>
        </div>
      </form>
      <div className="form-footnote">
        <Globe2 size={17} />
        <p>
          Ищем в выбранном городе.
          <br />
          Один запрос — одна категория.
        </p>
      </div>
    </aside>
  )
}
