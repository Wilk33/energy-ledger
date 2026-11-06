# Konfiguracja Energy Ledger

Wymagane są dwie encje Home Assistant ze stanem całkowitym w kWh:

- `grid_import_total_entity` - całkowita energia pobrana z sieci,
- `grid_export_total_entity` - całkowita energia oddana do sieci.

Nie używaj liczników dziennych. Wartości powinny rosnąć monotonicznie. Reset licznika jest wykrywany i ustanawia nową bazę bez naliczania sztucznego przepływu.

`discount_percent` wybiera opust 80% lub 70%. `balance_correction_kwh` jest korektą jednorazową i po zastosowaniu zostanie automatycznie ustawione na zero.

Jeżeli ceny Twojej umowy różnią się od wbudowanej taryfy, włącz `manual_prices_enabled` i wpisz wszystkie wartości brutto. W `manual_common_variable` wpisz łączną stawkę jakościową, OZE i kogeneracyjną. Opłaty OZE i kogeneracyjną wpisz także osobno, aby aplikacja mogła wydzielić części naliczane od całego importu przed rozliczeniem opustu. `additional_fixed_monthly` służy do opłaty mocowej, handlowej i innych stałych składników niewspólnych dla wszystkich odbiorców.

Aplikacja publikuje koszty brutto. Dotychczasowe identyfikatory encji kosztowych pozostają bez zmian.

Po uruchomieniu sprawdź dziennik. Stan pojawi się na urządzeniu Energy Ledger przez MQTT Discovery.

## Aktualizacja 1.2.0

Eksport rozliczany jest najpierw w swojej strefie, a nadwyżka w pozostałych według malejącej zmiennej stawki dystrybucji. Przy aktualizacji eksport strefowy jest odtwarzany z historii tylko po uzgodnieniu sumy ze stanem aplikacji. `legacy-zone-estimate` oznacza brak danych do pełnego przeliczenia bieżącego miesiąca; od następnego miesiąca działa nowe rozliczenie.

Profil fakturowy od października zawiera stałą sieciową 10,86 zł netto i abonament 0 zł, zgodnie z przekazaną fakturą. Opłata mocowa pozostaje w `additional_fixed_monthly` (29,5815 zł brutto przed zaokrągleniem). Inne umowy mogą wymagać własnych stawek. W trybie ręcznym aktualizacja katalogu nie zmienia cen.

Poprawność kalkulatora nie oznacza zgodności odczytów falownika z godzinowo bilansowanymi odczytami operatora. Wartości pozostają brutto. Poziom DEBUG pokazuje import, eksport i niedobory w każdej strefie oraz składniki kwoty.
