import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() {return {failed: true};}
  render() {return this.state.failed ? <main className="fatal"><h1>Не удалось отобразить страницу</h1><p>Ваш последний запрос сохранён. Перезагрузите страницу.</p><button className="primary" onClick={() => location.reload()}>Перезагрузить</button></main> : this.props.children;}
}
ReactDOM.createRoot(document.getElementById('root')!).render(<ErrorBoundary><App /></ErrorBoundary>);

