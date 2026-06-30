from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from nicegui import app, ui

SaveDocument = Callable[[dict[str, object]], str]

AMOUNT_OPTIONS = ['wenig', 'mittel', 'viel']
COLOR_OPTIONS = ['klar', 'rosa', 'rot']
DEFAULT_AMOUNT = 'mittel'
DEFAULT_COLOR = 'klar'
LAST_AMOUNT_STORAGE_KEY = 'tumor_last_amount'
LAST_COLOR_STORAGE_KEY = 'tumor_last_color'
TUMOR_ENTRY_TYPE = 'tumor'


def prioritize_option(options: list[str], selected_value: object) -> list[str]:
    selected = str(selected_value or '').strip()
    if not selected or selected not in options:
        return list(options)
    return [selected, *[option for option in options if option != selected]]


def remembered_option(storage_key: str, options: list[str], default_value: str) -> str:
    selected = str(app.storage.user.get(storage_key, '') or '').strip()
    return selected if selected in options else default_value


def current_quarter_hour() -> datetime:
    now = datetime.now()
    minute = (now.minute // 15) * 15
    return now.replace(minute=minute, second=0, microsecond=0)


def register_tumor_pages(build_shell: Callable[[str], None], save_document: SaveDocument) -> None:
    @ui.page('/tumor')
    def tumor_page() -> None:
        build_shell('Tumor')

        with ui.column().classes('min-h-screen w-full items-center justify-center gap-5 px-6'):
            ui.label('Tumor').classes('text-3xl font-bold text-slate-800 text-center')
            initial_amount = remembered_option(LAST_AMOUNT_STORAGE_KEY, AMOUNT_OPTIONS, DEFAULT_AMOUNT)
            initial_color = remembered_option(LAST_COLOR_STORAGE_KEY, COLOR_OPTIONS, DEFAULT_COLOR)
            amount_select = ui.select(
                prioritize_option(AMOUNT_OPTIONS, initial_amount),
                label='Menge',
                value=initial_amount,
            ).classes('w-64 max-w-full')
            color_select = ui.select(
                prioritize_option(COLOR_OPTIONS, initial_color),
                label='Farbe',
                value=initial_color,
            ).classes('w-64 max-w-full')

            def update_amount_selection() -> None:
                if amount_select.value:
                    app.storage.user[LAST_AMOUNT_STORAGE_KEY] = amount_select.value
                amount_select.set_options(
                    prioritize_option(AMOUNT_OPTIONS, amount_select.value),
                    value=amount_select.value,
                )

            def update_color_selection() -> None:
                if color_select.value:
                    app.storage.user[LAST_COLOR_STORAGE_KEY] = color_select.value
                color_select.set_options(
                    prioritize_option(COLOR_OPTIONS, color_select.value),
                    value=color_select.value,
                )

            amount_select.on_value_change(lambda _: update_amount_selection())
            color_select.on_value_change(lambda _: update_color_selection())

            def save_entry() -> None:
                timestamp = current_quarter_hour()
                document = {
                    'typ': TUMOR_ENTRY_TYPE,
                    'menge': amount_select.value or DEFAULT_AMOUNT,
                    'farbe': color_select.value or DEFAULT_COLOR,
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
                .style('background: #B84A5A !important; color: white !important;')
            timestamp_label = ui.label('').classes(
                'text-base font-medium text-slate-700 text-center'
            )
            ui.button('Zurueck', on_click=lambda: ui.run_javascript("window.location.replace('/')")).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
