# Ancient Text Research Kit

[English](#english-overview) · [Русский](#описание-на-русском)

## English overview

Ancient Text Research Kit is an open, AI-assisted research lab and a reusable set of agent instructions for studying ancient signs, texts, religious ideas and ritual practices. Its goal is to build and test explanations of how these signs conveyed meaning and how their use changed over time.

The study starts with the earliest surviving evidence and follows overlapping regional timelines. The method combines analysis of original images where available, attempts at decipherment, comparison and synthesis. Each case distinguishes visible marks, published readings, our own reading hypotheses, and interpretations of meaning or function. Source references, alternative explanations and unresolved questions remain part of the record.

The repository includes English agent instructions, research templates, an evidence registry, a static website, and an evolving comparative study currently written in Russian. You can follow the research, inspect the evidence, or adapt the kit for your own investigation. The main synthesis is kept within 30 rendered pages, with detailed object studies linked separately.

[Read the study (Russian)](study/reports/main_research.md) · [Use the agent instructions](AGENTS.md) · [Explore the templates](templates/cycle.md)

To build and check the local reader, use Python 3.9 or newer and the [commands below](#прочитать-и-проверить). These local tools need no extra packages or API key. An agent continuing the research needs access to the relevant sources.

Original code and instructions are licensed under MIT; original research prose under CC BY 4.0. Third-party editions, translations and images retain their own terms. See [licensing and attribution](LICENSING.md).

## Описание на русском

Лаборатория для построения проверяемой модели древних знаков, текстов, религиозных представлений и практик через анализ оригиналов, расшифровку, сравнение и синтез. В комплекте метод, инструкции агенту и пополняемое исследование на русском языке. Рабочая редакция 0.2.4, 11 октября 2026.

[Читать на сайте](https://dorsem.github.io/ancient-text-research-kit/) · [Важные выводы и основания](https://dorsem.github.io/ancient-text-research-kit/evidence.html) · [Репозиторий](https://github.com/dorsem/ancient-text-research-kit)

Шаблон и собственный код доступны по MIT, собственный исследовательский текст по CC BY 4.0. [Область действия лицензий и атрибуция](LICENSING.md).

Начните с [исследования](study/reports/main_research.md). Введение объясняет цель и четыре предметных результата; далее показана текущая модель и шесть выводов с основаниями. Модель строится по материалу, а общая древняя система не предполагается заранее. [Общая цель и ближайшая проверка](study/PROJECT.md). Полные чтения и разночтения вынесены в предметные карточки; основной текст сохраняет предел 30 страниц вместе с иллюстрациями и библиографией. Печатная версия основного HTML-текста редакции 013 занимает **21 страницу A4** в Google Chrome 154.0.8037.99, включая библиографию и ссылки на изображения. Изображения и подробные карточки остаются по ссылкам; параметры и контрольные суммы записаны в docs/VALIDATION.json. В другом браузере пагинация может отличаться.

## Прочитать и проверить

Можно читать Markdown прямо на GitHub. Для проверки и сборки HTML нужен Python 3.9 или новее, без дополнительных пакетов, сервера, ключа API или Foundry. Из каталога проекта выполните:

```sh
python3 tools/lab.py build
python3 tools/lab.py validate
python3 -m unittest discover -s tests -v
```

Откройте полученный site/index.html в браузере. В комплекте уже есть такая сборка. Она работает с локального диска; ссылки на оригиналы ведут к внешним хранителям. Доступность этих сайтов требует сети и может меняться.

## Продолжить исследование с агентом

Передайте агенту этот каталог и запрос: «Прочитай AGENTS.md и study/PROJECT.md. Выполни одну проверку из активной очереди: проанализируй оригинал, отдели собственные наблюдения и варианты чтения от опубликованных, проверь объяснение против альтернативы и покажи, что это меняет или подтверждает в общей модели». Агенту понадобится доступ к источникам. Один агент может выполнить роли последовательно; такую проверку нельзя называть независимым рецензированием.

Для другого исследования создайте отдельную копию проекта, задайте свой вопрос в study/PROJECT.md и заполните [шаблоны](templates/cycle.md). Образец реестра показан в study/registry.json. Уберите пример только после сохранения своей рабочей копии. Инструкция не гарантирует одинаковое качество у разных моделей.

## Как устроены записи

- study/reports/main_research.md: единственный основной синтез. Здесь редактируется рассказ и формулировки C01–C06.
- study/corpus/: оригиналы по ссылкам, покрытие осмотра, опубликованные и собственные чтения, рабочие русские переводы, гипотезы, проверки и ограничения по каждому предмету.
- templates/: шаблоны предмета, анализа изображения и различающей проверки объяснения.
- study/registry.json: небольшой указатель от C01–C06 к точным основаниям, независимым группам источников и проверкам. Он не заменяет карточки и не повторяет текст выводов.
- study/changes/: история содержательных пересмотров. Проверка примера C02 разбирает несоответствие изображения и подписи рисунка.
- docs/: метод, обзор инструментов 2026 года, решение о Foundry и подготовка публикации.
- tools/lab.py: проверка структуры, ссылок и актуальности HTML. Успешный запуск не подтверждает правильность перевода.

Внешние фотографии, музейные PDF и пользовательский снимок не включены в этот переносимый пакет. Сохранены ссылки и точные страницы. Некоторые архивные карточки описывают проверки локальных копий в исходной лаборатории; это журнал прежних действий, а не заявление о наличии этих файлов здесь. [Происхождение примера](docs/PROVENANCE.md).

[Как обновлять пакет и избежать двух расходящихся версий](docs/UPDATES.md).
