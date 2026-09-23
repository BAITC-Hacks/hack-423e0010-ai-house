import {CheckCheck, Info, MessageCircle} from 'lucide-react';
import type {Result} from './types';

export default function ChatSelectionContext({result, stale, disabled, onAsk}: {
  result: Result | null;
  stale: boolean;
  disabled: boolean;
  onAsk: (message: string) => void;
}) {
  if (!result) return null;
  const date = new Date(result.query.event_date + 'T12:00:00').toLocaleDateString('ru-RU');
  return <section className={`chat-selection ${stale ? 'stale' : ''}`} aria-label="Подборка в контексте помощника" data-testid="chat-selection">
    <div className="chat-selection-heading">{stale ? <Info size={14}/> : <CheckCheck size={14}/>}<strong>{stale ? 'Обсуждаем предыдущую подборку' : 'Вижу вашу подборку'}</strong></div>
    <p>{result.query.category} · {result.query.city} · {date}</p>
    {result.cards.length ? <ol>{result.cards.map((card, index) => <li key={card.id}>
      <button disabled={disabled} onClick={() => onAsk(`Расскажи про ${card.anon_name}`)}>
        <span>{index + 1}.</span>{card.anon_name}<MessageCircle size={12}/>
      </button>
    </li>)}</ol> : <p className="chat-selection-empty">{result.status === 'CATEGORY_ABSENT' ? 'В городе нет этой категории.' : 'По условиям нет подходящих кандидатов.'} Могу объяснить почему.</p>}
    <small>{stale ? 'Фильтры изменены. Выполните новый поиск, чтобы обновить кандидатов.' : 'Можно спросить об имени, цене или «втором кандидате».'}</small>
  </section>;
}
