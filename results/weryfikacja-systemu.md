# Sellart – weryfikacja zgodności systemu z wymaganiami

- **System:** Sellart – bilety własności dzieł sztuki w galerii
- **Ścieżka realizacji:** A – własny system rozproszony (własny blockchain na 3 węzłach, konsensus Raft)
- **Postać:** aplikacja desktopowa (Python, PySide6) z osobnym interfejsem dla każdego użytkownika + 3 węzły (osobne procesy, każdy z własną bazą SQLite) + niezależny weryfikator CLI

Dokument opisuje dla każdego kryterium z instrukcji projektowej: **jak system je spełnia** oraz **jak to sprawdzić**. Pojęcia techniczne wyjaśnia [słownik](slownik-pojec.md), obsługę aplikacji – [instrukcja obsługi](instrukcja-obslugi.md).

---

## 0. Technologie i decyzje projektowe

| Element | Wybór | Uzasadnienie |
|---|---|---|
| Język | Python 3.12 | zgodnie z zaleceniem |
| Interfejs | aplikacja desktopowa PySide6 (Qt): okno logowania/rejestracji + **osobne okno dla każdego zalogowanego użytkownika** (klient / administrator) | zgodnie z zaleceniem „aplikacja desktopowa”; każdy użytkownik ma własny interfejs |
| Konta | portfel użytkownika: para kluczy Ed25519, klucz prywatny **zaszyfrowany hasłem** (scrypt + AES-256-GCM) | logowanie = odszyfrowanie klucza; klucza nie zna ani węzeł, ani administrator (R7) |
| Baza danych | SQLite – **osobny plik dla każdego węzła** (`runtime/node-X/node.db`) | węzły nie współdzielą bazy (wymóg ścieżki A) |
| Architektura | własny, uprawniony (permissioned) blockchain + konsensus **Raft** | realizuje replikację, odporność na awarię, rozstrzyganie konfliktów i zbieżność po partycji (R11–R14) |
| Podpisy | Ed25519 (biblioteka `cryptography`) | autoryzacja kluczem prywatnym (R7) |
| Komunikacja | HTTP/JSON (biblioteka standardowa Pythona + `requests`) | prosty, czytelny interfejs węzłów |

**Uwaga o zmianach względem zaleceń:** zalecenie „aplikacja desktopowa w Pythonie z bazą danych” zostało zachowane. Doprecyzowano jedynie, że „baza danych” to **trzy niezależne bazy SQLite** (po jednej na węzeł), a nie jedna centralna – jedna wspólna baza nie spełniałaby wymagań R10–R14. Ścieżka A została zrealizowana jako *własny* blockchain (bez publicznej sieci), zgodnie z zapisem „Ścieżka A: BLOCKCHAIN” w zaleceniach.

**Domena:** aktywo = bilet własności dzieła sztuki. Pola: `uuid`, `owner` (właściciel), `status` (`ACTIVE` / `REDEEMED`), data przyjęcia przez galerię, oryginalny autor, cena; dodatkowo tytuł dzieła. Bilety wystawia administrator galerii (`issue`), klienci handlują nimi (`transfer`), a `redeem` to spieniężenie biletu po aktualnej cenie (cenę może zmienić administrator operacją *Revaluation*).

**Role i interfejsy:**

| Konto | Zakłada je | Okno (zakładki) |
|---|---|---|
| Klient (Alice, Bob, Charlie, …) | sam klient – rejestracja w oknie logowania | *My assets* (własne bilety, `transfer`, `redeem`), *Browse assets*, *Security tests*, *My account* |
| Gallery Admin | polecenie `reset` (hasło podawane przy resecie) | *Issue tickets* (`issue`, zmiana ceny), *Browse assets*, *Clients*, *Network & nodes*, *Blockchain* |

Okno logowania pozwala zalogować kilka kont jednocześnie – każde w osobnym oknie. W dalszej części „okno Alice” oznacza okno zalogowanej Alice itd.

