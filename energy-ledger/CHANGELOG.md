# Changelog

## 1.1.0

- Stawki G13 zweryfikowane na fakturze TAURON za wrzesień 2026.
- Osobne podstawy naliczania energii po opuście oraz opłat OZE i kogeneracyjnej od pełnego importu.
- Koszty brutto zgodne z pozycjami i VAT z faktury.
- Zaokrąglanie pozycji kosztowych zgodne z układem faktury.
- Zachowane identyfikatory dotychczasowych encji brutto i obsługa starszej ręcznej stawki łącznej.

## 1.0.0

- Pierwsza wersja testowa.
- Magazyn opustowy 80% lub 70% na podstawie liczników całkowitych.
- Historia REST i aktualizacje WebSocket Home Assistant.
- Koszt G13 aktualizowany po każdym zdarzeniu.
- Miesięczne zamknięcie ujemnego magazynu i przenoszenie dodatniego.
- Jednorazowa korekta odporna na restart.
- Automatyczny katalog TAURON i pełny tryb cen ręcznych.
- Encje MQTT Discovery bez Ingressu.

## 1.2.0

- Poprawiono rozliczanie eksportu: najpierw własna strefa, potem pozostałe według stawki dystrybucji zamiast FIFO.
- Dodano trwały eksport strefowy i kontrolowane odtworzenie go z historii przy aktualizacji.
- Dodano jakość legacy-zone-estimate dla miesiąca bez pełnej historii strefowej.
- Dodano październikowy profil fakturowy z abonamentem 0 zł i stałą sieciową 10,86 zł netto.
- Dodano regresję pozycji faktury na 131,10 zł brutto i analizę różnic pomiarowych.
