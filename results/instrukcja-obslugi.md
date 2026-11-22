# Sellart – instrukcja obsługi

Sellart to aplikacja do zarządzania **biletami własności dzieł sztuki** w galerii. Administrator galerii wystawia bilet po zakupie dzieła, klienci mogą bilety między sobą sprzedawać, a na końcu spieniężyć je po aktualnej cenie dzieła. Wszystkie operacje są zapisywane w łańcuchu bloków (blockchainie) przechowywanym przez trzy niezależne węzły.

Napisy w aplikacji są po angielsku – ich tłumaczenia zawiera [słownik pojęć](slownik-pojec.md).

---

## 1. Wymagania

- Windows 10/11, Linux lub macOS
- Python 3.10 lub nowszy
- wolne porty 8001, 8002 i 8003 (na nich działają węzły)

## 2. Instalacja

W katalogu projektu:

```bash
pip install -r requirements.txt
```

## 3. Uruchomienie

| Krok | Polecenie | Co się dzieje |
|---|---|---|
| 1 | `python manage.py reset` | Tworzy czyste środowisko: usuwa dane węzłów i portfele, generuje nowy klucz administratora galerii. Wykonuj tylko wtedy, gdy chcesz zacząć od zera. |
| 2 | `python manage.py cluster` | Uruchamia trzy węzły A, B i C. W systemie Windows każdy otwiera się w osobnym oknie konsoli – **nie zamykaj tych okien**, dopóki pracujesz z systemem. |
| 3 | `python manage.py app` | Otwiera aplikację. |

Przy kolejnym uruchomieniu (bez czyszczenia danych) wystarczą kroki 2 i 3 – węzły wczytają swoje łańcuchy z dysku.

**Zakończenie pracy:** zamknij aplikację, a następnie okna węzłów (albo zatrzymaj węzły przyciskami *Stop* w zakładce *Network & nodes*).

**Powrót do czystego stanu:** zatrzymaj wszystkie węzły i wykonaj ponownie `python manage.py reset`. Polecenie odmówi działania, jeśli któryś węzeł nadal pracuje.

---

## 4. Okno aplikacji

```
┌──────────────────────────────────────────────────────────────────────┐
│ Read state from: [Auto ▾]   Send operations via: [Auto ▾]   Cluster: A: leader | B: follower | C: follower │
├──────────────────────────────────────────────────────────────────────┤
│ Assets │ Operations │ Users & keys │ Security tests │ Network & nodes │ Blockchain │
│                                                                      │
│                       zawartość wybranej zakładki                     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│ Operation results:  SUCCESS  TRANSFER … by Alice -> Bob               │
│ czas │ operacja │ węzeł │ wynik │ komunikat                           │
└──────────────────────────────────────────────────────────────────────┘
```

**Pasek u góry**

- **Read state from** – z którego węzła aplikacja odczytuje dane. *Auto* oznacza pierwszy dostępny węzeł.
- **Send operations via** – do którego węzła aplikacja wysyła operacje. *Auto* oznacza pierwszy dostępny węzeł.
- **Cluster** – stan węzłów: rola (*leader* – lider, *follower* – pozostałe) albo *offline*, gdy węzeł nie działa.

**Panel wyników (na dole)** – każda operacja kończy się jednym z wyników:

| Wynik | Znaczenie | Co zrobić |
|---|---|---|
| `SUCCESS` (zielony) | Operacja została zapisana na stałe. | Nic – gotowe. |
| `REJECTED` (czerwony) | Operacja łamie zasady systemu, np. nie jesteś właścicielem albo bilet jest już spieniężony. Przyczyna jest w kolumnie *Message*. | Popraw dane i spróbuj ponownie. |
| `FAILED` (pomarańczowy) | Operacji nie dało się przetworzyć, np. wybrany węzeł nie działa albo jest odcięty od pozostałych. | Spróbuj ponownie za chwilę albo wyślij przez inny węzeł (*Send operations via*). |

Dane w oknie odświeżają się samoczynnie co 2 sekundy.

---

## 5. Pierwsze kroki: użytkownicy

Zakładka **Users & keys**.

1. Wpisz nazwę w pole *Name* i kliknij **Create user**. Do pokazu możesz od razu kliknąć **Create Alice, Bob and Charlie**.
2. W panelu wyników pojawi się `SUCCESS – REGISTER_USER …`.

