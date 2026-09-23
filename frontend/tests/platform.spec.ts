import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Найти совпадения'})).toBeEnabled();
});

test('basic selection, evidence, profile, comparison, and persisted history',async({page})=>{
  const errors:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  const cards=page.getByTestId('contractor-card');
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText('Куррапика');
  await cards.first().getByText('На чём основан выбор').click();
  await expect(cards.first().locator('blockquote')).toBeVisible();
  await cards.first().getByRole('button',{name:'Куррапика'}).click();
  await expect(page.getByRole('dialog')).toContainText('О подрядчике');
  await page.getByRole('button',{name:'Закрыть окно'}).click();
  await cards.nth(0).getByRole('checkbox').check();
  await cards.nth(1).getByRole('checkbox').check();
  await page.locator('.compare-bar').getByRole('button',{name:'Сравнить'}).click();
  await expect(page.getByRole('dialog')).toContainText('Аня Форджер');
  await page.keyboard.press('Escape');
  await page.screenshot({path:'../data/screenshots/desktop.png',fullPage:true});
  await page.reload();
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  await page.getByRole('button',{name:/История/}).click();
  await expect(page.locator('.history-row')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('same query same order; changed date changes availability',async({page})=>{
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  const before=await page.locator('.name-button').allTextContents();
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByRole('button',{name:'Найти совпадения'})).toBeEnabled();
  expect(await page.locator('.name-button').allTextContents()).toEqual(before);
  await page.getByLabel('Дата мероприятия',{exact:true}).fill('2026-10-17');
  await expect(page.getByTestId('contractor-card')).toHaveCount(0);
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  expect(await page.locator('.name-button').allTextContents()).not.toEqual(before);
  await expect(page.locator('.date-changes')).toContainText('занят');
});

test('rare category respects not-applicable duration',async({page})=>{
  await page.getByLabel('Категория подрядчика',{exact:true}).selectOption('Флорист');
  await page.getByLabel('Тип мероприятия',{exact:true}).selectOption('свадьба');
  await page.getByLabel('Бюджет на подрядчика',{exact:true}).fill('500000');
  await page.getByLabel('Длительность',{exact:true}).fill('24');
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(1);
  await expect(page.getByTestId('contractor-card')).toContainText('Тони Тони Чоппер');
  await expect(page.getByTestId('contractor-card')).toContainText('Длительность неприменима');
  await expect(page.locator('.rejection-summary')).toBeVisible();
});

test('empty result and verified alternative budget',async({page})=>{
  await page.getByLabel('Бюджет на подрядчика',{exact:true}).fill('10000');
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByText('В этот раз условия не совпали')).toBeVisible();
  await page.getByRole('button',{name:'Показать альтернативы'}).click();
  await page.locator('.alternative-list').getByRole('button',{name:/Бюджет от/}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(1);
  await expect(page.getByLabel('Бюджет на подрядчика',{exact:true})).toHaveValue('500000');
});

test('missing category is distinct from no matches',async({page})=>{
  await page.getByLabel('Город',{exact:true}).selectOption('Астана');
  await page.getByLabel('Категория подрядчика',{exact:true}).selectOption('Декоратор');
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByText('Здесь пока нет такой категории')).toBeVisible();
  await expect(page.getByRole('button',{name:'Показать альтернативы'})).toHaveCount(0);
});

test('assistant updates shared form and returns grounded results',async({page})=>{
  await page.getByLabel('Сообщение помощнику').fill('А теперь на 17 октября');
  await page.getByRole('button',{name:'Отправить сообщение'}).click();
  await expect(page.getByLabel('Дата мероприятия',{exact:true})).toHaveValue('2026-10-17');
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  await expect(page.getByLabel('Бюджет на подрядчика',{exact:true})).toHaveValue('1000000');
  await page.getByLabel('Сообщение помощнику').fill('Забронируй первого');
  await page.getByRole('button',{name:'Отправить сообщение'}).click();
  await expect(page.getByRole('log')).toContainText('не выполняются');
});

test('mobile layout has no overflow and assistant opens on request',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await expect(page.getByRole('button',{name:'Найти совпадения'})).toBeEnabled();
  await expect(page.getByLabel('Сообщение помощнику')).toHaveCount(0);
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../data/screenshots/mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Помощник',exact:true}).click();
  await expect(page.getByLabel('Сообщение помощнику')).toBeVisible();
  await page.getByRole('button',{name:'Скрыть помощника'}).click();
});

test('filter results become chat context and questions do not modify filters',async({page})=>{
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(page.getByTestId('contractor-card')).toHaveCount(3);
  const context=page.getByTestId('chat-selection');
  await expect(context).toContainText('Вижу вашу подборку');
  await expect(context).toContainText('Куррапика');
  await expect(context).toContainText('Аня Форджер');
  await page.getByLabel('Сообщение помощнику').fill('Второй говорит на английском?');
  await page.getByRole('button',{name:'Отправить сообщение'}).click();
  await expect(page.locator('.message.assistant').last()).toContainText('Аня Форджер');
  await expect(page.locator('.message.assistant').last()).toContainText('языки работы: русский');
  await expect(page.getByLabel('Язык',{exact:true})).toHaveValue('');
  await expect(page.locator('.nav-item .count')).toHaveText('1');
  await page.getByLabel('Дата мероприятия',{exact:true}).fill('2026-10-17');
  await expect(context).toContainText('Обсуждаем предыдущую подборку');
  await page.getByRole('button',{name:'Найти совпадения'}).click();
  await expect(context).toContainText('Буллма');
  await expect(context).not.toContainText('Аня Форджер');
  await page.getByLabel('Сообщение помощнику').fill('Расскажи про второго');
  await page.getByRole('button',{name:'Отправить сообщение'}).click();
  await expect(page.locator('.message.assistant').last()).toContainText('Буллма');
  await page.reload();
  await expect(context).toContainText('Буллма');
  await page.getByLabel('Сообщение помощнику').fill('Сколько стоит второй?');
  await page.getByRole('button',{name:'Отправить сообщение'}).click();
  await expect(page.locator('.message.assistant').last()).toContainText('1 000 000');
});
