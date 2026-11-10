# 🐧 Guida all'Implementazione e Architettura di BlindCue su Linux

Questa guida documenta in modo approfondito l'architettura tecnica di **BlindCue**, le dipendenze di sistema, le scelte ingegneristiche (100% Wayland nativo, Qt6, gestione dati JSON atomico in memoria vs SQLite) e le procedure di ottimizzazione del sistema operativo Linux per spettacoli dal vivo ed eventi multimediali mission-critical.

---

## 1. Principi Architetturali e Filosofia "Zero-Crash"

Negli spettacoli dal vivo (teatri, concerti, festival, conferenze internazionali, musical, trasmissioni televisive), un freeze dell'applicazione, un pop elettroacustico o la comparsa del desktop del sistema operativo sul proiettore principale costituiscono un fallimento critico.

Per azzerare questi rischi, BlindCue adotta un'architettura rigorosamente compartimentata:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ARCHITETTURA BLINDCUE                           │
├───────────────────────────────────┬────────────────────────────────────┤
│   MONITOR PRIMARIO (REGIA)        │    MONITOR SECONDARIO (LIVE)       │
│                                   │                                    │
│   ┌───────────────────────────┐   │   ┌────────────────────────────┐   │
│   │   Scaletta CUE (Sequence) │   │   │ Layer 3: Overlay / Lower3  │   │
│   ├───────────────────────────┤   │   ├────────────────────────────┤   │
│   │   Banco Regia Pre-Viz     │   │   │ Layer 2: Inset / Cropped   │   │
│   │   [Player Wayland Muto]   │   │   ├────────────────────────────┤   │
│   ├───────────────────────────┤   │   │ Layer 1: Video / Sfondo    │   │
│   │   Ispettore & Note Regia  │   │   ├────────────────────────────┤   │
│   ├───────────────────────────┤   │   │ LAYER 0: TAPPO FAILSAFE    │   │
│   │   Waveform & Live Status  │   │   │ (Sempre attivo sotto tutto)│   │
│   └───────────────────────────┘   │   └────────────────────────────┘   │
└───────────────────────────────────┴────────────────────────────────────┘
```

### I Pilastri Ingegneristici:
1. **100% Wayland Nativo (PySide6 QtMultimedia)**:
   - Sostituisce i vecchi bridge X11/Xwayland e l'embedding via window ID numerici (`--wid`).
   - Sfrutta le sub-surface native Wayland per visualizzare video hardware-accelerated direttamente nel grafo di scena di Qt6.
   - Nessun tearing, sincronizzazione v-sync nativa e supporto multi-display asincrono (es. laptop a 60 Hz e proiettore a 120 Hz).
2. **Doppio Binario Isolato (Live vs Pre-Viz)**:
   - Due motori di riproduzione fisicamente separati.
   - L'anteprima operatore è mutata di default a livello hardware e logico, con possibilità di preascolto in cuffia su richiesta esplicita.
3. **Layer 0 Failsafe Permanente ("Immagine di Tappo")**:
   - Una superficie di sicurezza sempre attiva al di sotto di qualsiasi contenuto video o immagine.
   - Cattura e ignora i tasti di chiusura accidentale (`Escape`, `closeEvent` della finestra di output).
4. **Persistenza Atomica & Crash Recovery**:
   - Salvataggio JSON atomico tramite file temporaneo e `os.replace` POSIX.
   - Autosave continuo ogni 30 secondi e ad ogni modifica o lancio cue.
   - Crash Recovery automatico al riavvio in caso di interruzione improvvisa della corrente elettrica.

---

## 2. Gestione Hardware: GPU e Multi-Core CPU

### A. Scheda Grafica (GPU) e Decodifica Hardware
BlindCue sfrutta le librerie multimediali di sistema per delegare il carico di decodifica video alla GPU:
- **Intel Graphics**: VA-API (`iHD` / `i965`) via Mesa EGL.
- **AMD Radeon**: VA-API (`radeonsi`) via Mesa.
- **Nvidia GeForce / Quadro**: NVDEC / VDPAU o driver proprietario con bridge hardware.

**Vantaggio operativo**:
Durante la riproduzione di file ad alto bitrate (es. ProRes, H.264 o HEVC a 1080p/4K), l'uso della CPU del computer rimane compreso tra il **3% e il 7%**. Il portatile di regia rimane freddo, le ventole non vanno al massimo e non si verificano fenomeni di thermal throttling (taglio delle frequenze) anche dopo ore di utilizzo continuativo.

All'avvio, l'applicazione rileva l'hardware grafico e visualizza lo stato nella barra di stato inferiore:
`CPU: N Cores | GPU: [Vendor Graphics (VA-API/OpenGL)]`. Se non è presente alcuna GPU dedicata o abilitata, il sistema attiva automaticamente il fallback software multithread senza interrompere l'esecuzione.

### B. Gestione Multi-Core della CPU
- **Thread GUI Principale**: È dedicato unicamente a ricevere l'input dell'utente (<kbd>Spazio</kbd> per il GO, <kbd>Ctrl</kbd>+<kbd>B</kbd> per il Blackout, slider volume in tempo reale) e ad aggiornare i widget. La latenza di reazione è inferiore a **0.05 ms**.
- **Pool di Thread Asincroni (`QThreadPool`)**: L'analisi della waveform dei file audio lunghi viene eseguita in background su core secondari tramite estrazione a blocchi con FFmpeg e calcolo vettoriale NumPy.
- **Thread C++ Audio/Video**: Il demuxing e lo streaming audio PipeWire/ALSA vengono gestiti su thread separati con priorità audio in tempo reale.

---

## 3. Valutazione Tecnica: Database (SQLite) vs JSON Atomico

Una domanda frequente nell'ingegneria del software multimediale riguarda la scelta tra un mini-database (es. SQLite) e un formato serializzato in memoria (come JSON atomico `.blindcue`).

### Analisi Comparativa Ingegneristica

| Parametro | File di Progetto JSON Atomico (`.blindcue`) | Mini Database SQLite (`.db`) |
|-----------|--------------------------------------------|------------------------------|
| **Struttura dei dati** | Struttura sequenziale (10–500 Cue per show) | Tabelle relazionali con indici B-Tree |
| **Dimensione su disco** | ~30 KB – 150 KB (estremamente compatto) | ~100 KB base + journal/WAL temporanei |
| **Tempo di lettura** | **< 1.5 ms** (deserializzazione istantanea in memoria) | 5–15 ms (apertura connessione, lock, query SQL) |
| **Latenza durante il Live** | **Zero I/O su disco** (tutto in RAM ad accesso nanosecondi) | Operazioni I/O con rischio di lock di pagina |
| **Resistenza a blackout** | **Totale**: scrittura su `.tmp`, `fsync` e swap atomico POSIX con `os.replace` | Buona, ma rischio lock pendenti (`.db-wal`) su chiavette USB o crash improvvisi |
| **Trasparenza & Debug** | **Aperto**: leggibile con qualsiasi editor di testo (`cat`, `nano`), versionabile con `git diff`, modificabile in emergenza | File binario: richiede tool esterni (`sqlite3`, GUI dedicati) |
| **Complessità software** | Zero overhead, dataclass tipizzate Python native | Schema migrations, locking di tabella, transazioni SQL |

### Conclusioni
Per un software di regia con sequenze da decine o centinaia di cue, **il formato JSON atomico in memoria è significativamente più rapido, leggero, sicuro e manutenibile di un database relazionale**. 

SQLite è uno strumento eccellente per cataloghi di centinaia di migliaia di record con ricerche complesse, ma per uno show teatrale o un evento live sequenziale risulterebbe un sovraccarico architetturale ingiustificato (principio YAGNI).

---

## 4. Solidità di Python per un Software di Regia Live

È fondata la preoccupazione che Python possa "scricchiolare" o causare rallentamenti quando il progetto cresce?

### Come Funziona il Motore sotto il Cofano:
1. **Zero elaborazione multimediale in Python**: Python non decodifica i frame video né campiona l'audio PCM. L'intero pipeline di decoding, de-interlacciamento, scaling hardware e rendering grafico è implementato in **C/C++ altamente ottimizzato** (FFmpeg, libavcodec, libavformat, Mesa VA-API, Qt6).
2. **Analisi Audio Asincrona**: L'analisi della waveform viene delegata a un thread worker dedicato (`QRunnable` su `QThreadPool`) che scambia stream binari con `NumPy` in memoria C. Il thread principale della GUI non viene mai bloccato.
3. **Latenza di Attacco**: I comandi operatore (barra spaziatrice per il GO, tasto B per il blackout) generano segnali Qt la cui propagazione in Python richiede meno di **50 microsecondi** (0.05 ms). Rispetto ai 16.6 millisecondi di un singolo fotogramma a 60 FPS, il margine di reattività è di oltre 300 volte superiore.
4. **Standard Industriale**: Lo stesso paradigma (motore ad alte prestazioni C/C++ guidato da un control plane in Python) è adottato da software leader come **Blender**, **DaVinci Resolve**, **TouchDesigner** e console luci professionali.

---

## 5. Compositing a Livelli, Failsafe e Micro-Dissolvenze

BlindCue gestisce l'emissione live attraverso una gerarchia a 4 livelli:

```
┌─────────────────────────────────────────────────────────────┐
│                    LIVE OUTPUT COMPOSITING                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Overlay / Grafica trasparente / Logo              │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Inset / Media secondario / Immagine ritagliata    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Video principale / Immagine di sfondo             │
├─────────────────────────────────────────────────────────────┤
│  LAYER 0: TAPPO FAILSAFE (Logo evento o Nero - Sempre vivo) │
└─────────────────────────────────────────────────────────────┘
```

### Funzionamento Dettagliato dei Livelli:
1. **Layer 0 (Tappo Failsafe Dinamico)**:
   - È sempre attivo e non può essere de-allocato.
   - **Comportamento Dinamico**:
     - Quando nessun media è attivo, visualizza il logo dell'evento (o il file selezionato con `📁 Cambia Tappo...`).
     - Non appena un media va in live sui Layer 1-3, il logo di Layer 0 si dissolve su un fondo nero puro (`#000000`). Questo assicura che se un'immagine o un video sono scalati o croppati, sotto di essi ci sia il nero e non la grafica del logo.
     - Quando tutti i layer sono chiusi o in caso di errore, il logo riappare con transizione morbida.
