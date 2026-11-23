# Sellart – instrukcja obsługi

Sellart to aplikacja do zarządzania **biletami własności dzieł sztuki** w galerii. Administrator galerii wystawia bilet po zakupie dzieła, klienci mogą bilety między sobą sprzedawać, a na końcu spieniężyć je po aktualnej cenie dzieła. Wszystkie operacje są zapisywane w łańcuchu bloków (blockchainie) przechowywanym przez trzy niezależne węzły.

W systemie są dwa rodzaje kont:

| Konto | Kto je zakłada | Co może |
|---|---|---|
| **Klient** (np. Alice, Bob, Charlie) | sam klient – rejestracja w oknie logowania | przeglądać swoje bilety i wszystkie bilety galerii, przekazywać i spieniężać własne bilety |
| **Gallery Admin** (administrator galerii) | tworzone poleceniem `reset` | wystawiać nowe bilety, zmieniać ceny, przeglądać klientów, nadzorować węzły i łańcuch bloków |

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
| 1 | `python manage.py reset` | Tworzy czyste środowisko: usuwa dane węzłów i wszystkie konta, tworzy konto **Gallery Admin**. Program poprosi dwukrotnie o **hasło administratora** – zapamiętaj je. Wykonuj tylko wtedy, gdy chcesz zacząć od zera. |
| 2 | `python manage.py cluster` | Uruchamia trzy węzły A, B i C. W systemie Windows każdy otwiera się w osobnym oknie konsoli – **nie zamykaj tych okien**, dopóki pracujesz z systemem. |
| 3 | `python manage.py app` | Otwiera okno logowania aplikacji. |

Przy kolejnym uruchomieniu (bez czyszczenia danych) wystarczą kroki 2 i 3 – węzły wczytają swoje łańcuchy z dysku, a konta pozostają.

**Zakończenie pracy:** wyloguj się (zamknij okna użytkowników), zamknij okno logowania, a następnie okna węzłów.

**Powrót do czystego stanu:** zatrzymaj wszystkie węzły i wykonaj ponownie `python manage.py reset`. Polecenie odmówi działania, jeśli któryś węzeł nadal pracuje.

---

## 4. Okno logowania i rejestracja

Po uruchomieniu aplikacji pojawia się okno **Sellart - sign in**.

### Rejestracja nowego klienta

1. W ramce **New client account** wpisz nazwę użytkownika (*User name*), hasło (*Password*, co najmniej 4 znaki) i powtórz je (*Repeat password*).
2. Kliknij **Register and sign in**.

Aplikacja generuje na tym komputerze parę kluczy klienta. **Klucz prywatny** zapisuje w pliku portfela, **zaszyfrowany hasłem**. Do węzłów trafia wyłącznie **klucz publiczny** i nazwa (operacja `REGISTER_USER`). Po udanej rejestracji od razu otwiera się okno klienta. Jeśli nazwa jest już zajęta albo węzły nie działają, rejestracja zostaje odrzucona i można spróbować ponownie.

### Logowanie

1. W ramce **Sign in** wybierz konto (*Account*) i wpisz hasło.
2. Kliknij **Sign in** (albo naciśnij Enter).

Konto administratora jest oznaczone na liście jako *(gallery administrator)*.

### Kilka osób naraz

Każde zalogowanie otwiera **osobne okno** danego użytkownika, a okno logowania pozostaje otwarte. Dzięki temu na jednym komputerze można prowadzić pokaz z oknami Alice, Boba, Charliego i administratora jednocześnie. W normalnym użyciu każda osoba uruchamia aplikację na swoim komputerze, ze swoim portfelem.

> **Hasła nie da się odzyskać** – klucz prywatny jest nim zaszyfrowany. Nie usuwaj i nie udostępniaj plików portfela: utrata pliku lub hasła oznacza utratę dostępu do biletów.

---

## 5. Wspólne elementy okna użytkownika

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Signed in as Alice (client) │ Read state from: [Auto ▾] │ Send operations via: [Auto ▾] │ Cluster: A: leader | B: follower | C: follower │ [Sign out] │
├─────────────────────────────────────────────────────────────────────────────────┤
│ zakładki (inne dla klienta, inne dla administratora)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Operation results:  SUCCESS  TRANSFER … by Alice -> Bob                           │
│ czas │ operacja │ węzeł │ wynik │ komunikat                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Pasek u góry**

