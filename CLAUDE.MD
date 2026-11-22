## Projekt systemu: Sellart
### Informacje o systemie
- Obsługiwane aktywo: bilety własności sztuki w galerii
- Postać systemu: Aplikacja desktopowa zarządzająca aktywami
- Architektura: Zastosowanie BLOCKCHAIN

### Zakres i domena
- issue() - wystawienie własności dzieła po zakupie
- transfer() - handel aktywem
- redeem() - spieniężenie biletu zgodnie z aktualną ceną aktywa
- Pola aktywa: uuid, owner, status, data-przyjecia, oryginalny autor, cena
- Aktywa tworzy użytkownik systemu administracji galerii

### Architektura
- Wybór ścieżki A: BLOCKCHAIN

### Technologie
- Język programowania: Propozycją jest aplikacja desktopowa w Pythonie z bazą danych

### Implementacja
Zasady odnośnie implementacji, specyficzne do instrukcji, znajdują się w osobnym pliku w projekcie: implementation.md