---

## 1. Przygotowanie do prezentacji (przed rozpoczęciem oceny)

```bash
pip install -r requirements.txt
python manage.py reset      # czysty stan; pyta o hasło konta Gallery Admin
python manage.py cluster    # uruchamia węzły A, B, C – trzy osobne okna/procesy
python manage.py app        # otwiera okno logowania
```

W oknie logowania:

1. Ramka **New client account**: zarejestrować kolejno `Alice`, `Bob`, `Charlie` (każdy z własnym hasłem) – **Register and sign in**. Każda rejestracja otwiera okno danego klienta.
2. Ramka **Sign in**: wybrać *Gallery Admin*, wpisać hasło podane przy `reset` → **Sign in** – otwiera się okno administratora.

**Lista kontrolna:** otwarte 4 okna (Alice, Bob, Charlie, Gallery Admin); wszystkie trzy węzły „online” (pasek u góry: `A: leader | B: follower | C: follower` – lider może być dowolny); w oknie administratora zakładka *Clients* pokazuje Alice, Boba i Charliego; zakładka *Browse assets* jest pusta.

**Oznaczenia A1–A5:** system sam nadaje identyfikatory (uuid). Powiązanie z oznaczeniami testowymi zapisuje się w polu **tytuł dzieła**, np. `A1 - Sunflowers`. Tytuł jest widoczny w każdej liście wyboru aktywa i w tabelach aktywów.

**Gdzie widać wynik operacji:** każda operacja trafia do panelu **Operation results** na dole okna użytkownika, który ją wykonał, z wynikiem `SUCCESS`, `REJECTED` lub `FAILED` i komunikatem z przyczyną.

**Test automatyczny (opcjonalnie):** `python tests/acceptance_test.py` uruchamia osobny klaster na portach 9101–9103 i wykonuje T1–T14 automatycznie (wynik: `14/14 tests passed`).

---

## 2. Wymagania względem aplikacji

| # | Wymaganie | Jak spełnione | Jak sprawdzić |
|---|---|---|---|
| 1 | Kod w repozytorium Git | Projekt jest repozytorium Git | `git log` w katalogu projektu |
| 2 | Instrukcja uruchomienia | `README.md` (rozdział *Quick start*), [instrukcja obsługi](instrukcja-obslugi.md), ten dokument (rozdział 1) | Otworzyć `README.md` |
| 3 | Uruchomienie całego systemu podczas prezentacji | 3 polecenia: `reset`, `cluster`, `app` – wszystko lokalnie, bez zewnętrznych usług | Wykonać polecenia z rozdziału 1 |
| 4 | Trzech niezależnych użytkowników | Każdy klient **sam rejestruje się** w oknie logowania: aplikacja generuje jego parę kluczy Ed25519, zapisuje ją w osobnym portfelu zaszyfrowanym jego hasłem i rejestruje klucz publiczny w blockchainie (`REGISTER_USER`, podpisane nowym kluczem). Każdy zalogowany użytkownik ma **własne okno** do przeglądania i zarządzania swoimi aktywami. | Zarejestrować Alice, Boba i Charliego (rozdział 1). W każdym oknie klienta zakładka *My account* pokazuje inny klucz publiczny i inny plik portfela; w oknie administratora zakładka *Clients* pokazuje 3 klientów |
| 5 | Start z czystego stanu | `python manage.py reset` usuwa bazy wszystkich węzłów i wszystkie portfele; nowe węzły zaczynają od bloku genesis | Po `reset` + `cluster` okno logowania zawiera tylko konto *Gallery Admin*, a w jego oknie zakładka *Blockchain* pokazuje tylko blok `GENESIS` |
| 6 | Pokazanie stanu aktywa bez modyfikacji kodu | Zakładki *My assets* i *Browse assets* (stan + historia), *Network & nodes* (stan na każdym węźle), weryfikator CLI | Kliknąć aktywo w zakładce *Browse assets* |
| 7 | Obserwowanie wyniku każdej operacji | Panel *Operation results* w każdym oknie: `SUCCESS` / `REJECTED` / `FAILED` + komunikat | Wykonać dowolną operację i spojrzeć na panel na dole okna |

