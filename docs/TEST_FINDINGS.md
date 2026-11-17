# Collaudo BlindCUE — risultati, bug e miglioramenti

Sessione di collaudo su hardware reale con due uscite video indipendenti.
Documento di lavoro: raccoglie cosa funziona, cosa non funziona, i numeri
misurati e le proposte di intervento ordinate per priorità.

Data: 17 novembre 2026
Commit collaudato: `6edcd19` + le due correzioni descritte al §5 (non committate)

---

## 1. Stato in una riga

**49 controlli funzionali su 49 superati.** Tutte le funzionalità del software
rispondono correttamente su entrambe le uscite. Resta un solo limite reale, di
prestazioni e non di correttezza: **con due uscite attive contemporaneamente e
più video per uscita, il thread grafico non regge** su questa macchina del 2014
(sezione §6.1). Nessun crash, nessuna perdita di memoria, nessun file corrotto.

---

## 2. Ambiente di collaudo

| Voce | Valore |
|---|---|
| Macchina | MacBook Pro 2014, Intel i7 Haswell 2.2 GHz (8 thread), 16 GB RAM |
| Sistema | Arch Linux, KDE Plasma su Wayland |
| Decodifica video | VA-API con **Intel i965 driver 2.4.5**, H.264 High in hardware |
| Uscita A | HDMI-A-2 → TV, 1920×1080 (rossa nel test di identificazione) |
| Uscita B | HDMI-A-3 → mini proiettore, 1920×1080 (blu) |
| Schermo operatore | eDP-1, 1670×1043 |
| Uscite audio viste da Qt | **1 sola**: "Audio interno Stereo analogico" (HDMI in profilo `off` a livello di sistema) |
| Materiali usati | 3 video 1080p H.264 (65 s / ~2 min / ~9 min), 6 JPEG, 5 MP3 (fino a 49 min) |

Nota importante: se il driver `libva-intel-driver` non è installato, Qt
decodifica tutto in software. Effetto misurato: 6 video passano da **~100 % di
CPU a ~600 %**, con la temperatura che sale di 15-25 °C. La differenza tra
"regge" e "non regge" sta quasi tutta qui.

---

## 3. Copertura dei test

Suite di accettazione esterna (`~/.cache/blindcue-stress/suite.py`), che guida
le classi reali del programma e verifica il risultato osservabile: pixel
renderizzati, posizioni di riproduzione, stato del sequencer, contenuto dei
progetti salvati.

| Area | Casi | Esito |
|---|---|---|
| Render (crop, rotazione, opacità, maschere, scale, superfici) | 15 | 15 PASS |
| Riproduzione reale (video, audio, seek, fade, loop, out-point) | 8 | 8 PASS |
| Logica (sezioni, envelope, scheduler) | 11 | 11 PASS |
| Gruppi e ShowEngine (SIMULTANEOUS/RANDOM/SEQUENCE/STEP-LOOP, catene, standby) | 7 | 7 PASS |
| Persistenza (round-trip progetto, corruzione, file mancanti) | 4 | 4 PASS |
| Doppia uscita (routing A/B, indipendenza, span) | 4 | 4 PASS |
| **Totale** | **49** | **49 PASS** |

### Cosa è stato verificato, in pratica

