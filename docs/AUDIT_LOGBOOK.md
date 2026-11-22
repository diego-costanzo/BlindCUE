# Diario di Bordo — Audit di Affidabilità Live & Ottimizzazioni

Memoria tecnica operativa delle verifiche, dei bug risolti e dei punti ancora da collaudare sul campo per le prossime iterazioni di **BlindCUE**.

- **Data sessione:** 22 novembre 2026
- **Obiettivo:** portare BlindCUE a uno standard sicuro per spettacoli dal vivo su Linux (Wayland nativo), risolvendo bug critici, race condition, leak di risorse e falle operative **senza aggiungere dipendenze esterne** e mantenendo il codice **100% open source** (solo stdlib Python + PySide6, NumPy, qrcode, FFmpeg/systemd-inhibit/vainfo).
- **Esito verifiche automatiche:** `ruff check` = **0 errori**; `pytest -v tests/` = **177/179 PASS** (`exit code 0`, 0 warning; 2 skipped su display headless/mock), di cui 20 test di regressione in [`tests/test_audit_regressions.py`](../tests/test_audit_regressions.py) e suite estesa isolata dalle impostazioni utente.

Per il collaudo hardware precedente vedi [TEST_FINDINGS.md](TEST_FINDINGS.md).
Per la guida architetturale e di fork vedi [ARCHITECTURE.md](ARCHITECTURE.md).
Per la scaletta guidata di collaudo sul campo (audio/video/immagini/LAN/soak) vedi [LIVE_TEST_PLAYBOOK.md](LIVE_TEST_PLAYBOOK.md).

---

## 1. Registro Completo Bug Trovati e Soluzioni Applicate

### 1.1 Priorità 0 — Critici da palcoscenico (Bloccanti / Crash / Schermo sbagliato)

| ID | Problema riscontrato | Causa radice | Soluzione applicata | File |
|---|---|---|---|---|
| **C1** | `NameError` alla fine di qualsiasi cue (EOF, immagine a tempo, post-delay) | `ShowEngine` e `GroupMode` usati in `_finalize_cue_exit()` senza essere importati in `main.py`; `test_duration` definito tardi; nessun `try/except` nei tick 30 Hz | Importati `ShowEngine` e `GroupMode`, spostata l'inizializzazione di `test_duration`, protetti `_on_live_img_tick()` e `_on_scheduler_finished()` con `try/except` | `blindcue/main.py` |
| **C2** | `Ctrl+B` (Blackout), `F5` (Modalità LIVE), `F7`, `Shift+F7`, `Ctrl+Y` bloccati da Qt (`Ambiguous shortcut overload`) | Scorciatoie registrate due volte: come `QAction` nella menu bar e come `QShortcut` in `_setup_shortcuts()`; `Redo` duplicava `Ctrl+Y` | Rimossi i `QShortcut` duplicati lasciando le `QAction` come unica fonte di verità; deduplicati gli shortcut di `_act_redo` | `blindcue/ui/main_window/_window_setup.py`, `blindcue/ui/main_window/_menu.py` |
| **C3** | Race condition di `show_fallback()`: un GO lanciato entro 215 ms da un Blackout veniva cancellato dal vecchio timer di fade | `OutputWindow.show_fallback()` usava `QTimer.singleShot` anonimo e non cancellabile | Introdotti `_fallback_timer` gestito + contatore generazionale `_fallback_gen` e `_cancel_fallback_timer()` chiamato ad ogni `show_image`, `show_video_widget`, `ensure_live_video_visible`, `clear_all_layers`, `panic_blackout`, `force_close` | `blindcue/ui/output_window.py` |
| **C4** | Il blocco di sicurezza Layer (`🔒 BLOCCO LAYER`) in modalità LIVE non bloccava mai lo scrub | `_LiveLayerBar.set_locked()` aggiornava lo stile ma non assegnava `self._locked = bool(locked)`; tooltip incoerente `(3s)` vs `1,2s` | Assegnato `self._locked = bool(locked)` in `set_locked()` e allineato tooltip a `(1,2s)` | `blindcue/ui/live_status_panel.py` |
| **C5** | Seek sul deck video LIVE invece che sul deck idle durante il pre-cue | `_on_deck_status` chiamava `self._standby_player.setPosition(...)` invece del deck `deck_idx`: quando `_active_deck == 1` faceva saltare il video in onda | Usato `idle_p, _ = self._deck_pair(deck_idx); idle_p.setPosition(...)` controllato da `_standby_seek_pending` | `blindcue/engine/player_live.py` |
| **C6** | Watchdog caricamento bloccato (`LoadingMedia`/`StalledMedia`) inefficace su Qt6 | Qt6 imposta `PlayingState` subito dopo `play()` anche a media bloccato in `LoadingMedia`, facendo uscire subito `_recover_stalled_load()` | Tracciati `_media_progressed` / `_play_started_pos_ms`; il watchdog considera sano il playback solo se c'è progresso/buffering reale e lo stato non è `LoadingMedia`/`StalledMedia`/`InvalidMedia`/`NoMedia` | `blindcue/engine/player_live.py` |
| **C7** | Chiusura da UI (`X` o `File → Quit`) non eseguiva `_perform_shutdown()` | `_perform_shutdown()` era collegato solo a `SIGINT`/`SIGTERM`, lasciando server Web/OSC, player e timer attivi durante l'uscita | Collegato `app.aboutToQuit` a `_perform_shutdown(from_about_to_quit=True)` con guardia idempotente `_shutdown_state["performed"]` | `blindcue/main.py` |

