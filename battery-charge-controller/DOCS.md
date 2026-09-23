# Battery Charge Controller

Aplikacja steruje ładowaniem baterii Deye z sieci w dwóch niezależnych segmentach:

- nocnym przez `Prog1 Capacity` i `Prog1 Charge`,
- dziennym przez `Prog4 Capacity` i `Prog4 Charge`.

Nie ma Ingressu. Cała konfiguracja znajduje się w ustawieniach aplikacji, a bieżące nastawy są dostępne przez MQTT Discovery.

## Encje MQTT

Aplikacja tworzy dokładnie:

- cztery suwaki: próg i cel SOC dla nocy oraz próg i cel SOC dla dnia,
- dwa przełączniki: ładowanie nocne i ładowanie dzienne,
- sensor czasu do planowanego startu,
- sensor czasu do twardego końca okna.

Nie tworzy kopii bieżącego SOC, sezonu, decyzji ani stanów zapisów. Te informacje są dostępne w oryginalnych encjach Deye i dzienniku aplikacji.

Oba przełączniki są wyłączone przy pierwszym uruchomieniu. Ich późniejszy stan jest zachowywany po restarcie. Wyłączenie aktywnego segmentu natychmiast wyłącza Grid Charge i uruchamia pełny reset.

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

## Pierwsze uruchomienie

1. Sprawdź wszystkie identyfikatory encji Deye w ustawieniach.
2. Uruchom aplikację z oboma przełącznikami automatyki wyłączonymi.
3. Sprawdź dziennik oraz sezonową wartość `Prog5 Time`.
4. Włącz jeden segment i obserwuj oryginalne encje Deye.
5. Zweryfikuj na instalacji kolejność zapisu oraz fizyczne zachowanie falownika.

Testy automatyczne nie potwierdzają fizycznego zapisu przez konkretny firmware falownika.
