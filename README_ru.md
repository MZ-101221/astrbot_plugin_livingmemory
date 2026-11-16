<p align="center">
  <a href="README.md">中文</a> · <a href="README_en.md">English</a> · <strong>Русский</strong>
</p>

![LivingMemory: долговременная память, связывающая предпочтения, людей, планы и контекст](docs/public/images/livingmemory-cover.svg)

<p align="center">
  <a href="https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/"><strong>Документация · EN</strong></a> ·
  <a href="https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/webui"><strong>Панель управления</strong></a> ·
  <a href="https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases"><strong>Скачать</strong></a> ·
  <a href="https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/issues"><strong>Обратная связь</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-52675c?style=flat-square" alt="Python 3.10 или новее">
  <img src="https://img.shields.io/badge/AstrBot-4.24.2%2B-52675c?style=flat-square" alt="Для представлений плагина требуется AstrBot 4.24.2 или новее">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-52675c?style=flat-square" alt="AGPL-3.0"></a>
</p>

## Сохранить важное из разговора

LivingMemory хранит для AstrBot предпочтения, отношения, ход проектов и прежние договорённости. Плагин создаёт сводки диалогов, находит нужный контекст с помощью ключевых слов, векторов и графа, а также управляет памятью через архивирование, затухание и усиление при обращении.

> **Последняя стабильная версия: 2.13.0**<br>
> Интерфейс управления по умолчанию переведён на macOS 26 Liquid Glass, добавлена панель оформления, стили сведены к общим токенам. Команды, настройки и структура базы не изменились, миграция не требуется.<br>
> [Скачать 2.13.0](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases/tag/2.13.0) · [Обновление · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/releases) · [Прежние версии](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases)

## От сохранения к воспоминанию

- **Автоматическая запись** — Сводки создаются после заданного числа реплик. Важные записи могут сохранять исходные сообщения для проверки и повторного обобщения.
- **Поиск с учётом контекста** — Документы и граф поддерживают поиск по ключевым словам и векторам, объединение рейтингов, фильтрацию области и проверку жизненного цикла.
- **Инструменты агента** — `recall_long_term_memory` и `memorize_long_term_memory` позволяют читать и записывать долговременную память по мере необходимости.
- **Управление через Views** — Просмотр графов 2D/3D, приближение к узлам и связанным воспоминаниям, редактирование памяти, тестирование поиска, настройка промптов и состояние системы.

## Одно пространство, четыре стиля

**macOS 26** — парящее стекло Liquid Glass поверх обоев. **Studio** — мягкие карточки. **Paper** — тёплые поверхности и заголовки с засечками. **Terminal** — моноширинный шрифт и приборная компоновка.

Каждый стиль поддерживает светлый, тёмный и автоматический режимы. Переключение доступно в настройках внешнего вида; выбор сохраняется в текущем браузере. При увеличении графа подписи остаются стабильными, а на телефоне доступны фильтр диалога и переход к записи.

Граф 3D использует отдельную сцену с тёплым светом, вращением, масштабированием, фокусировкой на узлах и связанными воспоминаниями. Узлы и связи отрисовываются пакетами на GPU.

[Темы и работа с панелью · EN →](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/webui)

## Начало работы

1. Установите плагин из каталога AstrBot или поместите выбранную версию в `data/plugins/astrbot_plugin_livingmemory`.
2. Сначала создайте и включите провайдер Embedding в разделе AstrBot «Model Providers → Embedding» (настройка бесплатной `BAAI/bge-m3` описана [здесь · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/guide/embedding-model)), затем перезагрузите AstrBot и укажите ID этого провайдера и LLM-провайдера в настройках LivingMemory. Пустое поле Embedding лишь выбирает первый доступный провайдер, что может привести к неверной модели или сбою инициализации индексов.
3. Откройте `Plugins → LivingMemory → Views → dashboard` (в старых версиях AstrBot раздел называется `Pages`). Для представлений плагина требуется **AstrBot 4.24.2 или новее**.

Для тестирования скачайте указанный выше тег и следуйте [инструкции по установке и откату · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/releases). Перед обновлением сохраните резервную копию данных и конфигурации плагина.

После нескольких реплик проверьте `/lmem status`, `/lmem summarize` и `/lmem search ключевые слова`.

## Бесплатная модель Embedding