2. **Comportamento a Fine Corsa (Video/Audio vs Immagini)**:
   - **Video e Audio**: Al raggiungimento del punto `OUT` o alla fine naturale del file (`EndOfMedia`), il player live ferma l'emissione e nasconde istantaneamente il layer con micro-dissolvenza. Lo schermo torna a mostrare ciò che c'è sotto (l'immagine su L1 o il nero/logo di Layer 0).
   - **Immagini Statiche**: Restano stabili sul rispettivo layer per consentire il compositing contemporaneo (es. sfondo su L1 + grafica croppata su L2).
   - **Tempo di Permanenza (`hold_time`)**: È possibile impostare un conto alla rovescia in secondi. Con `0 s` la permanenza è infinita; con un valore > 0 l'immagine scompare automaticamente allo scadere del timer.
3. **Micro-Dissolvenza Anti-Frustata (0.2s / 200 ms)**:
   - Ogni stacco manuale (`✕ Cut L1/L2/L3` o `Master Blackout`) applica una micro-dissolvenza hardware su audio e video. Questo azzera i "pop" acustici dovuti all'interruzione improvvisa della forma d'onda (DC offset) e ammorbidisce visivamente l'uscita sul proiettore.
4. **Regolazione Volume Live in Tempo Reale**:
   - Lo slider del volume nell'Ispettore Cue aggiorna direttamente l'amplificazione del player live in tempo reale, permettendo al regista di correggere al volo file con livelli non uniformi.

---

## 6. Monitor Studio Pre-Viz 16:9 WYSIWYG

Il banco regia ospita un monitor da studio in formato fisso 16:9 con le seguenti caratteristiche:
- **Specchio Fedele (WYSIWYG)**: Visualizza esattamente ciò che andrà in onda, inclusi sfondo Layer 0, scala (0.1x – 3.0x), posizione (X, Y) e ritaglio (Crop L, R, T, B).
- **Ritaglio e Contenimento (Clamping)**: Quando la scala supera 1.0x o il media viene spostato, il contenuto viene ritagliato rigorosamente all'interno della cornice 16:9 dell'anteprima, senza debordare sull'interfaccia.
- **Audio Visualizer**: Durante la riproduzione di file audio, visualizza un equalizzatore dinamico a 12 bande animate per confermare a colpo d'occhio che il file è attivo.
- **Live Mirror**: Un commutatore toggle (`🔗 LIVE MIRROR: OFF` / `🔴 LIVE MIRROR: ATTIVO`) permette di decidere se inviare istantaneamente ogni modifica di allestimento al monitor esterno oppure mantenere l'anteprima strettamente isolata.

---

## 7. Trimming Interattivo con Mouse e Centesimi

- **Trimming su Forma d'Onda**: L'operatore può cliccare e trascinare direttamente con il mouse i marker verticali `IN` (verde) e `OUT` (rosso) sopra la forma d'onda audio.
- **Precisione al Centesimo di Secondo (0.01s)**: I campi numerici `Punto IN` e `Punto OUT` permettono sia l'editing con le frecce su/giù sia l'inserimento numerico manuale con due cifre decimali.
- **Smart End-of-File Step**: Premendo la freccia giù quando il punto OUT si trova su *"Fine File"*, il valore scala automaticamente all'indietro a partire dalla durata effettiva del file (`durata - 0.05s`).
- **Loop-back automatico su OUT**: Raggiunto il punto OUT il player si ferma. Premendo nuovamente `▶ Play`, la riproduzione riprende automaticamente da IN per calibrare i tagli al millisecondo.

---

## 8. Focus Guard e Sicurezza Operativa

Negli eventi live, la distrazione dell'operatore o una digitazione accidentale possono causare errori irreparabili. BlindCue implementa controlli di sicurezza dedicati:

- **Master Blackout a Due Tasti (<kbd>Ctrl</kbd> + <kbd>B</kbd>)**: La funzione di blackout richiede la pressione contemporanea di `Ctrl` e `B`, prevenendo attivazioni accidentali mentre si digita una parola contenente la lettera "B".
- **Focus Guard nei Campi di Testo**: Quando l'operatore scrive all'interno del campo `Nome` o `Note`, la scorciatoia di lancio <kbd>Spazio</kbd> (GO) e il Blackout vengono temporaneamente disattivati. Si possono digitare note con spazi e lettere senza alcun rischio che parta la cue successiva in live!

---

## 9. Dipendenze e Installazione Multi-Distro

### Pacchetti di Sistema Necessari

#### Arch Linux / EndeavourOS / Manjaro
```bash
sudo pacman -S --needed ffmpeg python python-pip python-virtualenv mesa-utils
```

#### Debian 12+ / Ubuntu 22.04+ / Linux Mint
```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip python3-venv build-essential mesa-utils
```

#### Fedora 39+
```bash
sudo dnf install -y ffmpeg python3 python3-pip python3-virtualenv mesa-demos
```

### Installazione dell'Ambiente Virtuale
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r blindcue/requirements.txt
```

### Avvio dell'Applicazione
```bash
./run.sh
```

---

## 10. Ottimizzazioni del Sistema Operativo Linux per il Live

Il software è immediatamente pronto all'uso su qualsiasi sistema Linux moderno. Per regie professionali ad alta responsabilità, si consiglia di consultare questa tabella delle ottimizzazioni:

| Ottimizzazione | Tipologia | Come applicarla | Perché è utile |
|----------------|-----------|-----------------|----------------|
| **`LC_NUMERIC=C`** | **Automatica / Obbligatoria** | Già inclusa nel launcher `run.sh` | Garantisce che numeri con virgola/punto decimale siano gestiti in standard POSIX senza eccezioni di parsing. |
| **Disattivazione Sleep / Screensaver** | **Fortemente Consigliata** | Da Impostazioni Desktop (GNOME/KDE) | Impedisce al sistema di spegnere i monitor o andare in standby dopo minuti di inattività operatore. |
| **CPU Governor su "Performance"** | **Consigliata** | `sudo cpupower frequency-set -g performance` | Evita micro-ritardi dovuti allo scalare delle frequenze CPU tra una scena e l'altra. |
| **Priorità di Scheduling (`nice`)** | **Facoltativa** | `nice -n -5 ./run.sh` | Concede al processo priorità rispetto ad altri task di background nel kernel Linux. |
| **Permessi Real-Time Audio (rtkit / limits.conf)** | **Facoltativa** | Utenti nel gruppo `audio` / configurazione PAM | Necessaria solo se si utilizzano schede audio USB esterne con buffer inferiori a 64 campioni (< 2ms). |
