# Changelog

## 1.2.3

- Poprawiono aktualizację dodatku z wersji 1.2.1: pusta korekta rachunku jest opcjonalna w schemacie Supervisora. Usunięto domyślne `null`, które Supervisor traktował jako brak wartości wymaganej i odrzucał aktualizację.

## 1.2.2

- Dodano opcjonalną stałą korektę miesięcznej kwoty brutto w PLN. Puste pole oznacza 0, wartości ujemne obniżają wynik.
- Korekta jest dodawana raz do końcowej kwoty każdego miesiąca, bez ponownego VAT i bez zmiany kWh, taryfy lub opłat.
- Zapis zamkniętego miesiąca zachowuje zastosowaną korektę. Encja poprzedniego miesiąca uwzględnia ją i pokazuje osobno w atrybutach.
- Dotychczasowe zamknięcia bez korekty są wczytywane z wartością 0.

## 1.2.1

- Dodano jedną encję MQTT: szacowana kwota do zapłaty za poprzedni miesiąc, brutto z opłatami stałymi.
- Encja korzysta z zapisanego zamknięcia miesiąca; brak rekordu oznacza niedostępność zamiast rachunku 0 zł.
- Atrybuty encji zawierają okres oraz składniki zmienne i stałe brutto. Zmiana bieżącej taryfy nie przelicza zapisanych zamknięć.
- Dodano analizę wpływu rozdzielczości licznika i narzędzie porównujące przydział przyrostów do stref. Eksperymentalny podział czasowy nie zmienia działania aplikacji.

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
