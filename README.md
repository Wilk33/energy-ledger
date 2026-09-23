# Energy Ledger i Battery Charge Controller

Repozytorium zawiera dwie niezależne aplikacje Home Assistant OS:

- **Energy Ledger** - magazyn wirtualny prosumenta i bieżący koszt energii TAURON G13.
- **Battery Charge Controller** - automatyczne ładowanie baterii Deye nocą i przed popołudniową strefą szczytową. Szczegóły: [dokumentacja aplikacji](battery-charge-controller/DOCS.md).

## Energy Ledger

Energy Ledger to aplikacja Home Assistant OS prowadząca na żywo magazyn wirtualny prosumenta i szacowany koszt energii w taryfie TAURON G13. Nie ma Ingressu ani własnego panelu. Konfiguracja znajduje się w ustawieniach aplikacji, a wyniki pojawiają się jako encje MQTT Discovery.

## Wersja 1.0.0

- odczytuje historię dwóch encji całkowitych z Home Assistant REST API,
- po starcie subskrybuje `state_changed` przez Home Assistant WebSocket API,
- liczy `magazyn += eksport * opust - import`,
- obsługuje opust 80% albo 70%,
- klasyfikuje import do stref G13 w `Europe/Warsaw`, także w weekendy i polskie święta,
- pokazuje zmieniający się koszt niedoboru w trakcie miesiąca,
- przenosi dodatni magazyn na kolejny miesiąc,
- zamyka ujemny magazyn i koszt na końcu miesiąca, po czym zaczyna następny miesiąc od zera,
- stosuje ręczną korektę tylko raz i zeruje ustawienie po trwałym zapisaniu korekty,
- pobiera wersjonowany katalog taryfy przy uruchomieniu i zachowuje ostatnią poprawną kopię,
- pozwala całkowicie zastąpić taryfę ręcznie,
- publikuje stan, koszty, import strefowy i diagnostykę przez MQTT Discovery.

## Instalacja

1. W Home Assistant przejdź do Ustawienia - Aplikacje - Sklep z aplikacjami.
2. Dodaj repozytorium `https://github.com/Wilk33/energy-ledger`.
3. Zainstaluj Energy Ledger.
4. W ustawieniach wskaż encję całkowitego importu i całkowitego eksportu. Nie wybieraj encji dziennych.
5. Sprawdź opust, ceny, opłatę mocową i inne opłaty zależne od swojej umowy.
6. Uruchom aplikację i sprawdź jej dziennik.

Wymagana jest działająca integracja MQTT w Home Assistant. Aplikacja pobiera adres i dane logowania brokera z usługi MQTT Supervisora.

## Korekta magazynu

Pole `balance_correction_kwh` jest poleceniem jednorazowym:

- wartość dodatnia dodaje nadwyżkę,
- wartość ujemna dodaje niedobór,
- aplikacja najpierw zapisuje zmieniony stan,
- potem ustawia tę opcję z powrotem na `0` przez Supervisor API,
- awaria pomiędzy tymi operacjami nie powoduje ponownego naliczenia korekty.

Przy pierwszym uruchomieniu aplikacja odtwarza bieżący miesiąc z historii Home Assistant. Korektą należy wprowadzić stan magazynu sprzed początku tego miesiąca, najlepiej zgodny z ostatnim rozliczeniem lub własnym, zweryfikowanym zapisem.

## Taryfa i ceny

Wbudowany katalog `tauron-g13-2026-regulated` obowiązuje od 1 lutego do 31 grudnia 2026 r. Zawiera:

- regulowane ceny sprzedaży energii TAURON Sprzedaż G13, powiększone o akcyzę 0,005 PLN/kWh i VAT 23%,
- stawki zmienne dystrybucji G13 brutto,
- opłatę jakościową, OZE i kogeneracyjną brutto,
- stałą opłatę sieciową dla układu trójfazowego i abonament miesięczny.

Domyślne `additional_fixed_monthly=29.58` odpowiada opłacie mocowej brutto dla zużycia powyżej 2800 kWh rocznie. Zmień je zgodnie z własnym progiem i umową. Opłatę handlową lub inne stałe składniki także można dodać w tym polu.

Jeżeli masz ofertę handlową albo inną cenę niż taryfa regulowana, włącz `manual_prices_enabled` i wpisz wszystkie stawki brutto. W tym trybie katalog automatyczny nie wpływa na koszt.

Katalog jest pobierany wyłącznie przez HTTPS, ma limit rozmiaru i jest sprawdzany przed atomową podmianą. Błąd pobierania lub walidacji pozostawia poprzednią poprawną wersję.

## Sposób przypisywania kosztu

Import zużywa najpierw dodatni magazyn. Pozostała część tworzy niedobór w strefie G13 właściwej dla czasu zdarzenia. Późniejszy eksport pokrywa najstarszy niedobór, dlatego kwota do zapłaty może maleć jeszcze przed końcem miesiąca.

Wynik jest bieżącym oszacowaniem. Faktura operatora może różnić się przez zaokrąglenia, korekty odczytów, dodatkowe pozycje umowne albo inny sposób przypisania energii do stref. Historia zamkniętych miesięcy znajduje się w trwałym pliku stanu aplikacji.

## Encje MQTT

Aplikacja tworzy między innymi:

- Magazyn wirtualny,
- Niepokryta energia,
- Koszt energii w miesiącu,
- Opłaty stałe w miesiącu,
- Szacowana kwota miesiąca,
- Import i eksport w miesiącu,
- Import w trzech strefach G13,
- Wersja taryfy,
- Jakość danych,
- Ostatnia aktualizacja.

## Źródła

- [Komunikacja aplikacji Home Assistant z Core, Supervisorem i MQTT](https://developers.home-assistant.io/docs/apps/communication/)
- [Home Assistant REST API - historia encji](https://developers.home-assistant.io/docs/api/rest/)
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt)
- [TAURON Dystrybucja - taryfa 2026 i stawki brutto](https://www.tauron-dystrybucja.pl/uslugi-dystrybucyjne/dokumenty-do-pobrania)
- [URE - taryfa TAURON Sprzedaż na 2026 rok](https://bip.ure.gov.pl/download/3/20340/TauronSprzedaz.pdf)
- [Ministerstwo Finansów - stawka akcyzy na energię elektryczną w 2026 roku](https://www.podatki.gov.pl/akcyza/stawki-podatkowe)
- [Państwowa Inspekcja Pracy - Wigilia jako dzień wolny od pracy od 2025 roku](https://www.pip.gov.pl/dla-pracodawcow/pytania-i-odpowiedzi/czy-od-2025-roku-wigilia-jest-dniem-wolnym-od-pracy-i-czy-pracodawca-moze-polecic-mi-prace-we-wszystkie-niedziele-handlowe-w-grudniu?tmpl=pdf)

## Rozwój i testy

```text
python -m unittest discover -s tests -v
```

Szczegółowa specyfikacja znajduje się w `docs/specs/2026-09-22-energy-ledger-v1.md`.