---

### 1.2 Priorità 1 — Stabilità Operativa, Remoto LAN, Persistenza

| ID | Problema riscontrato | Causa radice | Soluzione applicata | File |
|---|---|---|---|---|
| **A1** | Cliccare il pulsante `GO` mentre il focus era su una `QComboBox` (es. Ispettore) veniva ignorato | `_on_go()` bloccava l'esecuzione per qualsiasi focus su `QLineEdit`/`QAbstractSpinBox`/`QComboBox` | Separato `_on_go_shortcut()` (per il tasto `Spazio`, rispetta i campi di input) da `_on_go()` (click su pulsanti/doppio clic, esegue sempre) | `blindcue/ui/main_window/_transport.py`, `_menu.py` |
| **A2** | Scambiare Proiettore B sullo schermo di A assegnava entrambi allo stesso schermo `(sA, sA)` | `set_output_screen("B", screen)` non salvava il vecchio `_output_b_screen` prima di sovrascriverlo | Scambio atomico `self._output_a_screen, self._output_b_screen = self._output_b_screen, screen` + aggiornamento `_target_screen` | `blindcue/engine/device_manager.py` |
| **A3** | Cue LIVE orfane su `Nuovo Show`, `Apri Show`, `Elimina Cue` e riferimenti obsoleti dopo `Undo` | Sostituzione/rimozione di `self._cues` senza fermare i layer live; lookup per identità oggetto (`is`/`list.index`) rotto dopo `Undo` | `_on_new_show()` e `_open_project_file()` fermano i layer attivi (solo dopo caricamento riuscito nel caso Open); `_on_delete_cue()` svuota il layer attivo della cue eliminata; riconciliazione per `cue_id` in `main.py`, `ShowEngine.auto_follow_target()` e `finish_live_cue_status()` | `_persistence.py`, `_cue_manip.py`, `_remote.py`, `main.py`, `show_engine.py` |
| **A4** | Web Remote / Monitor Regia: XSS nei nomi/note, case mismatch (`"LIVE"` vs `"live"`), tocchi persi ogni 250 ms, SSE che restavano aperti 10 s su revoca/stop, Slowloris, assenza Uscita B | `innerHTML` non escapato e riscritto a 4 Hz, `Connection: keep-alive` che teneva aperto il socket dopo l'uscita dal loop SSE, nessun `timeout` socket, nessuna decodifica URL per `?pin=`, nessun limite SSE | Aggiunti `escapeHtml()`, normalizzazione `.toLowerCase()`, label `⚠ OFFLINE`, diffing firma scaletta prima di toccare il DOM, probe `/api/status` su `onerror` SSE, pannello Uscita B su Monitor Regia, `timeout = 10`, `MAX_SSE_CLIENTS = 32`, `urllib.parse.parse_qs`, `do_OPTIONS`, sentinella `_SSE_CLOSE` + `self.close_connection = True` | `blindcue/services/web_server.py`, `blindcue/ui/main_window/_remote.py` |
| **A5** | Ricostruzione completa `6 × N` `QTableWidgetItem` in `LiveShowPanel.sync_cues()` anche a 10 Hz durante Pre/Post-Delay | Allocazione continua di oggetti Qt + scansioni $O(N^2)$ per gruppi/figli; conflitti layer non passati alle celle LIVE | Riuso in-place dei `QTableWidgetItem`, indicizzazione $O(N)$ (`cue_by_id`, `children_by_parent`), fast-path $O(1)$ `update_phase_badge(cue_id, text)` e propagazione `ROLE_LAYER_CONFLICT` + tooltip | `blindcue/ui/live_show_view.py`, `blindcue/ui/main_window/_remote.py` |
| **A6** | Le superfici di proiezione venivano perse nell'autosave / crash recovery | `_auto_save()` non serializzava `surfaces` e `_check_crash_recovery()` non le ripristinava; `settings` non era deep-copied verso il worker thread | Aggiunte `surfaces` in `_auto_save()` e ripristino in `_check_crash_recovery()`; `copy.deepcopy(settings)` in `build_autosave_payload()` | `blindcue/ui/main_window/_persistence.py`, `blindcue/models/project_manager.py` |
| **A7** | OSC & Web: `/pause` e `/resume` erano toggle (non idempotenti); blob OSC negativo non controllato; whitelist OSC aggirabile con `sender_addr == ""`; nessun rate-limit su `/auth` | Stesso segnale `pause_toggle_requested` per tutti i comandi; `b_len < 0` mancante; condizione `and sender_addr` nella whitelist | Segnali distinti `pause_requested` / `resume_requested` / `pause_toggle_requested` collegati a `MainWindow.pause_all_set` idempotente; check `b_len < 0`; whitelist stretta (`sender_addr not in self._allowed_ips`); lockout 5 tentativi / 30 s su OSC; match case-sensitive del prefisso PIN; risoluzione cue remota per `cue_id` → `q_label`/nome → indice 1-based | `osc_protocol.py`, `osc_server.py`, `web_server.py`, `remote_manager.py`, `window.py`, `_remote.py`, `main.py` |
| **A8** | Freeze del thread GUI su Wi-Fi di teatro offline durante apertura/aggiornamento Remoto | `get_local_lan_ips()` chiamava `socket.getaddrinfo(hostname, ...)` (DNS bloccante fino a 5–10 s) e non aveva cache; `_broadcast_timer` girava sempre anche a server spento | Rimossa chiamata DNS bloccante (usati solo `QNetworkInterface` + route UDP con `with socket.socket(...)`), cache TTL 15 s, `_broadcast_timer` avviato/fermato col server Web, snapshot protetto da lock | `blindcue/services/remote_manager.py` |
| **A9** | Sospensione automatica o screensaver del PC durante lo spettacolo | Nessuna inibizione di risparmio energetico a livello OS (già verificatosi in collaudo reale — `TEST_FINDINGS.md §6.6`) | Creato `SleepInhibitor` stdlib (`systemd-inhibit --what=sleep:idle --mode=block cat` su Linux tramite pipe così anche un `SIGKILL` rilascia il lock; `caffeinate` su macOS; `SetThreadExecutionState` su Windows) | `blindcue/engine/sleep_inhibitor.py`, `blindcue/main.py` |

