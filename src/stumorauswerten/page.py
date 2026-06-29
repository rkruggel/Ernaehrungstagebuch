from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from nicegui import ui

FetchTumorEntries = Callable[[str, str], list[dict[str, str]]]
UpdateTumorEntry = Callable[[str, dict[str, object]], None]
DeleteTumorEntry = Callable[[str], None]
AMOUNT_OPTIONS = ['wenig', 'mittel', 'viel']
COLOR_OPTIONS = ['klar', 'rosa', 'rot']
DEFAULT_AMOUNT = 'mittel'
DEFAULT_COLOR = 'klar'


def quarter_hour_time(value: object) -> str:
    base_time = str(value or '').strip().split('-', 1)[0]
    try:
        parsed_time = datetime.strptime(base_time, '%H:%M')
    except ValueError:
        return ''
    minute = (parsed_time.minute // 15) * 15
    return parsed_time.replace(minute=minute).strftime('%H:%M')


def register_tumor_analysis_pages(
    build_shell: Callable[[str], None],
    fetch_tumor_entries: FetchTumorEntries,
    update_tumor_entry: UpdateTumorEntry,
    delete_tumor_entry: DeleteTumorEntry,
) -> None:
    @ui.page('/tumor-auswerten')
    def tumor_analysis_page() -> None:
        build_shell('Tumor Auswerten')

        today = date.today().isoformat()

        with ui.column().classes('min-h-screen w-full items-center gap-5 px-6 py-10'):
            ui.label('Tumor Auswerten').classes('text-3xl font-bold text-slate-800 text-center')

            with ui.row().classes('w-full max-w-2xl flex-wrap items-end justify-center gap-4'):
                date_from_input = ui.input('Datum von', value=today).props('type=date') \
                    .classes('w-32 max-w-full')
                date_to_input = ui.input('Datum bis', value=today).props('type=date') \
                    .classes('w-32 max-w-full')
                source_switch = ui.switch(value=False).props('dense')
                with ui.button(icon='check', on_click=lambda: load_entries()).props(
                    'round unelevated color=positive aria-label="OK"'
                ).classes('h-12 w-12'):
                    ui.tooltip('Suchen')

            date_columns = [
                {'name': 'datum', 'label': 'Datum', 'field': 'datum', 'align': 'left'},
                {'name': 'zeit', 'label': 'Zeit', 'field': 'zeit', 'align': 'left'},
            ]
            source_column = {'name': 'quelle', 'label': 'Quelle', 'field': 'quelle', 'align': 'left'}
            data_columns = [
                {'name': 'farbe', 'label': 'Farbe', 'field': 'farbe', 'align': 'left'},
                {'name': 'menge', 'label': 'Menge', 'field': 'menge', 'align': 'left'},
            ]
            action_column = {'name': 'aktionen', 'label': '', 'field': 'aktionen', 'align': 'right'}
            result_table = ui.table(columns=[], rows=[], row_key='row_key') \
                .classes('w-full max-w-2xl')
            result_table.add_slot(
                'body-cell-aktionen',
                '''
                <q-td :props="props">
                    <q-fab icon="more_vert" direction="left" flat dense mini>
                        <q-fab-action icon="edit" color="primary" dense mini
                            @click="$parent.$emit('edit-row', props.row)" />
                        <q-fab-action icon="delete" color="negative" dense mini
                            @click="$parent.$emit('delete-row', props.row)" />
                    </q-fab>
                </q-td>
                ''',
            )
            status_label = ui.label('').classes('text-sm text-slate-600 text-center')

            def visible_columns() -> list[dict[str, str]]:
                columns = [*date_columns]
                if source_switch.value:
                    columns.append(source_column)
                return [*columns, *data_columns, action_column]

            def update_columns() -> None:
                result_table.columns = visible_columns()
                result_table.update()

            def load_entries() -> None:
                date_from = str(date_from_input.value or '')
                date_to = str(date_to_input.value or '')
                if not date_from or not date_to:
                    status_label.set_text('Bitte Datum von und Datum bis ausfuellen.')
                    result_table.rows = []
                    result_table.update()
                    return

                if date_from > date_to:
                    status_label.set_text('Datum von darf nicht nach Datum bis liegen.')
                    result_table.rows = []
                    result_table.update()
                    return

                try:
                    rows = fetch_tumor_entries(date_from, date_to)
                except Exception as exc:
                    status_label.set_text(f'Laden fehlgeschlagen: {exc}')
                    result_table.rows = []
                    result_table.update()
                    return

                result_table.rows = rows
                result_table.update()
                status_label.set_text(f'{len(rows)} Eintraege gefunden.')

            with ui.dialog() as edit_dialog, ui.card().classes('w-[360px] max-w-full gap-3'):
                ui.label('Tumor ändern').classes('text-lg font-semibold text-slate-900')
                edit_id = {'value': ''}
                edit_date_input = ui.input('Datum').props('type=date dense').classes('w-full')
                edit_time_input = ui.input('Zeit').props('type=time step=900 dense') \
                    .classes('w-full')
                edit_color_select = ui.select(
                    COLOR_OPTIONS,
                    label='Farbe',
                    value=DEFAULT_COLOR,
                ).props('dense options-dense').classes('w-full')
                edit_amount_select = ui.select(
                    AMOUNT_OPTIONS,
                    label='Menge',
                    value=DEFAULT_AMOUNT,
                ).props('dense options-dense').classes('w-full')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Abbrechen', on_click=edit_dialog.close).props('flat no-caps dense')
                    ui.button('Speichern', on_click=lambda: save_edit()).props('no-caps dense')

            with ui.dialog() as delete_dialog, ui.card().classes('w-[320px] max-w-full gap-3'):
                delete_id = {'value': ''}
                ui.label('Eintrag löschen?').classes('text-lg font-semibold text-slate-900')
                delete_label = ui.label('').classes('text-sm text-slate-600')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Abbrechen', on_click=delete_dialog.close).props('flat no-caps dense')
                    ui.button('Löschen', on_click=lambda: confirm_delete()).props(
                        'no-caps dense color=negative'
                    )

            def open_edit(row: dict[str, str]) -> None:
                edit_id['value'] = str(row.get('row_key', ''))
                edit_date_input.value = row.get('datum', '')
                edit_time_input.value = quarter_hour_time(row.get('zeit', ''))
                edit_color_select.value = row.get('farbe') or DEFAULT_COLOR
                edit_amount_select.value = row.get('menge') or DEFAULT_AMOUNT
                edit_dialog.open()

            def save_edit() -> None:
                row_id = edit_id['value']
                document = {
                    'datum': str(edit_date_input.value or ''),
                    'zeit': quarter_hour_time(edit_time_input.value),
                    'farbe': str(edit_color_select.value or DEFAULT_COLOR),
                    'menge': str(edit_amount_select.value or DEFAULT_AMOUNT),
                }
                if not document['datum'] or not document['zeit'] or not document['farbe']:
                    ui.notify('Bitte alle Felder ausfuellen.', color='warning')
                    return
                try:
                    update_tumor_entry(row_id, document)
                except Exception as exc:
                    ui.notify(f'Aendern fehlgeschlagen: {exc}', color='negative')
                    return
                edit_dialog.close()
                load_entries()
                ui.notify('Eintrag geaendert.', color='positive')

            def open_delete(row: dict[str, str]) -> None:
                delete_id['value'] = str(row.get('row_key', ''))
                delete_label.set_text(
                    f"{row.get('datum', '')} {row.get('zeit', '')} "
                    f"{row.get('farbe', '')} {row.get('menge', '')}"
                )
                delete_dialog.open()

            def confirm_delete() -> None:
                try:
                    delete_tumor_entry(delete_id['value'])
                except Exception as exc:
                    ui.notify(f'Loeschen fehlgeschlagen: {exc}', color='negative')
                    return
                delete_dialog.close()
                load_entries()
                ui.notify('Eintrag geloescht.', color='positive')

            def event_row(args: object) -> dict[str, str]:
                if isinstance(args, list) and args:
                    args = args[0]
                return args if isinstance(args, dict) else {}

            update_columns()
            result_table.on('edit-row', lambda event: open_edit(event_row(event.args)))
            result_table.on('delete-row', lambda event: open_delete(event_row(event.args)))
            source_switch.on_value_change(update_columns)
            date_from_input.on_value_change(load_entries)
            date_to_input.on_value_change(load_entries)
            ui.button('Zurueck', on_click=lambda: ui.navigate.to('/')).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
