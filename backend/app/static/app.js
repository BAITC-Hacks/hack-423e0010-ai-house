(function () {
  "use strict";

  const form = document.getElementById("search-form");
  const statusBox = document.getElementById("results-status");
  const cardsBox = document.getElementById("results-cards");
  const calendarHint = document.getElementById("calendar-hint");
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  const fields = {
    city: document.getElementById("city"),
    event_date: document.getElementById("event_date"),
    event_format: document.getElementById("event_format"),
    category: document.getElementById("category"),
    budget_kzt: document.getElementById("budget_kzt"),
    duration_hours: document.getElementById("duration_hours"),
    language: document.getElementById("language"),
    preferences: document.getElementById("preferences"),
  };

  // Latest search state, sent back to /api/v1/chat on every turn (server is
  // stateless — no session, no persisted history).
  let currentSearch = null;
  let lastRecommendation = null;

  function fillSelect(select, values, { placeholder } = {}) {
    select.innerHTML = "";
    if (placeholder) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      select.appendChild(opt);
    }
    for (const value of values) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      select.appendChild(opt);
    }
  }

  async function loadCatalogOptions() {
    try {
      const res = await fetch("/api/v1/catalog-options");
      if (!res.ok) throw new Error("catalog-options failed");
      const data = await res.json();
      fillSelect(fields.city, data.cities);
      fillSelect(fields.event_format, data.event_formats);
      fillSelect(fields.category, data.categories);
      fillSelect(fields.language, data.languages, { placeholder: "— не важно —" });
      if (data.calendar_start && data.calendar_end) {
        fields.event_date.min = data.calendar_start;
        fields.event_date.max = data.calendar_end;
        calendarHint.textContent =
          "Доступный период дат: " + data.calendar_start + " — " + data.calendar_end;
      }
    } catch (err) {
      calendarHint.textContent =
        "Не удалось загрузить список допустимых значений — проверьте, что сервер запущен.";
    }
  }

  function readFormAsSearch() {
    const search = {
      city: fields.city.value || null,
      event_date: fields.event_date.value || null,
      event_format: fields.event_format.value || null,
      category: fields.category.value || null,
      budget_kzt: fields.budget_kzt.value ? Number(fields.budget_kzt.value) : null,
      duration_hours: fields.duration_hours.value ? Number(fields.duration_hours.value) : null,
      language: fields.language.value || null,
      preferences: fields.preferences.value || null,
    };
    return search;
  }

  function applySearchToForm(search) {
    if (!search) return;
    if (search.city) fields.city.value = search.city;
    if (search.event_date) fields.event_date.value = search.event_date;
    if (search.event_format) fields.event_format.value = search.event_format;
    if (search.category) fields.category.value = search.category;
    if (search.budget_kzt != null) fields.budget_kzt.value = search.budget_kzt;
    if (search.duration_hours != null) fields.duration_hours.value = search.duration_hours;
    else fields.duration_hours.value = "";
    fields.language.value = search.language || "";
    fields.preferences.value = search.preferences || "";
  }

  function setStatus(kind, text) {
    statusBox.className = "status-box status-" + kind;
    statusBox.textContent = text;
  }

  function renderRejectionSummary(rejectionSummary) {
    const entries = Object.entries(rejectionSummary || {});
    if (entries.length === 0) return "";
    const items = entries.map(([reason, count]) => `<li>${reason}: ${count}</li>`).join("");
    return `<div class="rejection-summary">Причины отказа среди отклонённых кандидатов:<ul>${items}</ul></div>`;
  }

  function renderRecommendation(response) {
    lastRecommendation = response;
    cardsBox.innerHTML = "";

    if (response.status === "MATCHED") {
      setStatus("matched", `Найдено подходящих вариантов: ${response.results.length}.`);
      for (const card of response.results) {
        cardsBox.appendChild(renderCard(card));
      }
      return;
    }

    if (response.status === "CATEGORY_ABSENT") {
      setStatus(
        "category-absent",
        "Эта категория подрядчиков отсутствует в выбранном городе — по каталогу в этом городе таких подрядчиков нет вовсе."
      );
      return;
    }

    // NO_MATCH
    setStatus(
      "no-match",
      "Подрядчики этой категории в городе есть, но ни один не подходит под указанные условия (дата/формат/бюджет/язык/длительность)." +
        renderRejectionSummary(response.rejection_summary)
    );
  }

  function badge(text, cls) {
    return `<span class="badge ${cls || ""}">${text}</span>`;
  }

  function renderCard(card) {
    const el = document.createElement("article");
    el.className = "card";

    const badges = [];
    if (card.synthetic) badges.push(badge("синтетический профиль", "synthetic"));
    if (card.city_imputed) badges.push(badge("город восстановлен", "imputed"));
    if (card.price_imputed) badges.push(badge("цена восстановлена", "imputed"));
    if (card.semantic_score != null) {
      badges.push(badge("семантическая релевантность: " + card.semantic_score.toFixed(3), "semantic"));
    }

    el.innerHTML = `
      <div class="card-header">
        <span class="card-name">${escapeHtml(card.name)}</span>
        <span class="card-price">от ${formatPrice(card.price_from_kzt)} ₸</span>
      </div>
      <div class="card-meta">${escapeHtml(card.categories.join(", "))} · ${escapeHtml(card.city)}</div>
      <div class="card-meta">Форматы: ${escapeHtml(card.event_formats.join(", "))}</div>
      <div class="card-meta">Языки: ${escapeHtml(card.languages.join(", "))}${
      card.max_hours != null ? " · до " + card.max_hours + " ч" : ""
    }</div>
      <div class="badges">${badges.join("")}</div>
      <div class="explanation">
        <div class="explanation-label">Почему рекомендован</div>
        ${escapeHtml(card.explanation)}
      </div>
    `;
    return el;
  }

  function formatPrice(value) {
    return new Intl.NumberFormat("ru-RU").format(value);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  async function runSearch(search) {
    setStatus("idle", "Ищу подходящих подрядчиков…");
    try {
      const res = await fetch("/api/v1/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(search),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setStatus("error", "Ошибка запроса: " + (body.detail || res.status));
        return;
      }
      const data = await res.json();
      renderRecommendation(data);
    } catch (err) {
      setStatus("error", "Не удалось выполнить поиск — сервер недоступен.");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    currentSearch = readFormAsSearch();
    runSearch(currentSearch);
  });

  function addChatMessage(role, text) {
    const el = document.createElement("div");
    el.className = "chat-msg " + role;
    el.textContent = text;
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    addChatMessage("user", message);
    chatInput.value = "";
    chatInput.disabled = true;

    try {
      const res = await fetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, current_search: currentSearch }),
      });
      if (!res.ok) {
        addChatMessage("system", "Ошибка запроса к AI-помощнику.");
        return;
      }
      const data = await res.json();
      currentSearch = data.search;
      applySearchToForm(currentSearch);
      addChatMessage("assistant", data.assistant_message);
      if (data.recommendation) {
        renderRecommendation(data.recommendation);
      }
    } catch (err) {
      addChatMessage("system", "AI-помощник недоступен — сервер не отвечает.");
    } finally {
      chatInput.disabled = false;
      chatInput.focus();
    }
  });

  loadCatalogOptions();
})();
