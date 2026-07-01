"""
Projekt:
	Ernährungstagebuch und Stoma-/Tumor-Dokumentation für Patienten.

Modul:
  main.py

Beschreibung:
	Startpunkt und Konfiguration der Ernährungstagebuch- und Stoma-/Tumor-Dokumentationsanwendung.

Autor: Roland Kruggel
Version: 1.0.0
Start: 21.06.2026
Lizens: MIT
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from configparser import ConfigParser
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from nicegui import app, ui

from src.database import CouchDatabase
from src.sessenauswerten.page import register_essen_analysis_pages
from src.sessen.page import register_essen_pages
from src.smedisauswerten.page import register_medis_analysis_pages
from src.smedis.page import register_medis_pages
from src.sstomaauswerten.page import register_stoma_analysis_pages
from src.sstoma.page import register_stoma_pages
from src.stumorauswerten.page import register_tumor_analysis_pages
from src.stumor.page import register_tumor_pages


logging.basicConfig(level=logging.INFO)
APP_VERSION = '1.0.1'
T_LIST_ROW_COLORS = {
    'Tumor': 'rgba(184, 74, 90, 0.10)',
    'Stoma': 'rgba(183, 121, 69, 0.10)',
    'Essen': 'rgba(79, 143, 107, 0.10)',
    'Medis': 'rgba(93, 110, 173, 0.10)',
}


REQUIRED_CONFIG_OPTIONS = {
    'allgemein': ['title', 'host', 'port', 'storage_secret', 'quelle'],
    'couchdb': ['server_url', 'database'],
}
 

def abort_config_error(message: str) -> None:
    raise SystemExit(f'Fehler in config.ini: {message}')


def require_config_options(parser: ConfigParser) -> None:
    for section, options in REQUIRED_CONFIG_OPTIONS.items():
        if not parser.has_section(section):
            abort_config_error(f'Abschnitt [{section}] fehlt.')
        for option in options:
            if not parser.has_option(section, option):
                abort_config_error(f'[{section}] {option} fehlt.')
            if not parser.get(section, option).strip():
                abort_config_error(f'[{section}] {option} ist leer.')


def load_config() -> SimpleNamespace:
    parser = ConfigParser()
    config_path = Path(__file__).with_name('config.ini')
    if not config_path.exists():
        abort_config_error(f'{config_path} wurde nicht gefunden.')

    parser.read(config_path, encoding='utf-8')
    require_config_options(parser)

    quelle = parser.get('allgemein', 'quelle').strip().lower()
    if quelle not in {'dev', 'prod'}:
        abort_config_error('[allgemein] quelle muss dev oder prod sein.')

    try:
        port = parser.getint('allgemein', 'port')
    except ValueError as exc:
        abort_config_error('[allgemein] port muss eine Zahl sein.')
        raise exc

    return SimpleNamespace(
        app=SimpleNamespace(
            title=parser.get('allgemein', 'title').strip(),
            host=parser.get('allgemein', 'host').strip(),
            port=port,
            storage_secret=parser.get('allgemein', 'storage_secret').strip(),
            quelle=quelle,
        ),
        couchdb=SimpleNamespace(
            server_url=parser.get('couchdb', 'server_url').strip(),
            database=parser.get('couchdb', 'database').strip(),
            username=parser.get('couchdb', 'username', fallback='').strip(),
            password=parser.get('couchdb', 'password', fallback='').strip(),
        ),
    )


CONFIG = load_config()
DATABASE = CouchDatabase(CONFIG, APP_VERSION)
DATABASE_STATUS = DATABASE.ensure_database()
app.add_static_files('/static', Path(__file__).with_name('static'))


def build_shell(title: str) -> None:
    ui.page_title(title)
    ui.add_head_html('<link rel="stylesheet" href="/static/app.css">')


def action_button(label: str, target: str, color: str):
    return ui.button(label, on_click=lambda: ui.navigate.to(target)).props('unelevated') \
        .classes(
            'menu-action-button min-w-0 w-full rounded-2xl px-2 py-4 text-base '
            'font-semibold leading-tight text-white shadow-lg sm:px-4 sm:py-5 sm:text-lg'
        ).style(f'background: {color} !important; color: white !important; min-height: 88px;')


def time_sort_key(value: object) -> tuple[int, int]:
    try:
        parsed_time = datetime.strptime(str(value or '').split('-', 1)[0], '%H:%M')
    except ValueError:
        return (99, 99)
    return (parsed_time.hour, parsed_time.minute)


def menu_options_fab(
    color: str,
    fab_group: list,
    extra_actions: list[dict[str, object]] | None = None,
) -> None:
    fab = ui.fab('more_horiz', direction='left', color='primary') \
        .props('unelevated') \
        .classes('menu-fab-button') \
        .style(f'--menu-fab-color: {color};')
    fab_group.append(fab)

    def close_other_fabs(event) -> None:
        if not event.value:
            return
        for other_fab in fab_group:
            if other_fab is not fab:
                other_fab.close()

    fab.on_value_change(close_other_fabs)

    with fab:
        ui.fab_action('filter_1', label='L1', color='primary')
        for action in extra_actions or []:
            action_kwargs = {}
            on_click = action.get('on_click')
            if callable(on_click):
                action_kwargs['on_click'] = on_click
            ui.fab_action(
                str(action['icon']),
                label=str(action['label']),
                color='primary',
                **action_kwargs,
            )


def menu_button_row(
    label: str,
    target: str,
    color: str,
    analysis_label: str,
    analysis_target: str,
    analysis_color: str,
    fab_group: list,
    extra_fab_actions: list[dict[str, object]] | None = None,
) -> None:
    with ui.row().classes('w-full flex-nowrap gap-1 sm:gap-4'):
        action_button(label, target, color).classes('menu-main-button min-w-0')
        action_button(analysis_label, analysis_target, analysis_color) \
            .classes('menu-analysis-button min-w-0')
        menu_options_fab(analysis_color, fab_group, extra_fab_actions)


@ui.page('/')
def index_page() -> None:
    build_shell(CONFIG.app.title)

    with ui.column().classes('min-h-screen w-full items-center gap-5 px-2 pt-28 sm:px-6'):
        ui.label('Rolands').classes('text-xs font-light text-slate-500 text-center -mb-4')
        ui.label(CONFIG.app.title).classes('text-3xl font-bold text-slate-800 text-center')
        ui.label(f'Version {APP_VERSION} [{CONFIG.app.quelle}]') \
            .classes('text-xs text-slate-500 text-center')
        ui.label(DATABASE_STATUS).classes('text-sm text-slate-500 text-center')

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
                    <q-td key="zeit" :props="props">{{ props.row.zeit }}</q-td>
                    <q-td key="bereich" :props="props">{{ props.row.bereich }}</q-td>
                    <q-td key="details" :props="props">{{ props.row.details }}</q-td>
                </q-tr>
                ''',
            )
            t_list_status = ui.label('').classes('text-sm text-slate-600')

            def append_t_list_rows(
                rows: list[dict[str, str]],
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

                rows: list[dict[str, str]] = []
                try:
                    if tumor_checkbox.value:
                        append_t_list_rows(
                            rows,
                            DATABASE.fetch_tumor_entries(date_from, date_to),
                            'Tumor',
                            lambda entry: (
                                f"Farbe: {entry.get('farbe', '')}, "
                                f"Menge: {entry.get('menge', '')}"
                            ),
                        )
                    if stoma_checkbox.value:
                        append_t_list_rows(
                            rows,
                            DATABASE.fetch_stoma_entries(date_from, date_to),
                            'Stoma',
                            lambda entry: (
                                f"Konsistenz: {entry.get('konsistenz', '')}, "
                                f"Platte: {entry.get('platte', '')}"
                            ),
                        )
                    if essen_checkbox.value:
                        append_t_list_rows(
                            rows,
                            DATABASE.fetch_essen_entries(date_from, date_to),
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
                            DATABASE.fetch_medis_entries(date_from, date_to),
                            'Medis',
                            lambda entry: str(entry.get('medikament', '')),
                        )
                except Exception as exc:
                    t_list_status.set_text(f'Laden fehlgeschlagen: {exc}')
                    t_list_table.rows = []
                    t_list_table.update()
                    return

                rows.sort(key=lambda row: (row['datum'], time_sort_key(row['zeit']), row['bereich']))
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

        menu_fabs = []
        with ui.column().classes('w-full max-w-xl gap-3 sm:gap-4'):
            menu_button_row(
                'Tumor', '/tumor', '#B84A5A', 'Tumor Ausw.', '/tumor-auswerten', '#7E3A54',
                menu_fabs, [{'icon': 'list', 'label': 'T-Liste', 'on_click': open_t_list_dialog}],
            )
            menu_button_row(
                'Stoma', '/stoma', '#B77945', 'Stoma Ausw.', '/stoma-auswerten', '#6F5A3C',
                menu_fabs,
            )
            menu_button_row(
                'Essen', '/essen', '#4F8F6B', 'Essen Ausw.', '/essen-auswerten', '#2F6F73',
                menu_fabs,
            )
            menu_button_row(
                'Medis', '/medis', '#5D6EAD', 'Medis Ausw.', '/medis-auswerten', '#34497F',
                menu_fabs,
            )


register_stoma_pages(build_shell, DATABASE.save_document)
register_stoma_analysis_pages(
    build_shell,
    DATABASE.fetch_stoma_entries,
    DATABASE.update_stoma_entry,
    DATABASE.delete_stoma_entry,
)
register_tumor_pages(build_shell, DATABASE.save_document)
register_tumor_analysis_pages(
    build_shell,
    DATABASE.fetch_tumor_entries,
    DATABASE.update_tumor_entry,
    DATABASE.delete_tumor_entry,
)
register_essen_pages(
    build_shell,
    DATABASE.save_document,
    DATABASE.fetch_essen_places,
    DATABASE.add_essen_place,
    DATABASE.delete_essen_place,
    DATABASE.rename_essen_place,
)
register_essen_analysis_pages(
    build_shell,
    DATABASE.fetch_essen_entries,
    DATABASE.update_essen_entry,
    DATABASE.delete_essen_entry,
)
register_medis_pages(
    build_shell,
    DATABASE.save_document,
    DATABASE.fetch_medis_options,
    DATABASE.add_medis_option,
    DATABASE.delete_medis_option,
    DATABASE.rename_medis_option,
)
register_medis_analysis_pages(
    build_shell,
    DATABASE.fetch_medis_entries,
    DATABASE.update_medis_entry,
    DATABASE.delete_medis_entry,
    DATABASE.fetch_medis_options,
    DATABASE.add_medis_option,
)


def main() -> None:
    is_dev = CONFIG.app.quelle == 'dev'
    ui.run(
        title=CONFIG.app.title,
        host=CONFIG.app.host,
        port=CONFIG.app.port,
        storage_secret=CONFIG.app.storage_secret,
        reload=is_dev,
        uvicorn_reload_dirs='.,src' if is_dev else '.',
    )


if __name__ in {'__main__', '__mp_main__'}:
    main()