---

## 3. Wymagania R1–R14 i testy T1–T14

Każdy test opisano w formacie: **jak system spełnia wymaganie** → **kroki testu w aplikacji** → **oczekiwany wynik (PASS)**.

### Poziom 3,0

#### R1 / T1 – Utworzenie aktywa

**Jak spełnione:** Operacja `ISSUE` jest podpisywana kluczem administratora galerii. Węzły sprawdzają, że podpisał ją administrator (klucz publiczny administratora jest zapisany w bloku genesis), że `uuid` jest nowy i że odbiorca jest zarejestrowanym klientem. Po zatwierdzeniu przez większość węzłów aktywo ma status `ACTIVE`. Kod: `sellart/ledger.py` – `_check_issue`, `_apply_issue`.

**Test:** okno administratora → *Issue tickets* → ramka **issue()**: tytuł `A1 - Sunflowers`, autor, data przyjęcia, cena, *Owner (buyer)* = Alice → **Issue ownership ticket**. Następnie *Browse assets* → kliknąć wiersz A1 (bilet pojawia się też w oknie Alice, zakładka *My assets*).

**PASS:** panel wyników administratora: `SUCCESS … committed in block #n`. W *Browse assets* widać *Asset ID (uuid)*, *Owner* = Alice, *Status* = `ACTIVE`.

#### R2 / T2 – Odczyt właściciela

**Jak spełnione:** Węzeł zwraca właściciela z zatwierdzonego stanu swojej kopii łańcucha (`GET /assets/<id>`). Właściciel to jeden klucz publiczny, wyświetlany wraz z nazwą użytkownika.

**Test:** dowolne okno → *Browse assets* → wkleić identyfikator A1 w pole *Asset ID* → **Read owner**.

**PASS:** komunikat `Owner of …: Alice (key …, read from node X)`.

#### R3 / T3 – Transfer przez właściciela

**Jak spełnione:** `TRANSFER` podpisany kluczem właściciela; węzeł sprawdza podpis, właściciela, status i wersję aktywa, po czym zastępuje pole `owner` odbiorcą (aktywo ma zawsze dokładnie jednego właściciela). Kod: `_check_transfer`, `_apply_transfer`.

**Test:** okno Alice → *My assets* → kliknąć A1 → ramka **transfer()**: *Recipient* = Bob → **Transfer**. Odczytać stan w *Browse assets*.

**PASS:** `SUCCESS`; *Owner* = Bob, *Status* = `ACTIVE`; A1 znika z *My assets* Alice i pojawia się w *My assets* Boba.

#### R4 / T4 – Transfer przez osobę, która nie jest właścicielem

**Jak spełnione:** O prawie do operacji decydują węzły, nie aplikacja: węzeł odrzuca operację, której podpisujący (`payload.signer`) nie jest aktualnym właścicielem. Odrzucona operacja nie trafia do łańcucha, więc stan się nie zmienia.

**Test:** okno Charliego → *Security tests* → ramka **Authorisation and replay**: *Asset* = A1, *In the name of* = Charlie, *Recipient* = Charlie, **sign with MY private key (Charlie)** → **1. Prepare transfer** → **2. Send**. (Wariant: *My assets* → ramka **transfer()** → w pole *Asset* wkleić identyfikator A1 – nie ma go na liście Charliego – i kliknąć **Transfer**.) Odczytać stan.

**PASS:** `REJECTED – Charlie is not the current owner (owner: Bob)`; A1: Bob, `ACTIVE`.