---

### 1.3 Priorità 2/3 — Memoria, Architettura, Sicurezza UI e Rifiniture

| ID | Problema riscontrato | Soluzione applicata | File |
|---|---|---|---|
| **M1** | Leak di `QTimer(self)` ad ogni fade/swap | Chiamato `deleteLater()` in `_stop_timer_entry()`, `force_close()` e `_stop_fade_timer()`; reset pulito di `_manual_fade_active` in `set_volume()` | `output_window.py`, `player_live.py` |
| **M2** | Picchi di RAM (200–700 MB) nella decodifica waveform di file lunghi e cache loudnorm non atomica | Streaming PCM a chunk da 64 KiB con riduzione picchi dinamica $O(\text{target\_width})$ (< 2 MB anche su file di 3 ore) + `child_process_kwargs()` + deadline reale via `selectors`; `render_normalized_media()` usa hash SHA-256 comprensivo di LUFS/TP/LRA e scrittura atomica `.tmp` → `os.replace` | `blindcue/engine/audio_analyzer.py` |
| **M3 / B4** | Violazione architetturale `engine/device_manager.py → ui/hardware_info.py`; `QOpenGLContext` ricreato a ogni lettura; falso positivo VA-API su `llvmpipe` | Estratto `blindcue/engine/hardware_profile.py` con cache statica e probe VA-API reale (`vainfo` / `/dev/dri/renderD128`, escludendo renderer software `llvmpipe`/`swrast`); `ui/hardware_info.py` fa re-export retrocompatibile | `engine/hardware_profile.py`, `engine/device_manager.py`, `ui/hardware_info.py` |
| **M4** | Crash/stale state in `DeviceSettingsDialog` su hot-plug/unplug di schermi o schede audio | Collegati `audio_devices_changed` e `screens_changed` (disconnessi in `done()`) e verifica `screen in available_screens` prima di applicare | `blindcue/ui/device_settings_dialog.py` |
| **M5** | Gruppi ignorati dentro catene `SIMULTANEOUS` e `GroupMode.LOOP` con 1 solo figlio che usciva dal gruppo | Gestiti rami `MediaType.GROUP` in `_fire_cue_chain()` e standby bloccato su `children[0]` in `_fire_group_cue()` per `LOOP` a 1 figlio | `blindcue/ui/main_window/_transport.py` |
| **M6** | Ricreazione maschere PNG/feather e decodifica `QPixmap`/`toImage()` ripetute | Cache LRU (8 maschere, 16 pixmap) in `OutputWindow`; cache `self._image_qimage` in `StudioPreviewMonitor` invece di `toImage()` a 30 fps | `output_window.py`, `preview_monitor.py` |
| **M7** | Collisione nel salvataggio portatile tra file omonimi della stessa dimensione ma contenuto diverso; gruppi caricati come `OFFLINE`; Layer 0 / maschere non archiviati | Confronto SHA-256 in `_files_identical()`, pulizia `.tmp` su errore, archiviazione e risoluzione sicura (anti-traversal) di `layer0_image` e `mask_image_path`, `MediaType.GROUP` sempre `LOADED` | `blindcue/models/project_manager.py` |
| **M8** | Valori `NaN`/`Inf` o fuori range in JSON corrotto non sanificati in `Cue.from_dict()` | Helper `_safe_float`/`_safe_int`/`_safe_opt_float` applicati a tutti i campi numerici di `Cue.from_dict()` e `CueSection.from_dict()` | `blindcue/models/cue.py` |
| **M9** | Earcons di accessibilità suonavano sul dispositivo predefinito (rischio PA sala) + bip pausa spurio su Blackout/Panic | Aggiunta `EarconManager.set_audio_device()` collegata al monitor PFL in `DeviceManager` e flag `silent=True` su `set_global_paused(False)` durante Blackout/Panic | `earcon.py`, `device_manager.py`, `main.py`, `_transport.py`, `_remote.py` |
| **M10 / B6** | Dialogo Remoto: segnale `activity_updated` mai disconnesso, loop su `setChecked`, rigenerazione QR a ogni carattere del PIN, `singleShot` su widget chiusi, `_apply_ports` riaccendeva entrambi i servizi, porta OSC hardcoded `53000` | Disconnessione in `done()`, `blockSignals` sui checkbox, timer debounce 300 ms sul PIN, `_flash_button_text()` con timer posseduto, `_apply_ports()` riavvia solo i servizi abilitati, prontuario OSC dinamico | `blindcue/ui/remote_control_dialog.py` |
| **M11** | Collisione di `surface_id` dopo elimina + aggiungi/duplica in `SurfaceMappingDialog` | Helper `_next_unique_surface_id()` che garantisce unicità rispetto a tutte le superfici esistenti | `blindcue/ui/surface_mapping_dialog.py` |
| **M12** | Un singolo tocco involontario di `ESC` in modalità LIVE scatenava PANIC immediato | Doppia pressione `ESC` entro 0,6 s in modalità LIVE (con avviso esplicito in status bar al primo tocco); pulsante PANIC a schermo e `/panic` Web/OSC restano istantanei (0 ms) | `_window_setup.py`, `live_show_view.py`, `window.py` |
| **B1 / B2 / B3 / B5 / B7** | Attributi sbagliati in `apply_theme()`, errore waveform che puliva un'altra cue selezionata, `primaryScreen() is None`, `configure_screen()` che nascondeva L1 su hotplug, doppio decoder video su loop full-file | Corretti `_live_status`/`_inspector` in `apply_theme()`, guardia path in `_on_analyzer_failed()`, guardia `None` in `main.py`, riapplicazione layout L1–L3 in `configure_screen()`, pre-cue standby video solo quando `out_point` è impostato | `_window_setup.py`, `_waveform_worker.py`, `main.py`, `output_window.py`, `player_live.py` |

