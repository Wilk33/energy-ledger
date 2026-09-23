# Battery Charge Controller - specyfikacja projektu

Data: 2026-09-23

Status: projekt zatwierdzony w rozmowie, oczekuje na kontrolę zapisanej specyfikacji

## 1. Cel

Do repozytorium `energy-ledger` zostanie dodana druga, niezależna aplikacja Home Assistant o nazwie `Battery Charge Controller`. Aplikacja ma zastąpić dwa przepływy Node-RED odpowiedzialne za ładowanie akumulatora Deye z sieci w taryfie TAURON G13:

- ładowanie nocne,
- ładowanie dzienne przed popołudniową strefą szczytową.

Aplikacja ma sama obliczać najpóźniejszy bezpieczny moment rozpoczęcia ładowania, ustawiać odpowiednie programy falownika, kontrolować wynik zapisu i kończyć ładowanie przed granicą strefy taryfowej. Użytkownik steruje progami i celami SOC z czterech suwaków MQTT oraz może niezależnie wyłączyć automatykę dzienną i nocną dwoma przełącznikami MQTT.

Projekt nie jest częścią obliczeń magazynu wirtualnego. Obie aplikacje pozostają osobnymi dodatkami Home Assistant i współdzielą jedynie wzorce pakowania, komunikacji z Home Assistant oraz MQTT Discovery.

## 2. Zakres wydania

Pierwsze wydanie ma udostępnić dokładnie osiem nowych encji MQTT Discovery:

1. `number` - próg SOC ładowania nocnego.
2. `number` - cel SOC ładowania nocnego.
3. `number` - próg SOC ładowania dziennego.
4. `number` - cel SOC ładowania dziennego.
5. `switch` - włączenie automatyki ładowania nocnego.
6. `switch` - włączenie automatyki ładowania dziennego.
7. `sensor` - czas do planowanego rozpoczęcia ładowania.
8. `sensor` - czas do twardego zakończenia bieżącego okna ładowania.

Aplikacja nie publikuje kopii bieżącego SOC, progu, celu, sezonu, decyzji ani wyniku zapisu. Bieżący SOC pozostaje dostępny w oryginalnej encji falownika, a progi i cele są już widoczne na suwakach. Szczegóły decyzji, prób zapisu i kontroli wyniku trafiają do logu dodatku.

Poza zakresem pierwszego wydania pozostają:

- panel Ingress,
- automatyczne modyfikowanie cen lub danych Energy Ledger,
- uczenie modelu czasu ładowania na podstawie historii,
- dodatkowe encje diagnostyczne,
- sterowanie innymi parametrami falownika niż wskazane w tej specyfikacji.

## 3. Forma dodatku i struktura repozytorium

Nowa aplikacja będzie osobnym dodatkiem w tym samym repozytorium:

- katalog źródłowy Pythona: `battery_charge_controller/`,
- katalog dodatku Home Assistant: `battery-charge-controller/`,
- testy: istniejący katalog `tests/`, z plikami nazwanymi `test_charge_*`,
- narzędzie synchronizacji źródła do `rootfs`: rozbudowane istniejące `tools/sync_runtime.py` albo małe narzędzie o takim samym kontrakcie,
- metadane repozytorium: główny `repository.yaml` pozostaje wspólny dla obu dodatków.

Dodatek nie ma Ingress. Korzysta z:

- Home Assistant REST API do odczytów i wywołań usług,
- Home Assistant WebSocket API do szybkiego reagowania na zmiany obserwowanych encji,
- usługi MQTT Supervisora do MQTT Discovery, komend suwaków i przełączników oraz publikacji ich stanów,
- lokalnego pliku JSON w `/data` do trwałego przechowywania wartości czterech suwaków i dwóch przełączników.

Cała logika wykonawcza działa w jednym procesie asynchronicznym. Jedna blokada wykonawcza serializuje ładowanie nocne, ładowanie dzienne, zmianę `Prog5 Time` i reset. Nie mogą działać dwie sekwencje zapisu równocześnie.

## 4. Encje wejściowe i sterowane

Wszystkie identyfikatory encji są opcjami dodatku. Wartości domyślne odpowiadają instalacji przekazanej przez użytkownika.

### 4.1. Odczyt SOC

- `sensor.deye_deye_10kw_battery_soc`