#### R5 / T5 – Wykorzystanie (REDEEM)

**Jak spełnione:** `REDEEM` podpisany przez właściciela zmienia status na `REDEEMED`, zapisuje wypłaconą kwotę (aktualną cenę) i **nie zmienia właściciela**. Kod: `_apply_redeem`.

**Test:** okno Boba → *My assets* → kliknąć A1 → ramka **redeem()** → **Redeem**. Odczytać stan.

**PASS:** `SUCCESS`; *Owner* = Bob, *Status* = `REDEEMED`, *Paid out on redeem* = cena.

#### R6 / T6 – Ponowne REDEEM i TRANSFER po wykorzystaniu

**Jak spełnione:** Każda operacja na aktywie o statusie `REDEEMED` jest odrzucana (`_check_asset_state`).

**Test:** okno Boba → *My assets* → kliknąć A1 (status `REDEEMED`) → ponownie **Redeem**; odczytać stan. Następnie ramka **transfer()**: *Asset* = A1 (kliknięty wiersz lub wklejony identyfikator), *Recipient* = Charlie → **Transfer**; odczytać stan.

**PASS:** obie operacje: `REJECTED – asset is already REDEEMED …`; A1: Bob, `REDEEMED`.

### Poziom 3,5

#### R7 / T7 – Autoryzacja kryptograficzna

**Jak spełnione:**

* Każdy użytkownik ma parę kluczy Ed25519 wygenerowaną przy rejestracji **lokalnie, po stronie użytkownika**. Klucz prywatny jest zapisany wyłącznie w pliku portfela `runtime/client/wallets/<nazwa>.json`, **zaszyfrowany hasłem użytkownika** (scrypt + AES-256-GCM); odszyfrowuje go dopiero logowanie i tylko w pamięci okna użytkownika. Do węzłów trafia tylko klucz publiczny (operacja `REGISTER_USER`). Bazy węzłów (`runtime/node-X/node.db`) nie zawierają kluczy prywatnych; administrator nie zna haseł klientów, więc nie może odczytać ich kluczy, a w swoim oknie ma dostęp wyłącznie do własnego klucza.
* Węzeł weryfikuje podpis: `Ed25519.verify(payload.signer, signature, canonical_json(payload))`, a następnie sprawdza, czy `payload.signer` jest właścicielem aktywa. Kod: `sellart/ledger.py`, `Ledger.validate`; `sellart/crypto.py`, `verify_signature`.

**Test:**

1. Okno administratora → *Issue tickets* → **issue()**: `A2`, *Owner (buyer)* = Alice.
2. Miejsce przechowywania klucza: okno Alice → *My account* – pola *Private key stored in (your side only)* i *Private key protection* (przycisk *Open wallet folder* otwiera katalog; w pliku jest tylko `encrypted_private_key`). Okno administratora → *Clients* pokazuje, że system zna wyłącznie klucze publiczne.
3. Sposób weryfikacji podpisu: *Security tests* → opis pod podglądem operacji (oraz kod `Ledger.validate`).
4. Okno **Boba** → *Security tests* → ramka **Authorisation and replay**: *Asset* = A2, *In the name of* = Alice, *Recipient* = Bob, *Signature* = **no signature** → **1. Prepare transfer** → **2. Send**. Odczytać stan A2 (*Browse assets*).
5. W tym samym oknie *Signature* = **sign with MY private key (Bob)** → **1. Prepare transfer** → (opcjonalnie **Check signature locally**: „NOT valid”) → **2. Send**. Odczytać stan.
6. Okno **Alice** → *Security tests*: *Asset* = A2, *In the name of* = Alice, *Recipient* = Bob, **sign with MY private key (Alice)** → **1. Prepare transfer** → **2. Send**. Odczytać stan. **Nie przygotowywać ponownie** – ta operacja zostaje zachowana do T8 (można też **Save to file…**).

