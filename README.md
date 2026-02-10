# NRW Cup 2025 – Bewertungsberechnungen

Dieses Projekt dient der Verwaltung und Auswertung von Wettbewerbsdaten des NRW Cup 2025. Ziel war es, eine robuste und nachvollziehbare Alternative zu einer komplexen Excel-Lösung zu schaffen.

## Projekthintergrund

Dieses Hobbyprojekt entstand aus dem Wunsch heraus, eine Excel-Datei mit Makros durch eine schlankere Lösung zu ersetzen. Der Code wurde mit Unterstützung von Claude entwickelt. Das System läuft offline auf einem Raspberry Pi und in einer Entwicklungsumgebung auf einem Proxmox-Server.

---

## 1. Figurenwertung mit K-Faktoren

Jede Wettbewerbsfigur hat einen K-Faktor (z. B. 10, 15, 20), der die Schwierigkeit widerspiegelt. Die Bewertung erfolgt auf einer Skala von 0 bis 10 (mit halben Punkten).

**Berechnung:**

```
Figurenwertung = Rohwertung × K-Faktor
```

**Beispiele:**

- 7,5 × 15 = 112,5 Punkte
- 8,0 × 10 = 80 Punkte
- 6,5 × 20 = 130 Punkte

**Sonderfall: Segler-Flugzeit (SEGZEIT)**

```
Punkte = max(0, 300 - (abs(200 - tatsächliche_Zeit) × 3))
```

- Zielzeit: 200 s, max. Punkte: 300  
- Abweichung → Punktabzug mit Faktor 3

**Landezonen**

Punktwerte: 0, 5, 10, 20, 30 – je nach Landeposition.

---
NOTE: Die Beschreibung stimmt nicht, muss ich noch bearbeiten!!

## 2. Punktwerterwertungen

Die Punktwerter geben Bewertungen ab, die für jedes Team summiert werden:

- Bei 4 oder mehr Punktwertern wird die niedrigste Wertung für jedes Team gestrichen
- Die verbleibenden Wertungen werden gemittelt, um die Rohpunktzahl des Teams zu erhalten

**Beispiel mit 3 Punktwertern:**

- 950 + 1025 + 890 = 2865  


**Beispiel mit 4 Punktwertern:**

- 950 + 1025 + 890 + 840
- Niedrigste (840) wird gestrichen
- (950 + 1025 + 890) ÷ 3 = 955 Punkte

---

## 3. Normalisierung

Wertungen werden zur Vergleichbarkeit auf 1000 skaliert:

```
Normalisierte Wertung = (Rohwertung ÷ Höchste Rohwertung) × 1000
```

**Beispiel:**

- 955 ÷ 1150 × 1000 = 830,43 Punkte

---

## 4. Endwertung und Streichwertungen

Abhängig von der Anzahl der durchgeführten Durchgänge:

- 1-2 Durchgänge: Alle Durchgänge zählen
- Ab 3 Durchgängen: Der schwächste Durchgang wird gestrichen

Die Summe der verbleibenden Durchgänge ergibt die Gesamtwertung.

**Beispiel Team A (3 Durchgänge):**

- Durchgang 1: 856,52 Punkte
- Durchgang 2: 923,08 Punkte
- Durchgang 3: 742,31 Punkte (schwächster Durchgang, wird gestrichen)
- Gesamtwertung: 856,52 + 923,08 = 1779,60 Punkte

---

## 5. Finale Normalisierung

Die Gesamtwertungen aller Teams werden erneut auf einer 1000-Punkte-Skala normalisiert: (100%=1000 Punkte) 

```
Finale Wertung = (Gesamtwertung ÷ Höchste Gesamtwertung) × 1000
```

**Beispiel:**
- Team A: 1779,60 Punkte
- Höchste Teamwertung (Team B): 1863,58 Punkte  
- Normalisiert: 1779,60 ÷ 1863,58 × 1000 = 955,45 Punkte

---

## 6. Technische Umsetzung

Das System speichert sowohl Roh- als auch Normalwertungen nachvollziehbar ab. Bei Änderung von Durchgängen oder Wertungen wird alles automatisch neu berechnet.

---

## Startfolgen und Startlisten

### Erstdurchgang

Startfolge zufällig oder manuell festlegbar. Reihenfolge kann per Drag & Drop oder Zahleneingabe angepasst werden. Sperrfunktion verhindert versehentliche Änderungen.

### Druck der Startliste

Startliste als PDF erzeugbar mit Team, Schlepper, Segler, Startnummer.

### Weitere Durchgänge

Startreihenfolge ergibt sich aus der Wertung: Schwächere Teams starten zuerst.

**Beispiel:**

- Team A: 830,43 Punkte
- Team B: 1000,00 Punkte
- Team C: 800,00 Punkte
→ Startreihenfolge: C, A, B

### Druckoption auch für weitere Durchgänge verfügbar

Jede Liste enthält Ergebnisse des vorherigen Durchgangs.

---

### Automatisierte Startfolge für Folge-Durchgänge

Sortierung nach steigender Punktzahl, Teams ohne Wertung kommen ans Ende. Umgesetzt in `api_next_round_order()` im Modul `formular_bp`.




