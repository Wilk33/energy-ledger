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