**PASS:** krok 4: `REJECTED – missing signature`; krok 5: `REJECTED – invalid signature`; po obu A2 należy do Alice. Krok 6: `SUCCESS`, A2 należy do Bob.

#### R8 / T8 – Ponowne użycie autoryzacji (replay)

**Jak spełnione:** Każda operacja ma unikalny `op_id` objęty podpisem. Węzły pamiętają wszystkie wykonane `op_id` (odtwarzane z łańcucha) i odrzucają powtórzenie. Dodatkowo `asset_version` wiąże operację z konkretnym stanem aktywa.

**Test:** okno Alice → *Security tests* → **Send the SAME operation again (replay)** (wysyła dokładnie ten sam JSON z T7, z tym samym podpisem; po ponownym uruchomieniu aplikacji: **Load from file…** i ten sam przycisk – działa w dowolnym oknie, bo operacja jest już podpisana). Odczytać stan A2.

**PASS:** `REJECTED – replay detected - operation … was already executed in block #n`; A2 nadal należy do Bob (historia A2 zawiera tylko jeden TRANSFER).

### Poziom 4,0

#### R9 / T9 – Historia operacji

**Jak spełnione:** Historia jest wyliczana z bloków łańcucha w kolejności ich zatwierdzenia. Każdy wpis zawiera: typ operacji, identyfikator aktywa, poprzedniego właściciela (*From*), odbiorcę (*To*), unikalny identyfikator operacji (`op_id`), numer bloku i czas.

**Test:** okno administratora: **issue()** `A3` → Alice; okno Alice → *My assets*: **transfer()** A3 → Bob; okno Boba: **transfer()** A3 → Charlie; okno Charliego: **redeem()** A3. Dowolne okno → *Browse assets* → kliknąć A3.

**PASS:** tabela *History*: `ISSUE (- → Alice)`, `TRANSFER (Alice → Bob)`, `TRANSFER (Bob → Charlie)`, `REDEEM (Charlie)` – w tej kolejności, z kolumnami *Operation ID* i *Block*. Stan: Charlie, `REDEEMED`.

#### R10 / T10 – Niezależna weryfikacja

**Jak spełnione:** Program `verifier/verify_chain.py` jest **niezależny od aplikacji** – nie importuje jej kodu. Pobiera surowe, podpisane bloki z **każdego węzła osobno** (każdy węzeł czyta z własnej bazy) albo z wyeksportowanego pliku, a następnie samodzielnie: przelicza hashe bloków i ich powiązania, sprawdza podpis Ed25519 każdej operacji, odtwarza reguły własności i porównuje wyniki ze wszystkich źródeł. Nie jest to drugie API do tej samej tabeli – to kryptograficzna weryfikacja podpisanej historii.

**Test:** zanotować stan A3 z aplikacji (Charlie, `REDEEMED`) oraz jego *Asset ID*. **Zamknąć aplikację** (wszystkie okna użytkowników i okno logowania). W terminalu:

```bash
python verifier/verify_chain.py --asset <ID_A3>
```

(opcjonalnie wersja offline: `python verifier/verify_chain.py --export lancuch.json`, a potem `python verifier/verify_chain.py --file lancuch.json --asset <ID_A3>`).

**PASS:** dla każdego węzła: `chain OK … all hashes and signatures valid` oraz `owner = Charlie  status = REDEEMED`; na końcu `RESULT: all 3 verified sources report the SAME owner and status.`

### Poziom 4,5

#### R11 / T11 – Replikacja stanu

**Jak spełnione:** Każdy węzeł to osobny proces z własnym plikiem SQLite zawierającym pełną kopię łańcucha. Blok jest zatwierdzany dopiero, gdy zapisze go większość węzłów (2 z 3). Stan aktywów każdy węzeł wylicza z własnej kopii łańcucha. Dodatkowo każdy węzeł zapisuje migawkę stanu aktywów w tabeli `assets` swojej bazy (można ją obejrzeć dowolną przeglądarką plików SQLite).