---

## 2. File Creati e Modificati

### Nuovi file
- `blindcue/engine/sleep_inhibitor.py` — inibitore sleep/screensaver cross-platform 100% stdlib.
- `blindcue/engine/hardware_profile.py` — profiler hardware, probe VA-API reale e `ShowRuntimeGuard` nel layer `engine/`.
- `tests/test_audit_regressions.py` — 20 test automatici di regressione su tutte le aree sopra.
- `docs/AUDIT_LOGBOOK.md` — questo diario di bordo.

### File di codice modificati
`blindcue/main.py`, `blindcue/engine/audio_analyzer.py`, `blindcue/engine/device_manager.py`, `blindcue/engine/earcon.py`, `blindcue/engine/player_live.py`, `blindcue/engine/show_engine.py`, `blindcue/models/cue.py`, `blindcue/models/project_manager.py`, `blindcue/services/osc_protocol.py`, `blindcue/services/osc_server.py`, `blindcue/services/remote_manager.py`, `blindcue/services/web_server.py`, `blindcue/ui/device_settings_dialog.py`, `blindcue/ui/hardware_info.py`, `blindcue/ui/live_show_view.py`, `blindcue/ui/live_status_panel.py`, `blindcue/ui/output_window.py`, `blindcue/ui/preview_monitor.py`, `blindcue/ui/remote_control_dialog.py`, `blindcue/ui/surface_mapping_dialog.py`, `blindcue/ui/main_window/window.py`, `_menu.py`, `_window_setup.py`, `_transport.py`, `_remote.py`, `_persistence.py`, `_cue_manip.py`, `_waveform_worker.py`.

