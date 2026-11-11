# 📖 Manuale Operativo Interattivo di BlindCue

<a id="indice"></a>

Benvenuto nel **Manuale Operativo ufficiale di BlindCue**: una guida pratica pensata per registi, fonici e video-operatori per padroneggiare ogni funzione del programma dalle prove in allestimento fino alla diretta.

> [!TIP]
> **Come navigare questo manuale:** clicca su qualsiasi voce della mappa qui sotto per saltare subito all'argomento desiderato, apri i riquadri espandibili **▶ Approfondimento / Esempio Pratico** e usa i link `[↑ Indice]`, `[← Precedente]`, `[Successivo →]` alla fine di ogni sezione per muoverti rapidamente tra gli argomenti.

---

## 🧭 Indice Interattivo (Mappa Rapida)

| # | Argomento | Cosa impari | Vai a |
|---|-----------|-------------|-------|
| **1** | **Avvio, Proiettore & Tappo L0** | Collegare il secondo schermo e raddrizzare il proiettore con la griglia L0 | [Apri Sezione 1 →](#sec-1) |
| **2** | **Modalità Progetto vs LIVE** | Differenze tra banco editing e Show Mode (`[F5]`) e blocco pannelli | [Apri Sezione 2 →](#sec-2) |
| **3** | **Scaletta, Note & Batch** | Importare media, assegnare codici `Q`, Note di regia, Undo e selezione multipla | [Apri Sezione 3 →](#sec-3) |
| **4** | **I 3 Layer di Compositing** | Impilare `L3 Overlay` / `L2 Principale` / `L1 Sfondo` senza conflitti | [Apri Sezione 4 →](#sec-4) |
| **5** | **Posizione, Zoom, AR & Crop** | Inquadrare, deformare aspect ratio e ritagliare in `%` o `px` ancorati ai bordi | [Apri Sezione 5 →](#sec-5) |
| **6** | **Pre-Viz Isolata & Mirror Live** | Pre-ascolto in cuffia, equalizzatore audio e Mirror Live di foto e video | [Apri Sezione 6 →](#sec-6) |
| **7** | **Forma d'Onda, Zoom & Inviluppi** | Zoom `32×`, Snap IN/OUT, rampe Fade e keyframe Volume/Opacità (anche su Foto) | [Apri Sezione 7 →](#sec-7) |
| **8** | **Sezioni Virtuali `A/B/C` & Loop** | Dividere un file in blocchi ripetibili (`x2..∞`), salti ed `Esci da Loop` | [Apri Sezione 8 →](#sec-8) |
| **9** | **Tempi & 3 Modalità Sequenza** | Usare `Pre-Delay`, `Durata`, `Post-Delay` + `⏹ Blocco`, `⤵ Auto-GO`, `⇉ Simult.` | [Apri Sezione 9 →](#sec-9) |
| **10** | **Regia Live, Pausa & PANIC** | Leggere le barre live, congelare tutto (`⏸ PAUSA TUTTO`), Blackout & `PANIC [ESC]` | [Apri Sezione 10 →](#sec-10) |
| **11** | **Progetti `.blindcue` & Setup Linux** | Salvataggi atomici, Crash Recovery, installazione multi-distro e ottimizzazioni | [Apri Sezione 11 →](#sec-11) |

> 📚 **Cerchi la spiegazione tecnica file per file del codice Python?** Consulta [ARCHITETTURA_E_MODULI.md](ARCHITETTURA_E_MODULI.md).

---

<a id="sec-1"></a>

## 1. Avvio, Schermo Esterno & Reticolo Proiettore (Layer 0 / Tappo)

All'avvio tramite `./run.sh` (o `python3 blindcue/main.py`):
- **Con 2+ schermi collegati**: BlindCue posiziona automaticamente la Regia sul monitor principale e apre l'**Output Live a pieno schermo senza bordi** sul display esterno (Wayland nativo). Puoi forzare lo schermo con `--output-screen <indice>` oppure `--windowed`.
- **Con 1 solo monitor** (in ufficio o sui mezzi): l'Output Live si apre come **finestra 16:9 flottante** di collaudo, sempre visibile ma separata dal banco.

### Il Tappo Predefinito con Griglia di Calibrazione
Sotto i 3 livelli live esiste sempre il **Layer 0 (Tappo)**: impedisce che il pubblico veda il desktop Linux anche in caso di stop o file danneggiati.
Quando usi il **Tappo Predefinito**, BlindCue proietta attorno al proprio logo un **reticolo tecnico scuro** studiato per allineare il videoproiettore senza illuminare eccessivamente il palco:
- **Cornice cyan a `0px` e angoli Ambra/Verde**: toccano esattamente gli ultimi pixel proiettati; se un angolo o un'etichetta (`▲ ALTO / TOP ▲`, `▼ BASSO ▼`, `◀ SX`, `DX ▶`) risulta tagliata, il proiettore sta sbordando dallo schermo.
- **Doppi cerchi concentrici e diagonali**: se il cerchio appare ovale o le diagonali non sono simmetriche, il proiettore ha inclinazione trapezoidale (*keystone*) o aspect ratio errato.
- **Lettura risoluzione in basso a destra**: mostra in tempo reale risoluzione esatta e rapporto d'aspetto ricevuti dal proiettore (es. `L0 TAPPO • 1920×1080 (16:9)`).

<details>
<summary>▶ Come sostituire il Tappo con la locandina dello spettacolo (e come ripristinarlo)</summary>

1. Nel pannello **Live Output Status** (o dal menu `Show`), clicca **`📁 Cambia Tappo…`**.
2. Scegli un'immagine (`.png`, `.jpg`, ecc.) con logo festival, locandina o fondo nero personalizzato.
3. Il percorso viene salvato nel file `.blindcue` del progetto.
4. Per tornare al reticolo di calibrazione con il logo BlindCue, premi **`🔄 Reset`**.

</details>

[↑ Indice](#indice) · [Sezione Successiva: Modalità Progetto vs LIVE →](#sec-2)

---

<a id="sec-2"></a>

## 2. Le Due Interfacce: Modalità Progetto vs Modalità LIVE

BlindCue separa nettamente la fase di **Programmazione** dalla fase di **Spettacolo** tramite commutazione istantanea (`< 1 ms`, **zero interruzioni** ai media già attivi):

- **🛠 Modalità Progetto**: è l'area di lavoro a **3+3 settori fissi** (`Scaletta` · `Pre-Viz 16:9` · `Ispettore` sopra; `Forma d'Onda` · `Live Output Status` · `Drag&Drop` sotto).
  - I pannelli partono con **`🔒 Pannelli Bloccati`** per impedire deformazioni involontarie cliccando i bordi; dal menu `View` → *Blocca Larghezza Pannelli* puoi sbloccarli temporaneamente o scegliere *Ripristina Larghezze Standard*.
- **🎭 Modalità LIVE (`[F5]` o `[Ctrl+L]` o tasto `▶ VAI IN LIVE` in cima alla Scaletta)**:
  - Nasconde ispettore, forma d'onda e Pre-Viz per dare **massimo spazio alla Scaletta a 6 colonne** (con Note di Regia, Tempi e Stati ben leggibili anche da lontano).
  - Blocca automaticamente le scorciatoie distruttive (`Canc`, spostamenti `Alt+↑/↓`, modifica inline e Undo) per prevenire errori al buio.
  - Puoi cliccare **`← 🛠 Torna a Progetto [F5]`** in alto a sinistra in qualunque istante se occorre ritoccare una cue al volo.

[↑ Indice](#indice) · [← Precedente](#sec-1) · [Sezione Successiva: Scaletta & Batch →](#sec-3)

---

<a id="sec-3"></a>

## 3. Gestione Scaletta, Note, Codici `Q` & Selezione Multipla

- **Aggiungere file**: usa **`+ Video`**, **`+ Audio`**, **`+ Immagine`** oppure trascina uno o più file nell'area tratteggiata **Caricamento Rapido**.
- **Rinomina e Richiamo Copione (`Q`)**:
  - Fai **doppio clic** sulla colonna **`Q`** (es. `Q-12a`) o sul **Nome** (oppure seleziona e premi **`[F2]`**).
  - Doppio clic sulla colonna `#` (numero progressivo) manda direttamente in **`GO`** quella riga.
  - Il **Focus Guard** disattiva `Spazio` e scorciatoie mentre stai scrivendo dentro un campo di testo.
- **Note di Regia**: scrivile nell'Ispettore; nella Scaletta Progetto appare l'icona `📝` (visibile intera al passaggio del mouse), mentre in **Modalità LIVE** le Note hanno un'intera colonna dedicata sempre leggibile.
- **Selezione Multipla (`Ctrl+Click` o `Shift+Click`)**: selezionando più cue dello stesso tipo (es. 5 Immagini o 4 Audio), l'Ispettore abilita la modifica simultanea dei soli parametri comuni (`Layer`, `Opacità`, `Scala`, `Pre-Delay`, `Post-Delay`, `Fade`, ecc.), lasciando intatti i nomi individuali.
- **Undo / Redo (`Ctrl+Z` / `Ctrl+Y`)**: fino a `40` passaggi di annullamento protetti da debounce (`450ms`), senza mai toccare eventuali cue già in onda.

[↑ Indice](#indice) · [← Precedente](#sec-2) · [Sezione Successiva: Layer di Compositing →](#sec-4)

---

<a id="sec-4"></a>

## 4. I 3 Layer di Compositing (`L1`, `L2`, `L3`)

Ogni cue è indirizzata a uno dei 3 livelli indipendenti selezionabili nell'**Ispettore Cue** (default per tutte: **`L1: Sfondo`**):

```text
┌──────────────────────────────────────────────────────────┐
│  L3: Overlay      (in alto nel monitor Live — sovrimp.)  │
│  L2: Principale   (al centro — contenuti in primo piano) │
│  L1: Sfondo       (in basso — base video/foto/musica)    │
├──────────────────────────────────────────────────────────┤
│  L0: Tappo        (fondo permanente di sicurezza)        │
└──────────────────────────────────────────────────────────┘
```

- **Indipendenza totale**: mandare una cue su `L2` **non interrompe** ciò che sta suonando/scorrendo su `L1` o `L3`. Mandare una nuova cue su `L1` sostituisce **solo** il contenuto precedente di `L1`.
- Nel pannello **Live Output Status**, l'ordine verticale rispecchia la pila fisica reale (`L3` in alto → `L1` in basso).

<details>
<summary>▶ Esempio pratico: Musica + Video di sfondo + Titolo sovrapposto</summary>

1. Metti un Video loop o un'Immagine di fondo su **L1 (`Sfondo`)**.
2. Carica la traccia musicale di sottofondo su **L2 (`Principale`)** — il layer gestisce solo l'audio senza toccare l'immagine su L1!
3. Carica un PNG trasparente con il titolo dello spettacolo su **L3 (`Overlay`)** con `Pre-Delay = 3.0s` — apparirà sopra il video di L1 mentre suona la musica di L2.

</details>

[↑ Indice](#indice) · [← Precedente](#sec-3) · [Sezione Successiva: Posizione, Zoom & Crop →](#sec-5)

---

<a id="sec-5"></a>

## 5. Ispettore Cue: Posizione, Zoom, Aspect Ratio & Ritaglio (`%` / `px`)

Nell'**Ispettore Cue** (e direttamente sul monitor **Pre-Viz 16:9**):
- **Posizione (`Pos X`, `Pos Y`)**: muovi con i numeri, usa i 4 tasti freccia *nudge* + `⊕ Centro`, oppure **trascina il media con il mouse** direttamente dentro il monitor di anteprima 16:9.
- **Scala / Zoom (`0.1x – 3.0x`)** e **Opacità (`0% – 100%`)**: ogni cursore ha il pulsante reset individuale `↺`.
- **Formato (`Aspect Ratio`)**: `Nativo`, `16:9`, `4:3`, `21:9`, `1:1` — ridimensiona la proporzione del riquadro prima dell'eventuale ritaglio.
- **Ritaglio (`Crop`) in `%` oppure `px`**:
  - Commuta tra **Percentuale (`%`)** e **Pixel reali (`px`)** rispetto alla risoluzione del file (es. `1920×1080 px`).
  - **Ritaglio ancorato ai bordi**: tagliando il lato destro o superiore il media resta fermo nello spazio di scena invece di ricentrarsi (mostrando esattamente quale porzione viene tagliata via).
  - Puoi anche tirare le **8 maniglie bianche/cyan** direttamente sui bordi e sugli angoli nel monitor Pre-Viz.

[↑ Indice](#indice) · [← Precedente](#sec-4) · [Sezione Successiva: Pre-Viz & Mirror →](#sec-6)

---

<a id="sec-6"></a>

## 6. Anteprima Pre-Viz Isolata & `MIRROR LIVE`

Il pannello centrale **Anteprima Pre-Viz (Sandbox)** è completamente scollegato dall'uscita pubblica:
- **Sicurezza Audio**: all'avvio il pulsante **`🔒 MUTE: ON`** garantisce il silenzio assoluto. Sbloccalo per ascoltare in cuffia durante la preparazione; per file Audio mostra barre animate di livello.
- **Controlli `▶ Play` / `⏸ Pausa` / `■ Stop`**: collaudano trim `IN/OUT`, curve di Fade, keyframe Volume/Opacità e Sezioni virtuali **senza andare in sala**.
- **`🔗 MIRROR LIVE` (`OFF` / `🔴 MIRROR: ON`)**:
  - In fase di allestimento o puntamento scenico, attiva **`MIRROR LIVE`**: la cue selezionata in standby viene proiettata immediatamente sul proiettore sul suo Layer di destinazione (funziona sia per le **Foto** sia per i **Video** tramite il frame decodificato in Pre-Viz — nessuno schermo nero e nessun audio in sala!).
  - Muovendo `Crop`, `Scala`, `Pos X/Y` o premendo Play/Scrub in Pre-Viz vedi le modifiche dal vivo sulla scenografia.
  - Quando premi di nuovo **`MIRROR: ON`** per disattivarlo, l'uscita esterna ripristina esattamente solo le cue già in `LIVE` (o il Layer 0 Tappo).

[↑ Indice](#indice) · [← Precedente](#sec-5) · [Sezione Successiva: Forma d'Onda & Inviluppi →](#sec-7)

---

<a id="sec-7"></a>

## 7. Forma d'Onda, Zoom, Fade & Inviluppi (Volume / Opacità)

Il pannello **Forma d'Onda e Automazioni** lavora in alta risoluzione (fino a `3200+` campioni estratti in background con FFmpeg + NumPy):

- **Zoom & Pan Orizzontale (`1.0×` – `32.0×`)**:
  - Usa la **rotella del mouse** sopra il grafico per zoomare sul punto del cursore, **`−` / `3.0×` / `+`** in alto a destra, oppure fai clic sul valore `3.0×` / doppio clic per ripristinare `1.0×`.
  - Quando lo zoom supera `1.0×` appare la barra di scorrimento orizzontale sotto al grafico; puoi scorrere anche con `Shift + Rotella` o trascinando con il tasto centrale del mouse.
- **Testina di Lettura & Snap `IN / OUT`**:
  - Clicca o trascina nella parte superiore della forma d'onda per spostare la **testina gialla (`Testina: 00:02.35`)**.
  - Usa **`↦ IN Testina`** (`[I]`) e **`OUT Testina ↤`** (`[O]`) per fissare i tagli esattamente sul punto d'ascolto corrente, oppure **`⟲ Reset IN/OUT`** per ripristinare l'intero file.
- **Rampe Fade IN / Fade OUT**:
  - Trascina i **pallini verde (Fade IN)** e **corallo (Fade OUT)** direttamente sull'onda e scegli il profilo nel menu a tendina (**`Log`**, **`S-Curve`**, **`Linear`**).
- **Linea Orizzontale & Keyframe Volume / Opacità**:
  - Per i **Video**, il selettore in alto a destra commuta tra **`🔊 Volume`** e **`👁 Opacità`**.
  - Per le **Immagini** (anche con durata infinita!), la timeline diventa automaticamente un **editor Opacità** con orizzonte temporale regolabile (`5s`, `10s`, `20s`, `30s`, `60s`), testabile col `▶ Play` di Pre-Viz.
  - **Doppio clic** sulla linea orizzontale crea un punto di controllo (keyframe), **trascinalo** per creare abbassamenti di musica sotto una voce o dissolvenze intermedie, **tasto destro sul punto** lo elimina (oppure `Reset Punti`).

<details>
<summary>▶ Esempio pratico: Abbassare la musica sotto un dialogo (Ducking)</summary>

1. Seleziona il brano audio e premi **`▶ Play`** in Pre-Viz finché arriva il punto in cui entra l'attore.
2. Fai **doppio clic** sulla linea orizzontale del Volume prima del dialogo (rimane al 100%) e **doppio clic** mezzo secondo dopo abbassando il punto al `25%`.
3. A fine battuta crea un altro nodo al `25%` seguito da un nodo di risalita al `100%`.
4. Durante il Live il volume si abbasserà e rialzerà da solo con precisione al millisecondo!

</details>

[↑ Indice](#indice) · [← Precedente](#sec-6) · [Sezione Successiva: Sezioni Virtuali A/B/C →](#sec-8)

---

<a id="sec-8"></a>

## 8. Sezioni Virtuali (`A`, `B`, `C`…) e Loop Dinamici

Sui file **Audio** e **Video** puoi suddividere virtualmente la traccia senza tagliare il file su disco:
- **Creare sezioni**: porta la testina nel punto di stacco e clicca **`✂ Dividi`**. La timeline si divide nei blocchi colorati **`A`**, **`B`**, **`C`…**; puoi trascinare i divisori verticali tratteggiati per affinare i punti di giunzione.
- **Impostare le ripetizioni**: nella barra sotto la forma d'onda, ogni sezione ha il suo menu (`x1`, `x2`, `x3`, `x4`, `x5`, `x8`, **`∞` Loop infinito**, **`Salta`** per bypassarla al volo).
- **Navigare ed uscire dal loop in diretta**:
  - Clicca sul badge lettera **`A`**, **`B`**, **`C`** per saltare istantaneamente a quella sezione (in Pre-Viz o in Live se la cue è in onda).
  - Durante un loop infinito (`∞` *vamp* su scena parlata), premi **`⏭ Esci da Loop`** (disponibile sia sulla toolbar della forma d'onda sia nella barra Standby della Modalità LIVE): la traccia completerà la misura/ripetizione corrente o passerà in modo pulito alla sezione successiva!
  - Nei **Video**, BlindCue pre-carica silenziosamente la destinazione su un **secondo deck video dedicato** così i cambi/loop di sezione riducono al minimo gli scatti.
- **`⟲ Reset Sez.`**: elimina tutte le suddivisioni ripristinando il file intero (annullabile con `Ctrl+Z`).

[↑ Indice](#indice) · [← Precedente](#sec-7) · [Sezione Successiva: Tempi & 3 Modalità Sequenza →](#sec-9)

---

<a id="sec-9"></a>

## 9. Tempi di Regia (`Pre-Delay`, `Durata`, `Post-Delay`) & 3 Modalità di Sequenza

Ogni cue dispone di tre tempi in sequenza temporale:

```text
GO ──► [ Pre-Delay ] ──► [ Riproduzione / Durata Img ] ──► [ Post-Delay ] ──► Fine Cue
       (attende a          (file su schermo / audio)         (mantiene ultimo      │
        partire)                                              frame / stato)       ▼
                                                                             (se Auto-GO:
                                                                              lancia la seguente!)
```

- **`Pre-Delay`**: ritarda la partenza della cue dopo il `GO` (il countdown compare in cyan `⏳ PRE` sulla barra live senza toccare l'uscita prima dello scadere).
- **`Durata`** (`hold_time` sulle immagini oppure durata file `[IN..OUT]` su audio/video).
- **`Post-Delay`**: una volta finito il file o scaduta la durata immagine, **trattiene la cue ancora in onda** (ultimo frame per video, immagine fissa sul layer, countdown viola `⏱ POST`) prima di chiudere il layer e passare oltre.

### I 3 Pulsanti in fondo alla Scaletta (Salvati per ogni Cue)

1. **`⏹ Blocco`** *(Default)*: esegue la cue (`Pre → Durata → Post`) e si ferma. Lo spettacolo aspetta il tuo `GO`.
2. **`⤵ Auto-GO`**: conclusi `Pre + Durata + Post` di questa cue, BlindCue preme **automaticamente `GO`** sulla riga successiva. *(Sulle Immagini assicurati di impostare una `Durata Img > 0`, altrimenti resteranno infinite.)*
3. **`⇉ Simultanea`**: premendo `GO` su questa cue, **parte istantaneamente insieme anche la cue successiva**, che rispetterà il proprio `Pre-Delay` per entrare al secondo esatto!

<details>
<summary>▶ Ricetta Pratica: Musica immediata su L1 + Titolo dopo 4s su L2 + Chiusura automatica</summary>

1. **Cue #1 (`sigla.wav`, L1)**: `Pre-Delay = 0s` → seleziona **`⇉ Simultanea`**.
2. **Cue #2 (`titolo.png`, L2)**: `Pre-Delay = 4.0s`, `Durata Img = 6.0s`, `Post-Delay = 1.5s` → seleziona **`⤵ Auto-GO`**.
3. **Cue #3 (`scena1.mp4`, L1)**: `Pre-Delay = 0s` → seleziona **`⏹ Blocco`**.
4. Premi **un solo `GO`** su #1: la musica parte subito (`t=0`), la Standby salta a #3, a `t=4.0s` appare il titolo su L2, dura `6.0s`, rimane altri `1.5s` in Post-Delay e a `t=11.5s` esce lanciando da solo `scena1.mp4`!

</details>

[↑ Indice](#indice) · [← Precedente](#sec-8) · [Sezione Successiva: Regia Live, Pausa & PANIC →](#sec-10)

---

<a id="sec-10"></a>

## 10. Operatività in Diretta (`Show Mode`), Barre Live, Pausa Tutto & `PANIC`

### Leggere le Barre dei Layer (`L3 → L2 → L1`)
Ogni barra mostra in un colpo solo:
- **Sinistra**: tempo trascorso live (`01:24`, oppure `⏳ PRE` / `⏱ POST`).
- **Centro**: nome file in riproduzione (`⏸` se in pausa).
- **Destra**: conto alla rovescia rimanente (`-00:41`), colorato in **ambra sotto i 12s**, **rosso sotto i 5s**, oppure con **`∞`** se ha loop infinito.
- **Riempimento**: barra progressiva verde smeraldo (ambra in pausa, cyan in Pre-Delay, viola in Post-Delay).
- **Tasto circolare `⏸ / ▶`** (solo su Audio/Video): mette in pausa/riprende il singolo layer per comodità durante le prove.
- **`✕ Cut L3/L2/L1`**: arresta subito solo quel livello con micro-fade anti-pop.

### I Controlli Globali di Spettacolo (Modalità LIVE)
- **Orologio centrato & Cronometro Spettacolo (`⏱ 00:00:00` + `↺` in alto a destra)**:
  - **Avvio automatico**: appena lanci il **1° `GO`** dello spettacolo (anche con `Pre-Delay`), il cronometro parte automaticamente senza togliere attenzione dalla regia.
  - **Controllo manuale per prove e filate**: puoi cliccare direttamente sul cronometro **prima** del primo GO (es. all'ingresso attori o sull'attacco di una battuta recitata) per avviarlo subito, cliccarlo per metterlo in **PAUSA** (diventa ambra, senza fermare audio o video), ricliccarlo per **RIPRENDERE** o premere **`↺`** per azzerarlo e riarmarlo per la prova successiva.
- **`GO` (`[Spazio]`)**: lancia la cue in Standby (riportata sul tasto stesso e sul banner giallo).
- **`⏸ PAUSA TUTTO` ↔ `▶ RIPRENDI TUTTO`**: se il regista ferma la prova o c'è un imprevisto sul palco, un clic congela simultaneamente tutti i layer Audio/Video attivi, i timer Immagini e tutti i conti alla rovescia `Pre/Post-Delay`, trasformando il tasto in ambra acceso **`▶ RIPRENDI TUTTO`** per riprendere esattamente dallo stesso millisecondo.
- **`🚨 PANIC — STOP TOTALE` (`[ESC]` in Modalità LIVE)**: pulsante rosso in alto a destra lontano da `GO`. Interrompe all'istante (`0ms`) ogni audio, video e timer:
  - Se Layer 0 usa la griglia di calibrazione predefinita, **oscura a Nero puro (`#000000`)** per non mostrare linee tecniche al pubblico.
  - Se hai caricato un **Tappo personalizzato** (logo festival/sipario nero), mostra subito quello.
  - *(Nota: la sfumatura morbida `0.2s` verso Layer 0 / Blackout resta comunque sempre disponibile con `[Ctrl+B]` o dal pannello Live Output Status in Modalità Progetto.)*

[↑ Indice](#indice) · [← Precedente](#sec-9) · [Sezione Successiva: Salvataggi Atomici & Setup Linux →](#sec-11)

---

<a id="sec-11"></a>

## 11. Salvataggi `.blindcue`, Crash Recovery & Setup Linux/Wayland

### Salvataggio Atomico & Ripristino d'Emergenza
- Ogni file `.blindcue` è JSON leggero salvato in RAM ed ispezionabile come testo.
- Ogni scrittura (`Salva`, autosave ogni `30s` e ad ogni `GO`) usa file temporaneo + `fsync` + `os.replace` POSIX: anche se salta la corrente elettrica, il file precedente non viene mai troncato.
- Al riavvio dopo uno spegnimento anomalo, BlindCue propone il recupero automatico dall'ultimo snapshot di autosave (`~/.config/blindcue/autosave.json`).

<details>
<summary>▶ Installazione Multi-Distro & Avvio</summary>

#### Pacchetti di Sistema
- **Arch Linux / EndeavourOS / Manjaro**: `sudo pacman -S --needed ffmpeg python python-pip python-virtualenv mesa-utils`
- **Debian 12+ / Ubuntu 22.04+ / Mint**: `sudo apt update && sudo apt install -y ffmpeg python3 python3-pip python3-venv build-essential mesa-utils`
- **Fedora 39+**: `sudo dnf install -y ffmpeg python3 python3-pip python3-virtualenv mesa-demos`

#### Script Automatico & Avvio
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```
*(In `blindcue/requirements.txt` sono richieste solo `PySide6>=6.5` e `numpy>=1.24`.)*

</details>

<details>
<summary>▶ Tabella Ottimizzazioni Linux Consigliate per il Palco</summary>

| Ottimizzazione | Stato | Come applicarla | Perché serve |
|----------------|-------|-----------------|--------------|
| **Locale POSIX (`LC_NUMERIC=C`)** | **Automatica** | Inclusa in `run.sh` e `main.py` | Evita conflitti tra punto e virgola decimale sui sistemi IT |
| **Disattiva Sleep / Blocco Schermo** | **Obbligatoria in Live** | Impostazioni GNOME / KDE / Hyprland | Evita spegnimento monitor o sospensione durante lo spettacolo |
| **Governor CPU `performance`** | **Consigliata** | `sudo cpupower frequency-set -g performance` | Azzeramento micro-latenze di risveglio CPU |
| **Accelerazione GPU (`VA-API` / `NVDEC`)** | **Rilevata in automatico** | Verificabile in `Help → Info Hardware` | Mantiene il carico CPU tipicamente sotto il `5–8%` |
| **Priorità processo (`nice`)** | **Facoltativa** | `nice -n -5 ./run.sh` | Priorità alta al processo di regia rispetto ai servizi di sfondo |

</details>

[↑ Torna all'Indice Interattivo](#indice) · [Torna al README](../README.md)
