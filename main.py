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
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace

from nicegui import app, ui

from src.database import CouchDatabase
from src.sessenauswerten import register_essen_analysis_pages
from src.sessen import register_essen_pages
from src.smedisauswerten import register_medis_analysis_pages
from src.smedis import register_medis_pages
from src.sstomaauswerten import register_stoma_analysis_pages
from src.sstoma import register_stoma_pages
from src.stumorauswerten import register_tumor_analysis_pages
from src.stumor import register_tumor_pages
from src.tliste import create_t_list_dialog


logging.basicConfig(level=logging.INFO)
APP_VERSION = '1.0.2'


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

        open_t_list_dialog = create_t_list_dialog(DATABASE)

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