### Documentazione allineata
`README.md`, `docs/MANUAL.md`, `docs/ARCHITECTURE.md`, `docs/TEST_FINDINGS.md`.

---

## 3. Cosa Verificare Nelle Prossime Iterazioni (Checklist da Palco / Reale)

Le correzioni sono coperte da **150 test headless**, ma su un software da spettacolo restano verifiche che solo l'hardware reale (Wayland + proiettori + schede audio + LAN) può certificare definitivamente:

### Verifiche prioritarie sul campo (Linux Wayland reale)
1. **Doppia pressione `ESC ×2` e `Ctrl+B` / `F5` reali su KDE Plasma / GNOME Wayland:** verificare la risposta tattile in regia, la rapidità di blackout/panic e che il doppio `ESC` entro 0,6 s sia comodo anche al buio.
2. **`SleepInhibitor` su sessione desktop reale:** verificare con `systemd-inhibit --list` che il lock `BlindCue` compaia all'avvio e scompaia immediatamente sia su chiusura normale (`X` / `Ctrl+Q`) sia su `kill -9`.
3. **Probe VA-API reale (`hardware_profile.py`):** verificare su Intel/AMD con e senza `vainfo` installato che la barra di stato e il dialogo Hardware mostrino correttamente `VA-API` vs `EGL` vs `SW`.
4. **Hot-unplug / hot-plug HDMI e USB Audio durante lo show:** staccare e riattaccare il cavo del proiettore mentre L1 riproduce un video, e verificare che `configure_screen()` mantenga il video visibile senza schermate nere e che `DeviceSettingsDialog` si aggiorni senza crash.
5. **Web Remote & Monitor Regia da smartphone/tablet reali sulla stessa LAN:**
   - testare il tocco rapido su `[ ▶ GO ]` nella scaletta mentre il playhead aggiorna a 4 Hz (nessun tap perso);
   - testare `⛔ Disconnetti Tutti` e verificare che lo smartphone mostri subito la schermata PIN senza attendere 10 s e senza bloccarsi per 30 s;
   - testare il Monitor Regia in modalità Doppia Uscita (verifica visibilità B·L1..B·L3).
6. **Routing Earcons con 2 schede audio fisiche:** verificare che i suoni di conferma operatore escano esclusivamente in cuffia PFL e mai sull'impianto Master sala.
7. **Waveform streaming su file audio lunghi (1–3 ore):** importare una registrazione di spettacolo intero (> 90 min) e monitorare RSS (`htop` / `/proc/self/status`) per confermare l'assenza di picchi RAM.
8. **Salvataggio portatile + trasferimento su altro PC:** salvare uno show con Layer 0 personalizzato, maschera PNG di superficie, gruppi e file omonimi, spostare la cartella su un'altra macchina e verificare che si apra con 0 cue `OFFLINE`.

### Debito tecnico / evoluzioni future da valutare (non bloccanti)
- **Soak test di lunga durata (> 2–3 ore continue)** su hardware reale con media misti audio/video/immagini e Web Remote connesso.
- **Codec video oltre H.264** (HEVC/H.265, VP9, AV1, ProRes, 4K 10-bit) e audio multicanale 5.1/7.1.
- **Compositing GPU (`QOpenGLWidget` / RHI zero-copy)** per portare oltre 1 video 1080p per uscita in Dual Mode anche su hardware datato (vedi `TEST_FINDINGS.md §6.1`).
- **Collaudo manuale completo su Windows 10/11 e macOS** (incluse verifica `caffeinate` e `SetThreadExecutionState` di `SleepInhibitor`).
- **Preload opzionale della cue video in standby** per azzerare i ~140–290 ms del primo frame a freddo su macchine lente.
- **Test automatici degli installer** (`setup/common/installer_core.py`, `setup/linux/install.sh`) e verifica dei mixin UI rimanenti (`group_timeline_editor.py`, `mask_dialog.py`) su casi estremi.

---

## 4. Valutazione Prontezza Produzione, Roadmap & Limite GPU/Compositing

### 4.1 Il software è pronto per andare in produzione (spettacoli veri)?
**Sì, una volta superati i 10 test reali di [LIVE_TEST_PLAYBOOK.md](LIVE_TEST_PLAYBOOK.md) (incluso il soak test di 30–60+ minuti) sulla macchina di regia reale.**

Dal punto di vista del codice e dell'architettura, BlindCUE è oggi pulito, leggero, privo di dipendenze proprietarie e protetto da 150 test automatici. Per andare in scena in sicurezza restano 3 regole operative fondamentali (valide per qualsiasi software live):
1. **Prova generale completa** con gli esatti file, proiettori, cavi e schede audio dello spettacolo (preferendo H.264/MP4 standard a frame rate costante CFR, evitando VFR da smartphone o codec esotici non provati prima).
2. **Rispetto del budget video della macchina** (verificato durante la prova generale).
3. **Copia di sicurezza su chiavetta USB** salvata come archivio portatile (`Ctrl+Shift+S → Sì`), con il PC di regia pulito (niente browser aperti, niente aggiornamenti di sistema prima della replica).

