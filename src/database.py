from __future__ import annotations

import logging
from types import SimpleNamespace
from urllib.parse import quote

import requests


LOGGER = logging.getLogger(__name__)

DEFAULT_ESSEN_PLACES = ['Zuhause', 'Arbeit', 'Restaurant', 'Unterwegs']
ESSEN_PLACES_OPTION_NAME = 'essen_wo_gegessen'
MEDIS_OPTION_NAME = 'medis_medikament'
MEDIS_ENTRY_TYPE = 'medis'
STOMA_ENTRY_TYPE = 'stoma'
TUMOR_ENTRY_TYPE = 'tumor'


class CouchDatabase:
    def __init__(self, config: SimpleNamespace, app_version: str) -> None:
        self.config = config
        self.app_version = app_version

    def ensure_database(self) -> str:
        session = self._session()
        database_url = self._database_url()

        try:
            response = session.put(database_url, timeout=5)
            if response.status_code in {201, 202}:
                return f"Datenbank '{self.config.couchdb.database}' wurde angelegt."
            if response.status_code == 412:
                return f"Datenbank '{self.config.couchdb.database}' ist verbunden."

            response.raise_for_status()
            return f"Datenbank '{self.config.couchdb.database}' ist verbunden."
        except requests.RequestException as exc:
            LOGGER.warning('CouchDB konnte nicht initialisiert werden: %s', exc)
            return 'CouchDB derzeit nicht erreichbar.'

    def save_document(self, document: dict[str, object]) -> str:
        session = self._session()
        database_url = self._database_url()
        document['quelle'] = self.config.app.quelle
        document = self._with_unique_document_time(document, session, database_url)
        document['app_version'] = self.app_version
        response = session.post(database_url, json=document, timeout=5)
        response.raise_for_status()
        return str(response.json()['id'])

    def fetch_stoma_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        return [
            entry
            for entry in self._fetch_entries_by_type(date_from, date_to, STOMA_ENTRY_TYPE)
            if str(entry.get('konsistenz') or '').strip().lower() != 'tumor'
        ]

    def fetch_tumor_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        return self._fetch_entries_by_type(date_from, date_to, TUMOR_ENTRY_TYPE)

    def fetch_medis_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        session = self._session()
        database_url = self._database_url()
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
                or document.get('typ') != MEDIS_ENTRY_TYPE
                or not self._document_matches_quelle(document)
            ):
                continue

            entry_date = str(document.get('datum', ''))
            if date_from <= entry_date <= date_to:
                entries.append(
                    {
                        'row_key': str(
                            document.get('_id', f'{entry_date}-{document.get("zeit", "")}')
                        ),
                        'datum': entry_date,
                        'zeit': str(document.get('zeit', '')),
                        'medikament': str(document.get('medikament', '')),
                        'quelle': self._document_quelle(document),
                    }
                )

        return sorted(
            entries,
            key=lambda entry: (entry['datum'], self._time_sort_key(entry['zeit'])),
        )

    def fetch_essen_entries(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        session = self._session()
        database_url = self._database_url()
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
                or not self._document_matches_quelle(document)
            ):
                continue

            entry_date = str(document.get('datum', ''))
            if date_from <= entry_date <= date_to:
                entries.append(
                    {
                        'row_key': str(
                            document.get('_id', f'{entry_date}-{document.get("zeit", "")}')
                        ),
                        'datum': entry_date,
                        'zeit': str(document.get('zeit', '')),
                        'mahlzeit': str(document.get('mahlzeit', '')),
                        'was_gegessen': str(document.get('was_gegessen', '')),
                        'wo_gegessen': str(document.get('wo_gegessen', '')),
                        'quelle': self._document_quelle(document),
                    }
                )

        return sorted(
            entries,
            key=lambda entry: (entry['datum'], self._time_sort_key(entry['zeit'])),
        )

    def update_stoma_entry(self, document_id: str, values: dict[str, object]) -> None:
        self._update_entry(document_id, STOMA_ENTRY_TYPE, values)

    def delete_stoma_entry(self, document_id: str) -> None:
        self._delete_entry(document_id, STOMA_ENTRY_TYPE)

    def update_tumor_entry(self, document_id: str, values: dict[str, object]) -> None:
        self._update_entry(document_id, TUMOR_ENTRY_TYPE, values)

    def delete_tumor_entry(self, document_id: str) -> None:
        self._delete_entry(document_id, TUMOR_ENTRY_TYPE)

    def update_medis_entry(self, document_id: str, values: dict[str, object]) -> None:
        self._update_entry(document_id, MEDIS_ENTRY_TYPE, values)

    def delete_medis_entry(self, document_id: str) -> None:
        self._delete_entry(document_id, MEDIS_ENTRY_TYPE)

    def update_essen_entry(self, document_id: str, values: dict[str, object]) -> None:
        self._update_entry(document_id, 'essen', values)

    def delete_essen_entry(self, document_id: str) -> None:
        self._delete_entry(document_id, 'essen')

    def fetch_essen_places(self) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_essen_places_document(session, database_url)
        return self._clean_option_values(document.get('werte', []))

    def add_essen_place(self, place: str) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_essen_places_document(session, database_url)
        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = self._clean_option_values([*values, place])
        self._save_named_document(session, database_url, document)
        return self._clean_option_values(document['werte'])

    def delete_essen_place(self, place: str) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_essen_places_document(session, database_url)
        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = [value for value in values if value != place]
        self._save_named_document(session, database_url, document)
        return self._clean_option_values(document['werte'])

    def rename_essen_place(self, old_place: str, new_place: str) -> list[str]:
        old_text = str(old_place or '').strip()
        new_text = str(new_place or '').strip()
        session = self._session()
        database_url = self._database_url()
        document = self._load_essen_places_document(session, database_url)

        if not old_text or not new_text:
            return self._clean_option_values(document.get('werte', []))

        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = self._clean_option_values(
            [new_text if value == old_text else value for value in values]
        )
        self._save_named_document(session, database_url, document)

        if old_text == new_text:
            return self._clean_option_values(document['werte'])

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
                or not self._document_matches_quelle(entry)
                or str(entry.get('wo_gegessen') or '').strip() != old_text
            ):
                continue

            entry['wo_gegessen'] = new_text
            self._save_named_document(session, database_url, entry)

        return self._clean_option_values(document['werte'])

    def fetch_medis_options(self) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_medis_options_document(session, database_url)
        return self._clean_option_values(document.get('werte', []))

    def add_medis_option(self, medication: str) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_medis_options_document(session, database_url)
        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = self._clean_option_values([*values, medication])
        self._save_named_document(session, database_url, document)
        return self._clean_option_values(document['werte'])

    def delete_medis_option(self, medication: str) -> list[str]:
        session = self._session()
        database_url = self._database_url()
        document = self._load_medis_options_document(session, database_url)
        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = [value for value in values if value != medication]
        self._save_named_document(session, database_url, document)
        return self._clean_option_values(document['werte'])

    def rename_medis_option(self, old_medication: str, new_medication: str) -> list[str]:
        old_text = str(old_medication or '').strip()
        new_text = str(new_medication or '').strip()
        session = self._session()
        database_url = self._database_url()
        document = self._load_medis_options_document(session, database_url)

        if not old_text or not new_text:
            return self._clean_option_values(document.get('werte', []))

        values = self._clean_option_values(document.get('werte', []))
        document['werte'] = self._clean_option_values(
            [new_text if value == old_text else value for value in values]
        )
        self._save_named_document(session, database_url, document)

        if old_text == new_text:
            return self._clean_option_values(document['werte'])

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
                or entry.get('typ') != MEDIS_ENTRY_TYPE
                or not self._document_matches_quelle(entry)
                or str(entry.get('medikament') or '').strip() != old_text
            ):
                continue

            entry['medikament'] = new_text
            self._save_named_document(session, database_url, entry)

        return self._clean_option_values(document['werte'])

    def _session(self) -> requests.Session:
        session = requests.Session()
        if self.config.couchdb.username or self.config.couchdb.password:
            session.auth = (self.config.couchdb.username, self.config.couchdb.password)
        return session

    def _database_url(self) -> str:
        server_url = self.config.couchdb.server_url.rstrip('/')
        database_name = quote(self.config.couchdb.database, safe='')
        return f'{server_url}/{database_name}'

    def _document_url(self, database_url: str, document_id: str) -> str:
        return f'{database_url}/{quote(document_id, safe="")}'

    def _normalized_quelle(self, quelle: object) -> str:
        return str(quelle or '').strip().lower()

    def _document_quelle(self, document: dict[str, object]) -> str:
        # Legacy documents without source were created before dev/prod separation.
        return str(document.get('quelle') or 'prod')

    def _document_matches_quelle(self, document: dict[str, object]) -> bool:
        return self._normalized_quelle(self._document_quelle(document)) == self._normalized_quelle(
            self.config.app.quelle
        )

    def _existing_document_times(
        self,
        session: requests.Session,
        database_url: str,
        date: str,
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
                and self._document_matches_quelle(document)
                and document.get('typ') == document_type
                and document.get('datum') == date
                and document.get('zeit')
            ):
                times.add(str(document['zeit']))
        return times

    def _with_unique_document_time(
        self,
        document: dict[str, object],
        session: requests.Session,
        database_url: str,
    ) -> dict[str, object]:
        date = document.get('datum')
        time = document.get('zeit')
        document_type = document.get('typ')
        if not date or not time:
            return document

        document['zeit'] = self._next_unique_time(
            str(time),
            self._existing_document_times(session, database_url, str(date), document_type),
        )
        return document

    def _fetch_entries_by_type(
        self,
        date_from: str,
        date_to: str,
        entry_type: str,
    ) -> list[dict[str, str]]:
        session = self._session()
        database_url = self._database_url()
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
                or not self._document_matches_quelle(document)
            ):
                continue

            entry_date = str(document.get('datum', ''))
            if date_from <= entry_date <= date_to:
                entries.append(
                    {
                        'row_key': str(
                            document.get('_id', f'{entry_date}-{document.get("zeit", "")}')
                        ),
                        'datum': entry_date,
                        'zeit': str(document.get('zeit', '')),
                        'konsistenz': str(document.get('konsistenz', '')),
                        'menge': str(document.get('menge', '')),
                        'farbe': str(document.get('farbe', '')),
                        'platte': 'ja' if document.get('platte') else 'nein',
                        'quelle': self._document_quelle(document),
                    }
                )

        return sorted(
            entries,
            key=lambda entry: (entry['datum'], self._time_sort_key(entry['zeit'])),
        )

    def _fetch_document(
        self,
        session: requests.Session,
        database_url: str,
        document_id: str,
    ) -> dict[str, object] | None:
        response = session.get(self._document_url(database_url, document_id), timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def _save_named_document(
        self,
        session: requests.Session,
        database_url: str,
        document: dict[str, object],
    ) -> None:
        document_id = str(document['_id'])
        response = session.put(
            self._document_url(database_url, document_id),
            json=document,
            timeout=10,
        )
        response.raise_for_status()

    def _update_entry(
        self,
        document_id: str,
        expected_type: str,
        values: dict[str, object],
    ) -> None:
        session = self._session()
        database_url = self._database_url()
        document = self._fetch_document(session, database_url, document_id)
        if document is None:
            raise ValueError('Eintrag wurde nicht gefunden.')
        if document.get('typ') != expected_type:
            raise ValueError('Eintrag hat den falschen Typ.')
        if not self._document_matches_quelle(document):
            raise ValueError('Eintrag gehoert zu einer anderen Quelle.')

        document.update(values)
        document['app_version'] = self.app_version
        self._save_named_document(session, database_url, document)

    def _delete_entry(self, document_id: str, expected_type: str) -> None:
        session = self._session()
        database_url = self._database_url()
        document = self._fetch_document(session, database_url, document_id)
        if document is None:
            raise ValueError('Eintrag wurde nicht gefunden.')
        if document.get('typ') != expected_type:
            raise ValueError('Eintrag hat den falschen Typ.')
        if not self._document_matches_quelle(document):
            raise ValueError('Eintrag gehoert zu einer anderen Quelle.')

        response = session.delete(
            self._document_url(database_url, document_id),
            params={'rev': str(document['_rev'])},
            timeout=10,
        )
        response.raise_for_status()

    def _essen_places_document_id(self) -> str:
        return f'optionen:{self.config.app.quelle}:{ESSEN_PLACES_OPTION_NAME}'

    def _medis_options_document_id(self) -> str:
        return f'optionen:{self.config.app.quelle}:{MEDIS_OPTION_NAME}'

    def _fetch_legacy_essen_places(
        self,
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
                or not self._document_matches_quelle(document)
            ):
                continue

            place = str(document.get('wo_gegessen') or '').strip()
            if place:
                places.add(place)

        return self._clean_option_values(places)

    def _load_essen_places_document(
        self,
        session: requests.Session,
        database_url: str,
    ) -> dict[str, object]:
        document_id = self._essen_places_document_id()
        document = self._fetch_document(session, database_url, document_id)

        if document is None:
            legacy_places = self._fetch_legacy_essen_places(session, database_url)
            values = self._clean_option_values([*DEFAULT_ESSEN_PLACES, *legacy_places])
            document = {
                '_id': document_id,
                'typ': 'optionen',
                'name': ESSEN_PLACES_OPTION_NAME,
                'quelle': self.config.app.quelle,
                'werte': values,
                'app_version': self.app_version,
            }
            self._save_named_document(session, database_url, document)
            return document

        document['werte'] = self._clean_option_values(document.get('werte', []))
        document['typ'] = 'optionen'
        document['name'] = ESSEN_PLACES_OPTION_NAME
        document['quelle'] = self.config.app.quelle
        document['app_version'] = self.app_version
        return document

    def _fetch_legacy_medis_options(
        self,
        session: requests.Session,
        database_url: str,
    ) -> list[str]:
        response = session.get(
            f'{database_url}/_all_docs',
            params={'include_docs': 'true'},
            timeout=10,
        )
        response.raise_for_status()

        medications = set()
        for row in response.json()['rows']:
            document = row.get('doc')
            if (
                not document
                or document.get('typ') != MEDIS_ENTRY_TYPE
                or not self._document_matches_quelle(document)
            ):
                continue

            medication = str(document.get('medikament') or '').strip()
            if medication:
                medications.add(medication)

        return self._clean_option_values(medications)

    def _load_medis_options_document(
        self,
        session: requests.Session,
        database_url: str,
    ) -> dict[str, object]:
        document_id = self._medis_options_document_id()
        document = self._fetch_document(session, database_url, document_id)

        if document is None:
            document = {
                '_id': document_id,
                'typ': 'optionen',
                'name': MEDIS_OPTION_NAME,
                'quelle': self.config.app.quelle,
                'werte': self._fetch_legacy_medis_options(session, database_url),
                'app_version': self.app_version,
            }
            self._save_named_document(session, database_url, document)
            return document

        document['werte'] = self._clean_option_values(document.get('werte', []))
        document['typ'] = 'optionen'
        document['name'] = MEDIS_OPTION_NAME
        document['quelle'] = self.config.app.quelle
        document['app_version'] = self.app_version
        return document

    def _clean_option_values(self, values: object) -> list[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, (list, set, tuple)):
            values = []
        cleaned = {str(value).strip() for value in values if str(value).strip()}
        return sorted(cleaned)

    def _suffix_number(self, candidate: str, base_value: str) -> int | None:
        if candidate == base_value:
            return 0

        prefix = f'{base_value}-'
        if not candidate.startswith(prefix):
            return None

        suffix = candidate.removeprefix(prefix)
        if not suffix.isdecimal():
            return None
        return int(suffix)

    def _next_unique_time(self, base_time: str, existing_times: set[str]) -> str:
        used_numbers = {
            number
            for candidate in existing_times
            if (number := self._suffix_number(candidate, base_time)) is not None
        }

        if 0 not in used_numbers:
            return base_time

        next_number = 1
        while next_number in used_numbers:
            next_number += 1
        return f'{base_time}-{next_number}'

    def _time_sort_key(self, time: str) -> tuple[str, int]:
        base_time, separator, suffix = time.rpartition('-')
        if separator and suffix.isdecimal():
            return base_time, int(suffix)
        return time, 0
