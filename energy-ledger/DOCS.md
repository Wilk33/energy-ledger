# Konfiguracja Energy Ledger

Wymagane są dwie encje Home Assistant ze stanem całkowitym w kWh:

- `grid_import_total_entity` - całkowita energia pobrana z sieci,
- `grid_export_total_entity` - całkowita energia oddana do sieci.

Nie używaj liczników dziennych. Wartości powinny rosnąć monotonicznie. Reset licznika jest wykrywany i ustanawia nową bazę bez naliczania sztucznego przepływu.

`discount_percent` wybiera opust 80% lub 70%. `balance_correction_kwh` jest korektą jednorazową i po zastosowaniu zostanie automatycznie ustawione na zero.

Jeżeli ceny Twojej umowy różnią się od wbudowanej taryfy regulowanej, włącz `manual_prices_enabled` i wpisz wszystkie wartości brutto. `additional_fixed_monthly` służy do opłaty mocowej, handlowej i innych stałych składników niewspólnych dla wszystkich odbiorców.

Po uruchomieniu sprawdź dziennik. Stan pojawi się na urządzeniu Energy Ledger przez MQTT Discovery.