### 4.2 Cosa implementare nelle prossime iterazioni (valore alto, codice leggero)
- **Verifica Scaletta Pre-Show (Pre-Flight check):** pulsante che controlla in un colpo solo file `OFFLINE`, presenza VA-API, conflitti di layer, codec/VFR a rischio e spazio disco libero.
- **Preload opzionale della prossima cue video in standby:** riduce il micro-ritardo a freddo (~140–290 ms) al primo frame su macchine datate.
- **Soak test certificato (2–3 ore continue)** e verifica sul campo su **Windows 10/11** e **macOS**.

### 4.3 Cosa NON fare / evitare (per preservare leggerezza e stabilità)
- **Non aggiungere** editor/transcoder integrati, database (SQLite), framework web pesanti (Electron/React), servizi cloud o librerie/SDK proprietari.
- **Non riscrivere** la struttura a mixin di `MainWindow` né introdurre un renderer custom OpenGL/Vulkan *a meno che* non servano davvero **2–3 video 1080p simultanei su entrambe le uscite** in modalità Dual.
- **Non reintrodurre** scorciatoie duplicate (`QAction` + `QShortcut`), `QTimer.singleShot` anonimi sull'output, chiamate DNS bloccanti (`socket.getaddrinfo`) sul thread GUI o import `ui/` dentro `engine/`.

### 4.4 Chiarimento tecnico: GPU dedicata/VA-API vs video simultanei
Anche con una **GPU dedicata o integrata con VA-API/NVDEC attiva**, il limite dei molti video simultanei in Doppia Uscita **non sparisce del tutto**, perché il rendering video ha **due fasi**:
1. **Decodifica (H.264 → frame grezzi):** svolta dalla GPU (VA-API/NVDEC). Qui una buona GPU fa un'enorme differenza (riduce la CPU di 5–6 volte e impedisce il surriscaldamento).
2. **Composizione nella finestra (`OutputWindow`):** oggi `OutputWindow` usa `QGraphicsView` con **viewport raster (CPU)**, non un percorso GPU zero-copy. Quindi i frame decodificati dalla GPU vengono comunque ricopiati in RAM (`NV12 → RGB`) e composti da **un solo thread CPU**.

**In pratica:**
- Con **GPU attiva + CPU moderna** (veloce in single-thread), la singola uscita regge facilmente 3 video 1080p e la doppia uscita regge bene 1 video per proiettore (spesso anche 2 su CPU moderne) senza scatti.
- Su **CPU vecchie** (es. laptop del 2014), anche con VA-API attiva, superare 1 video 1080p per uscita in Dual Mode satura il thread di composizione raster.
- Solo passando in futuro a un **compositor GPU zero-copy (Qt RHI / OpenGL texture diretta)** il limite dei molti video simultanei in Dual Mode sparirebbe del tutto. Finché gli spettacoli usano 1 video per proiettore (più immagini e audio sugli altri layer), l'architettura attuale è più semplice, portabile su Wayland e molto più stabile.

### 4.5 Evoluzione futura: GPU Zero-Copy (100% Open Source)
Il **GPU zero-copy** non è un componente proprietario né un limite hardware: è un'**architettura software 100% open source** già standard su Linux (Kernel **DRM/DMA-BUF** + **Mesa/VA-API** + **Wayland** + shader **OpenGL/Vulkan**), in cui il frame video decodificato resta nella memoria video della GPU come handle **DMA-BUF** e viene composto direttamente via shader senza mai tornare in RAM/CPU (`NV12 → RGB` su GPU).

**Opzioni 100% open source compatibili con la licenza MIT di BlindCUE:**
1. **Qt6 Quick / RHI (`QQuickWindow` + `VideoOutput` + shader RHI):** già incluso in **PySide6 (LGPLv3)** — **zero nuove dipendenze esterne**, cross-platform (Vulkan/OpenGL/Metal/Direct3D) e nativo su Wayland. È la scelta più naturale e coerente con la leggerezza di BlindCUE.
2. **`libmpv` o `GStreamer` (`LGPLv2.1+`):** motori multimediali Linux maturi con pipeline DMA-BUF zero-copy collaudata, ma aggiungono una dipendenza nativa di sistema.

**Quando serve davvero:**
- **Spettacoli complessi / grandi produzioni:** 2–3+ video 1080p/4K simultanei su entrambi i proiettori in Doppia Uscita (es. crossfade continui tra video multipli su più layer o videomapping pesante).
- **CPU più scarica:** tenere il processore libero per altri software in background sulla stessa macchina di regia (console luci DMX/QLC+, mixer audio/Ardour, registrazione o streaming).

