from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from nicegui import app, ui

SaveDocument = Callable[[dict[str, object]], str]
FetchOptions = Callable[[], list[str]]
SaveOption = Callable[[str], list[str]]
RenameOption = Callable[[str, str], list[str]]
LAST_PLACE_STORAGE_KEY = 'essen_last_place'


def clean_options(options: list[object]) -> list[str]:
    cleaned: dict[str, str] = {}
    for option in options:
        text = str(option or '').strip()
        if text:
            cleaned.setdefault(text.casefold(), text)
    return sorted(cleaned.values(), key=str.casefold)


def prioritize_option(options: list[str], selected_value: object) -> list[str]:
    selected = str(selected_value or '').strip()
    if not selected or selected not in options:
        return list(options)
    return [selected, *[option for option in options if option != selected]]


class EditableOptionsSelect:
    def __init__(
        self,
        label: str,
        options: list[str],
        option_name: str,
        load_options: FetchOptions,
        add_option: SaveOption,
        delete_option: SaveOption,
        rename_option: RenameOption,
        storage_key: str | None = None,
    ) -> None:
        self._options = clean_options(options)
        self._option_name = option_name
        self._load_options = load_options
        self._add_option = add_option
        self._delete_option = delete_option
        self._rename_option = rename_option
        self._storage_key = storage_key
        self._dialog_mode = {'value': 'add'}
        initial_value = self._preferred_selection()

        with ui.row().classes('w-64 max-w-full gap-1 items-start'):
            self._element = ui.select(
                prioritize_option(self._options, initial_value),
                label=label,
                value=initial_value,
                clearable=True,
            ).props('dense options-dense').classes('min-w-0 flex-1')
            self._element.on_value_change(lambda _: self._on_value_change())
            with ui.fab('more_vert', direction='left').props('flat dense mini').classes('mt-1'):
                ui.fab_action('add', on_click=lambda: self._open_dialog('add')) \
                    .props('dense mini') \
                    .tooltip(f'{option_name} hinzufuegen')
                ui.fab_action('edit', on_click=lambda: self._open_dialog('edit')) \
                    .props('dense mini') \
                    .tooltip(f'{option_name} aendern')
                ui.fab_action('delete', on_click=self._delete_current_option, color='negative') \
                    .props('dense mini') \
                    .tooltip(f'{option_name} loeschen')

        with ui.dialog() as option_dialog, ui.card().classes('w-[360px] max-w-full gap-3'):
            self._dialog_title = ui.label(f'{option_name} hinzufuegen') \
                .classes('text-lg font-semibold text-slate-900')
            self._option_input = ui.input(option_name).props('dense autocomplete="off"') \
                .classes('w-full')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Abbrechen', on_click=option_dialog.close).props('flat no-caps dense')
                ui.button('Speichern', on_click=lambda: self._save_dialog(option_dialog)) \
                    .props('no-caps dense')
        self._option_dialog = option_dialog

    @property
    def value(self) -> str:
        return str(self._element.value or '').strip()

    def set_options(self, options: list[str], value: str | None = None) -> None:
        self._options = clean_options(options)
        selected = self._preferred_selection(value)
        self._element.set_options(prioritize_option(self._options, selected), value=selected)
        self._remember_value(selected)

    def _preferred_selection(self, value: str | None = None) -> str | None:
        selected = str(value or '').strip()
        if selected in self._options:
            return selected

        if hasattr(self, '_element'):
            selected = self.value
            if selected in self._options:
                return selected

        selected = self._remembered_value()
        if selected in self._options:
            return selected

        return self._options[0] if self._options else None

    def _remembered_value(self) -> str:
        if not self._storage_key:
            return ''
        return str(app.storage.user.get(self._storage_key, '') or '').strip()

    def _remember_value(self, value: str | None) -> None:
        if self._storage_key and value:
            app.storage.user[self._storage_key] = value

    def _sync_display_order(self) -> None:
        self._element.set_options(prioritize_option(self._options, self.value), value=self.value or None)

    def _on_value_change(self) -> None:
        self._remember_value(self.value)
        self._sync_display_order()

    def _reload_options(self, selected_value: str | None = None) -> None:
        try:
            options = self._load_options()
        except Exception as exc:
            ui.notify(f'{self._option_name} konnte nicht geladen werden: {exc}', color='warning')
            return

        self.set_options(options, selected_value)

    def _open_dialog(self, mode: str) -> None:
        self._reload_options()
        current_value = self.value
        if mode == 'edit' and not current_value:
            ui.notify(f'Bitte zuerst {self._option_name} auswaehlen.', color='warning')
            return

        self._dialog_mode['value'] = mode
        self._dialog_title.set_text(
            f'{self._option_name} aendern'
            if mode == 'edit'
            else f'{self._option_name} hinzufuegen'
        )
        self._option_input.value = current_value if mode == 'edit' else ''
        self._option_dialog.open()
        ui.timer(0.1, lambda: self._option_input.run_method('focus'), once=True)

    def _save_dialog(self, dialog: Any) -> None:
        value = str(self._option_input.value or '').strip()
        if not value:
            ui.notify(f'Bitte {self._option_name} eingeben.', color='warning')
            return

        current_value = self.value
        try:
            if self._dialog_mode['value'] == 'edit' and current_value:
                options = self._rename_option(current_value, value)
            else:
                options = self._add_option(value)
        except Exception as exc:
            ui.notify(f'{self._option_name} konnte nicht gespeichert werden: {exc}', color='negative')
            return

        self.set_options(options, value)
        dialog.close()

    def _delete_current_option(self) -> None:
        self._reload_options()
        value = self.value
        if not value:
            ui.notify(f'Bitte zuerst {self._option_name} auswaehlen.', color='warning')
            return

        try:
            options = self._delete_option(value)
        except Exception as exc:
            ui.notify(f'{self._option_name} konnte nicht geloescht werden: {exc}', color='negative')
            return

        self.set_options(options)


