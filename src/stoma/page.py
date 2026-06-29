from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from nicegui import app, ui

SaveDocument = Callable[[dict[str, object]], str]

CONSISTENCY_OPTIONS = ['sehr hart', 'hart', 'normal', 'weich', 'sehr weich', 'flüssig']
AMOUNT_OPTIONS = ['wenig', 'mittel', 'viel']
LAST_CONSISTENCY_STORAGE_KEY = 'stoma_last_consistency'
TUMOR_CONSISTENCY = 'Tumor'
DEFAULT_AMOUNT = 'mittel'


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


def register_stoma_pages(build_shell: Callable[[str], None], save_document: SaveDocument) -> None:
    def render_stoma_page(
        title: str,
        initial_value: str | None = None,
        show_consistency_select: bool = True,
        show_amount_select: bool = False,
        show_plate_switch: bool = True,
    ) -> None:
        build_shell(title)

        with ui.column().classes('min-h-screen w-full items-center justify-center gap-5 px-6'):
            ui.label(title).classes('text-3xl font-bold text-slate-800 text-center')
            if show_consistency_select:
                initial_consistency = (
                    initial_value
                    if initial_value in CONSISTENCY_OPTIONS
                    else remembered_consistency()
                )
            else:
                initial_consistency = initial_value or remembered_consistency()
            consistency_value = {'value': initial_consistency}
            if show_consistency_select:
                consistency_select = ui.select(
                    prioritize_option(CONSISTENCY_OPTIONS, initial_consistency),
                    value=initial_consistency,
                ).classes('w-64 max-w-full')
                def update_consistency_selection() -> None:
                    if consistency_select.value:
                        consistency_value['value'] = str(consistency_select.value)
                        app.storage.user[LAST_CONSISTENCY_STORAGE_KEY] = consistency_select.value
                    consistency_select.set_options(
                        prioritize_option(CONSISTENCY_OPTIONS, consistency_select.value),
                        value=consistency_select.value,
                    )

                consistency_select.on_value_change(lambda _: update_consistency_selection())
            plate_switch = None
            if show_plate_switch:
                plate_switch = ui.switch('Platte', value=False).props('dense')
            amount_select = None
            if show_amount_select:
                amount_select = ui.select(
                    AMOUNT_OPTIONS,
                    label='Menge',
                    value=DEFAULT_AMOUNT,
                ).classes('w-64 max-w-full')

            def save_entry() -> None:
                timestamp = current_quarter_hour()
                document = {
                    'typ': 'stoma',
                    'konsistenz': consistency_value['value'],
                    'datum': timestamp.strftime('%Y-%m-%d'),
                    'zeit': timestamp.strftime('%H:%M'),
                }
                if plate_switch is not None:
                    document['platte'] = bool(plate_switch.value)
                if amount_select is not None:
                    document['menge'] = amount_select.value or DEFAULT_AMOUNT
                
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

    @ui.page('/stoma')
    def stoma_page() -> None:
        render_stoma_page('Stoma')

    @ui.page('/tumor')
    def tumor_page() -> None:
        render_stoma_page(
            'Tumor',
            TUMOR_CONSISTENCY,
            show_consistency_select=False,
            show_amount_select=True,
            show_plate_switch=False,
        )