**Preparazione architetturale:**
Grazie all'interfaccia pulita di `OutputWindow`, un'eventuale migrazione a Qt6 Quick/RHI zero-copy in **v0.2/v1.0** richiederebbe di sostituire **solo il backend grafico di `OutputWindow`**, senza toccare motore cue, gruppi, sezioni, audio, salvataggio `.blindcue`, Web Remote né OSC.

**Conclusione operativa attuale (v0.1):**
Una volta superati i test reali con la scaletta di [LIVE_TEST_PLAYBOOK.md](LIVE_TEST_PLAYBOOK.md), BlindCUE è **stabile e robusto per spettacoli standard** (e, su macchine con CPU moderna/potente, regge bene anche **show più complessi**), mantenendo il progetto leggero, manutenibile e 100% open source.

---

## 5. Integrazione Pull Request #1–#20 & Nuove Pipeline di Sistema

A seguito dell'audit di affidabilità, sono state integrate su `main` le 19 Pull Request del collaboratore (`ciechomir`), portando la suite di test automatizzati a **177 passed, 2 skipped** con isolamento totale dell'ambiente utente (`test/isolate-user-settings`).

### 5.1 Riepilogo Completo delle 19 PR Integrate

| PR | Branch / Commit | Categoria | Descrizione e Impatto Operativo |
|---|---|---|---|
| **#1** | `fix/eof-freeze` (`2b83fd0`) | Motore Live | Risolto il freeze permanente alla fine naturale di riproduzione di una cue. |
| **#3** | `fix/portable-shows` (`55c7019`) | Persistenza | Mantenimento della modalità show portatile anche dopo la riapertura del progetto. |
| **#4** | `fix/recent-projects-windows` (`a9afbca`) | UI / Piattaforma | Normalizzazione dei percorsi recenti su Windows per rimozione affidabile da elenco. |
| **#5** | `fix/output-hotplug-fullscreen` (`5821f10`) | Display | Passaggio immediato a tutto schermo del proiettore collegato a caldo durante l'esecuzione. |
| **#6** | `fix/single-instance` (`b4c77fd`) | Sistema | Istanza singola tramite `QLocalServer`/`QLocalSocket`: previene avvii doppi accidentali. |
| **#7** | `feat/translations-and-manual` (`109b547`) | i18n / Docs | Livello di traduzione UI leggero (Italiano, English, Polski) e manuale utente completo in 3 lingue. |
| **#9** | `feat/output-f11` (`15f0f47`) | UI / Output | Tasto `F11` (ed `Esc`) per alternare finestra e fullscreen nell'anteprima a schermo singolo. |
| **#10** | `fix/preview-16-9` (`cd45b3e`) | Output | Mantenimento del formato nativo 16:9 nella finestra di anteprima flottante senza distorsioni. |
| **#11** | `feat/audio-cues-layer2` (`0379b0e`) | Workflow | Assegnazione automatica delle nuove cue audio al Layer 2 per separarle dal video (L1). |
| **#12** | `fix/cue-list-buttons-grid` (`15eee61`) | UI | Riorganizzazione dei pulsanti sotto la scaletta cue in griglia compatta 2×4. |
| **#13** | `feat/crossfade` (`eb7358d`) | Rendering | Dissolvenza incrociata (crossfade) tra cue sullo stesso layer (foto/video/immagini). |
| **#14** | `feat/text-cues` (`6054293`) | Cue Engine | Cue di testo e didascalie sovrapposte su Layer 3 (Overlay) con rendering vettoriale e dialog dedicato. |
| **#15** | `fix/app-version` (`9390e35`) | Packaging | Centralizzazione della versione dell'applicazione in un unico file `blindcue/version.py`. |
| **#16** | `fix/setup-run-install-bat` (`067c6eb`) | Setup Windows | Avvio robusto di `install.bat` come `.\install.bat` da PowerShell e ambienti Windows. |
| **#17** | `feat/remember-speakers` (`4b2f9cc`) | Audio | Memorizzazione per-computer dell'uscita audio principale/cuffia con etichetta neutra di sistema. |
| **#18** | `feat/manual-sources` (`dce2750`) | Documentazione | Sorgenti HTML modulari (`docs/manual/manual_*.src.html`) e toolchain di compilazione manuali (`tools/`). |
| **#19** | `feat/windows-installer` (`160589f`) | CI/CD | Installer autonomo Inno Setup compilato via GitHub Actions (`.github/workflows/windows-installer.yml`). |
| **#20** | `test/isolate-user-settings` (`344cae4`) | Testing | Isolamento completo del runner pytest da `QSettings` reali e autosave utente. |

---

### 5.2 Toolchain e Pipeline Automatizzate