Stan musi dać się przeliczyć na liczbę od 0 do 100. Stan `unknown`, `unavailable`, pusty, nieliczbowy albo spoza zakresu blokuje rozpoczęcie ładowania. Jeżeli taki stan utrzymuje się podczas aktywnego ładowania dłużej niż konfigurowalny limit świeżości, aplikacja wykonuje pełny reset.

### 4.2. Pojemności programów

- `number.deye_deye_10kw_prog1_capacity`
- `number.deye_deye_10kw_prog2_capacity`
- `number.deye_deye_10kw_prog3_capacity`
- `number.deye_deye_10kw_prog4_capacity`
- `number.deye_deye_10kw_prog5_capacity`
- `number.deye_deye_10kw_prog6_capacity`

Ładowanie nocne zapisuje wyłącznie `Prog1 Capacity`. Ładowanie dzienne zapisuje wyłącznie `Prog4 Capacity`. Pełny reset zapisuje wartość resetu do wszystkich sześciu encji.

### 4.3. Tryby ładowania programów

- `select.deye_deye_10kw_prog1_charge`
- `select.deye_deye_10kw_prog2_charge`
- `select.deye_deye_10kw_prog3_charge`
- `select.deye_deye_10kw_prog4_charge`
- `select.deye_deye_10kw_prog5_charge`
- `select.deye_deye_10kw_prog6_charge`

Ładowanie nocne zapisuje wyłącznie `Prog1 Charge`. Ładowanie dzienne zapisuje wyłącznie `Prog4 Charge`. Pełny reset zapisuje tryb resetu do wszystkich sześciu encji.

Domyślne opcje select:

- tryb aktywnego ładowania: `Allow Grid & Gen`,
- tryb po resecie: `Allow Gen`.

Obie wartości są konfigurowalne, ponieważ dokładne nazwy opcji pochodzą z integracji falownika.

### 4.4. Globalne zezwolenie na ładowanie z sieci

- `switch.deye_deye_10kw_grid_charge_enabled`

Przełącznik jest włączany jako ostatni krok sekwencji rozpoczęcia ładowania i wyłączany jako pierwszy krok resetu.

### 4.5. Czas `Prog5`

- `select.deye_deye_10kw_prog5_time`

Wartość zależy od sezonu:

- lato: `19:00`,
- zima: `16:00`.

Identyfikator encji i obie wartości są konfigurowalne. Aplikacja sprawdza i koryguje wartość przy każdym uruchomieniu oraz po przejściu granicy sezonu. Dzięki temu zatrzymanie dodatku dokładnie 1 kwietnia albo 1 października nie powoduje pominięcia zmiany.

## 5. Sezony, kalendarz i czas

Wszystkie obliczenia używają jawnej strefy `Europe/Warsaw`, włącznie ze zmianą czasu letniego i zimowego.

Domyślne granice sezonów TAURON G13:

- lato: od 1 kwietnia do 30 września,
- zima: od 1 października do 31 marca.

Daty graniczne są opcjami dodatku zapisanymi jako miesiąc i dzień. Zmiana sezonu następuje według lokalnej daty, niezależnie od restartu procesu.

Ładowanie dzienne jest pomijane w soboty, niedziele i polskie dni ustawowo wolne od pracy, ponieważ w tych dniach G13 nie wprowadza popołudniowej strefy szczytowej. Kalendarz świąt jest obliczany lokalnie, bez pobierania danych z sieci w czasie działania. Musi obejmować święta stałe, święta ruchome oraz 24 grudnia obowiązujący jako dzień ustawowo wolny od 2025 roku.

Przejście czasu letniego i zimowego nie może utworzyć podwójnej sekwencji zapisu. Identyfikator wykonania składa się z lokalnej daty, segmentu i zaplanowanego końca. Zakończone wykonanie tego samego segmentu tego samego dnia nie jest uruchamiane ponownie.

## 6. Ustawienia MQTT

### 6.1. Suwaki

Zakres wszystkich suwaków wynosi od 20 do 100 procent, krok 1 procent. Dodatkowo:

- nocny próg musi być mniejszy lub równy nocnemu celowi,
- dzienny próg musi być mniejszy lub równy dziennemu celowi.

Niepoprawna para blokuje tylko dany segment i jest opisana w logu. Aplikacja nie poprawia samoczynnie wartości użytkownika przez obcinanie progu lub celu.

Domyślne wartości pierwszego uruchomienia:

- nocny próg: 30 procent,
- nocny cel: 80 procent,
- dzienny próg: 75 procent,
- dzienny cel: 80 procent.

