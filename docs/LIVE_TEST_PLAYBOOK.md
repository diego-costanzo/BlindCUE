# Playbook di Collaudo Reale sul Campo — BlindCUE

Guida pratica per costruire una **scaletta di test "da palcoscenico"** con file audio, video e immagini reali, progettata per scovare bug nascosti di timing, rendering, memoria, hardware e rete **prima** di andare in scena.

Tutta la procedura usa esclusivamente strumenti open source già presenti su Linux (`ffmpeg`, `ffprobe`, `systemd-inhibit`, `ss`, `htop`/monitor di sistema).

---

## 1. Preparazione dell'ambiente di prova

### 1.1 Verifica pre-test (da terminale)
Prima di aprire BlindCUE, annota lo stato del sistema:

```bash
# 1. Conferma sessione Wayland attiva
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"

# 2. Verifica accelerazione hardware VA-API (se disponibile)
vainfo 2>&1 | grep -E "Driver version|VAProfileH264|VAEntrypointVLD" | head -n 15

# 3. Controlla il log live in una seconda finestra di terminale
tail -F ~/.local/share/BlindCue/blindcue.log
```

> **Consiglio:** tieni aperto il `tail -F` su un angolo del monitor di regia. Durante una prova sana **non deve mai comparire** `[CRITICAL]`, `Traceback`, `Ambiguous shortcut` o raffiche ripetute di `[ERROR]`.

### 1.2 Generare un kit di media di test (opzionale, 100% FFmpeg open source)
Se non hai già file pronti (o vuoi includere casi "cattivi" che spesso rompono i player in teatro), puoi generare una cartella `~/blindcue_test_kit/` con questi comandi:

```bash
mkdir -p ~/blindcue_test_kit/dir_a ~/blindcue_test_kit/dir_b
cd ~/blindcue_test_kit

# 1. Video 1080p 30fps con timecode visibile + beep ogni secondo (perfetto per vedere sync e frame drop!)
ffmpeg -y -f lavfi -i testsrc2=size=1920x1080:rate=30:duration=90 \
  -f lavfi -i "sine=frequency=880:duration=90" \
  -vf "drawtext=text='VIDEO-A %{pts\:hms} f=%{n}':x=40:y=40:fontsize=56:fontcolor=white:box=1:boxcolor=black@0.7" \
  -c:v libx264 -pix_fmt yuv420p -g 30 -c:a aac -b:a 192k video_tc_90s.mp4

# 2. Secondo video 1080p con colore e grafica diversi (per test multi-layer e Uscita B)
ffmpeg -y -f lavfi -i smptehdbars=size=1920x1080:rate=30:duration=60 \
  -f lavfi -i "sine=frequency=440:duration=60" \
  -vf "drawtext=text='VIDEO-B %{pts\:hms}':x=40:y=120:fontsize=56:fontcolor=yellow:box=1:boxcolor=black@0.7" \
  -c:v libx264 -pix_fmt yuv420p -g 30 -c:a aac -b:a 192k video_bars_60s.mp4

# 3. Video "difficile": senza traccia audio (verifica che la forma d'onda non blocchi il player!)
ffmpeg -y -f lavfi -i testsrc2=size=1920x1080:rate=30:duration=30 -an \
  -c:v libx264 -pix_fmt yuv420p video_muto_30s.mp4

# 4. Video breve 4 secondi (per testare EOF, Auto-Follow, Loop Scena e Post-Delay)
ffmpeg -y -f lavfi -i color=c=blue:s=1280x720:r=30:d=4 \
  -f lavfi -i "sine=frequency=660:duration=4" \
  -vf "drawtext=text='SHORT %{pts\:flt}s':x=60:y=300:fontsize=72:fontcolor=white" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac video_breve_4s.mp4

# 5. Audio normale + Audio molto basso (-30 dB) + Audio forte (per EBU R128 / Jam Mode)
ffmpeg -y -f lavfi -i "sine=frequency=330:duration=45" -c:a libmp3lame -b:a 192k audio_normale_45s.mp3
ffmpeg -y -f lavfi -i "sine=frequency=523:duration=30" -af "volume=-24dB" -c:a libmp3lame -b:a 192k audio_basso_30s.mp3
ffmpeg -y -f lavfi -i "sine=frequency=220:duration=15" -af "volume=-2dB" -c:a pcm_s16le audio_forte_15s.wav

# 6. Audio LUNGO 90 minuti (test RAM streaming waveform — deve usare < 5 MB extra, non 300 MB!)
ffmpeg -y -f lavfi -i "sine=frequency=110:duration=5400" -c:a libmp3lame -b:a 64k audio_lungo_90min.mp3

# 7. Immagini: alta risoluzione 4K + PNG con trasparenza (overlay L3) + PNG maschera bianca/nera
ffmpeg -y -f lavfi -i color=c=0x114488:s=3840x2160:d=1 -frames:v 1 img_sfondo_4k.jpg
ffmpeg -y -f lavfi -i "color=c=0x00000000:s=1920x1080:d=1,format=rgba,drawbox=x=100:y=800:w=1720:h=180:color=0xFFCC00CC:t=fill" -frames:v 1 img_overlay_trasparente.png
ffmpeg -y -f lavfi -i "color=c=black:s=512x512:d=1,drawbox=x=96:y=96:w=320:h=320:color=white:t=fill" -frames:v 1 mask_finestra.png

# 8. Due file omonimi in cartelle diverse (per test Archivio Portatile anti-collisione)
ffmpeg -y -f lavfi -i "sine=frequency=400:duration=5" -c:a pcm_s16le dir_a/stesso_nome.wav
ffmpeg -y -f lavfi -i "sine=frequency=900:duration=5" -c:a pcm_s16le dir_b/stesso_nome.wav
```