Przy tworzeniu użytkownika aplikacja generuje na tym komputerze jego parę kluczy. **Klucz prywatny** trafia tylko do pliku portfela użytkownika (kolumna *Private key stored in*, przycisk **Open wallet folder** otwiera katalog). Węzły otrzymują wyłącznie **klucz publiczny**. Tabela *Users registered on the blockchain* pokazuje, co znają węzły.

Konto **Gallery Admin** (administrator galerii) powstaje automatycznie przy `reset`.

> Nie usuwaj ani nie udostępniaj plików portfela: kto ma plik, ten może podpisywać operacje w imieniu użytkownika; kto go straci, nie odzyska dostępu do swoich biletów.

---

## 6. Operacje na biletach

Zakładka **Operations**. W każdej ramce pole **Acting user (signs)** wskazuje, czyim kluczem prywatnym zostanie podpisana operacja – czyli kto ją wykonuje.

### Wystawienie biletu – issue()

Wykonuje administrator galerii po sprzedaży dzieła.

1. Uzupełnij: *Artwork title* (tytuł), *Original author* (autor), *Accepted by gallery on* (data przyjęcia dzieła), *Price* (cena w PLN), *Owner (buyer)* (nabywca).
2. Kliknij **Issue ownership ticket**.

Nowy bilet ma status `ACTIVE` i pojawia się w zakładce *Assets*. Identyfikator (uuid) nadaje system.

### Sprzedaż / przekazanie – transfer()

1. *Asset* – wybierz bilet z listy (albo wklej jego identyfikator).
2. *Acting user* – aktualny właściciel.
3. *Recipient* – nowy właściciel.
4. Kliknij **Transfer**.

System przyjmie operację tylko wtedy, gdy podpisuje ją aktualny właściciel.

### Spieniężenie – redeem()

1. *Asset* – bilet, *Acting user* – właściciel.
2. Kliknij **Redeem (cash out at the current price)**.

Status zmienia się na `REDEEMED`, a wypłacona kwota (aktualna cena) jest zapisywana w danych biletu. **Spieniężonego biletu nie można już przekazać ani spieniężyć ponownie.**

### Zmiana ceny – Revaluation

Wykonuje administrator galerii (np. po wycenie dzieła).

1. *Asset* – bilet, *New price* – nowa cena.
2. Kliknij **Set new price**.

Cenę można zmieniać tylko dla biletów `ACTIVE`. Kwota wypłacana przy spieniężeniu jest zawsze równa aktualnej cenie.

---

## 7. Przeglądanie biletów i historii

Zakładka **Assets**.

- Tabela u góry zawiera wszystkie bilety: tytuł, autora, właściciela, status, cenę, datę przyjęcia i identyfikator.
- **Kliknij wiersz**, aby zobaczyć poniżej pełny stan biletu (*Current state of the asset*) oraz jego historię (*History*): każdą operację z poprzednim właścicielem (*From*), odbiorcą (*To*), identyfikatorem operacji, numerem bloku i czasem.
- Aby sprawdzić konkretny bilet, wklej jego identyfikator w pole *Asset ID* i kliknij **Show state & history** albo **Read owner** (sam właściciel).

Zakładka **Blockchain** pokazuje surowe bloki zapisane przez wybrany węzeł (wybierz węzeł i kliknij **Load blocks**; kliknięcie wiersza wyświetla pełną treść bloku).

---

## 8. Węzły i sieć

Zakładka **Network & nodes**.

- **Tabela węzłów** – czy węzeł działa (*Online*), jego rola, liczba zatwierdzonych bloków i hash ostatniego bloku. Gdy wszystkie węzły są zsynchronizowane, mają tę samą liczbę bloków i ten sam hash.
- **Start X / Stop X** – uruchamia lub zatrzymuje węzeł. System działa dalej, dopóki pracują co najmniej 2 z 3 węzłów. Ponownie uruchomiony węzeł sam pobiera brakujące bloki.
- **Split network: A | B,C** (i pozostałe warianty) – symuluje awarię sieci, która rozdziela węzły na dwie grupy. Grupa z jednym węzłem odrzuca nowe operacje (`FAILED`), grupa z dwoma działa normalnie. **Heal network** przywraca łączność – węzły samoczynnie uzgadniają jeden wspólny stan.
- **Replication check** – wybierz bilet i kliknij **Read this asset from EVERY node**, aby porównać jego stan na każdym węźle.