Wartości są wspólne dla obu sezonów. Sezon zmienia harmonogram dzienny i `Prog5 Time`, a nie tworzy kolejnych suwaków.

### 6.2. Przełączniki

Oba przełączniki są domyślnie wyłączone przy pierwszej instalacji, aby dodatek nie rozpoczął zapisu do falownika bez świadomego włączenia przez użytkownika. Po pierwszej zmianie ich stany są trwałe i wracają po restarcie.

Znaczenie stanu `OFF`:

- przed oknem blokuje rozpoczęcie danego segmentu,
- w trakcie aktywnego ładowania natychmiast rozpoczyna pełny reset,
- nie blokuje synchronizacji sezonowej `Prog5 Time`.

Wyłączenie przełącznika dziennego nie zmienia ustawienia przełącznika nocnego i odwrotnie.

### 6.3. Sensory czasu

Oba sensory mają `device_class: duration`, jednostkę sekund i aktualizują się co najmniej raz na minutę oraz po każdej zmianie decyzji.

`Czas do rozpoczęcia ładowania`:

- pokazuje liczbę sekund do obliczonego momentu startu segmentu, który wymaga ładowania,
- ma wartość `0` podczas aktywnego ładowania,
- ma stan `unavailable`, gdy ładowanie nie jest potrzebne, segment jest wyłączony, dzień jest wolny, dane są niepoprawne albo nie istnieje aktualny plan.

`Czas do zakończenia ładowania`:

- pokazuje liczbę sekund do twardego końca aktywnego lub zaplanowanego okna,
- ma wartość `0` w chwili rozpoczęcia resetu na końcu okna,
- ma stan `unavailable` poza właściwym oknem i gdy nie istnieje aktywny plan.

Sensory są wspólne dla obu segmentów. Jeżeli wyjątkowo oba segmenty mają plan, aplikacja pokazuje najbliższy czasowo segment. Nakładanie okien jest odrzucane podczas walidacji konfiguracji.

## 7. Algorytm ładowania nocnego

Domyślne parametry:

- początek okna: `22:00`,
- twardy koniec i reset: `06:55` następnego dnia,
- pełne ładowanie zakresu 80 punktów SOC: 157 minut,
- czas na 1 punkt SOC: `157/80` minuty,
- zapas bezpieczeństwa: 15 minut,
- odstęp ponownej oceny: 5 minut.

Wartości godzin, czasu pełnego ładowania, zakresu referencyjnego, zapasu oraz odstępu oceny są konfigurowalne.

Przebieg:

1. Po wejściu w okno aplikacja odczytuje przełącznik segmentu, SOC, próg i cel.
2. Gdy SOC jest równy progowi lub wyższy, aplikacja obserwuje stan i nie zapisuje ustawień ładowania.
3. Gdy SOC jest niższy od progu, oblicza brakujące punkty do celu.
4. Szacowany czas wynosi `brakujace_punkty * pelny_czas / zakres_referencyjny`.
5. Najpóźniejszy start wynosi `twardy_koniec - szacowany_czas - zapas`.
6. Po osiągnięciu najpóźniejszego startu wykonywana jest sekwencja ładowania nocnego.
7. O 06:55 rozpoczyna się pełny reset niezależnie od osiągniętego SOC.
8. Jeżeli SOC osiągnie cel wcześniej, aplikacja może zakończyć ładowanie pełnym resetem, nie czekając do 06:55.

Okno przechodzi przez północ i jest traktowane jako jedno wykonanie przypisane do daty jego zakończenia.

## 8. Algorytm ładowania dziennego

Ładowanie dzienne działa tylko w dni robocze niebędące dniami ustawowo wolnymi.

Domyślny harmonogram letni:

- początek obserwacji: `16:10`,
- twardy koniec ładowania i rozpoczęcie resetu: `18:55`,
- `Prog5 Time`: `19:00`.

Domyślny harmonogram zimowy:

- początek obserwacji: `13:10`,
- twardy koniec ładowania i rozpoczęcie resetu: `15:55`,
- `Prog5 Time`: `16:00`.

Pięć minut między twardym końcem ładowania a początkiem popołudniowej strefy szczytowej jest stałym marginesem operacyjnym wynikającym z przekazanych wymagań. Wszystkie godziny pozostają konfigurowalne, ale walidacja wymaga, aby twardy koniec był wcześniejszy od czasu `Prog5`.