- **Signed in as** – kto jest zalogowany w tym oknie (i początek jego klucza publicznego).
- **Read state from** – z którego węzła okno odczytuje dane. *Auto* oznacza pierwszy dostępny węzeł.
- **Send operations via** – do którego węzła okno wysyła operacje. *Auto* oznacza pierwszy dostępny węzeł.
- **Cluster** – stan węzłów: rola (*leader* – lider, *follower* – pozostałe) albo *offline*, gdy węzeł nie działa.
- **Sign out** – wylogowanie i zamknięcie okna (odszyfrowany klucz prywatny zostaje usunięty z pamięci).

**Panel wyników (na dole)** – każda operacja kończy się jednym z wyników:

| Wynik | Znaczenie | Co zrobić |
|---|---|---|
| `SUCCESS` (zielony) | Operacja została zapisana na stałe. | Nic – gotowe. |
| `REJECTED` (czerwony) | Operacja łamie zasady systemu, np. nie jesteś właścicielem albo bilet jest już spieniężony. Przyczyna jest w kolumnie *Message*. | Popraw dane i spróbuj ponownie. |
| `FAILED` (pomarańczowy) | Operacji nie dało się przetworzyć, np. wybrany węzeł nie działa albo jest odcięty od pozostałych. | Spróbuj ponownie za chwilę albo wyślij przez inny węzeł (*Send operations via*). |

Dane w oknie odświeżają się samoczynnie co 2 sekundy.

---

## 6. Okno klienta

### Zakładka My assets – moje bilety

- **Tickets you own** – tabela biletów zalogowanego klienta (aktywnych i spieniężonych) z podsumowaniem: liczba aktywnych biletów i ich łączna aktualna wartość.
- **Kliknięcie wiersza** pokazuje poniżej pełny stan biletu (*Current state of the asset*) i jego historię (*History*), a także wybiera ten bilet w formularzach po prawej.

**Przekazanie / sprzedaż – transfer()**

1. *Asset* – wybierz swój bilet (lista zawiera Twoje aktywne bilety; można też wkleić identyfikator dowolnego biletu).
2. *Recipient* – nowy właściciel.
3. Kliknij **Transfer**.

Operacja jest podpisywana Twoim kluczem prywatnym. Węzły przyjmą ją tylko wtedy, gdy jesteś aktualnym właścicielem biletu.

**Spieniężenie – redeem()**

1. *Asset* – wybierz swój bilet.
2. Kliknij **Redeem (cash out at the current price)**.

Status zmienia się na `REDEEMED`, a wypłacona kwota (aktualna cena dzieła) jest zapisywana w danych biletu. **Spieniężonego biletu nie można już przekazać ani spieniężyć ponownie**; nadal widnieje on jako Twój.

### Zakładka Browse assets – wszystkie bilety

Łańcuch bloków jest jawny, więc każdy może sprawdzić stan dowolnego biletu.

- Tabela zawiera wszystkie bilety galerii: tytuł, autora, właściciela, status, cenę, datę przyjęcia i identyfikator.
- **Kliknij wiersz**, aby zobaczyć stan i historię biletu.
- Aby sprawdzić konkretny bilet, wklej identyfikator w pole *Asset ID* i kliknij **Show state & history** albo **Read owner** (sam właściciel).

### Zakładka My account – moje konto

Pokazuje nazwę użytkownika, klucz publiczny (znany węzłom), **miejsce przechowywania klucza prywatnego** (plik portfela po stronie użytkownika), sposób jego ochrony (szyfrowanie hasłem) oraz to, czy konto jest zarejestrowane w blockchainie. Przycisk **Open wallet folder** otwiera katalog z portfelem.

### Zakładka Security tests – pokaz zabezpieczeń

Służy do demonstracji, jak system broni się przed nieuprawnionymi operacjami. Nie jest potrzebna w codziennej pracy.

**Authorisation and replay**