- **Crop** al 50 % destro/alto/centrale: la fetta resta ancorata al bordo giusto del palco.
- **Rotazioni** 90° e 180°: i quadranti dell'immagine di prova si spostano come previsto.
- **Opacità**: luminosità 85 → 42 al 50 %.
- **Maschera poligonale** e **sfumatura**: bordo netto = 2 livelli di grigio, bordo sfumato = 32 (gradiente reale, non finto).
- **Scala** e **spostamento**: contenuto ridotto e spostato senza deformazioni.
- **Superfici**: mappatura a 4 angoli (corner pinning) e maschera ellittica.
- **Video**: durata, avanzamento, seek/scrub, fade in/out, loop con conteggio, fine cue rispettata sull'out-point.
- **Audio**: riproduzione, controllo volume 0-100, loop.
- **Sezioni**: skip su due passaggi, 3 ripetizioni poi avanzamento, vampiro infinito, interruzione loop, salto e scrub su sezione skippata, modifica del flag in diretta.
- **Envelope**: interpolazione dei punti di automazione volume/opacità.
- **Scheduler**: pre-delay, pausa/ripresa, cancellazione.
- **Gruppi**: elenco figli, SIMULTANEOUS, collisione sullo stesso layer, SEQUENCE che avanza lo standby figlio per figlio, catena `follow` che raccoglie più cue in un solo GO, mini-editor timeline (flag `timeline_composed` persistito).
- **Persistenza**: round-trip di 13 campi + maschera + sezioni + gruppo; progetto corrotto degradato senza eccezioni; file mancante conservato con badge OFFLINE.
- **Doppia uscita**: routing layer A 1-3 / B 4-6 con fallback su A, due scene indipendenti, due video simultanei su A e B, modalità span su due schermi.
- **Tappo/failsafe**: visibile all'avvio, nascosto durante i media, **restituito dopo lo svuotamento** e dopo il panico.

---

## 4. Prestazioni — numeri misurati

### 4.1 Avvio a freddo (dopo il riavvio del sistema)

| Carico | Primo frame | Blocco UI max | CPU (media) | Temp |
|---|---|---|---|---|
| 1 video | **138 ms** | 74 ms | ~45 % | 64 °C |
| 3 video | **98 ms** | 34 ms | ~100 % | 68 °C |
| 6 video | **291 ms** | 173 ms | ~120 % | 70 °C |

Il costo del primo video dopo il boot è basso e accettabile: nessun
"riscaldamento" di 6 secondi. L'inizializzazione VA-API è rapida.

### 4.2 Quanto regge, per numero di video contemporanei

Due uscite attive, video 1080p30, decodifica hardware:

| Video per uscita | FPS realmente presentati | Lag max thread grafico | CPU | Temp |
|---|---|---|---|---|
| **1** | **30 / 30** | **11-18 ms** | ~60 % | 86-90 °C |
| 2 | 21-23 | 80-90 ms (picco 439) | ~95 % | 92-94 °C |
| 3 | 17-20 | 96-106 ms | ~96 % | 93 °C |

Controprova: con **3 video su una sola uscita** (seconda finestra nascosta ma
ancora in decodifica) si torna a **61 repaint/s e 15 ms di lag**. Quindi il
problema non è la decodifica: è il **disegno contemporaneo su due finestre**.

Sintesi operativa per questo hardware: **un video per uscita è fluido; due
iniziano a scattare; tre scattano in modo evidente.** L'audio resta sempre
perfetto e le posizioni di riproduzione restano a 1.00× anche nei casi peggiori.

### 4.3 Perché scatta (analisi tecnica)

1. `QGraphicsView` usa il **motore di disegno raster** (nessun viewport OpenGL):
   ogni frame viene composto **sulla CPU** nel thread grafico.
2. I frame arrivano dal decoder come **NV12 in memoria di sistema**
   (`HandleType.NoHandle`, quindi nessun percorso zero-copy verso la GPU).
   Convertire un frame 1080p costa **4.1 ms** (misurato); ridurlo a 960×540
   costa 0.9 ms, ma il costo di composizione non cambia con la dimensione della
   finestra (verificato: 960×540 dà gli stessi 16 fps).
3. Tutto avviene in **un solo thread**. Due finestre = due composizioni 1920×1080
   più le conversioni: il thread si satura e il sistema smette di presentare a
   30 fps.

### 4.4 Stabilità e memoria

- Soak di 5 minuti, 38 cicli di carica/scarica con 1-6 media casuali:
  RSS dopo scarico 359 MB → plateau stabile **431-477 MB** (nessuna crescita
  monotona), **file descriptor fissi a 49**, **thread fissi a 78**: nessuna perdita.