#### Pipeline del Manuale Multilingua (`tools/`)
- `tools/make_manual_media.py`: Genera file multimediali neutri con FFmpeg (due gradienti colore, pattern video di test con tono a 330 Hz, toni audio 440/262 Hz) per evitare foto personali nella documentazione.
- `tools/manual_screenshots.py`: Guida l'applicazione reale a finestra invisibile (off-screen a coordinate negative) nelle tre lingue (`it`, `en`, `pl`), catturando le 17 schermate ufficiali per ogni lingua.
- `tools/build_manual.py`: Compila i sorgenti `docs/manual/manual_<lang>.src.html` iniettando stylesheet comune, versione, crediti e calcolando larghezza/altezza nativa delle immagini PNG. Risolve i blocchi condizionali `<!--IF:feature-->` tramite `tools/manual_features.py` e genera i file finali in `blindcue/help/manual_<lang>.html`.
- `tools/i18n_check.py`: Effettua la scansione statica AST dei file Python in `blindcue/` per identificare stringhe prive di traduzione in `en.py` e `pl.py`.

#### Pipeline Installer Windows CI/CD (`.github/workflows/windows-installer.yml`)
- Esegue su runner GitHub Actions `windows-latest` con Python 3.13.
- Scarica la build ufficiale FFmpeg release essentials da gyan.dev verificando l'hash SHA-256 prima dell'estrazione.
- Installa Inno Setup 6 e invoca `packaging/windows/build.ps1` per generare `dist/BlindCue-Setup-*.exe`.
- Attacca automaticamente il file di installazione come asset alla GitHub Release corrispondente quando viene pushato un tag `v*` (o salva l'artifact via `workflow_dispatch` con "Run workflow").

---

### 5.3 Checklist Verifiche Manuali sul Campo (Linux / Wayland)

La seguente checklist raccoglie le verifiche operative consigliate da eseguire in ambiente Linux nativo Wayland prima del debutto sul palco:

- [ ] **1. F11 / Esc su preview a schermo singolo e collegamento a caldo secondo monitor:**
  - Avviare il software con un solo schermo attivo: l'uscita apre la finestra di anteprima flottante 16:9.
  - Premere `F11` sulla finestra di anteprima: verificare che entri in fullscreen senza barre né bordi.
  - Premere `Esc` o nuovamente `F11`: verificare il ritorno corretto alla finestra flottante.
  - Con l'anteprima aperta, collegare un secondo monitor/videoproiettore via HDMI o DisplayPort: verificare che `OutputWindow` si sposti automaticamente sul secondo schermo aprendosi a tutto schermo in modo pulito.

- [ ] **2. Single-instance (doppio avvio):**
  - Con BlindCUE già aperto, lanciare una seconda volta il comando `blindcue` (o `run.sh`) da terminale o menu.
  - Verificare che il secondo processo segnali che il programma è già in esecuzione, termini con codice pulito e porti in primo piano la finestra principale già attiva senza aprire doppi socket Web/OSC né conflitti audio.

- [ ] **3. Cambio lingua (IT/EN/PL) e apertura manuale F1:**
  - Dal menu impostazioni passare tra Italiano, English e Polski.
  - Verificare che tutte le label della GUI (scaletta cue, ispettore, impostazioni dispositivi, pannelli) si aggiornino istantaneamente nella lingua scelta.
  - Premere `F1`: verificare che si apra la finestra dell'Help con il manuale utente completo renderizzato nella lingua attiva con le immagini corrette.

- [ ] **4. Crossfade video -> video con VA-API su Wayland:**
  - Inserire due cue video su Layer 1 e impostare un tempo di crossfade (es. 1.5–2.0 s) sulla seconda cue con Fade In a 0.
  - Lanciare la prima cue e poi premere GO per la seconda durante la riproduzione.
  - Verificare con `vainfo` che la decodifica hardware VA-API resti attiva e che la transizione tra i due video avvenga in modo fluido senza freeze, tearing né frame neri.

- [ ] **5. Resa font di fallback delle cue di testo su Linux:**
  - Creare una cue di testo con il pulsante `+ Testo` inserendo caratteri accentati e simboli teatrali.
  - Configurare grassetto, fascia scura dietro il testo e ombra con posizione in basso.
  - Mandare in onda la cue su Layer 3 sopra un'immagine o video: verificare che il rendering dei font su Linux (es. DejaVu Sans / Noto Sans) sia nitido, centrato e privo di glifi mancanti o artefatti di antialiasing.

- [ ] **6. Prova a vuoto GitHub Actions ("Run workflow") per l'installer Windows:**
  - Dalla sezione *Actions* del repository GitHub, selezionare il workflow `Windows installer`.
  - Cliccare su *Run workflow* (dispatch manuale su branch `main`).
  - Verificare che la pipeline su `windows-latest` scarichi correttamente FFmpeg con validazione SHA-256, esegua Inno Setup 6 e produca l'artefatto `BlindCue-Setup-*.exe` scaricabile con esito verde.