**Test:** okno administratora: **issue()** `A4` → Alice. Okno Alice: na pasku u góry *Send operations via* = **node A** → *My assets* → **transfer()** A4 → Bob. Następnie okno administratora → *Network & nodes* → *Replication check*: wybrać A4 → **Read this asset from EVERY node** (albo w dowolnym oknie przełączyć *Read state from* na node B, potem node C, i odczytać A4 w *Browse assets*).

**PASS:** węzły B i C (oraz A) pokazują *Owner* = Bob, *Status* = `ACTIVE`; komunikat „read from this node's own database”. Pliki `runtime/node-A/node.db`, `node-B/node.db`, `node-C/node.db` są osobne.

#### R12 / T12 – Awaria pojedynczego węzła i powrót

**Jak spełnione:** Raft wymaga tylko większości (2 z 3). Gdy węzeł się wyłączy (także lider), pozostałe dwa w ciągu ok. 1–2 s wybierają lidera i dalej przyjmują operacje. Po ponownym uruchomieniu węzeł wczytuje swój łańcuch z dysku, a lider automatycznie przesyła mu brakujące bloki (mechanizm `AppendEntries`, dopasowanie po hashu poprzedniego bloku).

**Test:** okno administratora → *Network & nodes* → **Stop A** (albo zamknąć okno węzła A) – w tabeli węzeł A: `offline`. Okno Boba: *Send operations via* = **node B** → *My assets* → **transfer()** A4 → Charlie. Dowolne okno: *Read state from* = **node C** → sprawdzić A4 w *Browse assets*. Okno administratora → *Network & nodes* → **Start A** i odczekać kilka sekund; **Read this asset from EVERY node**.

**PASS:** transfer: `SUCCESS` mimo wyłączonego A; węzeł C: Charlie, `ACTIVE`. Po restarcie A tabela węzłów pokazuje tę samą liczbę bloków i ten sam hash ostatniego bloku na A, B i C, a A4 na wszystkich węzłach: Charlie, `ACTIVE`.

### Poziom 5,0

#### R13 / T13 – Konfliktujące operacje

**Jak spełnione:** Wszystkie zapisy przechodzą przez jednego lidera Raft, który ustala jedną kolejność operacji. Każda operacja niesie `asset_version` – wersję aktywa, dla której ją przygotowano. Pierwsza operacja zmienia wersję aktywa, więc druga (przygotowana dla tej samej wersji) zostaje automatycznie odrzucona jako konflikt. Reguła jest deterministyczna i wykonywana przez każdy węzeł; administrator nie ma żadnego wpływu na wynik.

**Test:** okno administratora: **issue()** `A5` → Alice. Okno Alice (*Send operations via* = Auto) → *Security tests* → ramka **Conflicting operations**: *Your asset* = A5, *#1 recipient* = Bob *send via* node A, *#2 recipient* = Charlie *send via* node B → **1. Prepare both** (obie operacje podpisane przez Alice, z tą samą wersją aktywa – widoczne w podglądzie JSON) → **2. Send both at the same time**. Następnie okno administratora → *Network & nodes* → **Read this asset from EVERY node** dla A5.

**PASS:** w panelu wyników Alice dokładnie jedna operacja `SUCCESS`, druga `REJECTED – conflict - the operation was prepared for asset version 1, but the asset is already at version 2 (another operation won)`. Wszystkie węzły pokazują tego samego właściciela A5 (zwycięzcę).

#### R14 / T14 – Partycjonowanie i zbieżność stanu

