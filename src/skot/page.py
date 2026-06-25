from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from nicegui import app, ui

SaveDocument = Callable[[dict[str, object]], str]

CONSISTENCY_OPTIONS = ['sehr hart', 'hart', 'normal', 'weich', 'sehr weich', 'flüssig', 'Tumor']
LAST_CONSISTENCY_STORAGE_KEY = 'kot_last_consistency'


def prioritize_option(options: list[str], selected_value: object) -> list[str]:
    selected = str(selected_value or '').strip()
    if not selected or selected not in options:
        return list(options)
    return [selected, *[option for option in options if option != selected]]


def current_quarter_hour() -> datetime:
    now = datetime.now()
    minute = (now.minute // 15) * 15
    return now.replace(minute=minute, second=0, microsecond=0)


def remembered_consistency() -> str:
    selected = str(app.storage.user.get(LAST_CONSISTENCY_STORAGE_KEY, '') or '').strip()
    return selected if selected in CONSISTENCY_OPTIONS else 'hart'


def register_kot_pages(build_shell: Callable[[str], None], save_document: SaveDocument) -> None:
    @ui.page('/kot')
    def kot_page() -> None:
        build_shell('Kot')

        with ui.column().classes('min-h-screen w-full items-center justify-center gap-5 px-6'):
            ui.label('Kot').classes('text-3xl font-bold text-slate-800 text-center')
            initial_consistency = remembered_consistency()
            consistency_select = ui.select(
                prioritize_option(CONSISTENCY_OPTIONS, initial_consistency),
                value=initial_consistency,
            ).classes('w-64 max-w-full')
            def update_consistency_selection() -> None:
                if consistency_select.value:
                    app.storage.user[LAST_CONSISTENCY_STORAGE_KEY] = consistency_select.value
                consistency_select.set_options(
                    prioritize_option(CONSISTENCY_OPTIONS, consistency_select.value),
                    value=consistency_select.value,
                )

            consistency_select.on_value_change(lambda _: update_consistency_selection())

            def save_entry() -> None:
                timestamp = current_quarter_hour()
                document = {
                    'typ': 'kot',
                    'konsistenz': consistency_select.value,
                    'datum': timestamp.strftime('%Y-%m-%d'),
                    'zeit': timestamp.strftime('%H:%M'),
                }
                
                try:
                    document_id = save_document(document)
                except Exception as exc:
                    timestamp_label.set_text('Speichern fehlgeschlagen.')
                    ui.notify(f'Speichern fehlgeschlagen: {exc}', color='negative')
                    return

                timestamp_label.set_text(f"Datum und Zeit: {document['datum']} {document['zeit']}")
                ui.notify(f'Gespeichert: {document_id}', color='positive')

            ui.button('save', on_click=save_entry).props('unelevated') \
                .classes(
                    'w-64 max-w-full rounded-2xl px-8 py-4 text-lg font-semibold text-white shadow-lg'
                ) \
                .style('background-color: #9b6b43;')
            timestamp_label = ui.label('').classes(
                'text-base font-medium text-slate-700 text-center'
            )
            ui.button('Zurueck', on_click=lambda: ui.navigate.to('/')).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