---

## 2. Come costruire la Scaletta di Test ("Tortura da Palco")

Crea un nuovo progetto (`Ctrl+N`) e inserisci queste **14 cue** in ordine. Coprono quasi tutti i percorsi critici del motore:

| # | Sigla Q | File | Tipo | Layer | Impostazioni chiave | Cosa mette sotto stress |
|---|---|---|---|---|---|---|
| 1 | `Q-1` | `img_sfondo_4k.jpg` | IMG | L1 | Fade In `1.5s`, Hold `0s` (infinita) | Decodifica 4K, cache pixmap, fade immagine su Layer 0 |
| 2 | `Q-2` | `img_overlay_trasparente.png` | IMG | L3 | Opacità `85%`, Hold `5s`, Fade Out `1s`, **Auto-Follow** | Sovrapposizione L3 sopra L1 senza toccare L1 + uscita automatica a fine Hold |
| 3 | `Q-3` | `audio_normale_45s.mp3` | AUD | L2 | Fade In `2s`, Fade Out `2s`, **3 Sezioni (A, B=Vamp ∞, C=Skip)** | Sezioni virtuali, vamp infinito, uscita da vamp, skip |
| 4 | `Q-4` | `video_tc_90s.mp4` | VID | L1 | Pre-Delay `2.0s`, Post-Delay `1.5s`, **Simulanea (`⇉`)** con Q-5 | Scheduler Pre/Post-Delay (badge 10 Hz), avvio sincrono |
| 5 | `Q-5` | `audio_basso_30s.mp3` | AUD | L2 | Analizza EBU R128 + attiva **Normalizza cue** | Auto-gain non distruttivo, coesistenza video L1 + audio L2 |
| 6 | `Q-6` | `video_muto_30s.mp4` | VID | L1 | Crop `50%`, Rotazione `90°`, Loop attivo | Video senza traccia audio, crop + rotazione in uscita e Pre-Viz |
| 7 | `Q-7` | **Gruppo "Scena Cascata"** | GRP | — | Modalità **`SEQUENCE`** contenente 3 cue brevi (`video_breve_4s.mp4`, `img_sfondo_4k.jpg` Hold `3s`, `audio_forte_15s.wav` OUT=`4s`) | Cascata automatica senza flag AUTO-GO sui figli + contenitore resta LIVE |
| 8 | `Q-8` | **Gruppo "Loop Scena"** | GRP | — | Modalità **`LOOP`** con 1 solo figlio (`video_breve_4s.mp4`) e poi prova con 2 figli | Rientro continuo al primo figlio senza uscire dal gruppo |
| 9 | `Q-9` | **Gruppo "Simultaneo"** | GRP | — | Modalità **`SIMULTANEOUS`**: Video su L1 + Audio su L2 + Immagine su L3 | Compositing 3 layer contemporanei; poi metti temporaneamente due figli su L1 per verificare il badge conflitto |
| 10 | `Q-10` | `video_bars_60s.mp4` | VID | L1 | Assegna a **Superficie Quad (4 angoli)** con maschera Ellisse + Feather `15px` | Prospettiva 4 punti + cache maschera sfumata |
| 11 | `Q-11` | `video_bars_60s.mp4` | VID | **B·L1** | *(Solo se hai 2 proiettori)* Uscita **B**, contemporanea a Q-4 su Uscita **A** | Doppia uscita indipendente, scambio A↔B, monitoraggio carico |
| 12 | `Q-12` | `audio_lungo_90min.mp3` | AUD | L2 | Selezionala per generare la forma d'onda | Streaming PCM a memoria costante (nessun picco RAM) |
| 13 | `Q-13` | `dir_a/stesso_nome.wav` | AUD | L2 | Nome identico a Q-14, stessa dimensione in byte ma nota diversa | Test anti-collisione SHA-256 nel salvataggio portatile |
| 14 | `Q-14` | `dir_b/stesso_nome.wav` | AUD | L3 | Nome identico a Q-13 | Verifica che entrambe suonino la propria nota dopo apertura del bundle |

