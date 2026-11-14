# BlindCue

[![Licenza: MIT](https://img.shields.io/badge/Licenza-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Framework: PySide6](https://img.shields.io/badge/GUI-PySide6%20Qt6-orange.svg)](https://wiki.qt.io/Qt_for_Python)
[![Piattaforme](https://img.shields.io/badge/Piattaforme-Linux%20%7C%20macOS%20%7C%20Windows-blueviolet.svg)](#requisiti-e-compatibilità)

**BlindCue** è un player multimediale e sequencer per spettacoli teatrali, performance dal vivo ed eventi broadcast. Il software separa nettamente l'ambiente di regia (sul monitor dell'operatore) dall'emissione video e audio verso la sala (su proiettore, videowall o display di scena), garantendo stabilità assoluta, zero latenza percettibile e assenza di interruzioni visive per il pubblico.

---

## Caratteristiche Principali

- **Doppio Ambiente Isolato**:
  - *Modalità Progetto*: Editing non distruttivo della scaletta, regolazione tempi (Pre-Wait, Play, Post-Wait), ritaglio frame (crop), curve di fade, livelli volume e sezioni virtuali.
  - *Modalità LIVE*: Interfaccia ad alto contrasto per l'esecuzione dello spettacolo, blocco delle modifiche accidentali, comandi a tasto singolo (`SPAZIO` per GO, `ESC` per Panic) e timer di scena.
- **Compositing Video a 3 Livelli + Layer 0 di Sicurezza**:
  - Tre layer video/grafici indipendenti sovrapponibili in tempo reale (`L1` Sfondo, `L2` Principale, `L3` Overlay).
  - Layer 0 (Failsafe): Reticolo geometrico per la calibrazione ottica del videoproiettore o blackout grafico personalizzabile.
- **Supporto Virtual Surface Mapping & Warping**:
  - Correzione prospettica a 4 punti (Quad Corner Pin / Keystone) e mascherature vettoriali (rettangolari, ellittiche, fori o maschere raster).
- **Automazione e Controllo Remoto di Rete**:
  - Server OSC UDP nativo per l'integrazione con mixer audio/luci o controller di scena esterni (`/go`, `/panic`, `/pause`, `/cue/<id>/go`, `/volume`).
  - Web Remote mobile-first reattivo su rete locale (LAN Wi-Fi) per smartphone e tablet (accesso rapido tramite QR Code e protezione con PIN numerico).
  - Web Monitor passivo in sola lettura per la direzione artistica e di scena.
- **Motore Audio Professionale**:
  - Analizzatore di forme d'onda con zoom fino a 32x, rilevazione integrata del volume (EBU R128 LUFS e True Peak) e compressione dinamica.
  - Routing audio indipendente: uscita Master Sala e monitor PFL (pre-ascolto in cuffia) su interfacce hardware distinte.
- **Resilienza e Sicurezza**:
  - Salvataggio atomico su disco in formato JSON aperto (`.blindcue`) e recupero automatico in caso di interruzione anomala della sessione (Crash Recovery).

---

## Requisiti e Compatibilità

- **Python**: `>= 3.10`
- **Motore Multimediale**: FFmpeg e librerie multimediali native di sistema (gestite tramite backend QtMultimedia).
- **Sistemi Operativi**:
  - **Linux**: Wayland nativo e X11 (Debian, Ubuntu, Arch Linux, Fedora e derivate).
  - **macOS**: Apple Silicon (M1/M2/M3/M4) e Intel (macOS 12+).
  - **Windows**: Windows 10 e Windows 11 (64-bit).

---

## Installazione Rapida

### 🐧 Linux
```bash
git clone https://github.com/diego-costanzo/BlinCUE.git
cd BlinCUE
chmod +x install.sh run.sh
./install.sh
./run.sh
```

### 🍎 macOS
```bash
git clone https://github.com/diego-costanzo/BlinCUE.git
cd BlinCUE
chmod +x install_mac.sh run.sh
./install_mac.sh
./run.sh
```

### 🪟 Windows
1. Clona o scarica il repository:
   ```cmd
   git clone https://github.com/diego-costanzo/BlinCUE.git
   cd BlinCUE
   ```
2. Esegui **`install.bat`** per preparare l'ambiente virtuale e le dipendenze.
3. Avvia il software con **`run.bat`**.

---

## Stack Tecnologico

- **Linguaggio**: Python 3.12+ (Type Hinting moderno PEP 585/604).
- **Interfaccia Grafica**: PySide6 (Qt 6 Framework).
- **Elaborazione Audio/Dati**: NumPy.
- **Networking**: `QUdpSocket` (OSC 1.0 binario), `http.server` multi-thread con Server-Sent Events (SSE).
- **Generatore Grafico**: Generatore di codici QR integrato in puro Python (ISO/IEC 18004).

---

## Documentazione Dettagliata

- [Paper Tecnico e Architettura Modulare](docs/ARCHITECTURE.md)
- [Manuale Utente Operativo](docs/MANUAL.md)

---

## Licenza

Questo progetto è rilasciato sotto licenza open-source [MIT](LICENSE).