- 40 cambi di cue ogni 250 ms: nessun crash.
- Temperatura massima osservata 97 °C con ventole al massimo; nessun throttling
  rilevato (le posizioni di riproduzione restano a 1.00×).

---

## 5. Bug trovati e **corretti** in questa sessione

### 5.1 CRITICO — Il Tappo non compariva mai (schermo nero)

`ui/output_window.py`, `_update_tappo_visibility()`

Il controllo "c'è un media attivo?" usava la lunghezza dei dizionari interni
`_layer_pixmaps`, che vengono popolati **tre volte all'avvio** (un item per
layer). Risultato: il Tappo veniva considerato "coperto" da subito e **non
tornava mai visibile**, né all'avvio né dopo `clear_all_layers()`. In scena
restava solo il rettangolo nero dietro, cioè **proiettore vuoto con il pubblico
davanti**.

Correzione: nuovo helper `_has_active_media()` che conta solo video davvero
visibili o immagini con pixmap non vuota dentro un contenitore visibile.
`show_fallback()` usa lo stesso criterio.

Verifica: 7 stati controllati (costruzione, avvio, hide, immagine attiva,
svuotamento, fallback, panico e revoca del panico). Prima: Tappo assente in 5
stati su 7. Dopo: presente in tutti gli stati corretti.

### 5.2 MEDIA — `crop` corrotto faceva sparire la cue in silenzio

`models/cue.py`, `Cue.from_dict()`

`crop` veniva letto **senza alcuna sanificazione**:

```python
crop=data.get("crop", _default_crop()),
```

Un progetto con `"crop": "non-un-dict"` (o con valori non numerici) arrivava
intatto fino a `show_image()`, che falliva con
`'str' object has no attribute 'get'`: la cue **non veniva disegnata e nessuno
se ne accorgeva**.

Correzione: nuova funzione `sanitize_crop()` applicata in `__post_init__`, quindi
a ogni cue costruita (da file o da codice). Un crop invalido degrada al frame
intero, che è il comportamento sicuro in scena.

Verifica: `P2b` falliva prima, passa ora; suite a 49/49.

---

## 6. Problemi aperti (da decidere insieme)

### 6.1 ALTA — Due uscite con più video: il thread grafico si satura

Dati al §4.2. Non è un errore di logica: i video vanno avanti a 1.00× e l'audio
è perfetto, ma **il proiettore mostra 17-20 fps invece di 30** e il pannello
dell'operatore risponde con ~100 ms di ritardo.

Cause: viewport raster + conversione colore su CPU + un solo thread (§4.3).

**Applicato in questa sessione l'opzione 2**: la barra di stato mostra un avviso
persistente quando il numero di video attivi supera ciò che l'hardware regge
(1 per uscita con due uscite attive, 3 con una sola). L'avviso è solo
informativo: non blocca mai un GO. L'operatore resta padrone della scena.

Opzioni, dalla più economica alla più invasiva:

1. **Regola operativa**: massimo un video per uscita quando sono attive
   entrambe le uscite. Nel 90 % degli spettacoli basta. Costo: zero.
2. **Limite automatico nell'app**: contatore "budget video" per uscita, con
   avviso nella UI quando si supera il numero che l'hardware regge. Costo: basso.
   → **Fatto** (vedi sopra).
3. **Viewport OpenGL** (`QOpenGLWidget`) sulla `QGraphicsView`: sposta la
   composizione sulla GPU e libera il thread grafico. Da misurare: su Haswell il
   guadagno può essere parziale perché la conversione NV12→RGB resta su CPU.
   Costo: medio, da provare in isolamento.
4. **Percorso zero-copy** (frame come texture GPU): il salto di qualità vero, ma
   richiede un item video custom con RHI. Costo: alto.

### 6.2 ALTA — Picchi da 2-6 secondi dovuti al garbage collector di Python

Con 6 video e due uscite si sono visti blocchi del thread grafico da **5.955 ms**
e 2.141 ms. **Con il GC Python disattivato il picco massimo scende a 773 ms**:
il GC è responsabile dei blocchi lunghi.

