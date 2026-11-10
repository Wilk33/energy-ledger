# Battery Charge Controller

Aplikacja steruje ładowaniem baterii Deye z sieci w dwóch niezależnych segmentach:

- nocnym przez `Prog1 Capacity` i `Prog1 Charge`,
- dziennym przez `Prog4 Capacity` i `Prog4 Charge`.

Nie ma Ingressu. Cała konfiguracja znajduje się w ustawieniach aplikacji, a bieżące nastawy są dostępne przez MQTT Discovery.

## Encje MQTT

Aplikacja tworzy dokładnie:

- osiem suwaków: osobne progi i cele SOC dla lata i zimy, niezależnie dla nocy oraz dnia,
- dwa przełączniki: ładowanie nocne i ładowanie dzienne,
- sensor czasu do planowanego startu,
- sensor czasu do twardego końca okna.

Przy włączonym warunku prognozy powstaje dodatkowy suwak „Nocny próg prognozy produkcji”.

## Opcjonalny warunek prognozy produkcji

W konfiguracji włącz `forecast_condition_enabled` i podaj `forecast_entity`.
Pole encji jest opcjonalnym ustawieniem Supervisora; może wymagać włączenia
wyświetlania opcji opcjonalnych. Przełącznik aktywuje wykorzystanie tego pola,
nie steruje jego dynamicznym ukrywaniem w standardowym formularzu dodatku.
Po zapisaniu zrestartuj dodatek.

Encja musi podawać prognozowaną energię w kWh. Dobierz prognozę właściwego dnia:
przed północą „jutro”, po północy „dzisiaj” oznaczają dzień po ładowaniu nocnym.
Aplikacja odczytuje stan wskazanej encji bez samodzielnej zmiany jej daty lub jednostek.

Suwak ma zakres 1-100 kWh, krok 1 kWh i początkową wartość 20 kWh. Wartość jest
zapamiętywana po restarcie. Start wymaga spełnienia dotychczasowych zasad SOC,
czasu i włączenia segmentu oraz prognozy mniejszej od tego progu.
Przykład dla progu 20 kWh: prognoza 15 kWh dopuszcza start, 20 lub 30 kWh blokuje.

`unknown`, `unavailable`, brak encji, błąd odczytu, wartość ujemna i nieliczbowa
oznaczają powrót do standardowych zasad SOC. Zero kWh jest poprawną prognozą.
Warunek jest sprawdzany ponownie w cyklu i po zmianie encji prognozy. Blokada
nie oznacza zakończenia nocnego okna: późniejsza niższa prognoza może dopuścić start.
Nie jest wtedy pokazywany czas planowanego startu. Prognoza nie przerywa sesji,
która już wystartowała, i nie wpływa na ładowanie dzienne.

Po wyłączeniu funkcji i restarcie dodatkowy suwak jest usuwany z MQTT Discovery,
ale jego wartość pozostaje zapisana na wypadek ponownego włączenia funkcji.

Nie tworzy kopii bieżącego SOC, sezonu, decyzji ani stanów zapisów. Te informacje są dostępne w oryginalnych encjach Deye i dzienniku aplikacji.

Oba przełączniki są wyłączone przy pierwszym uruchomieniu. Ich późniejszy stan jest zachowywany po restarcie. Wyłączenie aktywnego segmentu natychmiast wyłącza Grid Charge i uruchamia pełny reset.

Domyślnie oba sezony nocne mają próg 30 procent i cel 80 procent. Oba sezony dzienne mają próg 75 procent i cel 80 procent. Aktualizacja z wersji 1.0.0 kopiuje dotychczasową wartość nocną do ustawień noc lato i noc zima, a wartość dzienną do ustawień dzień lato i dzień zima.

## Domyślne godziny

- noc: od 22:00 do twardego resetu o 06:55,
- dzień latem: obserwacja od 16:10, twardy reset o 18:55, Prog5 Time 19:00,
- dzień zimą: obserwacja od 13:10, twardy reset o 15:55, Prog5 Time 16:00.

Ładowanie dzienne jest pomijane w soboty, niedziele i polskie dni ustawowo wolne. Sezon letni trwa domyślnie od 1 kwietnia do 30 września. Wszystkie godziny, daty i encje można zmienić w ustawieniach.

## Sposób działania

Gdy SOC spadnie poniżej progu, aplikacja oblicza czas potrzebny do celu i czeka do ostatniego bezpiecznego momentu rozpoczęcia. Model nocny używa 157 minut dla 80 punktów SOC i 15 minut zapasu. Model dzienny używa 201 minut dla 80 punktów SOC oraz korekty końcówki powyżej 98 procent.

Rozpoczęcie segmentu wykonuje kolejno:

1. Ustawienie celu Capacity właściwego programu.
2. Odczyt kontrolny Capacity.
3. Ustawienie `Allow Grid & Gen` właściwego programu.
4. Odczyt kontrolny trybu.
5. Włączenie Grid Charge.
6. Odczyt kontrolny Grid Charge.

Pełny reset wykonuje kolejno:

1. Wyłączenie i potwierdzenie Grid Charge.
2. Ustawienie Capacity Prog1-Prog6 na wartość resetu, domyślnie 20 procent.
3. Ustawienie Charge Prog1-Prog6 na `Allow Gen`.

Brak odczytu kontrolnego jest traktowany jako stan niepewny. Aplikacja nie przechodzi wtedy do kolejnego kroku uruchomienia i próbuje pozostawić Grid Charge wyłączony.

`Prog5 Time` jest odczytywany przy uruchomieniu. Jeżeli wartość jest już zgodna z bieżącym sezonem, aplikacja nie wykonuje zapisu. Kolejne sprawdzenie następuje dopiero po zmianie oczekiwanej wartości sezonowej. Chwilowy stan `unavailable` nie jest traktowany jako inna godzina.

Po rzeczywistym zapisie aplikacja czeka domyślnie do 30 sekund na oczekiwaną wartość i ponawia sam odczyt co 2 sekundy. Nie wysyła ponownie polecenia przy każdej opóźnionej odpowiedzi. Parametry `verify_timeout_seconds` i `verify_poll_seconds` można zmienić w konfiguracji.

## Pierwsze uruchomienie

1. Sprawdź wszystkie identyfikatory encji Deye w ustawieniach.
2. Uruchom aplikację z oboma przełącznikami automatyki wyłączonymi.
3. Sprawdź dziennik oraz sezonową wartość `Prog5 Time`.
4. Włącz jeden segment i obserwuj oryginalne encje Deye.
5. Zweryfikuj na instalacji kolejność zapisu oraz fizyczne zachowanie falownika.

Jeżeli skonfigurowana encja nie istnieje, aplikacja wypisuje w dzienniku pełną listę brakujących identyfikatorów. Wartość należy porównać z identyfikatorem encji widocznym w Home Assistant, a następnie poprawić ją w zakładce Konfiguracja aplikacji.

Testy automatyczne nie potwierdzają fizycznego zapisu przez konkretny firmware falownika.