Семантический поиск LivingMemory зависит от Embedding Provider. Рекомендуется бесплатная модель `BAAI/bge-m3` от SiliconFlow (1024 измерения). В разделе AstrBot «Model Providers → Embedding → Add Model Provider → OpenAI Embedding» укажите:

- Provider ID: оставьте значение, созданное AstrBot, например `openai_embedding`
- API Base URL: `https://api.siliconflow.cn/v1`
- API Key: ключ, созданный в консоли SiliconFlow
- Embedding Model: `BAAI/bge-m3`
- Embedding Dimensions: `1024`

Сохраните и протестируйте провайдер, затем укажите его Provider ID в `provider_settings.embedding_provider_id` настроек LivingMemory. ID модели и ID провайдера различаются; полная инструкция доступна [здесь · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/guide/embedding-model).

## Планируемые возможности этого форка

Форк развивается от версии 2.13.0. Области памяти, цепочка замещения, профили пользователей, общая память канала и внешние интерфейсы из первоначального плана уже реализованы в upstream. Этот форк добавляет оставшиеся четыре возможности как выключенные по умолчанию переключатели, поэтому после обновления поведение совпадает с 2.13.0.

Уже реализовано в upstream 2.13.0:

- области памяти `legacy` / `session` / `user` / `global` через `filtering_settings.memory_scope_mode`, а также принудительная изоляция, белые списки и псевдонимы;
- цепочка замещения: у заменённых записей остаётся указатель `superseded_by`, в выдачу они не попадают, `/lmem trace` проходит по цепочке;
- профили `memory_profiles` с историей версий;
- общая память канала `livingmemory:channel:<платформа>:<группа>`, по умолчанию выключена;
- внешние интерфейсы: `core/external_api_server.py` и `scripts/memory_mcp_server.py`.

Добавлено в этом форке (по умолчанию выключено):

- **метка приватности для каждой записи** — `privacy_settings.enabled`: при записи `privacy` приводится к `public` или `private:<область владельца>`, при выборке фильтруется по говорящему; в группах сравнивается только область уровня пользователя, в личных чатах допускается и владелец сессии, метка без владельца считается невидимой;
- **состояние актуальности** — `freshness_settings.enabled`: `timeless` / `current` / `pending` / `outdated` вычисляется из `valid_until` и `superseded_by` при каждом чтении, при инъекции добавляется пометка на китайском, уведомления о просрочке и замещении отключаются отдельно;
- **режим запуска инъекции** — `recall_engine.injection_mode`: `auto` (каждый ход, по умолчанию), `on_demand` (без инъекции, вместо неё подсказка модели вызвать инструмент поиска), `hybrid` (инъекция только при достижении `recall_engine.hybrid_auto_threshold`, по умолчанию 0.55);
- **привязка инъекции к говорящему** — `recall_engine.speaker_locked_injection`: в группах остаются только записи уровня пользователя текущего собеседника, общая память этой группы и глобальные записи.

Состояние актуальности не сохраняется в базе и вычисляется на чтении; метка приватности пишется в `documents.metadata.privacy` только при включённом переключателе. API списка возвращает оба поля, API редактирования принимает их; в таблице панели управления они пока не отображаются.

Не реализовано:

- автоматическое переписывание цепочки замещения: `outdated` служит только подсказкой, плагин не проставляет `superseded_by` старым записям — это по-прежнему делает процесс консолидации upstream.

Проектирование полей и файлы реализации описаны в [ANALYSIS.md](ANALYSIS.md).

## Подробнее

[Быстрый старт · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/guide/getting-started) · [Настройки · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/configuration) · [Команды · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/commands) · [Архитектура · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/architecture) · [История изменений](CHANGELOG.md)

При обновлении с v1.4.0–v1.4.2 сначала прочитайте [инструкцию по миграции · EN](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/en/configuration#backup-migration-and-cleanup).

---

Сообщество: группа QQ 2: `1129994749` (новая) · [Группа QQ 1: 953245617](https://qm.qq.com/cgi-bin/qm/qr?k=WdyqoP-AOEXqGAN08lOFfVSguF2EmBeO&jump_from=webapi&authKey=tPyfv90TVYSGVhbAhsAZCcSBotJuTTLf03wnn7/lQZPUkWfoQ/J8e9nkAipkOzwh) (заполнена) · Пароль: `lxfight`<br>
Лицензия: [AGPL-3.0](LICENSE)
