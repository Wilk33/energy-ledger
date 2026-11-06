# Konfiguracja Energy Ledger

Wymagane są dwie encje Home Assistant ze stanem całkowitym w kWh:

- `grid_import_total_entity` - całkowita energia pobrana z sieci,
- `grid_export_total_entity` - całkowita energia oddana do sieci.

Nie używaj liczników dziennych. Wartości powinny rosnąć monotonicznie. Reset licznika jest wykrywany i ustanawia nową bazę bez naliczania sztucznego przepływu.

`discount_percent` wybiera opust 80% lub 70%. `balance_correction_kwh` jest korektą jednorazową i po zastosowaniu zostanie automatycznie ustawione na zero.

Jeżeli ceny Twojej umowy różnią się od wbudowanej taryfy, włącz `manual_prices_enabled` i wpisz wszystkie wartości brutto. W `manual_common_variable` wpisz łączną stawkę jakościową, OZE i kogeneracyjną. Opłaty OZE i kogeneracyjną wpisz także osobno, aby aplikacja mogła wydzielić części naliczane od całego importu przed rozliczeniem opustu. `additional_fixed_monthly` służy do opłaty mocowej, handlowej i innych stałych składników niewspólnych dla wszystkich odbiorców.

Aplikacja publikuje koszty brutto. Dotychczasowe identyfikatory encji kosztowych pozostają bez zmian.

Po uruchomieniu sprawdź dziennik. Stan pojawi się na urządzeniu Energy Ledger przez MQTT Discovery.

## Kwota za poprzedni miesiąc

Encja „Szacowana kwota do zapłaty za poprzedni miesiąc” pokazuje sumę zapisanych
kosztów zmiennych i stałych brutto za poprzedni miesiąc kalendarzowy Europe/Warsaw.
Aplikacja dolicza również korektę brutto zapisaną przy zamknięciu miesiąca.
Atrybuty zawierają okres, składniki kwoty oraz źródło saved_month_close.
Brak zamknięcia tego miesiąca oznacza niedostępność, nie zerową fakturę.
Restart i zmiana bieżących cen nie przeliczają zapisanego wyniku. Starsze zamknięcia
zachowują kwoty obliczone wcześniejszym algorytmem. To szacunek kosztu energii,
bez rozliczenia wpłat, nadpłat i zaległości na koncie sprzedawcy.

## Stała korekta rachunku brutto

Opcja `monthly_bill_correction_pln` to ręcznie wpisywana kwota w PLN, dodawana
do ostatecznego kosztu każdego miesiąca. Domyślnie pole jest puste, co oznacza 0 zł.
Wartość dodatnia zwiększa wynik, ujemna go obniża. Jest to kwota brutto, bez
dodatkowego naliczania VAT, a nie procent ani mnożnik energii.

Przykład: wyliczenie 125,16 zł i korekta 5,94 zł dają 131,10 zł.
Korekta nie kumuluje się przy odczytach. Nie zeruje się automatycznie po miesiącu.
Działa z taryfą z katalogu oraz cenami ręcznymi. Zapisz ustawienia i uruchom
dodatek ponownie, aby zastosować nową wartość. W YAML używaj kropki dziesiętnej.

Kwoty zapisanych zamkniętych miesięcy nie zmieniają się po edycji ustawienia.
Starsze zamknięcia, bez zapisanej korekty, mają korektę 0 zł. Nowe zamknięcie
zapisuje zastosowaną kwotę w `bill_correction_pln`; encja poprzedniego miesiąca
pokazuje ją w atrybucie `correction_gross_pln`. Przy odzyskiwaniu niezamkniętych
miesięcy z historii stosowane jest aktualne ustawienie korekty.

## Aktualizacja 1.2.0

Eksport rozliczany jest najpierw w swojej strefie, a nadwyżka w pozostałych według malejącej zmiennej stawki dystrybucji. Przy aktualizacji eksport strefowy jest odtwarzany z historii tylko po uzgodnieniu sumy ze stanem aplikacji. `legacy-zone-estimate` oznacza brak danych do pełnego przeliczenia bieżącego miesiąca; od następnego miesiąca działa nowe rozliczenie.

Profil fakturowy od października zawiera stałą sieciową 10,86 zł netto i abonament 0 zł, zgodnie z przekazaną fakturą. Opłata mocowa pozostaje w `additional_fixed_monthly` (29,5815 zł brutto przed zaokrągleniem). Inne umowy mogą wymagać własnych stawek. W trybie ręcznym aktualizacja katalogu nie zmienia cen.

Poprawność kalkulatora nie oznacza zgodności odczytów falownika z godzinowo bilansowanymi odczytami operatora. Wartości pozostają brutto. Poziom DEBUG pokazuje import, eksport i niedobory w każdej strefie oraz składniki kwoty.
