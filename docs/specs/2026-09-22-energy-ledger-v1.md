# Energy Ledger 1.0.0 - specyfikacja

## Cel

Energy Ledger jest aplikacją Home Assistant OS bez Ingressu. Odczytuje historię i bieżące zmiany dwóch liczników całkowitych energii, prowadzi magazyn wirtualny prosumenta oraz publikuje stan i szacowane koszty przez MQTT Discovery.

## Dane wejściowe

- encja całkowitego importu energii w kWh,
- encja całkowitego eksportu energii w kWh,
- współczynnik opustu 0,8 albo 0,7,
- jednorazowa korekta stanu magazynu w kWh,
- taryfa G13 w strefie Europe/Warsaw,
- katalog stawek TAURON albo ręczne stawki brutto.

Encje dzienne nie są używane. Stany `unknown`, `unavailable`, nienumeryczne i niefinitywne są pomijane. Spadek licznika całkowitego ustanawia nową bazę i nie tworzy ujemnego zużycia.

## Magazyn

Magazyn jest wskaźnikiem ze znakiem:

`magazyn += eksport * opust - import`

Wartość dodatnia oznacza zapas, a ujemna niedobór. Stan jest przeliczany po każdym zdarzeniu `state_changed`. Historia Home Assistant uzupełnia przerwę po zatrzymaniu aplikacji.

## Okres miesięczny

W trakcie miesiąca koszt niedoboru zmienia się po każdym imporcie i eksporcie. Eksport może zmniejszyć wcześniejszy niedobór i koszt.

Przy przejściu do kolejnego miesiąca:

- dodatni magazyn przechodzi dalej,
- ujemny magazyn i jego koszt są zapisane w historii zamkniętego miesiąca,
- ujemny magazyn zostaje wyzerowany,
- liczniki i koszt bieżącego miesiąca zaczynają nowy okres.

## Korekta jednorazowa

Przy uruchomieniu aplikacja odczytuje `balance_correction_kwh`. Wartość różna od zera jest dodawana do trwałego stanu magazynu, a aplikacja zapisuje informację o jej zastosowaniu przed próbą wyzerowania opcji przez Supervisor API.

Jeżeli aplikacja zakończy się po zastosowaniu korekty, lecz przed wyzerowaniem opcji, następne uruchomienie nie zastosuje jej ponownie i tylko ponowi zerowanie. Po zaobserwowaniu zera można ponownie wpisać tę samą wartość jako nową korektę.

## G13 i koszt

Strefy G13 są wyznaczane w czasie Europe/Warsaw:

- szczyt przedpołudniowy: 07:00-13:00 w dni robocze,
- szczyt popołudniowy latem: 19:00-22:00 w dni robocze,
- szczyt popołudniowy zimą: 16:00-21:00 w dni robocze,
- pozostałe godziny oraz całe soboty, niedziele i polskie dni ustawowo wolne: strefa pozostała.

Koszt zmienny jest liczony z niepokrytej energii w strefach. Późniejszy eksport pokrywa najstarszą niepokrytą energię. Stałe opłaty miesięczne są pokazywane oddzielnie.

Wbudowany katalog zawiera oficjalne stawki dystrybucyjne TAURON na 2026 rok. Ceny sprzedaży energii i składniki zależne od umowy użytkownik może wpisać ręcznie. Automatyczna aktualizacja katalogu pobiera JSON, sprawdza schemat i datę obowiązywania, zapisuje go atomowo i zachowuje poprzednią poprawną wersję przy błędzie.

## Wyjście MQTT

Aplikacja publikuje przez MQTT Discovery co najmniej:

- stan magazynu wirtualnego,
- niepokrytą energię,
- bieżący koszt zmienny,
- bieżące opłaty stałe,
- szacowaną kwotę bieżącego miesiąca,
- import i eksport miesiąca,
- import w każdej strefie G13,
- status i wersję taryfy,
- czas ostatniej aktualizacji i jakość danych.

## Trwałość i odzyskiwanie

Stan jest zapisywany atomowo w `/data/energy-ledger-state.json`. Każda encja ma osobny czas ostatniego zdarzenia i bazę licznika. Powtórzone zdarzenia z historii są ignorowane. Katalog zdalny i stan lokalny przetrwają restart kontenera.