Parametry modelu czasu:

- pełne ładowanie zakresu 80 punktów SOC: 201 minut,
- czas na 1 punkt SOC: `201/80` minuty,
- zapas bezpieczeństwa: 0 minut,
- odstęp ponownej oceny: 5 minut.

Korekta końcówki ładowania:

- do 98 procent: 0 dodatkowych minut,
- od 98 do 99 procent: liniowo od 0 do 0,8 minuty,
- od 99 do 100 procent: liniowo od 0,8 do 6,5 minuty,
- powyżej 100 procent: wartość jest odrzucana przez walidację.

Przebieg odpowiada segmentowi nocnemu, ale szacowany czas uwzględnia różnicę korekty końcówki pomiędzy bieżącym SOC a celem. Po osiągnięciu najpóźniejszego startu aplikacja uruchamia ładowanie przez `Prog4`. O 18:55 latem albo 15:55 zimą zawsze rozpoczyna pełny reset. Osiągnięcie celu wcześniej również może zakończyć ładowanie pełnym resetem.

## 9. Sekwencje zapisu i kontrola wyniku

Każdy krok wywołuje usługę Home Assistant, czeka konfigurowalny czas na propagację i odczytuje stan encji. Następny krok jest wykonywany dopiero po potwierdzeniu poprzedniego.

### 9.1. Rozpoczęcie ładowania nocnego

1. Ustaw `Prog1 Capacity` na nocny cel SOC.
2. Potwierdź odczytem wartość `Prog1 Capacity`.
3. Ustaw `Prog1 Charge` na `Allow Grid & Gen`.
4. Potwierdź odczytem wartość `Prog1 Charge`.
5. Włącz `Grid Charge Enabled`.
6. Potwierdź odczytem stan `ON`.

### 9.2. Rozpoczęcie ładowania dziennego

1. Ustaw `Prog4 Capacity` na dzienny cel SOC.
2. Potwierdź odczytem wartość `Prog4 Capacity`.
3. Ustaw `Prog4 Charge` na `Allow Grid & Gen`.
4. Potwierdź odczytem wartość `Prog4 Charge`.
5. Włącz `Grid Charge Enabled`.
6. Potwierdź odczytem stan `ON`.

### 9.3. Pełny reset

1. Wyłącz `Grid Charge Enabled`.
2. Potwierdź odczytem stan `OFF`.
3. Ustaw kolejno `Prog1 Capacity` do `Prog6 Capacity` na domyślnie 20 procent i potwierdź każdy zapis.
4. Ustaw kolejno `Prog1 Charge` do `Prog6 Charge` na `Allow Gen` i potwierdź każdy zapis.
5. Zapisz w stanie lokalnym wynik resetu oraz czas jego ukończenia.

Pełny reset jest używany:

- na twardym końcu aktywnego okna,
- po osiągnięciu celu przez aktywne ładowanie,
- po wyłączeniu odpowiedniego przełącznika podczas ładowania,
- po utracie prawidłowego SOC podczas ładowania ponad limit świeżości,
- po błędzie sekwencji rozpoczęcia,
- przy uruchomieniu dodatku poza dozwolonym oknem, jeżeli odczyty wskazują aktywne ładowanie z sieci lub niestandardowe ustawienia kontrolowanych programów.

Nieudany krok rozpoczęcia nigdy nie prowadzi do włączenia `Grid Charge`. Jeżeli błąd wystąpi po jego włączeniu, aplikacja natychmiast przechodzi do resetu. Po nieudanym potwierdzeniu zapisu można ponowić ustawienie wyłącznie wtedy, gdy odczyt jednoznacznie pokazuje wartość inną od oczekiwanej. Brak odczytu jest stanem niepewnym i powoduje próbę wyłączenia `Grid Charge`, zakończenie sekwencji oraz błąd w logu.

Domyślnie dopuszczalne są dwie próby idempotentnego ustawienia przy potwierdzonej niezgodności. Liczba prób i opóźnienie kontroli są konfigurowalne.

## 10. Stan po restarcie i odzyskiwanie

Przy uruchomieniu aplikacja wykonuje kolejno:

