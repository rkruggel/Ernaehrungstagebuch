from __future__ import annotations

import logging
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from nicegui import ui
import requests

from src.sessenauswerten.page import register_essen_analysis_pages
from src.sessen.page import register_essen_pages
from src.sstomaauswerten.page import register_stoma_analysis_pages
from src.sstoma.page import register_stoma_pages


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)
APP_VERSION = '0.1.34'


DEFAULT_ESSEN_PLACES = ['Zuhause', 'Arbeit', 'Restaurant', 'Unterwegs']
ESSEN_PLACES_OPTION_NAME = 'essen_wo_gegessen'
STOMA_ENTRY_TYPE = 'stoma'
TUMOR_ENTRY_TYPE = 'tumor'
LEGACY_STOMA_ENTRY_TYPE = 'ko' + 't'
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
DATABASE_STATUS = 'Datenbankstatus wird geprueft.'


def ensure_couchdb_database(config: SimpleNamespace) -> str:
    session = requests.Session()
    if config.username or config.password:
        session.auth = (config.username, config.password)

    server_url = config.server_url.rstrip('/')
    database_name = quote(config.database, safe='')
    database_url = f'{server_url}/{database_name}'

    try:
        response = session.put(database_url, timeout=5)
        if response.status_code in {201, 202}:
            return f'Datenbank {config.database} wurde angelegt.'
        if response.status_code == 412:
            return f'Datenbank {config.database} ist verbunden.'

        response.raise_for_status()
        return f'Datenbank {config.database} ist verbunden.'
    except requests.RequestException as exc:
        LOGGER.warning('CouchDB konnte nicht initialisiert werden: %s', exc)
        return 'CouchDB derzeit nicht erreichbar.'


def couchdb_session(config: SimpleNamespace) -> requests.Session:
    session = requests.Session()
    if config.username or config.password:
        session.auth = (config.username, config.password)
    return session


def couchdb_database_url(config: SimpleNamespace) -> str:
    server_url = config.server_url.rstrip('/')
    database_name = quote(config.database, safe='')
    return f'{server_url}/{database_name}'


def couchdb_document_url(database_url: str, document_id: str) -> str:
    return f'{database_url}/{quote(document_id, safe="")}'


def normalized_quelle(quelle: object) -> str:
    return str(quelle or '').strip().lower()


def document_quelle(document: dict[str, object]) -> str:
    # Legacy documents without source were created before dev/prod separation.
    return str(document.get('quelle') or 'prod')


def document_matches_quelle(document: dict[str, object], quelle: str) -> bool:
    return normalized_quelle(document_quelle(document)) == normalized_quelle(quelle)


def existing_document_times(
    session: requests.Session,
    database_url: str,
    date: str,
    quelle: str,
    document_type: object,
) -> set[str]:
    response = session.get(
        f'{database_url}/_all_docs',
        params={'include_docs': 'true'},
        timeout=10,
    )
    response.raise_for_status()

    times = set()
    for row in response.json()['rows']:
        document = row.get('doc')
        if (
            document
            and document_matches_quelle(document, quelle)
            and document.get('typ') == document_type
            and document.get('datum') == date
            and document.get('zeit')
        ):
            times.add(str(document['zeit']))
    return times


def suffix_number(candidate: str, base_value: str) -> int | None:
    if candidate == base_value:
        return 0

    prefix = f'{base_value}-'
    if not candidate.startswith(prefix):
        return None

    suffix = candidate.removeprefix(prefix)
    if not suffix.isdecimal():
        return None
    return int(suffix)


def next_unique_time(base_time: str, existing_times: set[str]) -> str:
    used_numbers = {
        number
        for candidate in existing_times
        if (number := suffix_number(candidate, base_time)) is not None
    }

    if 0 not in used_numbers:
        return base_time

    next_number = 1
    while next_number in used_numbers:
        next_number += 1
    return f'{base_time}-{next_number}'


def with_unique_document_time(
    document: dict[str, object],
    session: requests.Session,
    database_url: str,
    quelle: str,
) -> dict[str, object]:
    date = document.get('datum')
    time = document.get('zeit')
    document_type = document.get('typ')
    if not date or not time:
        return document

    document['zeit'] = next_unique_time(
        str(time),
        existing_document_times(session, database_url, str(date), quelle, document_type),
    )
    return document


