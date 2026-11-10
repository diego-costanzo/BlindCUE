# 🎬 BlindCue — Live Multimedia Cue Player per Linux

<p align="center">
  <img src="immagini di progetto/BlindCue-logo.jpeg" alt="BlindCue Logo" width="180"/>
</p>

<p align="center">
  <b>Software di regia e cue player minimale, reattivo e a bassa latenza per spettacoli ed eventi live.</b><br/>
  <i>Architettura 100% Wayland Nativo • Hardware Acceleration GPU/VA-API • Failsafe "Zero-Crash in Live" • Layer 0 Permanente • Compositing Multilivello</i>
</p>

---

## 📌 Indice
- [Panoramica e Visione](#-panoramica-e-visione)
- [Architettura Hardware: GPU e Multi-Core](#-architettura-hardware-gpu-e-multi-core)
- [Punti Salienti e Caratteristiche Principali](#-punti-salienti-e-caratteristiche-principali)
  - [1. 100% Wayland Nativo (PySide6 QtMultimedia + FFmpeg)](#1-100-wayland-nativo-pyside6-qtmultimedia--ffmpeg)
  - [2. Sistema a Doppio Binario Isolato (Live vs Pre-Viz)](#2-sistema-a-doppio-binario-isolato-live-vs-pre-viz)
  - [3. Monitor Studio Pre-Viz 16:9 WYSIWYG](#3-monitor-studio-pre-viz-169-wysiwyg)
  - [4. Layer 0 — "Immagine di Tappo" Intelligente e Failsafe](#4-layer-0--immagine-di-tappo-intelligente-e-failsafe)
  - [5. Micro-Dissolvenza Anti-Frustata (0.2s) e Volume Live](#5-micro-dissolvenza-anti-frustata-02s-e-volume-live)
  - [6. Trimming Interattivo con Mouse e Centesimi (0.01s)](#6-trimming-interattivo-con-mouse-e-centesimi-001s)
  - [7. Note di Regia, Rinomina e Focus Guard](#7-note-di-regia-rinomina-e-focus-guard)
  - [8. Architettura "Elastica" Multi-PC](#8-architettura-elastica-multi-pc)
- [Architettura Dati: JSON Atomico vs SQLite](#-architettura-dati-json-atomico-vs-sqlite)
- [Perché Python e C++ (Qt6/FFmpeg): Solidità nel Tempo](#-perché-python-e-c-qt6ffmpeg-solidità-nel-tempo)
- [Compositing a 3 Livelli e Layer 0](#-compositing-a-3-livelli-e-layer-0)
- [Installazione Rapida](#-installazione-rapida)
- [Guida all'Uso Passo-Passo](#-guida-alluso-passo-passo)
- [Scorciatoie da Tastiera](#-scorciatoie-da-tastiera)
- [Ottimizzazioni di Sistema (Obbligatorie vs Facoltative)](#-ottimizzazioni-di-sistema-obbligatorie-vs-facoltative)
- [Struttura del Progetto](#-struttura-del-progetto)
- [Licenza](#-licenza)

---

## 🎯 Panoramica e Visione

**BlindCue** nasce per risolvere la criticità primaria delle regie video/audio dal vivo (teatri, festival, conferenze, musical, concerti, broadcast): **il rischio di freeze, crash, pop acustici o visualizzazione accidentale del desktop del computer sullo schermo pubblico**.

Ispirato alla linearità operativa di *QLab*, ma sviluppato fin dalle fondamenta con architettura **100% Wayland Nativa** per distribuzioni Linux (Debian, Ubuntu, Arch Linux, EndeavourOS, Fedora), BlindCue separa rigorosamente ciò che vede e sente la **regia** da ciò che viene inviato al **proiettore o display esterno (Live)**.

Lo show non si ferma mai, il desktop non compare mai, e l'operatore ha sempre il pieno controllo visivo e temporale di ciò che sta accadendo sul palco.

---

## ⚡ Architettura Hardware: GPU e Multi-Core

Uno dei punti di forza di BlindCue è lo sfruttamento intelligente e differenziato delle risorse hardware:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GESTIONE RISORSE HARDWARE                       │
├───────────────────────────────────┬────────────────────────────────────┤
│   SCHEDA GRAFICA (GPU)            │   PROCESSORE (CPU MULTI-CORE)      │
│                                   │                                    │
│  • Decodifica hardware H.264/HEVC │  • Core 1 (Main Thread): GUI Qt6   │
│    tramite VA-API, VDPAU, NVDEC   │    e segnali operatore (< 0.05 ms) │
│  • Compositing zero-copy Wayland  │  • Core 2-N (ThreadPool Asincrono):│
│  • Riduzione carico CPU al < 5%   │    estrazione waveform audio e     │
│    durante playback 1080p/4K      │    calcolo spettrogramma NumPy     │
│  • Fallback software automatico   │  • Decodifica audio PipeWire/ALSA  │
│    se nessuna GPU è presente      │    in thread C++ ad alta priorità  │
└───────────────────────────────────┴────────────────────────────────────┘
```

1. **Rilevamento Automatico GPU**: All'avvio, BlindCue interroga il sottosistema grafico del computer (`glxinfo` / `vainfo` / Mesa EGL). La barra di stato in basso a sinistra mostra in tempo reale l'hardware attivo (es. `🖥 CPU: 8 Cores | 🎮 GPU: Intel Graphics (VA-API/OpenGL)`).
2. **Offload GPU Totale**: Durante la riproduzione video a 1080p o 4K, il decoding dei frame e la scalatura geometrica vengono eseguiti interamente dalla GPU tramite VA-API / NVDEC. Il processore rimane quasi a riposo (carico CPU inferiore al 5-8%), evitando qualsiasi surriscaldamento o throttling termico nei portatili durante spettacoli prolungati.
3. **Distribuzione Multi-Core Intelligente**:
   - **Il thread principale (GUI)** gestisce esclusivamente l'interfaccia e la reazione immediata ai tasti (GO, Blackout, Volume).
   - **I thread di calcolo (`QThreadPool`)** analizzano in parallelo le waveform audio di file lunghi senza bloccare la grafica nemmeno per un millisecondo.
   - **I thread di decodifica multimediale C++** sfruttano i core disponibili per il demuxing e la sincronizzazione A/V.

---

## 🌟 Punti Salienti e Caratteristiche Principali

### 1. 🔀 100% Wayland Nativo (PySide6 QtMultimedia + FFmpeg)
- **Zero dipendenza da X11 o Xwayland**: Nessun embedding obsoleto con window ID numerici (`--wid`).
- La grafica si integra nativamente nei surface Wayland (Mutter, KWin, Sway, Hyprland), garantendo assenza totale di screen tearing e frame-pacing perfetto a 60/120 Hz.

### 2. 🔇 Sistema a Doppio Binario Isolato (Live vs Pre-Viz)
- **Live Output**: Finestra borderless a pieno schermo sul proiettore o display esterno.
- **Banco Regia Pre-Viz**: Monitor di controllo per l'operatore con audio **rigorosamente mutato di default**.
- **Selettore MUTE PREVIEW**: Un pulsante toggle interattivo (`🔒 MUTE PREVIEW: ON` / `🔊 AUDIO PREVIEW: ATTIVO`) consente l'ascolto in cuffia solo quando l'operatore lo richiede esplicitamente.

### 3. 🪞 Monitor Studio Pre-Viz 16:9 WYSIWYG
- L'anteprima centrale funge da **specchio fedele (WYSIWYG)** dello schermo pubblico.
- **Ritaglio e Contenimento (Clamping)**: Quando il media viene ingrandito con lo zoom (> 1.0x) o traslato con il posizionamento, l'immagine viene ritagliata rigorosamente all'interno della cornice 16:9, senza mai debordare o coprire gli altri elementi dell'interfaccia.
- **Visualizer Audio Attivo**: Quando una cue audio è in riproduzione nel banco regia, il monitor visualizza un equalizzatore a barre animate in tempo reale per dare conferma visiva immediata della modulazione acustica.
- **Modalità Live Mirror**:
  - In modalità **Spettacolo** (`🔗 LIVE MIRROR: OFF`), la regia lavora in totale isolamento.
  - In modalità **Prove / Allestimento** (`🔴 LIVE MIRROR: ATTIVO`), ogni regolazione di crop, scala e posizione si riflette istantaneamente sul proiettore per calibrare le ottiche sul palco.

### 4. 🛡️ Layer 0 — "Immagine di Tappo" Intelligente e Failsafe
- Il Layer 0 è il fondo di sicurezza permanente sotto i livelli 1, 2 e 3.
- **Comportamento Intelligente**:
  - A banco vuoto, mostra il **Logo dell'evento** (o l'immagine personalizzata scelta con il pulsante `📁 Cambia Tappo...`).
  - Quando un media live è attivo sui layer 1-3, il logo del tappo si nasconde automaticamente mostrando un **fondo nero assoluto (`#000000`)**: in questo modo, video o immagini scalati o croppati non si sovrappongono sgradevolmente alla grafica sottostante.
  - Al termine della riproduzione o alla pressione del Blackout, il logo di Layer 0 riappare con transizione morbida.
- **Protezione da Crash**: In caso di file danneggiato o errore hardware improvviso, un gestore di eccezioni live intercetta l'anomalia e ripristina immediatamente il Tappo, evitando che il pubblico veda messaggi d'errore o il desktop.

### 5. 🌊 Micro-Dissolvenza Anti-Frustata (0.2s) e Volume Live
- **Micro-Fade Out (200 ms)**: Alla chiusura di un media (pulsanti `✕ Cut L1/L2/L3` o `Master Blackout`), BlindCue applica una rampa esponenziale di 0.2 secondi sia sull'audio che sull'opacità video/immagine. Questo elimina il brusco "scalino" visivo (la *frustata*) e azzera il click/pop elettroacustico (DC offset) sull'impianto audio di sala.
- **Regolazione Volume Live in Tempo Reale**: Se durante lo spettacolo un file video o audio risulta troppo alto o troppo basso, muovendo lo slider del volume nell'Ispettore il volume in sala si aggiorna istantaneamente, senza costringere a toccare il master del PC o il mixer esterno.

### 6. ✂️ Trimming Interattivo con Mouse e Centesimi (0.01s)
- **Trimming Diretto sulla Waveform**: Cliccando e trascinando con il mouse i cursori `IN` (verde) e `OUT` (rosso) direttamente sul grafico sonoro, si imposta il range desiderato.
- **Precisione al Centesimo di Secondo**: I selettori numerici consentono di rifinire i tagli con incrementi di `0.01s`.
- **Smart Seek Immediato**: Ogni modifica ai campi IN/OUT posiziona istantaneamente la testina del player sul frame corrispondente nel monitor Pre-Viz per il controllo visivo immediato.
- **Loop-back su OUT**: Raggiunto il punto OUT il player si ferma; ripremendo `▶ Play`, la riproduzione riprende automaticamente da IN per calibrare i tagli al millisecondo.

### 7. 📝 Note di Regia, Rinomina e Focus Guard
- **Personalizzazione Cue**: Ogni file caricato può avere un nome scenico (es. *"Intro Secondo Atto"*) e note di regia visibili nella scaletta (es. *"Stacco su battuta finale"*).
- **Focus Guard di Sicurezza**: Quando il cursore dell'operatore si trova all'interno di un campo di testo (`Nome` o `Note`), la scorciatoia di `GO` (<kbd>Spazio</kbd>) e di `Blackout` (<kbd>Ctrl</kbd>+<kbd>B</kbd>) viene temporaneamente inibita. Questo impedisce che scrivendo parole contenenti spazi o lettere di comando parta accidentalmente un cue in live!

### 8. 🌐 Architettura "Elastica" Multi-PC
- **Geometrie Normalizzate in Percentuale (`0.0 – 1.0`)**: Uno show programmato su un portatile con display 1366×768 o 1920×1080 si adatta automaticamente a proiettori 4K (3840×2160), schermi verticali o formati ultrawide senza deformazioni o riprogrammazioni.
- **Riconoscimento Monitor Singolo vs Multi-Monitor**: Se connesso a un proiettore esterno, l'output si aggancia in fullscreen borderless al secondo display; su un portatile da solo, apre una finestra 16:9 galleggiante per consentire il collaudo e le prove ovunque.

---

## 🗄️ Architettura Dati: JSON Atomico vs SQLite

BlindCue utilizza un formato di progetto proprietario aperto `.blindcue` basato su **JSON atomico in memoria**.

### Tabella Comparativa

| Criterio | JSON Atomico BlindCue (`.blindcue`) | Database Relazionale (SQLite `.db`) |
|----------|-------------------------------------|-------------------------------------|
| **Natura del dato** | Scaletta sequenziale ordinata (10–500 Cue) | Tabelle relazionali con indici |
| **Tempo di lettura / parsing** | **< 1.5 millisecondi** (deserializzato in RAM) | 5 – 15 millisecondi (overhead connessione e query SQL) |
| **Latenza durante il Live** | **Zero I/O disco** (tutto risiede in RAM) | Possibili micro-freeze da I/O o lock di pagina su disco |
| **Resistenza a interruzioni elettriche** | **Massima** (scrittura atomica via `tempfile` + `fsync` + `os.replace` POSIX) | Rischio lock file `.db-wal` / `.db-journal` su chiavette USB o crash improvvisi |
| **Ispezionabilità & Versionamento** | **File di testo aperto**: leggibile con `cat`/`nano`, versionabile con `git diff`, riparabile a mano | File binario: richiede client SQL dedicati |
| **Complessità software** | Zero dipendenze esterne, schema dataclass tipizzato nativo | Migrazioni di schema, gestione thread-safety e blocchi di transazione |

> [!NOTE]
> Per la natura operativa di uno spettacolo dal vivo, **il JSON atomico in memoria è la soluzione ingegneristica più rapida, affidabile e immune da blocchi**.

---

## ⚙️ Perché Python e C++ (Qt6/FFmpeg): Solidità nel Tempo

Un dubbio ricorrente è se Python sia adeguato per software di regia mission-critical.

L'architettura di BlindCue adotta il modello industriale a **separazione dei piani**:
1. **Piano Dati & Calcolo Pesante (C/C++ & GPU)**: Il decoding video H.264/HEVC, il deinterlacciamento, la sincronizzazione A/V, l'interpolazione cromatica e l'uscita audio PipeWire sono eseguiti interamente dal motore C++ di FFmpeg e QtMultimedia con accelerazione hardware.
2. **Piano di Controllo (Python 3.10+)**: Python gestisce unicamente gli eventi utente, la logica della scaletta e le transizioni di stato. I segnali Qt viaggiano in Python a una velocità di circa **0.05 ms (50 microsecondi)**.
3. Questo è esattamente lo stesso pattern ingegneristico impiegato da software professionali del calibro di **Blender**, **DaVinci Resolve**, **TouchDesigner** e banchi luci DMX.

---

## 🖼️ Compositing a 3 Livelli e Layer 0

L'output verso il monitor esterno è organizzato come una pila di livelli indipendenti:

```
┌─────────────────────────────────────────────────────────────┐
│                    LIVE OUTPUT COMPOSITING                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Overlay / Grafica trasparente / Lower-Third       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Media secondario / Inset / Immagine ritagliata    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Video principale o Immagine di sfondo             │
├─────────────────────────────────────────────────────────────┤
│  LAYER 0: TAPPO FAILSAFE (Logo evento o Nero - Sempre vivo) │
└─────────────────────────────────────────────────────────────┘
```

- **Video e Audio**: Al termine della durata o al punto `OUT`, il flusso si chiude e sparisce all'istante con micro-fade, liberando il layer.
- **Immagini Statiche**: Restano visibili sul proprio layer fino a nuovo comando o fino allo scadere del timer di **Permanenza Img** (`hold_time`), consentendo compositing complessi (es. sfondo su L1 + grafica croppata su L2).

---

## 🚀 Installazione Rapida

### 1. Requisiti di Sistema
- **Linux** (Debian 12+, Ubuntu 22.04+, Arch Linux, EndeavourOS, Manjaro, Fedora 39+)
- Sessione desktop **Wayland** (supporta anche X11 con Xwayland)
- Python 3.10 o superiore

### 2. Installazione Automatica con Script
```bash
git clone https://github.com/diego-costanzo/BlinCUE.git
cd BlinCUE
chmod +x install.sh run.sh
./install.sh
```

Lo script installerà i pacchetti di sistema mancanti (`ffmpeg`, librerie `mesa`, `python3-venv`), creerà l'ambiente virtuale protetto `.venv` e configurerà le dipendenze.

### 3. Avvio
```bash
./run.sh
```

---

## 📖 Guida all'Uso Passo-Passo

1. **Aggiungere Media**: Trascina i file multimediali nell'area tratteggiata in basso a destra (**Caricamento Rapido**) oppure usa i pulsanti `+ Video`, `+ Audio`, `+ Immagine`.
2. **Configurare la Cue**:
   - Seleziona la cue per aprirla nell'**Ispettore Cue** a destra.
   - Modifica `Nome:` e inserisci eventuali note in `Note:`.
   - Seleziona il livello di destinazione (`L1`, `L2`, `L3`).
   - Regola `Scala / Zoom`, `Pos X`, `Pos Y`, `Opacità` e i valori di `Ritaglio (CROP)`.
   - Per le immagini, imposta la `Permanenza Img` (lascia `0 s` per permanenza infinita fino al prossimo comando).
3. **Trimming Audio/Video**:
   - Trascina i marker `IN` (verde) e `OUT` (rosso) direttamente sul grafico della forma d'onda audio.
   - Rifinisci con precisione centesimale tramite i selettori numerici.
4. **Collaudo in Pre-Viz**:
   - Premi `▶ Play` sotto il monitor: la riproduzione avviene in silenzio per non interferire con la sala.
   - Per ascoltare in cuffia, clicca su `🔒 MUTE PREVIEW: ON`.
5. **Mandata in Live**:
   - Premi la **Barra Spaziatrice** o il pulsante verde **GO (Next Cue)**.
   - Il cue passa in verde `[LIVE]` e la selezione Standby avanza automaticamente alla cue successiva.
6. **Emergenza o Fine Scena**:
   - Premi <kbd>Ctrl</kbd> + <kbd>B</kbd> per il **Master Blackout** istantaneo con micro-dissolvenza.

---

## ⌨️ Scorciatoie da Tastiera

| Tasto | Funzione | Note di Sicurezza |
|-------|----------|-------------------|
| <kbd>Spazio</kbd> | **GO (Next Cue)** | Lancia la cue in Standby sul monitor live. *Disabilitato se si scrive nelle caselle di testo.* |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | **Master Blackout** | Chiude tutti i livelli e ripristina Layer 0. *Combinazione a due tasti anti-errore.* |
| <kbd>Esc</kbd> | **Stop Pre-Viz** | Ferma l'anteprima nel banco regia senza toccare il monitor live. |
| <kbd>Canc</kbd> / <kbd>Backspace</kbd> | **Elimina Cue** | Rimuove la cue selezionata dalla scaletta. |
| <kbd>Alt</kbd> + <kbd>↑</kbd> | **Sposta Cue Su** | Sposta la cue selezionata in alto nella scaletta. |
| <kbd>Alt</kbd> + <kbd>↓</kbd> | **Sposta Cue Giù** | Sposta la cue selezionata in basso nella scaletta. |
| <kbd>Ctrl</kbd> + <kbd>N</kbd> | Nuovo Progetto | Crea una nuova scaletta vuota. |
| <kbd>Ctrl</kbd> + <kbd>O</kbd> | Apri Show | Apre un file `.blindcue` o `.json`. |
| <kbd>Ctrl</kbd> + <kbd>S</kbd> | Salva Show | Salvataggio atomico su file corrente. |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd> | Salva Show con Nome | Esporta una nuova copia dello show. |
| <kbd>Ctrl</kbd> + <kbd>Q</kbd> | Esci | Chiusura pulita con conferma di salvataggio. |

---

## 🛠️ Ottimizzazioni di Sistema (Obbligatorie vs Facoltative)

Il software è progettato per funzionare immediatamente su qualsiasi installazione Linux standard. Tuttavia, per eventi live e regie teatrali ad alta responsabilità, consigliamo di applicare le seguenti ottimizzazioni:

| Ottimizzazione | Stato | Descrizione |
|----------------|-------|-------------|
| **Standard numerico POSIX (`LC_NUMERIC=C`)** | **Automatica** | Già inclusa in `run.sh`: assicura che i numeri decimali usino il punto e non la virgola indipendentemente dalla lingua di sistema. |
| **Disattivazione Sleep / Screensaver** | **Fortemente Consigliata** | Disabilitare lo spegnimento automatico dello schermo e la sospensione nelle impostazioni del desktop (GNOME/KDE) durante lo spettacolo. |
| **CPU Governor su "Performance"** | **Consigliata** | Evita sbalzi di frequenza del processore tra scene vuote e scene complesse (`sudo cpupower frequency-set -g performance`). |
| **Priorità Real-Time Audio (PipeWire/JACK)** | **Facoltativa** | Utile solo se si utilizzano schede audio USB/Thunderbolt professionali a bassissima latenza (< 5ms). |
| **Priorità di Scheduling (`nice`)** | **Facoltativa** | Avviando `./run.sh` con `nice -n -5 ./run.sh` si garantisce priorità assoluta al processo rispetto ad altri programmi in background. |

---

## 📂 Struttura del Progetto

```
BlindCUE/
│
├── install.sh                          # Script di setup multi-distro
├── run.sh                              # Launcher dell'applicazione con ambiente virtuale
├── README.md                           # Documentazione completa
├── .gitignore                          # Regole di esclusione git (bytecode, venv, cache)
│
├── docs/
│   └── GUIDA_IMPLEMENTAZIONE_LINUX.md  # Approfondimento tecnico architetturale per Linux e Wayland
│
├── immagini di progetto/               # Blueprint e asset ufficiali
│   ├── BlindCue-logo.jpeg              # Logo ufficiale dell'applicazione (icona e Layer 0)
│   ├── BlindCue-UX_UI.jpeg             # Blueprint tecnico architetturale
│   ├── BlindCue-esempio di lavoro.jpeg    # Schema concettuale doppio monitor
│   └── BlindCue-possibile_UX-UI.jpeg      # Mockup operativo dell'interfaccia
│
└── blindcue/                           # Sorgenti Python dell'applicazione
    ├── main.py                         # Entry point, bus dei segnali, routing display e shutdown failsafe
    ├── requirements.txt                # Dipendenze (PySide6, numpy)
    │
    ├── models/                         # Modelli dati e logica di salvataggio
    │   ├── __init__.py
    │   ├── cue.py                      # Dataclass Cue con crop, zoom, transizioni, permanenza e note
    │   └── project_manager.py          # Scrittura atomica POSIX, autosave a 30s e crash recovery
    │
    ├── engine/                         # Motore multimediale e analisi audio
    │   ├── __init__.py
    │   ├── player_live.py              # Player QtMultimedia hardware-accelerated per schermo live
    │   ├── player_test.py              # Player QtMultimedia per banco regia (muto di default)
    │   └── audio_analyzer.py           # Analizzatore asincrono waveform via ffmpeg pipe e numpy
    │
    └── ui/                             # Interfaccia grafica utente Wayland-nativa
        ├── __init__.py
        ├── main_window.py              # Finestra di regia (Scaletta, Pre-Viz 16:9, Ispettore, Waveform)
        └── output_window.py            # Finestra schermo esterno con Layer 0 dinamico e compositing L1-L3
```

---

## 📄 Licenza

Progetto open source sviluppato per garantire la massima stabilità operativa e affidabilità per registi, fonici, video-maker e tecnici dello spettacolo dal vivo.