def current_quarter_hour() -> datetime:
    now = datetime.now()
    minute = (now.minute // 15) * 15
    return now.replace(minute=minute, second=0, microsecond=0)


MEAL_OPTIONS = ['Fruehstueck', 'Mittagessen', 'Kaffeetrinken', 'Abendessen', 'Snack']


def default_meal() -> str:
    now = datetime.now().time()
    if datetime.strptime('05:00', '%H:%M').time() <= now <= datetime.strptime('10:00', '%H:%M').time():
        return 'Fruehstueck'
    if datetime.strptime('12:00', '%H:%M').time() <= now <= datetime.strptime('14:00', '%H:%M').time():
        return 'Mittagessen'
    if datetime.strptime('15:00', '%H:%M').time() <= now <= datetime.strptime('17:00', '%H:%M').time():
        return 'Kaffeetrinken'
    if datetime.strptime('18:00', '%H:%M').time() <= now <= datetime.strptime('20:00', '%H:%M').time():
        return 'Abendessen'
    return 'Snack'


def register_essen_pages(
    build_shell: Callable[[str], None],
    save_document: SaveDocument,
    fetch_places: FetchOptions,
    add_place: SaveOption,
    delete_place: SaveOption,
    rename_place: RenameOption,
) -> None:
    @ui.page('/essen')
    def essen_page() -> None:
        build_shell('Essen')

        with ui.column().classes('min-h-screen w-full items-center justify-center gap-5 px-6'):
            ui.label('Essen').classes('text-3xl font-bold text-slate-800 text-center')
            food_input = ui.input('Was gegessen') \
                .classes('w-64 max-w-full')
            try:
                place_options = fetch_places()
            except Exception:
                place_options = ['Zuhause', 'Arbeit', 'Restaurant', 'Unterwegs']

            meal_select = ui.select(
                prioritize_option(MEAL_OPTIONS, default_meal()),
                label='Mahlzeit',
                value=default_meal(),
            ).props('dense options-dense').classes('w-64 max-w-full')
            meal_select.on_value_change(
                lambda _: meal_select.set_options(
                    prioritize_option(MEAL_OPTIONS, meal_select.value),
                    value=meal_select.value,
                )
            )
            place_select = EditableOptionsSelect(
                'Wo gegessen',
                place_options,
                'Ort',
                fetch_places,
                add_place,
                delete_place,
                rename_place,
                LAST_PLACE_STORAGE_KEY,
            )

            def update_place_options(options: list[str], value: str | None = None) -> None:
                selected = value if value in options else place_select.value
                if selected not in options:
                    selected = options[0] if options else None
                place_select.set_options(options, selected)

            def save_entry() -> None:
                food = str(food_input.value or '').strip()
                meal = str(meal_select.value or '').strip()
                place = str(place_select.value or '').strip()
                if not food:
                    timestamp_label.set_text('Bitte Was gegessen ausfuellen.')
                    ui.notify('Bitte Was gegessen ausfuellen.', color='warning')
                    return
                if not meal:
                    timestamp_label.set_text('Bitte Mahlzeit ausfuellen.')
                    ui.notify('Bitte Mahlzeit ausfuellen.', color='warning')
                    return
                if not place:
                    timestamp_label.set_text('Bitte Wo gegessen ausfuellen.')
                    ui.notify('Bitte Wo gegessen ausfuellen.', color='warning')
                    return

                timestamp = current_quarter_hour()
                document = {
                    'typ': 'essen',
                    'was_gegessen': food,
                    'mahlzeit': meal,
                    'wo_gegessen': place,
                    'datum': timestamp.strftime('%Y-%m-%d'),
                    'zeit': timestamp.strftime('%H:%M'),
                }

                try:
                    options = add_place(place)
                    update_place_options(options, place)
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
                .style('background: #4F8F6B !important; color: white !important;')
            timestamp_label = ui.label('').classes(
                'text-base font-medium text-slate-700 text-center'
            )
            ui.button('Zurueck', on_click=lambda: ui.navigate.to('/')).props('outline') \
                .classes('rounded-2xl px-6 py-3 text-base font-medium')