def save_couchdb_document(document: dict[str, object]) -> str:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document['quelle'] = CONFIG.app.quelle
    document = with_unique_document_time(document, session, database_url, CONFIG.app.quelle)
    document['app_version'] = APP_VERSION
    response = session.post(database_url, json=document, timeout=5)
    response.raise_for_status()
    return str(response.json()['id'])


def time_sort_key(time: str) -> tuple[str, int]:
    base_time, separator, suffix = time.rpartition('-')
    if separator and suffix.isdecimal():
        return base_time, int(suffix)
    return time, 0


def fetch_entries_by_type(
    date_from: str,
    date_to: str,
    entry_type: str,
) -> list[dict[str, str]]:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    response = session.get(
        f'{database_url}/_all_docs',
        params={'include_docs': 'true'},
        timeout=10,
    )
    response.raise_for_status()

    entries = []
    for row in response.json()['rows']:
        document = row.get('doc')
        if (
            not document
            or document.get('typ') != entry_type
            or not document_matches_quelle(document, CONFIG.app.quelle)
        ):
            continue

        entry_date = str(document.get('datum', ''))
        if date_from <= entry_date <= date_to:
            entries.append(
                {
                    'row_key': str(document.get('_id', f'{entry_date}-{document.get("zeit", "")}')),
                    'datum': entry_date,
                    'zeit': str(document.get('zeit', '')),
                    'konsistenz': str(document.get('konsistenz', '')),
                    'menge': str(document.get('menge', '')),
                    'farbe': str(document.get('farbe', '')),
                    'platte': 'ja' if document.get('platte') else 'nein',
                    'quelle': document_quelle(document),
                }
            )

    return sorted(entries, key=lambda entry: (entry['datum'], time_sort_key(entry['zeit'])))


def fetch_stoma_entries(date_from: str, date_to: str) -> list[dict[str, str]]:
    return [
        entry
        for entry in fetch_entries_by_type(date_from, date_to, STOMA_ENTRY_TYPE)
        if str(entry.get('konsistenz') or '').strip().lower() != 'tumor'
    ]


def fetch_tumor_entries(date_from: str, date_to: str) -> list[dict[str, str]]:
    return fetch_entries_by_type(date_from, date_to, TUMOR_ENTRY_TYPE)


def fetch_essen_entries(date_from: str, date_to: str) -> list[dict[str, str]]:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    response = session.get(
        f'{database_url}/_all_docs',
        params={'include_docs': 'true'},
        timeout=10,
    )
    response.raise_for_status()

    entries = []
    for row in response.json()['rows']:
        document = row.get('doc')
        if (
            not document
            or document.get('typ') != 'essen'
            or not document_matches_quelle(document, CONFIG.app.quelle)
        ):
            continue

        entry_date = str(document.get('datum', ''))
        if date_from <= entry_date <= date_to:
            entries.append(
                {
                    'row_key': str(document.get('_id', f'{entry_date}-{document.get("zeit", "")}')),
                    'datum': entry_date,
                    'zeit': str(document.get('zeit', '')),
                    'mahlzeit': str(document.get('mahlzeit', '')),
                    'was_gegessen': str(document.get('was_gegessen', '')),
                    'wo_gegessen': str(document.get('wo_gegessen', '')),
                    'quelle': document_quelle(document),
                }
            )

    return sorted(entries, key=lambda entry: (entry['datum'], time_sort_key(entry['zeit'])))


def clean_option_values(values: object) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, set, tuple)):
        values = []
    cleaned = {str(value).strip() for value in values if str(value).strip()}
    return sorted(cleaned)


def essen_places_document_id() -> str:
    return f'optionen:{CONFIG.app.quelle}:{ESSEN_PLACES_OPTION_NAME}'


