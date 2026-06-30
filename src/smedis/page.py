from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from nicegui import ui

from src.sessen.page import EditableOptionsSelect

SaveDocument = Callable[[dict[str, object]], str]
FetchOptions = Callable[[], list[str]]
SaveOption = Callable[[str], list[str]]
RenameOption = Callable[[str, str], list[str]]

LAST_MEDICATION_STORAGE_KEY = 'medis_last_medication'
MEDIS_ENTRY_TYPE = 'medis'


def current_quarter_hour() -> datetime:
    now = datetime.now()
    minute = (now.minute // 15) * 15
    return now.replace(minute=minute, second=0, microsecond=0)


def register_medis_pages(
    build_shell: Callable[[str], None],
    save_document: SaveDocument,
    fetch_medications: FetchOptions,
    add_medication: SaveOption,
    delete_medication: SaveOption,
    rename_medication: RenameOption,
) -> None:
    @ui.page('/medis')
    def medis_page() -> None:
        build_shell('Medis')

        with ui.column().classes('min-h-screen w-full items-center justify-center gap-5 px-6'):
            ui.label('Medis').classes('text-3xl font-bold text-slate-800 text-center')
            try:
                medication_options = fetch_medications()
            except Exception:
                medication_options = []

            medication_select = EditableOptionsSelect(
                'Medikament',
                medication_options,
                'Medikament',
                fetch_medications,
                add_medication,
                delete_medication,
                rename_medication,
                LAST_MEDICATION_STORAGE_KEY,
            )

            def update_medication_options(options: list[str], value: str | None = None) -> None:
                selected = value if value in options else medication_select.value
                if selected not in options:
                    selected = options[0] if options else None
                medication_select.set_options(options, selected)

            def save_entry() -> None:
                medication = str(medication_select.value or '').strip()
                if not medication:
                    timestamp_label.set_text('Bitte Medikament ausfuellen.')
                    ui.notify('Bitte Medikament ausfuellen.', color='warning')
                    return

                timestamp = current_quarter_hour()
                document = {
                    'typ': MEDIS_ENTRY_TYPE,
                    'medikament': medication,
                    'datum': timestamp.strftime('%Y-%m-%d'),
                    'zeit': timestamp.strftime('%H:%M'),
                }

                try:
                    options = add_medication(medication)
                    update_medication_options(options, medication)
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
                .style('background: #5D6EAD !important; color: white !important;')
            timestamp_label = ui.label('').classes(
                'text-base font-medium text-slate-700 text-center'
            )
            ui.button('Zurueck', on_click=lambda: ui.run_javascript("window.location.replace('/')")).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
