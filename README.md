# 🎬 BlindCue — Live Multimedia Cue Player per Linux

<p align="center">
  <img src="immagini di progetto/BlindCue-logo.jpeg" alt="BlindCue Logo" width="170"/>
</p>

<p align="center">
  <b>Regia Video, Audio e Immagini a bassa latenza per teatro, eventi live e broadcast su Linux.</b><br/>
  <i>100% Wayland Nativo (PySide6 QtMultimedia + FFmpeg) • 3 Layer Compositing + Layer 0 Calibrazione • Modalità Progetto & Modalità LIVE • Pre/Post-Delay & Sezioni Virtuali</i>
</p>

> [!NOTE]
> **Stato del progetto:** software in sviluppo attivo ma già concreto e operativo end-to-end per prove e spettacoli.
> 📖 Per imparare tutte le funzioni passo-passo vai al **[Manuale Operativo Interattivo](docs/GUIDA_IMPLEMENTAZIONE_LINUX.md)**.
> 🧩 Per capire il codice file per file vai all'**[Architettura e Mappa dei Moduli](docs/ARCHITETTURA_E_MODULI.md)**.

---

## 📌 Indice

- [Cos'è BlindCue e Perché Nasce](#cose-blindcue)
- [Due Modalità Operative: Progetto & LIVE](#due-modalita)
- [Funzionalità Implementate](#funzionalita)
- [Compositing a 3 Livelli + Layer 0 Tappo](#compositing)
- [Installazione e Avvio Rapido](#installazione)
- [Scorciatoie da Tastiera](#scorciatoie)
- [Struttura Reale del Progetto](#struttura)
- [Documentazione & Licenza](#documentazione)

---

<a id="cose-blindcue"></a>

## 🎯 Cos'è BlindCue e Perché Nasce

Negli spettacoli dal vivo, **il software non si può bloccare mai** e il pubblico **non deve mai vedere il desktop del PC**, errori di sistema o stacchi bruschi.

BlindCue separa completamente ciò che vede e sente il tecnico sul **monitor primario (Regia / Sandbox Pre-Viz)** da ciò che esce verso la sala sul **proiettore secondario (Output Window Wayland borderless)**, sfruttando la decodifica C++/GPU nativa di QtMultimedia e FFmpeg orchestrata da un layer di controllo Python snello (< 0.05 ms di latenza comando).

---

<a id="due-modalita"></a>

## 🔀 Due Modalità Operative: Progetto & LIVE

Dalla cima della Scaletta (`▶ VAI IN LIVE`) oppure con **`[F5]`** / **`[Ctrl+L]`** puoi commutare istantaneamente tra le due viste **senza interrompere audio, video o immagini in esecuzione**:

1. **🛠 Modalità Progetto (Programmazione & Allestimento)**
   - Interfaccia a 6 pannelli proporzionati e bloccabili (`🔒 Pannelli Bloccati` / `🔓 Sbloccabili`): **Scaletta Cue**, **Anteprima Pre-Viz 16:9**, **Ispettore Cue** sopra; **Forma d'Onda & Automazioni**, **Live Output Status**, **Drag & Drop** sotto.
   - Pensata per tagliare, croppare, disegnare inviluppi, creare sezioni e provare in cuffia in totale isolamento.
2. **🎭 Modalità LIVE (Show Mode — Esecuzione Spettacolo)**
   - Schermata teatrale ad altissima leggibilità dominata dalla **Scaletta LIVE estesa a 6 colonne** con rendering grafico custom pixel-perfect:
     - **Colonna `#`**: barra luminosa verticale verde neon (`● LIVE`) o oro ambra (`▶ STANDBY`), nastro con colore personalizzato cue, freccia `▶`/`▼` per gruppi e binari di collegamento a catena (`Auto-GO` e `Simultanee`) con frecce direzionali.
     - **Colonna `Q`**: richiamo copione in capsula ciano scuro (`#082f49`) ad alto contrasto.
     - **Colonna `Media / Titolo Cue`**: badge arrotondati dedicati (`VID`, `AUD`, `IMG`, `GRP`), indentazione ad albero con rami gerarchici (`├── `, `└── `), titolo ad alta visibilità, pillole di sezione `[N sez.]`, badge `🔁 LOOP`, e pillole modalità scena (`⇉ SIMULT`, `⤵ CASCATA`, `⏹ PASSO`, `🎲 RND`, `🔁 LOOP`) con conteggio cue interne.
     - **Colonna `Note di Regia`**: icona taccuino `📝`, testo sempre visibile e avviso in capsula ambra per parole chiave urgenti di regia (`ATTENZIONE`, `BUIO TOTALE`, `EMERGENZA`, `PERICOLO`).
     - **Colonna `Tempi · Sequenza`**: pillola `Pre +X.Xs` ambra, durata calcolata/stimata in monospace bold, pillola `Post +X.Xs` viola e pillola modalità avanzamento (`⏹ MANUALE`, `⤵ AUTO-GO`, `⇉ SIMULT`).
     - **Colonna `Layer · Stato`**: capsula layer `L1`/`L2`/`L3`/`GRP` e badge di stato dinamico (`● LIVE` verde smeraldo, `⏳ ATTESA` ciano, `▶ STANDBY` oro ambra, `PRONTO` ardesia).
     - **Lavaggio a Colori & Divisori di Scena**: l'intero sfondo della riga riceve la tinta della cue con linee divisorie sottili al cambio di colore/capitolo.
     - **Hero Bar Standby**: prompter panoramico ad alta leggibilità con capsula ambra `▶ STANDBY`, nome cue, layer, tipo media, avviso di pre-delay/auto-follow e note di regia.
     - **Controllo da Tastiera & Menu Contestuale Pro**: Spazio lancia il GO, Esc attiva il PANIC, frecce Su/Giù scorrono lo Standby, doppio clic esegue la cue istantaneamente, tasto destro apre il menu contestuale per salto rapido (`GO Forzato`, `Imposta Standby`, `Espandi/Collassa`).
     - **Ora esatta di sistema centrata** e **Cronometro Spettacolo (`⏱`)** in alto a destra (avvio automatico al 1° `GO` o manuale per le filate + reset `↺`).
     - Blocca le scorciatoie di modifica/cancellazione accidentale ed evidenzia i soli comandi essenziali di regia: **`GO [SPAZIO]`**, **`⏸ PAUSA TUTTO` / `▶ RIPRENDI TUTTO`** e **`🚨 PANIC [ESC]`** in alto a destra lontano da `GO`.

---

<a id="funzionalita"></a>

## ⚙️ Funzionalità Implementate

- **Doppio Motore Isolato (Live vs Pre-Viz) & Routing Audio / Video**:
  - 3 player indipendenti (`L1`, `L2`, `L3`) per l'uscita pubblica e 1 player `TestPlayer` muto di default per collaudare in cuffia (`MUTE ON/OFF`).
  - **Pannello `⚙️ Dispositivi · Uscite`**: assegna l'uscita **Master Sala (PA)** e il **Monitor Cuffia Tecnico (PFL)** su schede audio diverse, seleziona il monitor/proiettore a caldo e imposta il profilo prestazionale (`Auto`, `🍃 Eco` per portatili datati o `🚀 Performance`).
  - **Protezione Live GC (`ShowRuntimeGuard`)**: sospende i cicli pesanti del Garbage Collector durante la Modalità LIVE per garantire zero micro-lag sulle Cue.
- **Pre-Viz 16:9 WYSIWYG + `MIRROR LIVE` Foto & Video**:
  - Trascinamento diretto posizione, **8 maniglie per ritaglio sul frame**, equalizer audio animato.
  - Attivando **`MIRROR LIVE`**, le regolazioni su Foto **e Video in Standby** si vedono in tempo reale sul proiettore esterno senza emettere audio in sala.
- **Gruppi e Scene Teatrali Collassabili (`Ctrl+G` o `+ Gruppo`)**:
  - Raggruppa più cue eterogenee (Audio, Video, Immagini) in un contenitore di scena con colore personalizzato e albero gerarchico grafico (`├── `, `└── `).
  - **Espansione / Collasso istantaneo (`▶`/`▼`)** sia in Vista Progetto che nella Scaletta LIVE estesa per mantenere scalette lunghe pulite e leggibili.
  - **5 Modalità di esecuzione avanzate**:
    - `⇉ Simultaneo` (Fire All: tutti i media partono insieme sul GO).
    - `⤵ Sequenziale` (Cascata continua con rispetto dei ritardi Pre/Post).
    - `⏹ Passo-Passo` (Capitolo teatrale: ogni pressione del GO avanza di un elemento interno alla scena).
    - `🎲 Random` (Variazioni e scelte casuali anti-ripetizione immediata).
    - `🔁 Loop Scena` (Ciclo continuo degli elementi interni).
  - **Scheda dedicata nell'Ispettore (`📁 Gruppo · Scena`)**: riepilogo conteggio elementi, durata totale stimata, regolazione tempi Pre/Post-Wait, lista modificabile con rimozione rapida elemento (`✕`) e scioglimento gruppo (`🔓 Sciogli Gruppo`).
  - **Estrazione flessibile ed intuitiva di Cue da un Gruppo**:
    - **Scorciatoia universale `Ctrl+Shift+G`**: scioglie il gruppo se è selezionato il contenitore, oppure estrae la singola cue selezionata posizionandola subito all'esterno della scena.
    - **Menu Contestuale (Tasto Destro)**: opzione diretta `"⏏ Estrai dal Gruppo (Ctrl+Shift+G)"`.
    - **Pannello Ispettore (Scheda `🎯 Cue · Tempi`)**: banner informativo con pulsante rapido `"⏏ Estrai dal Gruppo"`.
    - **Spostamento intelligente (`Alt+▲` / `Alt+▼`)**: muovendo una cue oltre il limite superiore (sopra l'intestazione della scena) o inferiore del gruppo, la cue si sgancia automaticamente tornando a livello radice.
  - Auto-espansione automatica quando una cue interna diventa Standby o Live, garantendo la visibilità continua all'operatore.
- **Ispettore Cue a Schede (Linguette) & Modifiche Multi-Selezione**:
  - **Scheda `🎯 Cue · Tempi`**: richiamo copione `Q`, Nome, Note, **Colori Gruppo/Scena (con divisori visivi e binario sinistro grafico per cue collegate)**, selezione Layer (`L1`, `L2`, `L3`), **`Pre-Delay`**, **`Post-Delay`**, **`Durata Img`** e sequenza (`Blocco / Auto-GO / Simult.`).
  - **Scheda `🖼 Video · Foto`**: `Pos X/Y` + nudge/Centro, `Scala`, `Opacità`, `Formato`, **Crop in `%` o `px` reali** e guida contestuale.
  - **Scheda `🎵 Audio · Tagli`**: `Volume`, `Fade In/Out`, `IN/OUT` e `Loop` (`∞` o `N` ripetizioni).
  - Selezionando più cue dello stesso tipo puoi applicare modifiche batch in un colpo solo (tutto protetto da **Undo / Redo** fino a 40 step).
- **Forma d'Onda Pro (`Zoom 1.0×–32.0×`) & Editor Automazioni**:
  - Campionamento ad alta risoluzione in background su `QThreadPool` (FFmpeg PCM + NumPy fino a `3200+` picchi), zoom ancorato al cursore, pan con scrollbar/mouse.
  - Testina di lettura live, snap **`IN / OUT` a testina** (`[I]`/`[O]`), reset IN/OUT.
  - Pallini trascinabili di **Fade IN/OUT** con curve (`Log`, `S-Curve`, `Linear`).
  - **Linea grafica a keyframe per Volume Audio e Opacità** (attiva anche sulle **Immagini a durata infinita** con orizzonte temporale `5s–60s` ed anteprima Play dedicata).
- **Sezioni Virtuali `A / B / C...` & Doppio Deck Video**:
  - Taglio virtuale del file in blocchi colorati con tendina ripetizioni indipendente (`x1..x8`, `∞` loop infinito, `Salta`), salto diretto cliccando sul badge lettera e pulsante **`⏭ Esci da Loop`** durante lo spettacolo.
  - Sui video con loop/salti di sezione, `LivePlayer` utilizza un secondo `QMediaPlayer` secondario in pre-caricamento silenzioso per ridurre al minimo gli scatti visivi.
- **Tempi di Incastro & 3 Modalità di Avanzamento per Cue**:
  - Ogni cue gestisce **`Pre-Delay → Durata/Play → Post-Delay`** (trattiene l'uscita dopo la fine del file o del timer prima di liberare il layer).
  - Barra a 3 stati in Scaletta con suggerimenti a comparsa e tooltip: **`⏹ Blocco`** (default), **`⤵ Auto-GO`** (avvia la successiva alla fine di Pre+Durata+Post) e **`⇉ Simultanea`** (lancia insieme anche la successiva al proprio `Pre-Delay`).
- **Monitor Live Output Intuitivo (`L3 → L2 → L1`)**:
  - Stack verticale coerente con la sovrapposizione video (`L3` sopra `L2` sopra `L1`), barre con riempimento progressivo, **trascorso a sinistra**, **nome centrato**, **countdown a destra** (ambra `<12s`, rosso `<5s`, `∞` per loop), stati `⏳ PRE` / `⏱ POST`, tasto circolare `⏸/▶` di prova per singolo layer e `✕ Cut`.
- **Emergenza & Stabilità Assoluta**:
  - **Salvataggio `.blindcue` JSON atomico** in memoria (`tempfile` + `fsync` + `os.replace`), autosave ogni `30s` e **Crash Recovery** all'avvio.
  - **`Blackout [Ctrl+B]`** con micro-fade `0.2s` anti-pop verso Layer 0; **`PANIC [ESC]`** in Modalità LIVE a taglio istantaneo `0ms` su Nero puro `#000000` (se Layer 0 è la griglia tecnica) o sul Tappo personalizzato.

---

<a id="compositing"></a>

## 🖼️ Compositing a 3 Livelli + Layer 0 Tappo

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPOSIZIONE LIVE SU SCHERMO ESTERNO                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 3 (In alto)   │ Overlay, titoli, lower-third, sovrimpressioni    │
│  Layer 2 (Centro)    │ Contenuto principale secondario o foto in-frame  │
│  Layer 1 (In basso)  │ Sfondo scena, video base o traccia audio base    │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 0 (Failsafe)  │ Tappo predefinito con RETICOLO DI CALIBRAZIONE   │
│                      │ PROIETTORE (bordo 0px, angoli, cerchi keystone)  │
│                      │ oppure immagine personalizzata ("Cambia Tappo")  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

<a id="installazione"></a>

## 🚀 Installazione e Avvio Rapido

### Requisiti
- **OS**: Linux (Arch / EndeavourOS / Manjaro, Debian 12+, Ubuntu 22.04+, Fedora 39+)
- **Sessione**: Wayland nativo (compatibile anche con X11/Xwayland)
- **Dipendenze**: Python `>= 3.10`, `ffmpeg`, `ffprobe`, librerie Python in `blindcue/requirements.txt` (`PySide6>=6.5`, `numpy>=1.24`)

### Setup & Avvio
```bash
git clone https://github.com/diego-costanzo/BlinCUE.git
cd BlinCUE
chmod +x install.sh run.sh
./install.sh
./run.sh
```

> All'avvio `run.sh` attiva `.venv`, forza `LC_NUMERIC=C` per evitare errori sui separatori decimali e lancia `blindcue/main.py`.

---

<a id="scorciatoie"></a>

## ⌨️ Scorciatoie da Tastiera

| Tasto | Modalità Progetto | Modalità LIVE |
|-------|-------------------|---------------|
| <kbd>F5</kbd> / <kbd>Ctrl</kbd>+<kbd>L</kbd> | Passa a **Modalità LIVE** | Torna a **Modalità Progetto** |
| <kbd>Spazio</kbd> | **GO** *(bloccato mentre scrivi in caselle testo)* | **GO** (Avvia cue in Standby / catena Simultanea) |
| <kbd>Esc</kbd> | Ferma ascolto/anteprima **Pre-Viz** | **🚨 PANIC STOP TOTALE (0ms)** |
| <kbd>Ctrl</kbd> + <kbd>G</kbd> | **Crea Gruppo / Scena** (raggruppa selezione) | *(Disabilitato per sicurezza)* |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | **Blackout** con micro-fade `0.2s` verso Layer 0 | **Blackout** con micro-fade `0.2s` verso Layer 0 |
| <kbd>I</kbd> / <kbd>O</kbd> | Imposta `IN` / `OUT` alla testina nella waveform | *(Disabilitato per sicurezza)* |
| <kbd>F2</kbd> | Modifica inline `Q` / `Nome` | *(Disabilitato — sola lettura)* |
| <kbd>Canc</kbd> / <kbd>Alt</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd> | Elimina o sposta cue selezionata | *(Disabilitato per sicurezza)* |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> / <kbd>Ctrl</kbd> + <kbd>Y</kbd> | Undo / Redo (fino a 40 step) | *(Disabilitato in diretta)* |
| <kbd>Ctrl</kbd> + <kbd>N</kbd> / <kbd>O</kbd> / <kbd>S</kbd> | Nuovo / Apri / Salva show `.blindcue` | Nuovo / Apri / Salva show `.blindcue` |

---

<a id="struttura"></a>

## 📂 Struttura Reale del Progetto

```text
BlindCUE/
├── install.sh                          # Installer multi-distro (Arch, Debian/Ubuntu, Fedora + venv)
├── run.sh                              # Launcher applicazione (.venv + LC_NUMERIC=C)
├── README.md                           # Panoramica del progetto
├── docs/
│   ├── GUIDA_IMPLEMENTAZIONE_LINUX.md  # Manuale Operativo Interattivo per tecnici e registi
│   └── ARCHITETTURA_E_MODULI.md        # Spiegazione dettagliata file per file dell'intero codice
├── immagini di progetto/
│   └── BlindCue-logo.jpeg              # Logo ufficiale (base per icona app e Tappo Layer 0)
└── blindcue/
    ├── main.py                         # Entry point, bus segnali, routing monitor, runtime live
    ├── requirements.txt                # Dipendenze Python (PySide6>=6.5, numpy>=1.24)
    ├── models/
    │   ├── cue.py                      # Dataclass Cue, CueSection, FollowMode, serializzazione JSON
    │   └── project_manager.py          # Salvataggio atomico .blindcue, autosave 30s e crash recovery
    ├── engine/
    │   ├── player_live.py              # LivePlayer L1-L3 (QtMultimedia, dual-deck video, fade/inviluppi)
    │   ├── player_test.py              # TestPlayer Pre-Viz muto di default
    │   ├── audio_analyzer.py           # WaveformAnalyzer asincrono (ffprobe + ffmpeg + NumPy)
    │   ├── envelope.py                 # Matematica curve fade, keyframe & SectionSequencer (A/B/C...)
    │   └── show_scheduler.py           # ShowScheduler per Pre-Delay, Post-Delay e Pausa Tutto globale
    └── ui/
        ├── main_window.py              # Orchestratore principale (QStackedWidget Progetto ↔ LIVE)
        ├── output_window.py            # Finestra output Wayland (Layer 0 + L1-L3 + PANIC)
        ├── live_show_view.py           # Schermata dedicata Modalità LIVE (Scaletta estesa, GO, Pausa, PANIC)
        ├── live_status_panel.py        # Barre live progressive L3→L1, Pausa layer, PRE/POST, Cut, Tappo
        ├── cue_list_panel.py           # Pannello Scaletta Progetto, tasto VAI IN LIVE e selettore 3 modalità
        ├── cue_table.py                # Tabella cue (#, Q, Nome/Media) e delegate badge/note/link
        ├── inspector_panel.py          # Ispettore Cue (batch multi-selezione, crop %/px, Pre/Post-Delay)
        ├── preview_panel.py            # Intestazione e comandi trasporto Pre-Viz + toggle Mirror/Mute
        ├── preview_monitor.py          # Monitor 16:9 WYSIWYG (drag posizione, 8 maniglie crop, video mirror)
        ├── waveform_widget.py          # Timeline forma d'onda zoomabile, testina, fade e punti inviluppo
        ├── section_bar.py              # Barra sezioni virtuali (A, B, C...) sincronizzata con zoom/pan
        ├── tappo_pattern.py            # Generatore vettoriale griglia calibrazione proiettore su Layer 0
        ├── layout_math.py              # Matematica condivisa frame, aspect ratio e crop ancorato ai bordi
        ├── undo_manager.py             # Cronologia Undo/Redo leggera a snapshot (40 livelli)
        ├── spinboxes.py                # Spinbox decimali con +/- vettoriali e step intelligenti
        ├── drop_zone.py                # Area importazione rapida Drag & Drop
        ├── hardware_info.py            # Diagnostica CPU / GPU / VA-API / Wayland
        └── theme.py                    # Palette colori Pro Broadcast, stylesheet e formati media
```

---

<a id="documentazione"></a>

## 📄 Documentazione & Licenza

- **[Manuale Operativo Interattivo (`docs/GUIDA_IMPLEMENTAZIONE_LINUX.md`)](docs/GUIDA_IMPLEMENTAZIONE_LINUX.md)** — guida all'uso completa di tutte le funzionalità, trucchi di regia e ottimizzazioni Linux.
- **[Architettura e Spiegazione dei File (`docs/ARCHITETTURA_E_MODULI.md`)](docs/ARCHITETTURA_E_MODULI.md)** — mappa completa di ogni file Python e di come dialogano tra loro.

Progetto open source progettato per offrire massima velocità, semplicità operativa e solidità in scena.