Wyłączanie węzłów i dzielenie sieci służą do pokazu odporności systemu; w zwykłej pracy wszystkie węzły powinny działać.

---

## 9. Zakładka Security tests (pokaz zabezpieczeń)

Zakładka służy do demonstracji, jak system broni się przed nieuprawnionymi operacjami. Nie jest potrzebna w codziennej pracy.

**Authorisation and replay**

1. Wybierz bilet, właściciela (*On behalf of*) i odbiorcę.
2. Wybierz rodzaj podpisu: własnym kluczem właściciela, bez podpisu albo kluczem innego użytkownika.
3. **1. Prepare transfer** – przygotowuje operację i pokazuje ją po prawej stronie (dokładnie to, co trafi do węzła).
4. **2. Send** – wysyła ją.
5. **Send the SAME operation again (replay)** – wysyła ponownie dokładnie tę samą podpisaną operację; system ją odrzuci.

Dodatkowo: **Check signature locally** sprawdza podpis bez wysyłania, **Save to file… / Load from file…** zapisują i wczytują przygotowaną operację.

**Conflicting operations** – przygotowuje dwie poprawnie podpisane, ale wykluczające się operacje (ten sam bilet do dwóch różnych osób) i wysyła je jednocześnie przez dwa różne węzły (**Send both at the same time**) albo osobno (**Send #1 only**, **Send #2 only**). System zawsze przyjmie dokładnie jedną z nich.

---

## 10. Weryfikacja bez aplikacji

Stan biletów można sprawdzić niezależnym programem, bez otwierania aplikacji (węzły muszą działać):

```bash
python verifier/verify_chain.py                  # wszystkie bilety, wszystkie węzły
python verifier/verify_chain.py --asset <ID>     # jeden bilet
```

Program pobiera łańcuch z każdego węzła osobno, sprawdza wszystkie podpisy i powiązania bloków, a na końcu informuje, czy wszystkie węzły pokazują tego samego właściciela i status. Łańcuch można też zapisać do pliku (`--export plik.json`) i sprawdzić później bez węzłów (`--file plik.json`).

---

## 11. Rozwiązywanie problemów

| Objaw | Przyczyna i rozwiązanie |
|---|---|
| `Cluster configuration not found` przy starcie | Nie wykonano `python manage.py reset`. Wykonaj je raz przed pierwszym uruchomieniem. |
| `Stop the running nodes first` przy `reset` | Węzły nadal działają. Zatrzymaj je (zamknij okna węzłów) i powtórz. |
| W pasku *Cluster* wszystkie węzły `offline` | Węzły nie zostały uruchomione – wykonaj `python manage.py cluster`. |
| Okno węzła zamyka się od razu | Port 8001–8003 jest zajęty przez inny program albo węzeł już działa. Uruchom węzeł w terminalu poleceniem `python manage.py node A`, aby zobaczyć komunikat błędu. |
| `FAILED – no leader reachable…` / `no majority of nodes reachable…` | Wybrany węzeł nie ma kontaktu z pozostałymi (wyłączone węzły albo podział sieci). Uruchom brakujące węzły lub kliknij **Heal network**, ewentualnie wyślij operację przez inny węzeł. |
| `REJECTED – … is not the current owner` | W polu *Acting user* wybrano osobę, która nie jest właścicielem biletu. |
| `REJECTED – conflict …` | Bilet zmienił się od chwili przygotowania operacji (inna operacja była pierwsza). Odśwież dane i wykonaj operację ponownie. |
| `REJECTED – asset is already REDEEMED` | Bilet został spieniężony – nie można go już przekazać ani spieniężyć. |
| `REJECTED – replay detected` | Ta sama podpisana operacja została już wykonana. Przygotuj nową operację. |
| Listy wyboru są puste | Brak użytkowników lub biletów – utwórz je w zakładkach *Users & keys* i *Operations*. |

---

## 12. Gdzie są dane

| Ścieżka | Zawartość |
|---|---|
| `runtime/cluster.json` | adresy węzłów i klucz publiczny administratora |
| `runtime/node-A/node.db` (oraz `node-B`, `node-C`) | kopia łańcucha bloków danego węzła (SQLite) |
| `runtime/client/wallets/*.json` | portfele użytkowników z kluczami prywatnymi |

Katalog `runtime/` nie jest zapisywany w repozytorium Git. Polecenie `reset` usuwa całą jego zawartość.