Il rischio in scena è concreto: il proiettore resta fermo sull'ultimo frame per
diversi secondi.

**Corretto in questa sessione con `gc.freeze()`** dopo il bootstrap
(`blindcue/main.py`): gli oggetti permanenti (albero dei widget Qt, moduli, show
caricato) escono dalle generazioni raccolte, quindi una raccolta completa non
deve più percorrerli. Misura A/B con 6 video e due uscite, 45 s per prova:

| Configurazione | Blocco peggiore del thread grafico |
|---|---|
| Senza freeze | **3.672 ms** (sessione precedente: 5.955 ms) |
| Con freeze, prova 1 | **572 ms** |
| Con freeze, prova 2 | 3.002 ms (evento isolato nei primi 4 s) |
| Con freeze, prova 3 | **189 ms**, raccolte GC sotto 1 ms |

Nelle prove 1 e 3 nessuna raccolta GC ha più causato blocchi; il caso peggiore
residuo della prova 2 cade nei primi secondi, quando 6 decoder VA-API si
inizializzano insieme, e non è attribuibile al GC (nessuna raccolta misurata).
Non è stato disattivato il GC: con il freeze le raccolte costano meno di 1 ms,
quindi disattivarlo non porterebbe alcun vantaggio e aumenterebbe il rischio di
crescita di memoria.

### 6.3 MEDIA — Una sola uscita audio visibile

Qt vede solo "Audio interno Stereo analogico". I profili HDMI risultano `off` a
livello di sistema, quindi non è un problema di BlindCUE: è la configurazione
PipeWire/WirePlumber della macchina. Da verificare prima di uno spettacolo con
audio su impianto esterno.

### 6.4 BASSA — Il pattern del Tappo nasce a 640×480

Alla creazione della finestra il pattern viene disegnato a 640×480 e solo dopo
`configure_screen()` viene ridimensionato alla risoluzione reale. Per un istante
potrebbe comparire sfocato. Soluzione: costruire il pattern solo dopo aver
conosciuto la geometria, oppure partire da una dimensione maggiore.

### 6.5 BASSA — Temperatura elevata

97 °C con ventole al massimo sotto carico di 6 video. Non c'è throttling e le
posizioni restano a 1.00×, ma è un dato da tenere d'occhio su una macchina di 12
anni (pulizia ventole / pasta termica). Su hardware moderno il problema non si
pone.

### 6.6 Nota — Sospensione automatica del sistema

Nella sessione precedente il PC si è sospeso da solo durante uno spettacolo
(`systemd-logind: The system will suspend now!`). Non è un bug di BlindCUE ma è
il tipo di evento che rovina una serata. Vedi §8.1.

---

## 7. Miglioramenti tecnici proposti

1. **Preflight VA-API**: all'avvio verificare che la decodifica hardware sia
   disponibile; se manca, mostrare un avviso chiaro con il pacchetto da
   installare (`libva-intel-driver` su Intel, `libva-mesa-driver` su AMD). Oggi
   la differenza è invisibile all'operatore finché non vede i ventola al massimo.
2. **Indicatore di salute in diretta**: nella barra di stato mostrare fps
   effettivi per uscita e lag del thread grafico. Se l'operatore vede "17 fps"
   sa che deve togliere un video prima che se ne accorga il pubblico.
3. **Budget video per uscita**: contatore che tiene conto dell'hardware rilevato
   e impedisce (o avvisa) oltre il limite sostenibile.
4. **GC tuning** come al §6.2.
5. **Viewport OpenGL** come al §6.1, da valutare con una misura A/B.
6. **Preload delle cue in standby**: il primo frame a freddo costa 291 ms con 6
   video; precaricando la cue successiva durante lo standby si riduce il vuoto
   al momento del GO.
7. **Test guidato all'avvio** (self-test opzionale, 3 secondi): pattern su ogni
   uscita con conto alla rovescia, come il test di identificazione usato in
   questo collaudo. Serve all'operatore per verificare i collegamenti prima
   dell'apertura porte.