1. Walidację kompletności konfiguracji.
2. Wczytanie trwałego stanu czterech suwaków i dwóch przełączników.
3. Publikację dokładnie ośmiu konfiguracji MQTT Discovery i ich bieżących stanów.
4. Połączenie z Home Assistant i sprawdzenie wszystkich encji wejściowych.
5. Synchronizację `Prog5 Time` z lokalną datą.
6. Odczyt rzeczywistego stanu `Grid Charge`, `Prog1`, `Prog4` i pozostałych encji resetowanych.
7. Uzgodnienie stanu:
   - poza dozwolonym oknem aktywne ładowanie powoduje pełny reset,
   - w dozwolonym oknie aplikacja przelicza decyzję od początku,
   - aktywne ustawienia zgodne z prawidłowym bieżącym planem mogą być kontynuowane,
   - niejednoznaczny lub częściowy stan powoduje wyłączenie `Grid Charge` i pełny reset.
8. Uruchomienie subskrypcji zmian i zegara oceny.

Stan `charging` nie jest przywracany wyłącznie na podstawie pliku lokalnego. Rzeczywiste encje Home Assistant są źródłem prawdy po restarcie.

## 11. Model wykonawczy

Sterownik ma stany wewnętrzne:

- `STARTING`,
- `IDLE`,
- `WAITING_NIGHT`,
- `WAITING_DAY`,
- `CHARGING_NIGHT`,
- `CHARGING_DAY`,
- `RESETTING`,
- `FAULT`.

Zmiana SOC, suwaka, przełącznika, daty, sezonu albo stanu kontrolowanej encji wyzwala ponowną ocenę. Dodatkowy zegar uruchamia ocenę co domyślnie 5 minut i dokładnie na granicach startu oraz końca. Każde zdarzenie trafia do jednej kolejki, a wcześniejsze nieaktualne żądania oceny są łączone.

Priorytet działań:

1. Pełny reset wymagany ze względów bezpieczeństwa.
2. Twardy koniec okna.
3. Wyłączenie przełącznika.
4. Synchronizacja `Prog5 Time`.
5. Kontynuacja lub rozpoczęcie ładowania.
6. Obserwacja bez zapisu.

Ładowanie dzienne i nocne nie mogą działać równocześnie. Walidacja konfiguracji odrzuca nachodzące okna. Gdy mimo zmiany czasu lub ręcznej zmiany encji pojawi się konflikt, reset ma pierwszeństwo.

## 12. Konfiguracja dodatku

Konfiguracja obejmuje:

- wszystkie 15 identyfikatorów encji Deye wymienionych w sekcji 4,
- strefę czasową,
- początek i koniec sezonu letniego,
- nocny początek i twardy koniec,
- letni i zimowy początek obserwacji dziennej,
- letni i zimowy twardy koniec dzienny,
- letnią i zimową wartość `Prog5 Time`,
- model czasu ładowania nocnego,
- model czasu ładowania dziennego i parametry korekty końcówki,
- zapasy bezpieczeństwa,
- odstęp ponownej oceny,
- limit świeżości SOC,
- wartość pojemności resetu,
- aktywną i resetową opcję trybu ładowania,
- czas oczekiwania na odczyt kontrolny i liczbę prób przy potwierdzonej niezgodności,
- bazowy temat MQTT, prefiks Discovery, nazwę urządzenia i poziom logowania.

Walidacja przy starcie kończy proces czytelnym błędem przed jakimkolwiek zapisem do Home Assistant, jeśli:

- brakuje wymaganej encji,
- godzina ma niepoprawny format,
- koniec nie jest późniejszy od początku w logice danego okna,
- dzienny twardy koniec nie poprzedza `Prog5 Time`,
- okna dzienne i nocne nachodzą na siebie,
- zakres lub czas referencyjny jest niedodatni,
- wartość resetu jest poza zakresem 0-100,
- temat MQTT jest pusty.

## 13. Logowanie i błędy

Log w formacie czytelnym dla użytkownika zawiera:

- segment i bieżący stan sterownika,
- powód decyzji,
- lokalny czas i sezon,
- odczytany SOC oraz użyty próg i cel,
- szacowany czas, najpóźniejszy start i twardy koniec,
- każdy zamiar zapisu bez sekretów i tokenów,
- wynik usługi Home Assistant i wynik odczytu kontrolnego,
- przyczynę resetu,
- rozbieżność konfiguracji lub nieosiągalną encję.

Powtarzające się komunikaty obserwacyjne są ograniczane, aby log nie był zasypywany co kilka sekund. Błędy i zmiany decyzji są logowane natychmiast.

