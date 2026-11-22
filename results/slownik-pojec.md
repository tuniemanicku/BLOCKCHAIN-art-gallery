# Słownik pojęć – Sellart

Tłumaczenia pojęć technicznych i angielskich napisów widocznych w aplikacji, z krótkim wyjaśnieniem znaczenia dla użytkownika.

## Aktywa i operacje

| Pojęcie (w aplikacji) | Tłumaczenie | Znaczenie |
|---|---|---|
| Asset | aktywo, bilet własności | Cyfrowy bilet potwierdzający własność dzieła sztuki w galerii. |
| Asset ID (uuid) | identyfikator aktywa | Unikalny, losowo nadany identyfikator biletu (UUID – *Universally Unique Identifier*). |
| Owner | właściciel | Użytkownik, do którego aktualnie należy bilet. Zawsze dokładnie jeden. |
| Status: ACTIVE | status: aktywny | Bilet można przekazać lub spieniężyć. |
| Status: REDEEMED | status: wykorzystany / spieniężony | Bilet został spieniężony; nie można go już przekazać ani ponownie spieniężyć. |
| Title | tytuł dzieła | Nazwa dzieła; używana też do oznaczeń testowych A1–A5. |
| Original author | oryginalny autor | Twórca dzieła sztuki. |
| Accepted by gallery on | data przyjęcia | Dzień, w którym galeria przyjęła dzieło. |
| Price / Current price (PLN) | cena / aktualna cena | Aktualna wartość dzieła; według niej wypłacana jest kwota przy spieniężeniu. |
| Paid out on redeem | wypłacono przy spieniężeniu | Kwota wypłacona właścicielowi w chwili REDEEM. |
| Version | wersja aktywa | Liczba operacji wykonanych na aktywie. Służy do wykrywania konfliktów. |
| issue() / ISSUE | wystawienie | Utworzenie nowego biletu po zakupie dzieła (wykonuje administrator galerii). |
| transfer() / TRANSFER | przekazanie, handel | Przekazanie biletu innemu użytkownikowi (wykonuje właściciel). |
| redeem() / REDEEM | spieniężenie, wykorzystanie | Wymiana biletu na pieniądze po aktualnej cenie; status zmienia się na REDEEMED. |
| Revaluation / SET_PRICE | przeszacowanie / zmiana ceny | Zmiana aktualnej ceny dzieła przez administratora galerii. |
| REGISTER_USER | rejestracja użytkownika | Opublikowanie w systemie nazwy użytkownika i jego klucza publicznego. |
| Acting user (signs) | działający użytkownik (podpisuje) | Osoba, której klucz prywatny podpisuje operację. |
| Recipient | odbiorca | Użytkownik, który otrzyma bilet. |
| History | historia | Chronologiczna lista operacji na aktywie odczytana z blockchaina. |
| From (previous owner) / To (recipient) | od (poprzedni właściciel) / do (odbiorca) | Strony operacji zapisane w historii. |

## Wyniki operacji

| Pojęcie | Tłumaczenie | Znaczenie |
|---|---|---|
| SUCCESS | sukces | Operacja została zapisana w bloku zatwierdzonym przez większość węzłów. Jest ostateczna. |
| REJECTED | odrzucona | Operacja łamie regułę systemu (np. brak podpisu, nie jesteś właścicielem, aktywo wykorzystane, powtórzenie, konflikt). Stan się nie zmienia. |
| FAILED | nieudana | Operacji nie dało się przetworzyć (np. węzeł odcięty od większości, brak lidera, węzeł wyłączony). Stan się nie zmienia; można spróbować przez inny węzeł. |
| committed in block #n | zatwierdzona w bloku nr n | Numer bloku łańcucha, w którym zapisano operację. |
| forwarded to leader X | przekazana do lidera X | Węzeł, do którego wysłano operację, przekazał ją liderowi. |
| conflict | konflikt | Operacja została przygotowana dla starszej wersji aktywa – inna operacja została wykonana wcześniej. |
| replay detected | wykryto powtórzenie | Ta sama podpisana operacja została już wykonana; ponowne wysłanie jest odrzucane. |
| missing signature | brak podpisu | Operacja nie ma podpisu – nie jest autoryzowana. |
| invalid signature | nieprawidłowy podpis | Podpis nie został złożony kluczem prywatnym osoby podanej jako podpisujący. |

## Kryptografia i klucze