---

## 8. Idee di funzionalità per l'operatore

### 8.1 Blocco anti-sospensione integrato

BlindCUE dovrebbe inibire sospensione e spegnimento dello schermo **finché
l'applicazione è aperta** (`systemd-inhibit --what=sleep:idle` su Linux, API
equivalenti su Windows/macOS). È la protezione più economica contro lo scenario
peggiore: il computer che si addormenta durante lo spettacolo.

### 8.2 Allarme "Tappo non impostato"

Se non è stata scelta un'immagine di Tappo, all'avvio proporre quella di default
con un avviso: il failsafe deve esistere sempre, non solo quando ci si pensa.

### 8.3 Riepilogo di fine serata

Un pannello con: cue eseguite, cue in errore, picchi di lag, temperatura massima,
file non trovati. Da esportare come testo da allegare al report dello spettacolo.

### 8.4 Modalità "prova con carico"

Un pulsante che avvia il carico massimo sostenibile e mostra gli fps: permette
di scoprire in sala prove, e non in scena, che quel determinato progetto è
troppo pesante per quella macchina.

### 8.5 Indicatore di conflitto di layer

Prima del GO, evidenziare se una cue sostituirà un media già in onda su un altro
layer della stessa uscita (internamente la collisione è già gestita, ma
l'operatore non la vede).

---

## 9. Come ripetere il collaudo

```bash
# suite funzionale completa (49 casi)
QT_QPA_PLATFORM=offscreen .venv/bin/python ~/.cache/blindcue-stress/suite.py

# carico video su due uscite con telemetria al secondo
VPO=1 .venv/bin/python ~/.cache/blindcue-stress/stress6.py 30   # 1 video per uscita
VPO=3 .venv/bin/python ~/.cache/blindcue-stress/stress6.py 30   # 3 video per uscita

# soak carica/scarica (memoria)
.venv/bin/python ~/.cache/blindcue-stress/soak_cycle.py 5

# costo di conversione di un frame
.venv/bin/python ~/.cache/blindcue-stress/frame_cost.py
```

Vincolo importante: i test **devono** girare fuori da sandbox/contenitori che
nascondono `/dev/dri`, altrimenti Qt decodifica in software e i numeri non sono
rappresentativi (6 video passano da 100 % a 600 % di CPU).

---

## 10. Cosa NON è stato coperto

Da mettere in programma prima di considerare il collaudo concluso:

- Windows e macOS (solo Linux Wayland è stato provato).
- Codec diversi da H.264: HEVC, VP9, ProRes, e file 4K o 10 bit.
- Audio multicanale reale (5.1/7.1) su impianto esterno.
- Edge blending reale tra due proiettori sovrapposti (le superfici sono state
  verificate pixel per pixel, ma su uno schermo solo per volta).
- Rete: controllo remoto, OSC, web server.
- Undo/redo, autosave, recupero dopo crash (verificati solo indirettamente dalla
  suite).
- Sessioni continue oltre i 10 minuti.
- Proiettore cinese reale: è stato usato come uscita B, ma non ne è stata
  verificata la fedeltà cromatica né la latenza di scaling interno.

---

## 11. File modificati in questa sessione

| File | Modifica |
|---|---|
| `blindcue/ui/output_window.py` | Tappo: nuovo `_has_active_media()`, usato da `_update_tappo_visibility()` e `show_fallback()` |
| `blindcue/models/cue.py` | nuova `sanitize_crop()`, applicata in `__post_init__` |
| `blindcue/main.py` | `gc.collect()` + `gc.freeze()` dopo il bootstrap; guardia del carico video con avviso nella barra di stato (controllo ogni secondo) |
| `blindcue/ui/main_window/_menu.py` | nuova etichetta `_lbl_perf_hint` e metodo `set_performance_hint()` |

Nessun commit è stato creato: le modifiche sono da rivedere e committare quando
si decide.
