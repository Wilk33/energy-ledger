# Porównanie października 2026

Źródła: przekazany przez użytkownika eksport history.csv i ocenzurowana faktura
TAURON z 4 listopada 2026, okres 1-31 października. Nie publikujemy danych osobowych.
Wszystkie kwoty poniżej są brutto.

| Pozycja | Ostatni stan CSV | Faktura |
| --- | ---: | ---: |
| Import rano kWh | 50,8 | 50 |
| Import po południu kWh | 1,5 | 3 |
| Import pozostałe kWh | 214,4 | 217 |
| Import razem kWh | 266,7 | 270 |
| Eksport razem kWh | 181,5 | 176 |
| Niedobór kWh | 121,5 | 130 |
| Koszty zmienne | 82,78 | 88,16 |
| Opłaty stałe | 48,55 | 42,94 |
| Razem | 131,33 | 131,10 |

CSV kończy się 31 października o 22:55:32 UTC (23:55:32 Europe/Warsaw).
Wiersze z 30 września o 22:00 UTC zawierają również stan poprzedniego miesiąca,
po którym następuje wyzerowanie. Przy rekonstrukcji przyrostów należy zacząć
od tego wyzerowania osobno dla każdej encji. Nie sumować stanów narastających.

Potwierdzone błędy:

- katalog doliczał abonament 4,56 zł netto, którego październikowa faktura nie nalicza;
- FIFO pokrywało najstarszy niedobór bez uwzględnienia strefy eksportu;
- w starym pliku stanu nie zapisywano eksportu według stref.

Nowy algorytm rozlicza miesięczny eksport po opuście najpierw w swojej strefie,
a nadwyżkę w pozostałych strefach według malejącej stawki zmiennej dystrybucji.
Źródło zasad: https://www.tauron.pl/dla-domu/obsluga-i-pomoc/strefa-prosumenta
(sekcja bilansowania międzystrefowego, sprawdzona 6 listopada 2026).

Z przyrostów eksportu CSV, sklasyfikowanych według czasu publikacji, wychodzi
42,2 / 3,6 / 135,7 kWh w strefach rano / po południu / pozostałe.
To rekonstrukcja przybliżona: czas publikacji encji może różnić się od czasu pomiaru.
Nowe rozliczenie tych danych daje niedobory 15,66 / 0 / 105,84 kWh,
zmienne 82,22 zł + stałe 42,94 zł = 125,16 zł. Różnica wobec faktury wynosi 5,94 zł.
Nie oznacza to zgodności pomiarów falownika z licznikiem rozliczeniowym.

Faktura rozlicza 15 / 1 / 114 kWh. Wprowadzenie tych ilości oraz pełnych importów
50 / 3 / 217 do testu kalkulacji daje dokładnie 131,10 zł. Nie jest to test
odtwarzający odczyty licznika operatora. Z samych pokazanych ilości eksportu
44 / 3 / 129 pomnożonych przez 0,8 wychodzi 35,2 / 2,4 / 103,2 kWh;
faktura pokazuje kredyt 35 / 2 / 103. Z jednej faktury nie rozstrzygamy ogólnej
reguły zaokrąglania kWh i nie obcinamy precyzji bieżących pomiarów.

Faktura dodatkowo opisuje godzinowe bilansowanie operatora. Przesłany CSV
zawiera wyniki aplikacji, a nie surowe godzinowe odczyty licznika operatora.
Nie pozwala więc ustalić, jaka część różnicy pochodzi z urządzenia pomiarowego,
bilansowania godzinowego, opóźnień aktualizacji albo braków historii.

Aktualizacja zachowuje istniejące rekordy. Eksport strefowy starego miesiąca
jest odtwarzany wyłącznie po uzgodnieniu sumy i końcowego stanu licznika.
Gdy to niemożliwe, jakość danych przyjmuje legacy-zone-estimate do nowego miesiąca.
Nie przeliczamy automatycznie zamkniętych miesięcy bez ich danych źródłowych.

## Rozdzielczość 0,1 kWh i granice stref

Użytkownik potwierdził, że źródłowe liczniki Deye mają rozdzielczość 0,1 kWh
i zliczają całość, bez osobnych liczników strefowych. Przyrost odczytany po granicy
stref może zawierać energię z poprzedniej strefy. To rzeczywiste ograniczenie
przypisania energii, nawet przy poprawnym kalendarzu G13.

Przykład: zmiana 100,0 na 100,1 kWh zarejestrowana chwilę po 13:00 nie dowodzi,
że całe 0,1 kWh przepłynęło po 13:00. Nie dowodzi też równomiernego przepływu
od ostatniej zmiany licznika. Przy małej mocy odstęp pomiędzy zmianami może być
długi. Opóźnienia odczytu mogą dodatkowo łączyć kilka kroków licznika.

Samo przesuwanie przyrostów między strefami zachowuje miesięczny import i eksport.
Nie tłumaczy więc całych różnic 266,7 wobec 270 kWh importu oraz 181,5 wobec
176 kWh eksportu. Nie utożsamiamy rozdzielczości 0,1 kWh z dokładnością pomiarową.
CSV nie obejmuje ostatnich około 4,5 minuty miesiąca, a także nie pozwala
odtworzyć bilansowania godzinowego operatora.

Narzędzie `tools/compare_zone_allocation.py` porównuje dwa warianty na tym samym
CSV: cały przyrost w strefie publikacji oraz równomierny podział czasu pomiędzy
zmianami wartości, tylko dla odstępów do 30 minut przecinających granicę strefy.
Pozostałe przyrosty pozostają w strefie końcowego odczytu. Jest to eksperyment,
nie algorytm zastosowany w aplikacji. Kwoty uwzględniają opłatę mocową z faktury.

| Wartość | Strefa publikacji | Podział czasowy do 30 min | Faktura |
| --- | ---: | ---: | ---: |
| Import rano kWh | 50,80 | 50,14 | 50 |
| Import po południu kWh | 1,50 | 1,50 | 3 |
| Import pozostałe kWh | 214,40 | 215,06 | 217 |
| Eksport rano kWh | 42,20 | 44,61 | 44 |
| Eksport po południu kWh | 3,60 | 3,29 | 3 |
| Eksport pozostałe kWh | 135,70 | 133,59 | 129 |
| Kwota brutto zł | 125,16 | 124,51 | 131,10 |

Podzielono 31 przyrostów o łącznej energii 10,8 kWh. To suma dzielonych
przyrostów, nie ilość energii przesunięta między strefami. Dla 72 odstępów
z różnymi strefami na końcach czas był dłuższy niż 30 minut. Sam wybór limitu
30 minut jest założeniem eksperymentu, nie parametrem licznika ani operatora.

Wniosek: prosty podział czasowy poprawia niektóre ilości strefowe, ale zwiększa
różnicę kwoty do faktury z 5,94 do 6,59 zł. Nie ma podstaw, aby na tej próbce
uznać go za lepszy algorytm produkcyjny. Nie dobieramy przesunięć do oczekiwanej
kwoty faktury.

Do dokładniejszego przydziału potrzebna jest historia surowych liczników z czasem
pomiaru oraz, jeśli dostępna, moc sieci. Można wtedy szacować udział każdej
strefy na podstawie przepływu mocy i normalizować udziały do faktycznego przyrostu
licznika. Import i eksport trzeba traktować oddzielnie. To nadal estymacja;
zgodność z fakturą wymaga również uzgodnienia sum i zasad bilansowania operatora.
