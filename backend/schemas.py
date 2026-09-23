from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import CALENDAR_START, CALENDAR_END

CITIES = ['Алматы', 'Астана', 'Зарубежье']
FORMATS = ['свадьба', 'той', 'корпоратив', 'конференция', 'юбилей', 'день рождения']
LANGUAGES = ['русский', 'казахский', 'английский']
CATEGORIES = ['Ведущий', 'Фотограф', 'Банкетный зал', 'Видеограф', 'Декоратор', 'Флорист', 'Подарки и сувениры', 'Ведущий церемонии', 'Инструменталист', 'Лайв-бэнд', 'Национальный ансамбль', 'Танцевальный коллектив', 'Шоу-программа', 'Фото и видеобудки', 'Загородная площадка', 'Ресторан', 'Отель']
FIELD_LABELS = {'city': 'город', 'event_date': 'дата с годом', 'event_format': 'тип мероприятия', 'category': 'категория подрядчика', 'budget_kzt': 'бюджет на подрядчика'}


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    city: str | None = None
    event_date: date | None = None
    event_format: str | None = None
    category: str | None = None
    budget_kzt: int | None = Field(None, gt=0, le=1_000_000_000)
    duration_hours: float | None = Field(None, gt=0, le=100)
    language: str | None = None
    preferences: str = Field('', max_length=2000)

    @field_validator('city', 'event_format', 'category', 'language')
    @classmethod
    def known_value(cls, value, info):
        allowed = {'city': CITIES, 'event_format': FORMATS, 'category': CATEGORIES, 'language': LANGUAGES}
        if value is not None and value not in allowed[info.field_name]:
            raise ValueError('Выберите значение из справочника')
        return value

    @field_validator('event_date')
    @classmethod
    def calendar_window(cls, value):
        if value and not date.fromisoformat(CALENDAR_START) <= value <= date.fromisoformat(CALENDAR_END):
            raise ValueError('Календарь доступен только с 23.09.2026 по 31.12.2026')
        return value

    def missing(self):
        return [name for name in FIELD_LABELS if getattr(self, name) is None]


class RequestUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    draft: Draft


class RunInput(BaseModel):
    expected_revision: int = Field(ge=1)


class ChatInput(BaseModel):
    request_id: str
    expected_revision: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=4000)
    displayed_run_id: str | None = Field(None, max_length=100)


class CompareInput(BaseModel):
    candidate_ids: list[str] = Field(min_length=2, max_length=3)


class AlternativeInput(BaseModel):
    expected_revision: int = Field(ge=1)
    kind: Literal['all', 'date', 'budget', 'language', 'duration'] = 'all'

