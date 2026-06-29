from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from nicegui import ui

SaveDocument = Callable[[dict[str, object]], str]

AMOUNT_OPTIONS = ['wenig', 'mittel', 'viel']
COLOR_OPTIONS = ['klar', 'rosa', 'rot']
DEFAULT_AMOUNT = 'mittel'
DEFAULT_COLOR = 'klar'
TUMOR_ENTRY_TYPE = 'tumor'


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
            amount_select = ui.select(
                AMOUNT_OPTIONS,
                label='Menge',
                value=DEFAULT_AMOUNT,
            ).classes('w-64 max-w-full')
            color_select = ui.select(
                COLOR_OPTIONS,
                label='Farbe',
                value=DEFAULT_COLOR,
            ).classes('w-64 max-w-full')

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
            ui.button('Zurueck', on_click=lambda: ui.navigate.to('/')).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
