from __future__ import annotations

import logging
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace

from nicegui import ui

from src.database import CouchDatabase
from src.sessenauswerten.page import register_essen_analysis_pages
from src.sessen.page import register_essen_pages
from src.sstomaauswerten.page import register_stoma_analysis_pages
from src.sstoma.page import register_stoma_pages
from src.stumorauswerten.page import register_tumor_analysis_pages
from src.stumor.page import register_tumor_pages


logging.basicConfig(level=logging.INFO)
APP_VERSION = '0.1.37'


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


def build_shell(title: str) -> None:
    ui.page_title(title)
    ui.add_head_html(
        '''
        <style>
            body {
                background: linear-gradient(180deg, #f7f4ea 0%, #e4efe7 100%);
            }
        </style>
        '''
    )


def action_button(label: str, target: str, color: str) -> None:
    ui.button(label, on_click=lambda: ui.navigate.to(target)).props('unelevated') \
        .classes(
            'w-full rounded-2xl px-4 py-5 text-lg font-semibold text-white shadow-lg'
        ).style(f'background: {color} !important; color: white !important; min-height: 88px;')


@ui.page('/')
def index_page() -> None:
    build_shell(CONFIG.app.title)

    with ui.column().classes('min-h-screen w-full items-center gap-5 px-6 pt-28'):
        ui.label('Rolands').classes('text-xs font-light text-slate-500 text-center -mb-4')
        ui.label(CONFIG.app.title).classes('text-3xl font-bold text-slate-800 text-center')
        ui.label(f'Version {APP_VERSION} [{CONFIG.app.quelle}]') \
            .classes('text-xs text-slate-500 text-center')
        ui.label(DATABASE_STATUS).classes('text-sm text-slate-500 text-center')
        with ui.grid(columns=2).classes('w-full max-w-xl gap-4'):
            action_button('Tumor', '/tumor', '#B84A5A')
            action_button('Tumor Auswerten', '/tumor-auswerten', '#7E3A54')
            action_button('Stoma', '/stoma', '#B77945')
            action_button('Stoma Auswerten', '/stoma-auswerten', '#6F5A3C')
            action_button('Essen', '/essen', '#4F8F6B')
            action_button('Essen Auswerten', '/essen-auswerten', '#2F6F73')


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
