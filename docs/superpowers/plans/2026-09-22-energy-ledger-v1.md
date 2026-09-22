# Energy Ledger 1.0.0 Implementation Plan

> **Spec:** `docs/specs/2026-09-22-energy-ledger-v1.md`

**Goal:** Dostarczyć instalowalną aplikację Home Assistant OS 1.0.0, która na żywo prowadzi magazyn opustowy, koszt G13 i encje MQTT.

**Architecture:** Czysty rdzeń domenowy przetwarza monotoniczne liczniki i miesiące. Adaptery Home Assistant, Supervisor, MQTT i katalogu taryf są oddzielone od rdzenia. Trwały stan JSON jest zapisywany atomowo.

**Tech Stack:** Python 3.12+, aiohttp, paho-mqtt, Home Assistant app base image, unittest.

## Global Constraints

- Brak Ingressu i własnego panelu.
- Wszystkie ustawienia w konfiguracji aplikacji.
- Historia REST i bieżące zdarzenia WebSocket.
- Tylko liczniki całkowite importu i eksportu.
- Strefa Europe/Warsaw i taryfa G13.
- Testy rdzenia są wykonywane bez Home Assistant i bez brokera.

## Task 1: Rdzeń taryfy G13

- [ ] Napisać testy stref letnich, zimowych, weekendów i świąt.
- [ ] Zaimplementować klasyfikację stref oraz model stawek.
- [ ] Zweryfikować testami obliczenia kosztu brutto.

## Task 2: Magazyn i zamknięcie miesiąca

- [ ] Napisać testy opustu, importu, eksportu, resetu licznika i ignorowania błędnych danych.
- [ ] Napisać test kosztu malejącego po późniejszym eksporcie.
- [ ] Napisać test przeniesienia dodatniego i rozliczenia ujemnego magazynu.
- [ ] Zaimplementować rdzeń i serializację stanu.

## Task 3: Jednorazowa korekta i trwały zapis

- [ ] Napisać test zastosowania korekty dokładnie raz mimo przerwania zerowania.
- [ ] Napisać test ponownego użycia tej samej wartości po zaobserwowaniu zera.
- [ ] Zaimplementować koordynator korekty i atomowy magazyn JSON.

## Task 4: Adaptery Home Assistant i MQTT

- [ ] Napisać testy normalizacji historii, filtrowania encji i payloadu MQTT Discovery.
- [ ] Zaimplementować REST, WebSocket, Supervisor options i MQTT.
- [ ] Zaimplementować startowy backfill oraz ciągłe przetwarzanie zdarzeń.

## Task 5: Katalog taryf, pakowanie i dokumentacja

- [ ] Napisać test walidacji i wyboru katalogu obowiązującego w dacie.
- [ ] Dodać katalog TAURON G13 2026 i ręczne nadpisania.
- [ ] Dodać `repository.yaml`, konfigurację aplikacji, obraz i skrypt startowy.
- [ ] Opisać instalację, ustawienia, encje, źródła stawek i ograniczenia.
- [ ] Uruchomić pełny zestaw testów, walidację składni i kontrolę repozytorium.
- [ ] Ustawić wersję 1.0.0, utworzyć commit i tag `v1.0.0`, wypchnąć do `origin`.

## Review Focus

- Korekta nie może zostać zastosowana drugi raz po awarii pomiędzy zapisem stanu a zerowaniem opcji.
- Zdarzenia historyczne nie mogą zostać naliczone drugi raz.
- Reset licznika energii nie może utworzyć sztucznego importu ani eksportu.
- Granice stref G13 muszą działać po konwersji do Europe/Warsaw.
- Brak sieci nie może uszkodzić ostatniego poprawnego katalogu taryfy.