---

## 3. Batteria di Test da Eseguire (Checklist Passo-Passo)

Esegui questi **10 scenari** in ordine. Segna `PASS` o `FAIL` (e salva subito l'orario per ritrovare le righe in `blindcue.log`).

### Test 1 — Scorciatoie e Focus (Regia sotto stress)
- [ ] Apri l'Ispettore, clicca su una casella a discesa (`QComboBox`, es. *Modalità Avanzamento* o *Superficie*) lasciandoci il focus.
  - Premi `Spazio` → **non** deve partire nulla (stai modificando l'ispettore).
  - Clicca il pulsante verde **GO** con il mouse → **deve partire subito** la cue.
- [ ] Premi `Ctrl+B` da tastiera → deve partire il **Blackout** (dissolvenza verso Layer 0), nessun errore di scorciatoia ambigua.
- [ ] Premi `F5` da tastiera → entra in **Modalità LIVE**; premi ancora `F5` → torna in **Progetto** senza fermare ciò che è in onda.
- [ ] Premi `F7` (Superfici), `Shift+F7` (Guide sul proiettore), `F8` (Remoto) → devono aprirsi/commutare al primo colpo.

### Test 2 — Race Condition Blackout → GO rapidissimo (il test dei 200 ms)
- [ ] Manda in onda `Q-1` (immagine 4K) o `Q-4` (video).
- [ ] Premi **`Ctrl+B`** (Blackout) e **immediatamente dopo** (entro 100 ms, "doppio tap" rapido) premi **`Spazio` (GO)** sulla cue successiva.
- [ ] **Esito atteso:** la nuova cue appare e **resta visibile**. Non deve sparire dopo 0,2 secondi sostituita dal Tappo!

### Test 3 — Sicurezza Modalità LIVE (Blocco Layer & Doppio ESC)
- [ ] Entra in Modalità LIVE (`F5`) e lancia `Q-3` o `Q-4`.
- [ ] Prova a cliccare/trascinare sulla barra di avanzamento del Layer 1 → **deve essere bloccata** (nessuno scrub accidentale!).
- [ ] Tieni premuto **`🔒 BLOCCO LAYER`** per **1,2 s** → si sblocca e ora puoi fare scrub/pausa sul layer; clicca 1 volta → si riblocca istantaneamente.
- [ ] Premi **`ESC` una sola volta** → **non** deve tagliare lo spettacolo; nella barra di stato compare l'avviso *"Premi di nuovo ESC entro 0.6s per PANIC"*.
- [ ] Premi **`ESC` due volte rapidamente** (entro 0,6 s) → taglio immediato a **0 ms** (audio e video spenti).
- [ ] Rilancia un video e clicca il pulsante rosso **`🚨 PANIC`** col mouse → taglio immediato al **primo click (0 ms)**.

### Test 4 — Pausa Globale, Pre/Post-Delay e Sezioni
- [ ] Lancia `Q-4` (Pre-Delay `2.0s`): mentre il countdown `PRE` scorre, clicca **`PAUSA TUTTO`** → il countdown si congela, il badge resta fermo; clicca **`RIPRENDI TUTTO`** → riparte esattamente dal decimo di secondo lasciato.
- [ ] Durante la riproduzione di `Q-4`, premi **`PAUSA TUTTO`** e poi **`RIPRENDI TUTTO`** 3 volte di fila → audio e video restano sincronizzati, nessun salto di posizione.
- [ ] Lancia `Q-3` (sezioni A / B=Vamp ∞ / C=Skip): verifica che entri in loop infinito su B, premi **Esci da Loop Sezione** → salta C e chiude pulito a EOF senza ripetizioni doppie.

### Test 5 — Gruppi, Undo/Redo ed Eliminazione di Cue LIVE
- [ ] Lancia `Q-7` (*Scena Cascata*): con un solo GO devono susseguirsi automaticamente tutti e 3 i figli e il gruppo resta marcato `LIVE`.
- [ ] Lancia `Q-8` (*Loop Scena*): verifica che a fine video ricominci automaticamente dal primo figlio all'infinito finché non fai Blackout/Panic.
- [ ] Mentre una cue è `LIVE`: modifica il nome di un'altra cue e premi `Ctrl+Z` (Undo) → la riproduzione in onda **non si interrompe** e alla fine della cue il suo stato torna correttamente `LOADED` (e l'eventuale Auto-Follow funziona ancora).
- [ ] In modalità Progetto, con una cue **LIVE**, selezionala e premi `Canc` (`Del`) → il suo layer audio/video deve **fermarsi subito**, senza lasciare audio fantasma in sala.
- [ ] Con una cue **LIVE**, fai `File → Nuovo Show` → audio e video in onda devono fermarsi subito.

### Test 6 — Controllo Remoto Web, Monitor Regia & OSC su LAN reale
- [ ] Apri `F8`, avvia i servizi e inquadra il QR da uno smartphone/tablet sulla stessa Wi-Fi.
- [ ] Rinomina una cue inserendo caratteri speciali tipo `<img src=x onerror=alert(1)> & "test"` → sullo smartphone deve apparire come **testo semplice**, nessun popup/script eseguito.
- [ ] Mentre un video è in onda (stato aggiornato 4 volte al secondo), tocca rapidamente **`[ ▶ GO ]`** su una cue nella lista del telefono → il tap deve partire al primo colpo senza mancare il clic.
- [ ] Sul PC clicca **`⛔ Disconnetti Tutti`** → lo smartphone deve mostrare la schermata di blocco PIN **entro 1 secondo** (non dopo 10 s) senza andare in lockout.
- [ ] Invia comandi OSC da un'app (es. TouchOSC, `oscsend`, o script Python qui sotto):
  - `/pause` inviato **due volte** → mette in pausa e **resta** in pausa (non riavvia al secondo invio!).
  - `/resume` inviato **due volte** → riprende e **resta** in play.
  - `/pause_toggle` → alterna pausa/play.

Script rapido open source (zero librerie extra) per testare OSC dal terminale di un secondo PC o in locale:

```bash
.venv/bin/python -c "
import socket, sys; sys.path.insert(0, 'blindcue')
from services.osc_protocol import build_osc_message
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for addr in ('/go', '/pause', '/pause', '/resume', '/resume', '/blackout'):
    s.sendto(build_osc_message(addr), ('127.0.0.1', 53000))
    print('Sent', addr)
"
```

### Test 7 — Audio PFL, Earcons e Doppia Uscita (se hai 2 schede / 2 proiettori)
- [ ] **Con 2 schede audio:** imposta Master = casse/mixer, Monitor PFL = cuffie USB. Attiva `View → Segnali Acustici Operatore (Earcons)` e premi GO / Pausa → i bip operatore devono sentirsi **solo in cuffia**, silenzio assoluto sul Master sala.
- [ ] **Con 2 proiettori esterni:** attiva **Due uscite indipendenti**, lancia `Q-4` su A e `Q-11` su B; poi scambia **Proiettore B** sullo schermo di **A** dal pannello dei layer → i due schermi devono invertirsi pulitamente (mai due finestre sullo stesso schermo).
- [ ] **Hot-unplug HDMI:** mentre `Q-4` (video) è in onda su L1, scollega e ricollega il cavo HDMI (o cambia risoluzione nel sistema) → nessun crash; al ricollegamento il video su L1 non sparisce dietro schermo nero.

### Test 8 — Archivio Portatile, Autosave e Crash Recovery
- [ ] Configura almeno 1 **Superficie personalizzata** (`F7`) con maschera `mask_finestra.png` e un **Layer 0** personalizzato (`img_sfondo_4k.jpg`).
- [ ] Salva con **`Ctrl+Shift+S` → Sì (copia i media)** in `/tmp/prova_bundle/show.blindcue`.
- [ ] Verifica in `/tmp/prova_bundle/show_media/`:
  - ci sono sia `stesso_nome.wav` sia `stesso_nome_2.wav` (nonostante la dimensione identica in byte!), più la maschera e il Layer 0;
  - sposta la cartella `/tmp/prova_bundle` in `/tmp/prova_spostata` e aprila in BlindCUE → **0 cue OFFLINE**, i gruppi risultano `LOADED`, Q-13 e Q-14 suonano le due note diverse (400 Hz e 900 Hz).
- [ ] **Test Crash Recovery vero:** modifica la scaletta e aggiungi una superficie, attendi 2 secondi (autosave), poi termina bruscamente BlindCUE con `kill -9 <PID>` → riavvia BlindCUE → deve proporre il **Crash Recovery** e ripristinare **sia le cue sia le superfici di proiezione**!

### Test 9 — Anti-Sospensione (`SleepInhibitor`) & Chiusura pulita
- [ ] Con BlindCUE aperto, controlla da terminale:
  ```bash
  systemd-inhibit --list | grep -i blindcue
  ```
  Deve risultare attivo il blocco `sleep:idle` (`mode=block`).
- [ ] Chiudi BlindCUE cliccando la **`X`** della finestra (non `Ctrl+C`):
  - verifica che il processo Python termini entro 1–2 secondi (nessun processo appeso in `ps aux | grep main.py`);
  - verifica che `systemd-inhibit --list | grep -i blindcue` sia vuoto;
  - verifica con `ss -tulnp | grep -E "8080|53000"` che le porte Web/OSC siano state liberate.

### Test 10 — Stress Memoria, CPU e Soak Test (minimo 30–60 minuti)
- [ ] Seleziona `Q-12` (`audio_lungo_90min.mp3`): osserva la RAM del processo durante l'estrazione della forma d'onda. Non deve esserci un picco da centinaia di MB e la UI deve restare fluida.
- [ ] Lascia girare in loop per **30–60 minuti** una scena con video L1 + audio L2 + immagine L3 (con Web Remote aperto su uno smartphone) monitorando ogni 5 minuti con questo one-liner:

```bash
PID=$(pgrep -f "blindcue/main.py" | head -n1)
while kill -0 "$PID" 2>/dev/null; do
  printf "%s | RSS=%s kB | FD=%s | THR=%s\n" \
    "$(date +%H:%M:%S)" \
    "$(awk '/VmRSS/{print $2}' /proc/$PID/status)" \
    "$(ls /proc/$PID/fd | wc -l)" \
    "$(awk '/Threads/{print $2}' /proc/$PID/status)"
  sleep 60
done
```

**Cosa significa PASS:**
- `FD` (file descriptor) resta costante dopo i primi 2 minuti (es. oscilla ±2, non sale mai all'infinito);
- `THR` (thread) resta stabile;
- `RSS` raggiunge un plateau e non cresce linearmente ogni minuto;
- temperatura CPU/GPU e fluidità visiva sul proiettore restano stabili;
- nessun errore in `blindcue.log`.

---

## 4. Come segnalare un eventuale bug trovato in prova

Se qualcosa va storto durante uno dei 10 test, annota subito:
1. Numero del test e azione esatta fatta (es. *"Test 4, cliccato PAUSA TUTTO a 1.2s di Pre-Delay"*).
2. Ultime ~100 righe del log: `tail -n 100 ~/.local/share/BlindCue/blindcue.log`.
3. Output di `RSS / FD / THR` se il problema era un rallentamento o un blocco.
4. Versione OS, compositore Wayland (KDE/GNOME/Hyprland/Sway) e se eri in modalità Singola, Span o Doppia Uscita.

Con quei 4 elementi è quasi sempre possibile riprodurre il problema e trasformarlo subito in un nuovo test automatico dentro `tests/test_audit_regressions.py`.