**Jak spełnione:** Zatwierdzenie bloku wymaga większości. Podczas podziału `A | B,C` węzeł A jest w mniejszości: nie może zatwierdzić niczego i **odmawia przyjęcia operacji** (wynik `FAILED` – dopuszczalne wg instrukcji). Część `B,C` ma większość, wybiera lidera i zatwierdza operację. Po przywróceniu komunikacji węzeł A widzi wyższą kadencję (term) lidera, porzuca ewentualne niezatwierdzone bloki i pobiera łańcuch większości. Nie ma możliwości trwałego split-brain: dwie różne wersje bloku nigdy nie mogą zostać zatwierdzone, bo dwie większości z 3 węzłów zawsze mają wspólny węzeł.

*Sposób podziału sieci:* przyciski w oknie administratora każą węzłom odrzucać wszystkie wiadomości węzeł–węzeł z drugą grupą (w obu kierunkach) – symulacja zapory sieciowej na jednym komputerze. Aplikacja nadal może wysyłać operacje do każdego węzła.

**Test:** ponieważ A5 zostało przeniesione w T13, do T14 należy utworzyć nowe aktywo w tym samym stanie początkowym: okno administratora → **issue()** `A5b (T14)` → Alice i sprawdzić **Read this asset from EVERY node** (wszędzie Alice).

1. Okno Alice → *Security tests* → **Conflicting operations**: *Your asset* = A5b, #1 → Bob przez **node A**, #2 → Charlie przez **node B** → **1. Prepare both**.
2. Okno administratora → *Network & nodes* → **Split network: A | B,C**. Odczekać ok. 3 s (kolumna *Blocked peers* pokazuje podział; B lub C zostaje liderem).
3. Okno Alice → *Security tests* → **Send #1 only** (do A), potem **Send #2 only** (do B).
4. Okno administratora → *Network & nodes* → **Heal network (reconnect all)**, odczekać kilka sekund → **Read this asset from EVERY node**.

**PASS:** #1 przez A: `FAILED – no leader reachable from this node (it may be in a minority partition)` (lub `no majority of nodes reachable`); #2 przez B: `SUCCESS`. Po przywróceniu komunikacji wszystkie węzły pokazują A5b: Charlie, `ACTIVE`, a tabela węzłów – ten sam hash ostatniego zatwierdzonego bloku. Można to dodatkowo potwierdzić weryfikatorem: `python verifier/verify_chain.py --asset <ID>`.

---

## 4. Podział odpowiedzialności

W ścieżce A wszystkie mechanizmy są zaimplementowane w projekcie:

| Mechanizm | Plik |
|---|---|
| Format operacji i bloków, hash łańcucha | `sellart/operations.py` |
| Reguły biznesowe, weryfikacja podpisów, ochrona przed replay, wykrywanie konfliktów | `sellart/ledger.py` |
| Replikacja, wybór lidera, synchronizacja po restarcie, zbieżność po partycji | `sellart/consensus.py` |
| Trwały stan każdego węzła | `sellart/storage.py` |
| Konta użytkowników: klucze, szyfrowanie hasłem | `sellart/client/wallets.py` |
| Logowanie, rejestracja, okna użytkowników | `sellart/client/ui/login_window.py`, `sellart/client/ui/session_window.py` |
| Niezależna weryfikacja | `verifier/verify_chain.py` |

Z gotowych bibliotek wykorzystano jedynie: prymitywy kryptograficzne Ed25519/SHA-256/scrypt/AES-GCM (`cryptography`, `hashlib`), SQLite, serwer HTTP z biblioteki standardowej, `requests` oraz Qt (PySide6) do interfejsu.

## 5. Podsumowanie

| Poziom | Wymagania | Test automatyczny |
|---|---|---|
| 3,0 | R1–R6 | T1–T6 PASS |
| 3,5 | R7–R8 | T7–T8 PASS |
| 4,0 | R9–R10 | T9–T10 PASS |
| 4,5 | R11–R12 | T11–T12 PASS |
| 5,0 | R13–R14 | T13–T14 PASS |

Wynik `python tests/acceptance_test.py`: **14/14 tests passed** (wielokrotne uruchomienia).
