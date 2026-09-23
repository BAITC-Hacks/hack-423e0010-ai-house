import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { z } from 'zod'
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  Flower2,
  Heart,
  HelpCircle,
  Leaf,
  MapPin,
  Scale,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { Artwork } from './components/Artwork'
import { Modal } from './components/Modal'
import { ProfileDetails } from './components/ProfileDetails'
import { RequestForm } from './components/RequestForm'
import { Results } from './components/Results'
import { AgentExplanation, AgentSummary } from './components/AgentExplanation'
import { NaturalRequest, fieldNames } from './components/NaturalRequest'
import { explainSelection } from './services/agent'
import type { AgentResponse, NearbyOption, ParsedRequest } from './domain/agent'
import {
  dateLabel,
  defaultForm,
  money,
  parseForm,
  profileSchema,
  requestSchema,
  requestToForm,
} from './domain/selection'
import type {
  FieldErrors,
  FormValues,
  Profile,
  Recommendation,
  SelectionRequest,
  SelectionResponse,
} from './domain/selection'
import { getRecommendations, isDemoMode } from './services/api'
import './App.css'

const FORM_KEY = 'tandau:request:v1'
const SAVED_KEY = 'tandau:favorites:v1'
function loadForm(): FormValues {
  try {
    const parsed = requestSchema.safeParse(JSON.parse(localStorage.getItem(FORM_KEY) ?? 'null'))
    if (parsed.success) return requestToForm(parsed.data)
  } catch {
    /* Storage may be unavailable. */
  }
  return { ...defaultForm }
}
function loadSaved(): Profile[] {
  try {
    return z.array(profileSchema).parse(JSON.parse(localStorage.getItem(SAVED_KEY) ?? '[]'))
  } catch {
    return []
  }
}
type DialogState = 'how' | 'favorites' | 'compare' | 'helper' | 'agent' | null