def fetch_couchdb_document(
    session: requests.Session,
    database_url: str,
    document_id: str,
) -> dict[str, object] | None:
    response = session.get(couchdb_document_url(database_url, document_id), timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def save_couchdb_named_document(
    session: requests.Session,
    database_url: str,
    document: dict[str, object],
) -> None:
    document_id = str(document['_id'])
    response = session.put(
        couchdb_document_url(database_url, document_id),
        json=document,
        timeout=10,
    )
    response.raise_for_status()


def update_couchdb_entry(
    document_id: str,
    expected_type: str,
    values: dict[str, object],
) -> None:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = fetch_couchdb_document(session, database_url, document_id)
    if document is None:
        raise ValueError('Eintrag wurde nicht gefunden.')
    if document.get('typ') != expected_type:
        raise ValueError('Eintrag hat den falschen Typ.')
    if not document_matches_quelle(document, CONFIG.app.quelle):
        raise ValueError('Eintrag gehoert zu einer anderen Quelle.')

    document.update(values)
    document['app_version'] = APP_VERSION
    save_couchdb_named_document(session, database_url, document)


def delete_couchdb_entry(document_id: str, expected_type: str) -> None:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = fetch_couchdb_document(session, database_url, document_id)
    if document is None:
        raise ValueError('Eintrag wurde nicht gefunden.')
    if document.get('typ') != expected_type:
        raise ValueError('Eintrag hat den falschen Typ.')
    if not document_matches_quelle(document, CONFIG.app.quelle):
        raise ValueError('Eintrag gehoert zu einer anderen Quelle.')

    response = session.delete(
        couchdb_document_url(database_url, document_id),
        params={'rev': str(document['_rev'])},
        timeout=10,
    )
    response.raise_for_status()


def update_stoma_entry(document_id: str, values: dict[str, object]) -> None:
    update_couchdb_entry(document_id, STOMA_ENTRY_TYPE, values)


def delete_stoma_entry(document_id: str) -> None:
    delete_couchdb_entry(document_id, STOMA_ENTRY_TYPE)


def update_tumor_entry(document_id: str, values: dict[str, object]) -> None:
    update_couchdb_entry(document_id, TUMOR_ENTRY_TYPE, values)


def delete_tumor_entry(document_id: str) -> None:
    delete_couchdb_entry(document_id, TUMOR_ENTRY_TYPE)


def update_essen_entry(document_id: str, values: dict[str, object]) -> None:
    update_couchdb_entry(document_id, 'essen', values)


def delete_essen_entry(document_id: str) -> None:
    delete_couchdb_entry(document_id, 'essen')


def fetch_legacy_essen_places(
    session: requests.Session,
    database_url: str,
) -> list[str]:
    response = session.get(
        f'{database_url}/_all_docs',
        params={'include_docs': 'true'},
        timeout=10,
    )
    response.raise_for_status()

    places = set()
    for row in response.json()['rows']:
        document = row.get('doc')
        if (
            not document
            or document.get('typ') != 'essen'
            or not document_matches_quelle(document, CONFIG.app.quelle)
        ):
            continue

        place = str(document.get('wo_gegessen') or '').strip()
        if place:
            places.add(place)

    return clean_option_values(places)


def load_essen_places_document(
    session: requests.Session,
    database_url: str,
) -> dict[str, object]:
    document_id = essen_places_document_id()
    document = fetch_couchdb_document(session, database_url, document_id)

    if document is None:
        legacy_places = fetch_legacy_essen_places(session, database_url)
        values = clean_option_values([*DEFAULT_ESSEN_PLACES, *legacy_places])
        document = {
            '_id': document_id,
            'typ': 'optionen',
            'name': ESSEN_PLACES_OPTION_NAME,
            'quelle': CONFIG.app.quelle,
            'werte': values,
            'app_version': APP_VERSION,
        }
        save_couchdb_named_document(session, database_url, document)
        return document

    document['werte'] = clean_option_values(document.get('werte', []))
    document['typ'] = 'optionen'
    document['name'] = ESSEN_PLACES_OPTION_NAME
    document['quelle'] = CONFIG.app.quelle
    document['app_version'] = APP_VERSION
    return document


def fetch_essen_places() -> list[str]:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = load_essen_places_document(session, database_url)
    return clean_option_values(document.get('werte', []))


def add_essen_place(place: str) -> list[str]:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = load_essen_places_document(session, database_url)
    values = clean_option_values(document.get('werte', []))
    document['werte'] = clean_option_values([*values, place])
    save_couchdb_named_document(session, database_url, document)
    return clean_option_values(document['werte'])


def delete_essen_place(place: str) -> list[str]:
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = load_essen_places_document(session, database_url)
    values = clean_option_values(document.get('werte', []))
    document['werte'] = [value for value in values if value != place]
    save_couchdb_named_document(session, database_url, document)
    return clean_option_values(document['werte'])


def rename_essen_place(old_place: str, new_place: str) -> list[str]:
    old_text = str(old_place or '').strip()
    new_text = str(new_place or '').strip()
    session = couchdb_session(CONFIG.couchdb)
    database_url = couchdb_database_url(CONFIG.couchdb)
    document = load_essen_places_document(session, database_url)

    if not old_text or not new_text:
        return clean_option_values(document.get('werte', []))

    values = clean_option_values(document.get('werte', []))
    document['werte'] = clean_option_values(
        [new_text if value == old_text else value for value in values]
    )
    save_couchdb_named_document(session, database_url, document)

    if old_text == new_text:
        return clean_option_values(document['werte'])

    response = session.get(
        f'{database_url}/_all_docs',
        params={'include_docs': 'true'},
        timeout=10,
    )
    response.raise_for_status()
    for row in response.json()['rows']:
        entry = row.get('doc')
        if (
            not entry
            or entry.get('typ') != 'essen'
            or not document_matches_quelle(entry, CONFIG.app.quelle)
            or str(entry.get('wo_gegessen') or '').strip() != old_text
        ):
            continue

        entry['wo_gegessen'] = new_text
        save_couchdb_named_document(session, database_url, entry)

    return clean_option_values(document['werte'])


def migrate_stoma_document_type(config: SimpleNamespace) -> str:
    session = couchdb_session(config)
    database_url = couchdb_database_url(config)
    migrated_count = 0

    try:
        response = session.get(
            f'{database_url}/_all_docs',
            params={'include_docs': 'true'},
            timeout=10,
        )
        response.raise_for_status()
        for row in response.json()['rows']:
            document = row.get('doc')
            if not document or document.get('typ') != LEGACY_STOMA_ENTRY_TYPE:
                continue

            document['typ'] = STOMA_ENTRY_TYPE
            document['app_version'] = APP_VERSION
            save_couchdb_named_document(session, database_url, document)
            migrated_count += 1
    except requests.RequestException as exc:
        LOGGER.warning('Stoma-Migration konnte nicht ausgefuehrt werden: %s', exc)
        return 'Stoma-Migration derzeit nicht moeglich.'

    if migrated_count == 0:
        return 'Stoma-Migration: keine alten Eintraege gefunden.'
    return f'Stoma-Migration: {migrated_count} Eintraege aktualisiert.'


def migrate_tumor_document_type(config: SimpleNamespace) -> str:
    session = couchdb_session(config)
    database_url = couchdb_database_url(config)
    migrated_count = 0

    try:
        response = session.get(
            f'{database_url}/_all_docs',
            params={'include_docs': 'true'},
            timeout=10,
        )
        response.raise_for_status()
        for row in response.json()['rows']:
            document = row.get('doc')
            if (
                not document
                or document.get('typ') != STOMA_ENTRY_TYPE
                or str(document.get('konsistenz') or '').strip().lower() != 'tumor'
            ):
                continue

            document['typ'] = TUMOR_ENTRY_TYPE
            document.pop('konsistenz', None)
            document['app_version'] = APP_VERSION
            save_couchdb_named_document(session, database_url, document)
            migrated_count += 1
    except requests.RequestException as exc:
        LOGGER.warning('Tumor-Migration konnte nicht ausgefuehrt werden: %s', exc)
        return 'Tumor-Migration derzeit nicht moeglich.'

    if migrated_count == 0:
        return 'Tumor-Migration: keine alten Eintraege gefunden.'
    return f'Tumor-Migration: {migrated_count} Eintraege aktualisiert.'


DATABASE_STATUS = (
    f'{ensure_couchdb_database(CONFIG.couchdb)} '
    f'{migrate_stoma_document_type(CONFIG.couchdb)} '
    f'{migrate_tumor_document_type(CONFIG.couchdb)}'
)


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


register_stoma_pages(build_shell, save_couchdb_document)
register_stoma_analysis_pages(
    build_shell,
    fetch_stoma_entries,
    update_stoma_entry,
    delete_stoma_entry,
    fetch_tumor_entries,
    update_tumor_entry,
    delete_tumor_entry,
)
register_essen_pages(
    build_shell,
    save_couchdb_document,
    fetch_essen_places,
    add_essen_place,
    delete_essen_place,
    rename_essen_place,
)
register_essen_analysis_pages(
    build_shell,
    fetch_essen_entries,
    update_essen_entry,
    delete_essen_entry,
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
