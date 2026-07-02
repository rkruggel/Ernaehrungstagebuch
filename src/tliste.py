from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Protocol

from nicegui import ui


T_LIST_ROW_COLORS = {
    'Tumor': 'rgba(184, 74, 90, 0.10)',
    'Stoma': 'rgba(183, 121, 69, 0.10)',
    'Essen': 'rgba(79, 143, 107, 0.10)',
    'Medis': 'rgba(93, 110, 173, 0.10)',
}


class TListDatabase(Protocol):
    def fetch_tumor_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        ...

    def fetch_stoma_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        ...

    def fetch_essen_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        ...

    def fetch_medis_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        ...


def time_sort_key(value: object) -> tuple[int, int]:
    try:
        parsed_time = datetime.strptime(str(value or '').split('-', 1)[0], '%H:%M')
    except ValueError:
        return (99, 99)
    return (parsed_time.hour, parsed_time.minute)


def t_list_datetime(row: dict[str, object]) -> datetime | None:
    time_value = str(row.get('zeit', '')).split('-', 1)[0]
    try:
        return datetime.strptime(f"{row.get('datum', '')} {time_value}", '%Y-%m-%d %H:%M')
    except ValueError:
        return None


def format_t_list_duration(start: datetime, end: datetime) -> str:
    total_minutes = int(abs(end - start).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f'{hours:02d}:{minutes:02d}'


def add_t_list_time_differences(rows: list[dict[str, object]]) -> None:
    for index, row in enumerate(rows):
        row['previous_time_diff'] = ''
        row['next_time_diff'] = ''
        row['has_time_diffs'] = False
        if index == 0 or index == len(rows) - 1:
            continue

        previous_time = t_list_datetime(rows[index - 1])
        current_time = t_list_datetime(row)
        next_time = t_list_datetime(rows[index + 1])
        if previous_time is None or current_time is None or next_time is None:
            continue

        row['previous_time_diff'] = format_t_list_duration(previous_time, current_time)
        row['next_time_diff'] = format_t_list_duration(current_time, next_time)
        row['has_time_diffs'] = True


def create_t_list_dialog(database: TListDatabase) -> Callable[[], None]:
    with ui.dialog().props('position=top') as t_list_dialog, ui.card().classes(
        'w-[920px] max-w-full gap-4'
    ):
        ui.label('T-Liste').classes('text-lg font-semibold text-slate-900')
        with ui.row().classes('w-full flex-wrap items-end gap-4'):
            today = date.today().isoformat()
            t_list_date_from_input = ui.input('Datum von', value=today) \
                .props('type=date dense') \
                .classes('w-28 max-w-full')
            t_list_date_to_input = ui.input('Datum bis', value=today) \
                .props('type=date dense') \
                .classes('w-28 max-w-full')
            with ui.button_group().props('unelevated'):
                ui.button(icon='chevron_left', on_click=lambda: shift_t_list_date_range(-1)) \
                    .props('aria-label="Vorheriger Tag"')
                ui.button(icon='home', on_click=lambda: jump_t_list_to_today()) \
                    .props('aria-label="Heute"')
                ui.button(icon='chevron_right', on_click=lambda: shift_t_list_date_range(1)) \
                    .props('aria-label="Nächster Tag"')
        with ui.row().classes('w-full flex-wrap items-center gap-4'):
            tumor_checkbox = ui.checkbox('Tumor', value=False).props('dense')
            stoma_checkbox = ui.checkbox('Stoma', value=False).props('dense')
            essen_checkbox = ui.checkbox('Essen', value=False).props('dense')
            medis_checkbox = ui.checkbox('Medis', value=False).props('dense')
            ui.button(icon='done_all', on_click=lambda: toggle_t_list_checkboxes()) \
                .props('dense round unelevated aria-label="Alle Checkboxen umschalten"')
            ui.button(icon='swap_horiz', on_click=lambda: toggle_t_list_pair()) \
                .props('dense round unelevated aria-label="Tumor und Medis / Stoma und Essen umschalten"')

        t_list_table = ui.table(
            columns=[
                {'name': 'datum', 'label': 'Datum', 'field': 'datum', 'align': 'left'},
                {'name': 'zeit', 'label': 'Zeit', 'field': 'zeit', 'align': 'left'},
                {'name': 'bereich', 'label': 'Bereich', 'field': 'bereich', 'align': 'left'},
                {'name': 'details', 'label': 'Details', 'field': 'details', 'align': 'left'},
            ],
            rows=[],
            row_key='row_key',
        ).classes('w-full')
        t_list_table.add_slot(
            'body',
            '''
            <q-tr :props="props" :style="{ backgroundColor: props.row.row_color }">
                <q-td key="datum" :props="props">{{ props.row.datum }}</q-td>
                <q-td key="zeit" :props="props">
                    <span v-if="props.row.has_time_diffs">
                        <a href="#" @click.prevent>{{ props.row.zeit }}</a>
                        <q-popup-proxy anchor="center right" self="center left" :offset="[8, 0]">
                            <div class="t-list-time-popup">
                                <div>{{ props.row.previous_time_diff }}</div>
                                <div>{{ props.row.next_time_diff }}</div>
                            </div>
                        </q-popup-proxy>
                    </span>
                    <span v-else>{{ props.row.zeit }}</span>
                </q-td>
                <q-td key="bereich" :props="props">{{ props.row.bereich }}</q-td>
                <q-td key="details" :props="props">{{ props.row.details }}</q-td>
            </q-tr>
            ''',
        )
        t_list_status = ui.label('').classes('text-sm text-slate-600')

        def append_t_list_rows(
            rows: list[dict[str, object]],
            entries: list[dict[str, str]],
            area: str,
            details_builder: Callable[[dict[str, str]], str],
        ) -> None:
            for entry in entries:
                rows.append(
                    {
                        'row_key': f"{area}-{entry.get('row_key', '')}",
                        'datum': str(entry.get('datum', '')),
                        'zeit': str(entry.get('zeit', '')),
                        'bereich': area,
                        'details': details_builder(entry),
                        'row_color': T_LIST_ROW_COLORS[area],
                    }
                )

        def load_t_list() -> None:
            date_from = str(t_list_date_from_input.value or '')
            date_to = str(t_list_date_to_input.value or '')
            if not date_from or not date_to:
                t_list_status.set_text('Bitte Datum von und Datum bis auswaehlen.')
                t_list_table.rows = []
                t_list_table.update()
                return

            if date_from > date_to:
                t_list_status.set_text('Datum von darf nicht nach Datum bis liegen.')
                t_list_table.rows = []
                t_list_table.update()
                return

            rows: list[dict[str, object]] = []
            try:
                if tumor_checkbox.value:
                    append_t_list_rows(
                        rows,
                        database.fetch_tumor_entries(date_from, date_to),
                        'Tumor',
                        lambda entry: (
                            f"Farbe: {entry.get('farbe', '')}, "
                            f"Menge: {entry.get('menge', '')}"
                        ),
                    )
                if stoma_checkbox.value:
                    append_t_list_rows(
                        rows,
                        database.fetch_stoma_entries(date_from, date_to),
                        'Stoma',
                        lambda entry: (
                            f"Konsistenz: {entry.get('konsistenz', '')}, "
                            f"Platte: {entry.get('platte', '')}"
                        ),
                    )
                if essen_checkbox.value:
                    append_t_list_rows(
                        rows,
                        database.fetch_essen_entries(date_from, date_to),
                        'Essen',
                        lambda entry: (
                            f"{entry.get('mahlzeit', '')}: "
                            f"{entry.get('was_gegessen', '')} "
                            f"({entry.get('wo_gegessen', '')})"
                        ),
                    )
                if medis_checkbox.value:
                    append_t_list_rows(
                        rows,
                        database.fetch_medis_entries(date_from, date_to),
                        'Medis',
                        lambda entry: str(entry.get('medikament', '')),
                    )
            except Exception as exc:
                t_list_status.set_text(f'Laden fehlgeschlagen: {exc}')
                t_list_table.rows = []
                t_list_table.update()
                return

            rows.sort(key=lambda row: (row['datum'], time_sort_key(row['zeit']), row['bereich']))
            add_t_list_time_differences(rows)
            t_list_table.rows = rows
            t_list_table.update()
            t_list_status.set_text(f'{len(rows)} Eintraege gefunden.')

        def set_t_list_date_range(date_from: date, date_to: date) -> None:
            t_list_date_from_input.value = date_from.isoformat()
            t_list_date_to_input.value = date_to.isoformat()
            load_t_list()

        def shift_t_list_date_range(days: int) -> None:
            try:
                date_from = date.fromisoformat(str(t_list_date_from_input.value or ''))
                date_to = date.fromisoformat(str(t_list_date_to_input.value or ''))
            except ValueError:
                t_list_status.set_text('Bitte Datum von und Datum bis auswaehlen.')
                return
            set_t_list_date_range(
                date_from + timedelta(days=days),
                date_to + timedelta(days=days),
            )

        def jump_t_list_to_today() -> None:
            today_date = date.today()
            set_t_list_date_range(today_date, today_date)

        def toggle_t_list_checkboxes() -> None:
            new_value = not all(
                [
                    tumor_checkbox.value,
                    stoma_checkbox.value,
                    essen_checkbox.value,
                    medis_checkbox.value,
                ]
            )
            tumor_checkbox.value = new_value
            stoma_checkbox.value = new_value
            essen_checkbox.value = new_value
            medis_checkbox.value = new_value
            load_t_list()

        pair_toggle_state = {'tumor_medis_next': True}

        def toggle_t_list_pair() -> None:
            tumor_medis_next = pair_toggle_state['tumor_medis_next']
            tumor_checkbox.value = tumor_medis_next
            medis_checkbox.value = tumor_medis_next
            stoma_checkbox.value = not tumor_medis_next
            essen_checkbox.value = not tumor_medis_next
            pair_toggle_state['tumor_medis_next'] = not tumor_medis_next
            load_t_list()

        def open_t_list_dialog() -> None:
            today = date.today().isoformat()
            t_list_date_from_input.value = today
            t_list_date_to_input.value = today
            load_t_list()
            t_list_dialog.open()

        t_list_date_from_input.on_value_change(load_t_list)
        t_list_date_to_input.on_value_change(load_t_list)
        tumor_checkbox.on_value_change(load_t_list)
        stoma_checkbox.on_value_change(load_t_list)
        essen_checkbox.on_value_change(load_t_list)
        medis_checkbox.on_value_change(load_t_list)

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Schliessen', on_click=t_list_dialog.close).props('flat no-caps dense')

    return open_t_list_dialog