function App() {
  const [form, setForm] = useState<FormValues>(loadForm)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [result, setResult] = useState<SelectionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Profile[]>(loadSaved)
  const [compared, setCompared] = useState<string[]>([])
  const [dialog, setDialog] = useState<DialogState>(null)
  const [activeProfile, setActiveProfile] = useState<{
    profile: Profile
    recommendation?: Recommendation
  } | null>(null)
  const [helperText, setHelperText] = useState('')
  const [toast, setToast] = useState('')
  const [agentData, setAgentData] = useState<AgentResponse | null>(null)
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState('')
  const agentController = useRef<AbortController | null>(null)
  const controller = useRef<AbortController | null>(null)
  const initialForm = useRef(form)
  const workbench = useRef<HTMLElement>(null)

  const runAgent = useCallback(async (selection: SelectionResponse) => {
    agentController.current?.abort()
    const next = new AbortController()
    agentController.current = next
    setAgentLoading(true)
    setAgentError('')
    setAgentData(null)
    try {
      const response = await explainSelection(selection.request, selection, next.signal)
      if (!next.signal.aborted) setAgentData(response)
    } catch (cause) {
      if (!next.signal.aborted) setAgentError(cause instanceof Error ? cause.message : 'Не удалось получить разбор агента.')
    } finally {
      if (!next.signal.aborted) setAgentLoading(false)
    }
  }, [])

  const search = useCallback(async (request: SelectionRequest, withAgent = true) => {
    controller.current?.abort()
    agentController.current?.abort()
    setAgentData(null)
    setAgentError('')
    setAgentLoading(false)
    const nextController = new AbortController()
    controller.current = nextController
    setLoading(true)
    setError(null)
    setCompared([])
    try {
      const response = await getRecommendations(request, nextController.signal)
      if (!nextController.signal.aborted) {
        setResult(response)
        if (withAgent) {
          setActiveProfile(null)
          setDialog('agent')
          void runAgent(response)
        }
      }
    } catch (cause) {
      if (!nextController.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : 'Не удалось завершить подбор. Попробуйте ещё раз.',
        )
    } finally {
      if (!nextController.signal.aborted) setLoading(false)
    }
  }, [runAgent])
  useEffect(() => {
    const initial = parseForm(initialForm.current).request
    if (isDemoMode && initial) void search(initial, false)
    return () => { controller.current?.abort(); agentController.current?.abort() }
  }, [search])
  useEffect(() => {
    const parsed = parseForm(form).request
    if (parsed) {
      try {
        localStorage.setItem(FORM_KEY, JSON.stringify(parsed))
      } catch {
        /* In-memory state still works. */
      }
    }
  }, [form])
  useEffect(() => {
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(saved))
    } catch {
      /* In-memory favorites still work. */
    }
  }, [saved])
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(''), 3600)
    return () => clearTimeout(timer)
  }, [toast])

  const updateForm = (patch: Partial<FormValues>) => {
    setForm((current) => ({ ...current, ...patch }))
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(patch)) delete next[key as keyof FormValues]
      return next
    })
  }
  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    const parsed = parseForm(form)
    setErrors(parsed.errors)
    if (parsed.request) {
      void search(parsed.request)
      if (window.innerWidth < 800)
        document
          .getElementById('results-heading')
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else {
      const first = Object.keys(parsed.errors)[0]
      const ids: Record<string, string> = {
        event_date: 'event-date',
        budget_kzt: 'budget',
        duration_hours: 'duration',
      }
      document.getElementById(ids[first] ?? first)?.focus()
    }
  }
  const focusForm = () => {
    workbench.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    document.getElementById('city')?.focus({ preventScroll: true })
  }
  const applyAlternative = (patch: Partial<SelectionRequest>) => {
    if (!result) return
    const next = { ...result.request, ...patch }
    setForm(requestToForm(next))
    setErrors({})
    void search(next)
  }
  const applyNearby = (option: NearbyOption) => {
    setForm(requestToForm(option.request))
    setErrors({})
    setDialog(null)
    void search(option.request)
  }
  const applyNaturalRequest = (parsed: ParsedRequest) => {
    const patch: Partial<FormValues> = {}
    const fields = parsed.fields
    if (fields.city && !parsed.invalid_fields.includes('city')) patch.city = fields.city
    if (fields.event_date && !parsed.invalid_fields.includes('event_date')) patch.event_date = fields.event_date
    if (fields.category) patch.category = fields.category
    if (fields.event_format) patch.event_format = fields.event_format
    if (fields.budget_kzt !== null && !parsed.invalid_fields.includes('budget_kzt')) patch.budget_kzt = String(fields.budget_kzt)
    patch.duration_hours = fields.duration_hours === null || parsed.invalid_fields.includes('duration_hours') ? '' : String(fields.duration_hours)
    patch.language = fields.language
    patch.preferences = fields.preferences.slice(0, 500)
    updateForm(patch)
    if (parsed.ready) {
      const request = requestSchema.safeParse(fields)
      if (request.success) { setForm(requestToForm(request.data)); void search(request.data) }
    } else {
      setToast(`Уточните в форме: ${[...parsed.missing_fields, ...parsed.invalid_fields].map((name) => fieldNames[name]).join(', ')}. Остальные значения формы не подтверждены текстом.`)
      focusForm()
    }
  }
  const openAgent = () => {
    if (!result) return
    setDialog('agent')
    if (!agentData && !agentLoading) void runAgent(result)
  }
  const save = (profile: Profile) => {
    const exists = saved.some((item) => item.id === profile.id)
    setSaved((current) =>
      exists ? current.filter((item) => item.id !== profile.id) : [...current, profile],
    )
    setToast(exists ? 'Профиль удалён из избранного' : 'Профиль сохранён в избранном')
  }
  const toggleCompare = (id: string) =>
    setCompared((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    )
  const openProfile = (card: Recommendation) =>
    setActiveProfile({ profile: card.contractor, recommendation: card })
  const stale =
    !!result && JSON.stringify(parseForm(form).request) !== JSON.stringify(result.request)
  const comparison =
    result?.recommendations.filter((card) => compared.includes(card.contractor.id)) ?? []
  const closeModal = () => {
    setDialog(null)
    setActiveProfile(null)
  }
  const example = (patch: Partial<SelectionRequest>) => {
    const request = { ...parseForm(defaultForm).request!, ...patch }
    setForm(requestToForm(request))
    setErrors({})
    closeModal()
    void search(request)
    workbench.current?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <>
      <a href="#selection" className="skip-link">
        Перейти к подбору
      </a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="#" aria-label="Tandau — на главную">
            <span className="brand-mark">
              <Flower2 size={27} strokeWidth={1.6} />
            </span>
            <span>
              tandau<span className="brand-period">.</span>
            </span>
          </a>
          <nav className="main-nav" aria-label="Основная навигация">
            <a className="nav-active" href="#selection">
              Подбор подрядчиков
            </a>
            <button onClick={() => setDialog('how')}>Как это работает</button>
          </nav>
          <div className="header-actions">
            <span className="country-label">
              <MapPin size={14} />
              Казахстан
            </span>
            <button className="favorites-nav" onClick={() => setDialog('favorites')}>
              <Heart size={17} />
              <span>Избранное</span>
              {saved.length > 0 && <b>{saved.length}</b>}
            </button>
          </div>
        </div>
      </header>
      <main>
        <section className="hero page-width">
          <div className="hero-copy">
            <span className="hero-eyebrow">
              <span />
              ЛЮДИ, КОТОРЫЕ СОЗДАЮТ СОБЫТИЯ
            </span>
            <h1>
              Ваше событие.
              <br />
              <em>Ваши люди.</em>
              <span className="heading-spark">✳</span>
            </h1>
            <p>
              Найдите тех, кто совпадает с вашим замыслом.
              <br />
              До трёх подрядчиков — с объяснением каждого выбора.
            </p>
            <a className="hero-link" href="#selection">
              Начнём с ваших планов <ArrowDown size={15} />
            </a>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="hero-orbit orbit-one" />
            <div className="hero-orbit orbit-two" />
            <div className="hero-back-card">
              <span>TANDAU SELECT</span>
              <Flower2 size={110} strokeWidth={0.6} />
              <span>people · places · moments</span>
            </div>
            <div className="hero-front-card">
              <span className="art-mini-eyebrow">ТО САМОЕ СОВПАДЕНИЕ</span>
              <span className="art-main-text">
                У каждого
                <br />
                события —<br />
                <em>свои люди.</em>
              </span>
              <span className="art-bottom">
                <span>С заботой о деталях</span>
                <ArrowUpRight size={17} />
              </span>
            </div>
            <div className="match-sticker">
              <span>
                <CheckCheck size={20} />
              </span>
              <div>
                <strong>Подходит именно вам</strong>
                <small>По условиям. По характеру.</small>
              </div>
            </div>
            <span className="hero-star star-one">✳</span>
            <span className="hero-star star-two">✦</span>
          </div>
        </section>
        <div className="workspace-wrapper">
          <section className="workspace page-width" id="selection" ref={workbench}>
            <div className="workspace-topline">
              <span>
                <Leaf size={15} />
                Осознанный выбор для важного дня
              </span>
              <button className="mode-badge" onClick={() => setDialog('how')}>
                <span />
                {isDemoMode ? 'Демо на каталоге · 66 профилей' : 'Сервис подбора подключён'}
                <HelpCircle size={13} />
              </button>
            </div>
            <NaturalRequest onApply={applyNaturalRequest} />
            <div className="workspace-grid">
              <RequestForm
                form={form}
                errors={errors}
                loading={loading}
                onChange={updateForm}
                onSubmit={submit}
                onReset={() => {
                  setForm({ ...defaultForm })
                  setErrors({})
                  setToast('Восстановлены начальные параметры. Нажмите «Подобрать подрядчиков».')
                }}
                onHelp={() => {
                  setHelperText(form.preferences)
                  setDialog('helper')
                }}
              />
              <Results
                result={result}
                loading={loading}
                error={error}
                stale={stale}
                savedIds={saved.map((profile) => profile.id)}
                comparedIds={compared}
                onSave={(card) => save(card.contractor)}
                onCompare={toggleCompare}
                onProfile={openProfile}
                onRetry={() => submit()}
                onEdit={focusForm}
                onAlternative={applyAlternative}
                demo={isDemoMode}
                agentPanel={<AgentSummary data={agentData} loading={agentLoading} error={agentError} onOpen={openAgent} onApply={applyNearby} stale={stale} />}
              />
            </div>
          </section>
        </div>
        <section className="closing-line page-width">
          <Flower2 size={25} strokeWidth={1.3} />
          <p>
            Вы создаёте повод. <span>Мы помогаем найти людей.</span>
          </p>
          <button onClick={() => setDialog('how')}>
            О подходе Tandau <ArrowUpRight size={16} />
          </button>
        </section>
      </main>
      <footer className="site-footer page-width">
        <a className="footer-brand" href="#">
          tandau.
        </a>
        <span>События начинаются с людей</span>
        <span>
          Сделано для Казахстана <span className="footer-flower">✳</span>
        </span>
      </footer>

      {compared.length > 0 && !loading && (
        <div className="comparison-bar">
          <div className="comparison-icon">
            <Scale size={19} />
          </div>
          <span>
            <strong>Сравнить варианты</strong>
            <small>Выбрано {compared.length} из 3</small>
          </span>
          <button
            className="primary-button"
            disabled={compared.length < 2}
            onClick={() => setDialog('compare')}
          >
            {compared.length < 2 ? 'Выберите ещё один' : 'Сравнить'}
            <ArrowRight size={15} />
          </button>
          <button
            className="icon-button"
            aria-label="Очистить сравнение"
            onClick={() => setCompared([])}
          >
            <X size={17} />
          </button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
          <button onClick={() => setToast('')} aria-label="Закрыть уведомление">
            <X size={15} />
          </button>
        </div>
      )}

      {!activeProfile && dialog === 'agent' && result && (
        <Modal title="Объяснение и предложения агента" onClose={closeModal} wide>
          <AgentExplanation data={agentData} loading={agentLoading} error={agentError} selection={result} onRetry={() => void runAgent(result)} onApply={applyNearby} stale={stale} />
        </Modal>
      )}
      {activeProfile && (
        <Modal title={activeProfile.profile.name} onClose={closeModal}>
          <ProfileDetails
            profile={activeProfile.profile}
            recommendation={activeProfile.recommendation}
            saved={saved.some((p) => p.id === activeProfile.profile.id)}
            onSave={() => save(activeProfile.profile)}
          />
        </Modal>
      )}
      {!activeProfile && dialog === 'favorites' && (
        <Modal
          title={`Избранное${saved.length ? ` · ${saved.length}` : ''}`}
          onClose={closeModal}
          drawer
        >
          <p className="modal-intro">
            Ваши сохранённые профили — в одном месте. Для новой даты запускайте подбор заново.
          </p>
          {saved.length === 0 ? (
            <div className="favorites-empty">
              <Heart size={38} strokeWidth={1.2} />
              <h3>Здесь будут ваши люди</h3>
              <p>Нажмите на сердечко в карточке, чтобы вернуться к подрядчику позже.</p>
              <button className="secondary-button" onClick={closeModal}>
                Вернуться к подборке
              </button>
            </div>
          ) : (
            <div className="saved-list">
              {saved.map((profile) => (
                <article className="saved-item" key={profile.id}>
                  <button
                    className="saved-profile-button"
                    onClick={() => setActiveProfile({ profile })}
                  >
                    <Artwork
                      palette={profile.artwork}
                      category={profile.category}
                      name={profile.name}
                      compact
                    />
                    <span>
                      <strong>{profile.name}</strong>
                      <small>
                        {profile.category} · {profile.city}
                      </small>
                      <span>от {money(profile.price_from_kzt)}</span>
                    </span>
                  </button>
                  <button
                    className="icon-button"
                    onClick={() => save(profile)}
                    aria-label={`Удалить из избранного: ${profile.name}`}
                  >
                    <Heart size={18} fill="currentColor" />
                  </button>
                </article>
              ))}
            </div>
          )}
        </Modal>
      )}
      {!activeProfile && dialog === 'compare' && (
        <Modal title="Детали, которые помогают выбрать" onClose={closeModal} wide>
          <p className="modal-intro">
            Одна подборка, одинаковые условия.{' '}
            {result &&
              `${result.request.city} · ${dateLabel(result.request.event_date)} · ${result.request.event_format}`}
          </p>
          {stale && (
            <p className="comparison-stale">
              Сравниваются результаты предыдущего запроса. Обновите подбор после изменения условий.
            </p>
          )}
          <div className="comparison-scroll">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th scope="col">Условия</th>
                  {comparison.map(({ contractor: p }) => (
                    <th scope="col" key={p.id}>
                      <Artwork palette={p.artwork} category={p.category} name={p.name} compact />
                      <span>{p.name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Цена «от»</th>
                  {comparison.map(({ contractor: p }) => (
                    <td key={p.id}>
                      <strong>{money(p.price_from_kzt)}</strong>
                      {p.price_is_estimated && <small>Дополнена в датасете</small>}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Свободен по календарю</th>
                  {comparison.map((card) => (
                    <td key={card.contractor.id}>
                      <span className="green-text">{dateLabel(card.available_on)}</span>
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Языки</th>
                  {comparison.map(({ contractor: p }) => (
                    <td key={p.id}>{p.languages.join(', ')}</td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Длительность</th>
                  {comparison.map(({ contractor: p }) => (
                    <td key={p.id}>
                      {p.max_hours === null ? 'Неприменима к услуге' : `До ${p.max_hours} ч`}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Основания выбора</th>
                  {comparison.map((card) => (
                    <td key={card.contractor.id}>{card.explanation}</td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Происхождение</th>
                  {comparison.map(({ contractor: p }) => (
                    <td key={p.id}>
                      {p.origin === 'synthetic'
                        ? 'Синтетический профиль'
                        : 'Анонимизированный каталог'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="muted">
            Цена «от» не является окончательной сметой. Доступность из каталога не означает
            бронирование.
          </p>
        </Modal>
      )}
      {!activeProfile && dialog === 'how' && (
        <Modal title="Выбор, в котором всё понятно" onClose={closeModal}>
          <p className="modal-intro">
            Tandau помогает выбрать из каталога вашего города. Мы показываем до трёх вариантов и
            объясняем, на каких фактах основана каждая рекомендация.
          </p>
          <div className="how-steps">
            <div>
              <span>01</span>
              <div>
                <h3>Ваши условия — отправная точка</h3>
                <p>
                  Проверяем дату, формат и стартовую цену. Указанные язык и длительность тоже
                  становятся обязательными условиями.
                </p>
              </div>
            </div>
            <div>
              <span>02</span>
              <div>
                <h3>У каждого варианта есть причина</h3>
                <p>
                  Пожелания помогают определить порядок. В карточке — конкретные факты и фрагменты
                  описания. Одинаковый запрос к той же версии каталога даёт тот же порядок.
                </p>
              </div>
            </div>
            <div>
              <span>03</span>
              <div>
                <h3>Последнее слово — за вами</h3>
                <p>
                  Изучайте профили, сохраняйте и сравнивайте. Если вариантов мало или нет, мы скажем
                  почему. Условия меняются только по вашему действию.
                </p>
              </div>
            </div>
          </div>
          <div className="demo-explainer">
            <ShieldCheck size={20} />
            <div>
              <strong>
                {isDemoMode
                  ? 'Сейчас работает локальная демо-версия'
                  : 'Результаты предоставляет подключённый сервис'}
              </strong>
              <p>
                {isDemoMode
                  ? '66 анонимизированных профилей из вашего CSV. 13 из них синтетические; дополненные цены и города отмечены в карточках. Фильтры проверяются по данным. ИИ разбирает текстовый запрос и подробно объясняет выбранные и ближайшие варианты с опорой на подтверждённые факты.'
                  : 'Форма отправляет параметры в сервис и показывает его проверенный ответ.'}
              </p>
              <p>
                Календарь покрывает 23 сентября — 31 декабря 2026 года. Требования, которых нет в
                структурированных данных (например, вместимость зала), нельзя считать
                подтверждёнными.
              </p>
            </div>
          </div>
          {isDemoMode && (
            <div className="demo-examples">
              <h3>Попробуйте разные сценарии</h3>
              <button onClick={() => example({})}>
                <span>
                  Ведущий на корпоратив<small>Алматы · 10 октября · до 1 млн ₸</small>
                </span>
                <ArrowRight size={17} />
              </button>
              <button
                onClick={() =>
                  example({ category: 'Флорист', event_format: 'свадьба', budget_kzt: 500000 })
                }
              >
                <span>
                  Только один подходящий вариант<small>Флорист · Алматы · 10 октября</small>
                </span>
                <ArrowRight size={17} />
              </button>
              <button
                onClick={() =>
                  example({
                    city: 'Астана',
                    category: 'Декоратор',
                    event_format: 'свадьба',
                    budget_kzt: 3000000,
                  })
                }
              >
                <span>
                  Категории нет в городе<small>Декоратор · Астана</small>
                </span>
                <ArrowRight size={17} />
              </button>
              <button onClick={() => example({ budget_kzt: 10000 })}>
                <span>
                  Никто не проходит по условиям<small>Ведущий · бюджет 10 000 ₸</small>
                </span>
                <ArrowRight size={17} />
              </button>
            </div>
          )}
        </Modal>
      )}
      {!activeProfile && dialog === 'helper' && (
        <Modal title="Что сделает событие вашим?" onClose={closeModal} drawer>
          <div className="helper-intro">
            <span>
              <Sparkles size={25} />
            </span>
            <p>
              Подумайте об атмосфере, стиле общения и том, что важно вашим гостям. Эти детали
              помогут сравнить подрядчиков.
            </p>
          </div>
          <label className="helper-label" htmlFor="helper-text">
            Ваши пожелания
          </label>
          <textarea
            id="helper-text"
            className="helper-textarea"
            rows={6}
            maxLength={500}
            value={helperText}
            onChange={(event) => setHelperText(event.target.value)}
            placeholder="Хочется спокойной атмосферы, интеллигентного юмора и живого общения с гостями…"
          />
          <div className="wish-suggestions">
            {[
              'Интеллигентный юмор',
              'Танцы и развлечения',
              'Камерная атмосфера',
              'Уважение к традициям',
            ].map((wish) => (
              <button
                key={wish}
                onClick={() =>
                  setHelperText((text) =>
                    (text ? `${text}, ${wish.toLowerCase()}` : wish).slice(0, 500),
                  )
                }
              >
                + {wish}
              </button>
            ))}
          </div>
          <p className="helper-note">
            Пожелания влияют на порядок, но не заменяют условия в форме. Вместимость, оборудование и
            другие отсутствующие в каталоге детали требуют уточнения.
          </p>
          {isDemoMode && (
            <p className="helper-demo">
              Для разбора свободного текста используйте поле агента над формой. После подбора ИИ объяснит результат и возможные изменения условий.
            </p>
          )}
          <button
            className="primary-button full-width"
            onClick={() => {
              updateForm({ preferences: helperText })
              closeModal()
              setToast('Пожелания добавлены. Обновите подбор, чтобы учесть их.')
            }}
          >
            Добавить к запросу
            <ArrowRight size={16} />
          </button>
        </Modal>
      )}
    </>
  )
}
export default App
