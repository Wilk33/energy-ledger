# Changelog

## 1.2.0

- Dodano opcjonalny warunek prognozy produkcji dla rozpoczęcia ładowania nocnego.
- Dodano przełącznik funkcji w konfiguracji i opcjonalną encję prognozy energii w kWh.
- Włączenie funkcji tworzy dodatkowy suwak progu produkcji 1-100 kWh, z zapisem wartości po restarcie.
- Prognoza równa progowi lub wyższa blokuje start nocny. Brak poprawnej prognozy pozostawia standardowe progi SOC.
- Warunek nie przerywa rozpoczętego ładowania i nie dotyczy ładowania dziennego. Logi pokazują prognozę, próg i wynik warunku.

## 1.1.1

- `Prog5 Time` jest sprawdzany przy starcie i dopiero po zmianie oczekiwanej wartości sezonowej.
- Chwilowy stan `unavailable` przed zapisem nie powoduje niepotrzebnej zmiany `Prog5 Time`.
- Odczyt kontrolny po zapisie jest ponawiany przez konfigurowalny czas, bez ponawiania samego zapisu.

## 1.1.0

- Osiem suwaków SOC: osobne progi i cele dla lata i zimy, niezależnie dla ładowania nocnego i dziennego.
- Automatyczny wybór zestawu suwaków według bieżącego sezonu.
- Migracja czterech ustawień wersji 1.0.0 do obu sezonów.
- Usuwanie czterech nieaktualnych encji MQTT po aktualizacji.
- Czytelna lista wszystkich nieistniejących identyfikatorów encji podczas uruchamiania.

## 1.0.0

- Niezależne ładowanie nocne przez Prog1 i dzienne przez Prog4.
- Cztery suwaki SOC i dwa trwałe przełączniki MQTT.
- Dwa sensory czasu bez powielania istniejącego SOC.
- Twarde końce 06:55, 18:55 latem i 15:55 zimą.
- Automatyczna sezonowa synchronizacja Prog5 Time.
- Pełny reset Prog1-Prog6 z wyłączeniem Grid Charge w pierwszym kroku.
- Odczyt kontrolny po każdym zapisie i bezpieczne odzyskiwanie po restarcie.