## 14. Testy akceptacyjne

Implementacja ma powstać testami jednostkowymi i integracyjnymi bez wykonywania rzeczywistych zapisów do falownika podczas CI.

Wymagane przypadki:

- wybór lata i zimy na datach granicznych,
- prawidłowe zachowanie podczas zmiany czasu Europe/Warsaw,
- pominięcie soboty, niedzieli oraz każdego polskiego dnia ustawowo wolnego,
- walidacja czterech suwaków i relacji próg-cel,
- dokładne obliczenie najpóźniejszego startu nocnego,
- dokładne obliczenie najpóźniejszego startu dziennego z korektą powyżej 98 i 99 procent,
- reset nocny dokładnie o 06:55,
- reset dzienny dokładnie o 18:55 latem i 15:55 zimą,
- brak startu po wyłączeniu odpowiedniego przełącznika,
- natychmiastowy reset po wyłączeniu przełącznika w trakcie ładowania,
- zapis nocny wyłącznie do `Prog1`,
- zapis dzienny wyłącznie do `Prog4`,
- reset wszystkich sześciu pojemności i wszystkich sześciu trybów,
- wymagana kolejność zapisów, odczytów kontrolnych i włączenia Grid Charge,
- brak włączenia Grid Charge po błędzie wcześniejszego kroku,
- zachowanie po braku SOC i po przekroczeniu limitu świeżości,
- synchronizacja `Prog5 Time` na granicy sezonu i przy starcie po pominiętej granicy,
- bezpieczne odzyskanie po restarcie w każdym stanie częściowym,
- dokładnie osiem encji MQTT Discovery bez kopii SOC i diagnostyki,
- trwałość czterech suwaków i dwóch przełączników,
- zgodność skopiowanego kodu w `rootfs` ze źródłem kanonicznym,
- poprawność `config.yaml`, obrazu i skryptu startowego dodatku,
- pełny istniejący zestaw testów Energy Ledger bez regresji.

Testy Home Assistant i MQTT używają atrap rejestrujących wywołania, kolejność, dane oraz symulowane stany po zapisie. Testy nie są dowodem fizycznego wykonania zapisu przez konkretny falownik lub jego firmware. Pierwsze uruchomienie na instalacji wymaga obserwacji oryginalnych encji Deye i logu dodatku.

## 15. Kryteria ukończenia

Wydanie jest gotowe, gdy:

- oba dodatki są widoczne w repozytorium Home Assistant,
- nowy dodatek uruchamia się na `aarch64` i `amd64`,
- publikuje dokładnie osiem uzgodnionych encji,
- zachowuje ustawienia po restarcie,
- poprawnie wybiera sezon i dzień taryfowy,
- rozpoczyna każdy segment w wyliczonym czasie,
- nigdy nie przekracza twardych końców 06:55, 18:55 i 15:55,
- kontroluje każdy zapis odczytem,
- pełny reset obejmuje wszystkie sześć programów i Grid Charge,
- awaria lub stan niepewny pozostawia Grid Charge wyłączony,
- wszystkie testy automatyczne przechodzą,
- dokumentacja opisuje instalację, konfigurację, encje, zachowanie przełączników, testowe uruchomienie i bezpieczny powrót do ustawień początkowych.

## 16. Źródła projektu

Projekt korzysta z następujących rzeczywistych źródeł:

- przekazane przez użytkownika funkcje Node-RED `M2 policz ładowanie nocne` i `M6 policz ładowanie dzienne`, w tym modele 157/80 i 201/80 minut na punkt SOC oraz korekta końcówki ładowania,
- przekazane przez użytkownika zrzuty przepływów Node-RED, które potwierdzają `Prog1` dla ładowania nocnego, `Prog4` dla dziennego oraz reset sześciu programów,
- przekazane przez użytkownika identyfikatory encji Deye i wymaganie zmiany `Prog5 Time`,
- [Taryfa TAURON Dystrybucja na rok 2026](https://www.tauron-dystrybucja.pl/-/media/offer-documents/dystrybucja/aktualna-taryfa/taryfa-tauron-dystrybucja-2026_ocr.ashx) - okresy sezonowe G13, godziny popołudniowego szczytu oraz traktowanie sobót, niedziel i dni ustawowo wolnych,
- istniejący kod i pakowanie dodatku `Energy Ledger` w tym repozytorium - wzorzec komunikacji z Supervisorem, Home Assistant i MQTT.