1. *Asset (any ID)* – dowolny bilet.
2. *In the name of (payload.signer)* – w czyim imieniu ma być operacja (domyślnie: Ty).
3. *Recipient* – odbiorca.
4. *Signature* – **sign with MY private key** (Twoim kluczem) albo **no signature** (bez podpisu).
5. **1. Prepare transfer** – przygotowuje operację i pokazuje ją po prawej stronie (dokładnie to, co trafi do węzła).
6. **2. Send** – wysyła ją.
7. **Send the SAME operation again (replay)** – wysyła ponownie dokładnie tę samą podpisaną operację; system ją odrzuci.

Przykład: zalogowany Bob przygotowuje transfer biletu Alice „w imieniu Alice”. Bez podpisu → `REJECTED – missing signature`; z podpisem Boba → `REJECTED – invalid signature`. Tylko Alice, podpisując w swoim oknie, wykona transfer poprawnie.

Dodatkowo: **Check signature locally** sprawdza podpis bez wysyłania, **Save to file… / Load from file…** zapisują i wczytują przygotowaną operację.

**Conflicting operations** – przygotowuje dwie poprawnie podpisane przez Ciebie, ale wykluczające się operacje (ten sam Twój bilet do dwóch różnych osób) i wysyła je jednocześnie przez dwa różne węzły (**Send both at the same time**) albo osobno (**Send #1 only**, **Send #2 only**). System zawsze przyjmie dokładnie jedną z nich.

---

## 7. Okno administratora galerii

### Zakładka Issue tickets – wystawianie biletów

**Wystawienie biletu – issue()** (po sprzedaży dzieła):

1. Uzupełnij: *Artwork title* (tytuł), *Original author* (autor), *Accepted by gallery on* (data przyjęcia dzieła), *Price* (cena w PLN), *Owner (buyer)* (nabywca – zarejestrowany klient).
2. Kliknij **Issue ownership ticket**.

Nowy bilet ma status `ACTIVE`, identyfikator (uuid) nadaje system. Bilet od razu pojawia się w zakładce *My assets* nabywcy.

**Zmiana ceny – Revaluation** (np. po wycenie dzieła):

1. *Asset* – aktywny bilet, *New price* – nowa cena.
2. Kliknij **Set new price**.

Kwota wypłacana przy spieniężeniu jest zawsze równa aktualnej cenie.

### Zakładka Browse assets

Taka sama jak u klienta (punkt 6).

### Zakładka Clients – klienci

Lista użytkowników zarejestrowanych w blockchainie: nazwa, rola, liczba i wartość aktywnych biletów, klucz publiczny. Administrator **nie zakłada kont klientów i nie zna ich kluczy prywatnych**.

### Zakładka Network & nodes – węzły i sieć

- **Tabela węzłów** – czy węzeł działa (*Online*), jego rola, liczba zatwierdzonych bloków i hash ostatniego bloku. Gdy wszystkie węzły są zsynchronizowane, mają tę samą liczbę bloków i ten sam hash.
- **Start X / Stop X** – uruchamia lub zatrzymuje węzeł. System działa dalej, dopóki pracują co najmniej 2 z 3 węzłów. Ponownie uruchomiony węzeł sam pobiera brakujące bloki.
- **Split network: A | B,C** (i pozostałe warianty) – symuluje awarię sieci, która rozdziela węzły na dwie grupy. Grupa z jednym węzłem odrzuca nowe operacje (`FAILED`), grupa z dwoma działa normalnie. **Heal network** przywraca łączność – węzły samoczynnie uzgadniają jeden wspólny stan.
- **Replication check** – wybierz bilet i kliknij **Read this asset from EVERY node**, aby porównać jego stan na każdym węźle.

Wyłączanie węzłów i dzielenie sieci służą do pokazu odporności systemu; w zwykłej pracy wszystkie węzły powinny działać.

### Zakładka Blockchain

Pokazuje surowe bloki zapisane przez wybrany węzeł (wybierz węzeł i kliknij **Load blocks**; kliknięcie wiersza wyświetla pełną treść bloku).

---

## 8. Typowe scenariusze

| Zadanie | Kto | Gdzie |
|---|---|---|
| Założyć konto | klient | okno logowania → *New client account* |
| Wystawić bilet po sprzedaży dzieła | administrator | *Issue tickets* → *issue()* |
| Sprzedać bilet innemu klientowi | właściciel | *My assets* → *transfer()* |
| Spieniężyć bilet | właściciel | *My assets* → *redeem()* |
| Zmienić cenę dzieła | administrator | *Issue tickets* → *Revaluation* |
| Sprawdzić właściciela i historię dowolnego biletu | każdy | *Browse assets* |
| Sprawdzić, gdzie jest mój klucz prywatny | klient | *My account* |
| Sprawdzić stan węzłów | administrator | *Network & nodes* |

---

## 9. Weryfikacja bez aplikacji

Stan biletów można sprawdzić niezależnym programem, bez otwierania aplikacji (węzły muszą działać):

```bash
python verifier/verify_chain.py                  # wszystkie bilety, wszystkie węzły
python verifier/verify_chain.py --asset <ID>     # jeden bilet
```

Program pobiera łańcuch z każdego węzła osobno, sprawdza wszystkie podpisy i powiązania bloków, a na końcu informuje, czy wszystkie węzły pokazują tego samego właściciela i status. Łańcuch można też zapisać do pliku (`--export plik.json`) i sprawdzić później bez węzłów (`--file plik.json`).

---

## 10. Rozwiązywanie problemów

| Objaw | Przyczyna i rozwiązanie |
|---|---|
| `Cluster configuration not found` przy starcie | Nie wykonano `python manage.py reset`. Wykonaj je raz przed pierwszym uruchomieniem. |
| `Stop the running nodes first` przy `reset` | Węzły nadal działają. Zatrzymaj je (zamknij okna węzłów) i powtórz. |
| `Wrong password.` przy logowaniu | Błędne hasło. Hasła nie da się odzyskać; administrator może jedynie wykonać `reset` (usuwa wszystkie dane). |
| `No node is reachable` przy logowaniu lub rejestracji | Węzły nie działają – wykonaj `python manage.py cluster`. |
| `Registration REJECTED: user name '…' is already taken` | Nazwa jest zajęta w blockchainie – wybierz inną. |
| `an account named '…' already exists on this computer` | Na tym komputerze jest już portfel o tej nazwie – zaloguj się na nie zamiast rejestrować ponownie. |
| W pasku *Cluster* wszystkie węzły `offline` | Węzły nie zostały uruchomione – wykonaj `python manage.py cluster`. |
| Okno węzła zamyka się od razu | Port 8001–8003 jest zajęty przez inny program albo węzeł już działa. Uruchom węzeł w terminalu poleceniem `python manage.py node A`, aby zobaczyć komunikat błędu. |
| `FAILED – no leader reachable…` / `no majority of nodes reachable…` | Wybrany węzeł nie ma kontaktu z pozostałymi (wyłączone węzły albo podział sieci). Uruchom brakujące węzły lub (administrator) kliknij **Heal network**, ewentualnie wyślij operację przez inny węzeł. |
| `REJECTED – … is not the current owner` | Próbujesz przekazać lub spieniężyć bilet, który nie należy do Ciebie. |
| `REJECTED – conflict …` | Bilet zmienił się od chwili przygotowania operacji (inna operacja była pierwsza). Odśwież dane i wykonaj operację ponownie. |
| `REJECTED – asset is already REDEEMED` | Bilet został spieniężony – nie można go już przekazać ani spieniężyć. |
| `REJECTED – replay detected` | Ta sama podpisana operacja została już wykonana. Przygotuj nową operację. |
| Lista *Owner (buyer)* u administratora jest pusta | Żaden klient się jeszcze nie zarejestrował. |

---

## 11. Gdzie są dane

| Ścieżka | Zawartość |
|---|---|
| `runtime/cluster.json` | adresy węzłów i klucz publiczny administratora |
| `runtime/node-A/node.db` (oraz `node-B`, `node-C`) | kopia łańcucha bloków danego węzła (SQLite) |
| `runtime/client/wallets/*.json` | portfele (konta) – klucz publiczny i **zaszyfrowany hasłem** klucz prywatny |

Katalog `runtime/` nie jest zapisywany w repozytorium Git. Polecenie `reset` usuwa całą jego zawartość.