| Pojęcie | Tłumaczenie | Znaczenie |
|---|---|---|
| Wallet | portfel | Plik po stronie użytkownika z jego parą kluczy. Nigdy nie jest wysyłany do węzłów. |
| Private key | klucz prywatny | Tajny klucz użytkownika; tylko nim można podpisać operację w jego imieniu. |
| Public key | klucz publiczny | Jawny klucz, którym węzły sprawdzają podpisy; identyfikuje właściciela. |
| Signature | podpis cyfrowy | Dowód, że operację zatwierdził posiadacz klucza prywatnego i że jej treść nie została zmieniona. |
| Ed25519 | Ed25519 | Algorytm podpisu cyfrowego używany w systemie. |
| Hash (SHA-256) | skrót kryptograficzny | „Odcisk palca” danych; najmniejsza zmiana danych zmienia skrót. |
| Payload | treść operacji | Dane operacji objęte podpisem (typ, aktywo, odbiorca, wersja itd.). |
| op_id (Operation ID) | identyfikator operacji | Unikalny numer operacji; chroni przed jej ponownym wykonaniem. |
| Signer | podpisujący | Klucz publiczny osoby, która autoryzuje operację. |
| Canonical JSON | kanoniczny JSON | Jednoznaczny zapis danych (posortowane klucze, bez spacji), dzięki któremu wszyscy liczą ten sam podpis i hash. |
| Replay | atak powtórzeniowy | Ponowne wysłanie przechwyconej, poprawnie podpisanej operacji. |
| Gallery Admin | administrator galerii | Konto uprawnione do wystawiania biletów i zmiany cen. Nie zna kluczy prywatnych klientów. |

## Blockchain i sieć węzłów

| Pojęcie | Tłumaczenie | Znaczenie |
|---|---|---|
| Blockchain / chain | łańcuch bloków | Uporządkowany zapis wszystkich operacji; każdy blok zawiera hash poprzedniego, więc zmiana historii jest wykrywalna. |
| Block | blok | Pojedynczy wpis łańcucha (jedna operacja albo wpis techniczny). |
| GENESIS block | blok początkowy | Pierwszy blok łańcucha; zawiera klucz publiczny administratora galerii. |
| LEADER block | blok lidera | Wpis techniczny oznaczający wybór nowego lidera. |
| Previous hash | hash poprzedniego bloku | Powiązanie bloku z poprzednim. |
| Node | węzeł | Niezależny proces systemu z własną bazą danych i własną kopią łańcucha (A, B, C). |
| Cluster | klaster | Wszystkie węzły działające razem. |
| Consensus (Raft) | konsensus (algorytm Raft) | Sposób, w jaki węzły uzgadniają jeden wspólny stan i kolejność operacji. |
| Leader / Follower / Candidate | lider / naśladowca / kandydat | Role węzłów w Raft: lider porządkuje operacje, pozostali je replikują; kandydat ubiega się o rolę lidera. |
| Term | kadencja | Numer kolejnej „kadencji” lidera; rośnie przy każdych wyborach. |
| Election | wybory lidera | Automatyczny wybór nowego lidera, gdy obecny przestaje odpowiadać. |
| Majority | większość | Co najmniej 2 z 3 węzłów; bez większości nic nie może zostać zatwierdzone. |
| Commit / committed | zatwierdzenie / zatwierdzony | Blok zapisany przez większość węzłów – ostateczny. |
| Committed blocks | zatwierdzone bloki | Liczba bloków ostatecznie zapisanych w danym węźle. |
| Replication | replikacja | Kopiowanie bloków na wszystkie węzły. |
| Synchronisation | synchronizacja | Automatyczne uzupełnienie brakujących bloków przez węzeł, który był wyłączony lub odcięty. |
| Network partition / Split network | podział sieci, partycja | Sytuacja, w której grupy węzłów nie mogą się ze sobą komunikować. |
| Heal network | przywróć sieć | Ponowne połączenie wszystkich węzłów. |
| Blocked peers | zablokowani sąsiedzi | Węzły, z którymi dany węzeł nie wymienia wiadomości (symulowany podział). |
| Minority partition | partycja mniejszościowa | Część sieci bez większości – nie może zatwierdzać operacji. |
| Split-brain | rozszczepienie stanu | Błędny stan, w którym części systemu trwale pokazują różne wyniki; Raft temu zapobiega. |
| Online / offline | dostępny / niedostępny | Czy węzeł odpowiada. |
| Read state from | odczytuj stan z | Węzeł, z którego aplikacja odczytuje dane (Auto = pierwszy dostępny). |
| Send operations via | wysyłaj operacje przez | Węzeł, do którego aplikacja wysyła operacje. |
| Replication check | kontrola replikacji | Odczyt tego samego aktywa z każdego węzła osobno. |
| Verifier | weryfikator | Niezależny program sprawdzający łańcuch (hashe, podpisy, właścicieli) bez użycia aplikacji. |
