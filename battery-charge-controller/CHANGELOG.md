# Changelog

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
