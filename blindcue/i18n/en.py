"""English UI translations for BlindCue.

Keys are the original UI strings found in the source code (mostly Italian).
Placeholders ``{}`` mark variable parts; the translation must contain the
same number of ``{}`` (or ``{0}``, ``{1}``... to reorder them).
Generated from the translation sheets; edit freely.
"""

T: dict[str, str] = {
    'Ottimizzazione dinamica fallita.':
        'Dynamic optimisation failed.',
    'Nessun secondo schermo rilevato: la superficie unica richiede almeno un proiettore esterno.':
        'No second screen detected: the single surface needs at least one external projector.',
    "Su Wayland un'unica finestra che copre due uscite può essere rifiutata dal compositore. Se i due proiettori non si uniscono, usa X11 oppure la modalità due uscite indipendenti.":
        'On Wayland a single window covering two outputs may be refused by the compositor. If the two projectors do not merge, use X11 or the two independent outputs mode.',
    'La doppia uscita indipendente richiede due proiettori esterni (oltre al monitor di regia). Con un solo schermo esterno usa la modalità singola o la superficie unica.':
        'Independent dual output requires two external projectors (besides the control monitor). With a single external screen use single mode or the single surface.',
    'Predefinito di Sistema':
        'System Default',
    'Doppia uscita non disponibile':
        'Dual output not available',
    'Span non applicabile':
        'Span not applicable',
    'Doppia uscita persa: schermo esterno rimosso':
        'Dual output lost: external screen removed',
    'Configurazione doppia uscita fallita':
        'Dual output configuration failed',
    'Logaritmica (Naturale)':
        'Logarithmic (Natural)',
    'S-Curve Morbida':
        'Soft S-Curve',
    'Lineare':
        'Linear',
    "Impossibile avviare '{}': file danneggiato o codec non supportato":
        "Cannot start '{}': damaged file or unsupported codec",
    'con due uscite attive il limite fluido è 1 video per uscita':
        'with two active outputs the smooth limit is 1 video per output',
    'oltre 3 video il proiettore perde fluidità':
        'above 3 videos the projector loses smoothness',
    '{} video su uscita A':
        '{} video on output A',
    '{} video su uscita B':
        '{} video on output B',
    'ATTENZIONE: Errore Live L{} ({})':
        'WARNING: Live error L{} ({})',
    '⚠ Carico video elevato: ':
        '⚠ High video load: ',
    'Uscita B disattivata: interrotti ':
        'Output B disabled: stopped ',
    'Layer {} · Uscita B':
        'Layer {} · Output B',
    'Conflitto {}: {} elementi ({}) condividono il {} in modalità simultanea. Assegna layer differenti (L1, L2, L3).':
        'Conflict {}: {} items ({}) share the {} in simultaneous mode. Assign different layers (L1, L2, L3).',
    "Conflitto {}: Viene attivato in simultanea con {} nel gruppo '{}' sullo stesso {}. Assegna un layer differente (L1, L2, L3).":
        "Conflict {}: Triggered simultaneously with {} in group '{}' on the same {}. Assign a different layer (L1, L2, L3).",
    'Conflitto {}: Avvio simultaneo (Follow Simultaneo) con {} sullo stesso {}. Assegna un layer differente (L1, L2, L3).':
        'Conflict {}: Simultaneous start (Simultaneous Follow) with {} on the same {}. Assign a different layer (L1, L2, L3).',
    'Singolo schermo':
        'Single screen',
    'Superficie unica (span)':
        'Single surface (span)',
    'Due uscite indipendenti':
        'Two independent outputs',
    '{}: file non trovato ({})':
        '{}: file not found ({})',
    '{}: copia non riuscita ({})':
        '{}: copy failed ({})',
    'Schermo Intero (Default)':
        'Full Screen (Default)',
    'Schermo Intero (100%)':
        'Full Screen (100%)',
    'Proiezione a schermo intero standard sul monitor / proiettore selezionato':
        'Standard full-screen projection on the selected monitor / projector',
    'Doppio Proiettore: Metà Sinistra (0% – 50%)':
        'Dual Projector: Left Half (0% – 50%)',
    'Occupa il primo proiettore in una configurazione desktop estesa a 2 proiettori':
        'Uses the first projector in a desktop extended over 2 projectors',
    'Doppio Proiettore: Metà Destra (50% – 100%)':
        'Dual Projector: Right Half (50% – 100%)',
    'Occupa il secondo proiettore in una configurazione desktop estesa a 2 proiettori':
        'Uses the second projector in a desktop extended over 2 projectors',
    'Doppio Proiettore: Span Panoramico (0% – 100%)':
        'Dual Projector: Panoramic Span (0% – 100%)',
    'Si estende su entrambi i proiettori affiancati come un unico grande fondale panoramico':
        'Extends over both side-by-side projectors as one large panoramic backdrop',
    'Triplo Proiettore: Sinistra (1/3)':
        'Triple Projector: Left (1/3)',
    'Occupa il proiettore 1/3 in configurazione a 3 schermi affiancati':
        'Uses projector 1/3 in a 3-screen side-by-side setup',
    'Triplo Proiettore: Centro (2/3)':
        'Triple Projector: Centre (2/3)',
    'Occupa il proiettore centrale in configurazione a 3 schermi affiancati':
        'Uses the centre projector in a 3-screen side-by-side setup',
    'Triplo Proiettore: Destra (3/3)':
        'Triple Projector: Right (3/3)',
    'Occupa il proiettore 3/3 in configurazione a 3 schermi affiancati':
        'Uses projector 3/3 in a 3-screen side-by-side setup',
    'Picture-in-Picture (PiP Basso DX)':
        'Picture-in-Picture (PiP Bottom Right)',
    "Riquadro d'angolo per sovrapporre una seconda immagine o video sopra il fondale":
        'Corner box to overlay a second image or video on the backdrop',
    'Quadro 4:3 Centrale':
        'Centred 4:3 Frame',
    'Area classica 4:3 centrata su schermo 16:9 con bande laterali pulite':
        'Classic 4:3 area centred on a 16:9 screen with clean side bars',
    'Colonna / Scenografia SX':
        'Column / Scenery Left',
    'Superficie verticale ideale per banner o colonna scenica sinistra':
        'Vertical surface ideal for a banner or left stage column',
    'Colonna / Scenografia DX':
        'Column / Scenery Right',
    'Superficie verticale ideale per banner o colonna scenica destra':
        'Vertical surface ideal for a banner or right stage column',
    '{} da {} (tot: {})':
        '{} from {} (total: {})',
    'Nessun comando ricevuto':
        'No command received',
    '⏹ Blocco':
        '⏹ Hold',
    '⏹ Blocco (Default): esegue solo la cue selezionata (Pre+Durata+Post) e attende GO manuale.':
        '⏹ Hold (Default): runs only the selected cue (Pre+Duration+Post) and waits for a manual GO.',
    '⤵ GO Automatico: al termine di Pre-Delay + Durata + Post-Delay avvia automaticamente la cue successiva.':
        '⤵ Auto GO: after Pre-Delay + Duration + Post-Delay the next cue starts automatically.',
    '⇉ Simult.':
        '⇉ Simult.',
    '⇉ Simultanea: al GO avvia subito insieme la cue successiva (che rispetta comunque il proprio Pre-Delay).':
        '⇉ Simultaneous: on GO the next cue starts at once together (still honouring its own Pre-Delay).',
    'SCALETTA CUE (Sequence List)':
        'CUE LIST (Sequence List)',
    '0 Cue':
        '0 Cues',
    'Standby: Nessuna':
        'Standby: None',
    '🎭 VAI IN LIVE':
        '🎭 GO LIVE',
    'Apri la modalità semplificata LIVE (Show Mode) centrata su Scaletta, GO, PAUSA TUTTO e PANIC [F5 / Ctrl+L]':
        'Open the simplified LIVE mode (Show Mode) focused on Cue List, GO, PAUSE ALL and PANIC [F5 / Ctrl+L]',
    'Modalità LIVE Show':
        'LIVE Show Mode',
    'Passa alla schermata di regia semplificata per il live.':
        'Switch to the simplified control screen for the live show.',
    'Scaletta delle Cue':
        'Cue List',
    'Elenco sequenziale delle scene e dei media. Naviga con freccia Su e Giù, premi Spazio per il GO.':
        'Sequential list of scenes and media. Navigate with Up and Down arrows, press Space for GO.',
    'Aggiungi file video alla scaletta':
        'Add a video file to the cue list',
    'Aggiungi Video':
        'Add Video',
    'Apre la finestra di selezione per aggiungere un file video alla scaletta.':
        'Opens the file picker to add a video file to the cue list.',
    'Aggiungi file audio alla scaletta':
        'Add an audio file to the cue list',
    'Aggiungi Audio':
        'Add Audio',
    'Apre la finestra di selezione per aggiungere un file audio alla scaletta.':
        'Opens the file picker to add an audio file to the cue list.',
    '+ Foto':
        '+ Photo',
    'Aggiungi immagine / foto statica (Layer 1-3)':
        'Add a still image / photo (Layer 1-3)',
    'Aggiungi Foto o Immagine':
        'Add Photo or Image',
    'Apre la finestra di selezione per aggiungere una foto o grafica statica alla scaletta.':
        'Opens the file picker to add a photo or still graphic to the cue list.',
    '+ Gruppo':
        '+ Group',
    'Crea un gruppo di cue / scena (Ctrl+G)':
        'Create a cue group / scene (Ctrl+G)',
    'Aggiungi Gruppo o Scena':
        'Add Group or Scene',
    'Crea un nuovo contenitore di gruppo o scena sincronizzata.':
        'Create a new synchronised group or scene container.',
    '▲ Su':
        '▲ Up',
    'Sposta la cue in alto (Alt+↑)':
        'Move the cue up (Alt+↑)',
    '▼ Giù':
        '▼ Down',
    'Sposta la cue in basso (Alt+↓)':
        'Move the cue down (Alt+↓)',
    '🗑 Elimina':
        '🗑 Delete',
    'Rimuovi la cue dalla scaletta (Canc)':
        'Remove the cue from the list (Del)',
    '⏹ Blocco: attende il prossimo GO manuale':
        '⏹ Hold: waits for the next manual GO',
    'Selezione multipla mista — clicca una modalità per applicarla a tutte':
        'Mixed multiple selection — click a mode to apply it to all',
    'Seleziona una o più cue per scegliere Blocco / Auto-GO / Simultanea':
        'Select one or more cues to choose Hold / Auto-GO / Simultaneous',
    '⤵ CASCATA':
        '⤵ CASCADE',
    '⏹ PASSO':
        '⏹ STEP',
    'Numero progressivo di posizione in scaletta (doppio click = GO)':
        'Progressive position number in the list (double click = GO)',
    'Richiamo copione Q (doppio click per modificare)':
        'Script Q call-out (double click to edit)',
    'Nome personalizzato scena / file (doppio click per rinominare; Ctrl/Shift+Click per selezione multipla)':
        'Custom scene / file name (double click to rename; Ctrl/Shift+Click for multiple selection)',
    '🎨 Colore Scena / Gruppo':
        '🎨 Scene / Group Colour',
    'Nome / Media':
        'Name / Media',
    '{} Cue':
        '{} Cues',
    '📁 Raggruppa in Scena (Ctrl+G)':
        '📁 Group into Scene (Ctrl+G)',
    '🎬 Apri Studio Timeline Gruppo…':
        '🎬 Open Group Timeline Studio…',
    '▶ / ▼ Espandi o Collassa Gruppo':
        '▶ / ▼ Expand or Collapse Group',
    '🔓 Sciogli Gruppo (Ctrl+Shift+G)':
        '🔓 Ungroup (Ctrl+Shift+G)',
    '⏏ Estrai dal Gruppo (Ctrl+Shift+G)':
        '⏏ Remove from Group (Ctrl+Shift+G)',
    'Configurazione Hardware & Uscite di Regia':
        'Hardware & Control Outputs Configuration',
    '⚙️ Dispositivi di Uscita & Ottimizzazione Hardware':
        '⚙️ Output Devices & Hardware Optimisation',
    '⚡ Profilo Hardware · Modalità Adattiva':
        '⚡ Hardware Profile · Adaptive Mode',
    'Profilo Prestazioni:':
        'Performance Profile:',
    'Auto (Consigliato — Rilevamento Intelligente)':
        'Auto (Recommended — Smart Detection)',
    '🍃 Eco (Muletto / <=4GB RAM / Risparmio Risorse)':
        '🍃 Eco (Old machine / <=4GB RAM / Resource Saving)',
    '⚡ Standard (Bilanciato per Live)':
        '⚡ Standard (Balanced for Live)',
    '🔊 Routing Uscite Audio di Regia':
        '🔊 Control Audio Output Routing',
    '🔊 Master Spettacolo (Impianto Sala / PA Pubblico):':
        '🔊 Show Master (House PA / Audience):',
    '🎧 Pre-Ascolto / Monitor (Cuffia Tecnico / PFL):':
        '🎧 Pre-Listen / Monitor (Operator Headphones / PFL):',
    "💡 <i>Suggerimento:</i> Assegna la Cuffia per ascoltare in anteprima i brani nell'Ispettore o nella Scaletta senza che il pubblico in sala senta nulla. Se usi una sola scheda, entrambi usano l'uscita predefinita.":
        '💡 <i>Tip:</i> Assign the headphones to preview tracks in the Inspector or Cue List without the audience hearing anything. With a single sound card both use the default output.',
    '🖥️ Uscita Video Live (Proiettore / Display Esterno)':
        '🖥️ Live Video Output (Projector / External Display)',
    'Schermo Live Output:':
        'Live Output Screen:',
    '🔄 Rileva':
        '🔄 Detect',
    'Modalità Uscita:':
        'Output Mode:',
    '🖥️ Singolo schermo (una sola uscita)':
        '🖥️ Single screen (one output)',
    '🖥️🖥️ Superficie unica — span su più proiettori':
        '🖥️🖥️ Single surface — span over several projectors',
    '🖥️ ⇄ 🖥️ Due uscite indipendenti (contenuti diversi)':
        '🖥️ ⇄ 🖥️ Two independent outputs (different content)',
    "💡 BlindCue proietta solo sugli schermi esterni al monitor di regia. Con un solo proiettore tutto va lì; con due proiettori puoi scegliere quale alimenta l'uscita A e quale l'uscita B dal pannello dei layer.":
        '💡 BlindCue projects only on screens other than the control monitor. With one projector everything goes there; with two projectors you can choose which feeds output A and which output B from the layer panel.',
    'Annulla':
        'Cancel',
    '✓ Applica e Salva':
        '✓ Apply and Save',
    "Due uscite separate e indipendenti: ogni proiettore ha i propri 3 layer. Assegna ogni cue all'uscita A o B nell'Ispettore.":
        'Two separate independent outputs: each projector has its own 3 layers. Assign every cue to output A or B in the Inspector.',
    "I proiettori esterni saranno uniti in un'unica tela continua.":
        'The external projectors will be joined into one continuous canvas.',
    'Nessun dispositivo rilevato (Default)':
        'No device detected (Default)',
    "⚠️ Nessuna uscita audio rilevata dal sistema operativo: l'audio userà l'impianto predefinito.":
        '⚠️ No audio output detected by the operating system: audio will use the default device.',
    ' (Predefinito)':
        ' (Default)',
    '⚠️ Una sola uscita audio rilevata: il pre-ascolto in cuffia richiede una seconda scheda audio collegata (USB/DAC). Senza di essa il monitor PFL userebbe lo stesso impianto del pubblico.':
        '⚠️ Only one audio output detected: headphone pre-listen needs a second sound card (USB/DAC). Without it the PFL monitor would use the same system as the audience.',
    ' [Primario / Regia]':
        ' [Primary / Control]',
    ' [Esterno / Proiettore]':
        ' [External / Projector]',
    '🍃 <b>Modalità ECO / Muletto:</b> Limitazione thread di calcolo a 2 core, gestione memoria leggera, protezione RAM <= 4GB (perfetta per portatili datati come MacBook Air 2014).':
        '🍃 <b>ECO / Old-machine mode:</b> compute threads limited to 2 cores, light memory handling, RAM protection up to 4 GB (perfect for older laptops such as a 2014 MacBook Air).',
    'Proiettori coinvolti: {}.':
        'Projectors involved: {}.',
    'Nessun proiettore esterno rilevato.':
        'No external projector detected.',
    'Schermi coinvolti: {}.':
        'Screens involved: {}.',
    'Nessuno schermo esterno rilevato.':
        'No external screen detected.',
    '🚀 <b>Modalità PERFORMANCE:</b> Multi-threading completo (fino a 8+ core), precaricamento istantaneo e massime prestazioni per workstation con GPU dedicata.':
        '🚀 <b>PERFORMANCE mode:</b> full multi-threading (up to 8+ cores), instant preloading and maximum performance for workstations with a dedicated GPU.',
    '⚡ <b>Modalità STANDARD:</b> Bilanciamento ottimale tra consumo di risorse e fluidità live.':
        '⚡ <b>STANDARD mode:</b> optimal balance between resource use and live smoothness.',
    'Trascina qui file multimediali\n(Video, Audio, Immagini)\nper aggiungerli alla regia':
        'Drop media files here\n(Video, Audio, Images)\nto add them to the show',
    "🎬 Studio Timeline Compositore Gruppo — '{}'":
        "🎬 Group Compositor Timeline Studio — '{}'",
    'Montaggio multi-traccia non distruttivo (Layer 1, 2, 3) · Modifica solo i file del gruppo':
        "Non-destructive multi-track editing (Layer 1, 2, 3) · Edits only the group's files",
    '⏱ Durata Scena: 00:00.00':
        '⏱ Scene Duration: 00:00.00',
    '↺ Annulla':
        '↺ Cancel',
    'Annulla Modifiche Timeline':
        'Discard Timeline Changes',
    'Chiude lo studio senza salvare le modifiche apportate alla timeline.':
        'Closes the studio without saving the timeline changes.',
    '✓ Salva e Sincronizza nel Gruppo':
        '✓ Save and Sync to Group',
    'Salva e Sincronizza nel Gruppo':
        'Save and Sync to Group',
    "Salva ritardi, layer, tagli e dissolvenze all'interno delle cue del gruppo.":
        "Saves delays, layers, trims and fades into the group's cues.",
    '📦 ELEMENTI DEL GRUPPO ({} file)':
        '📦 GROUP ITEMS ({} files)',
    'Lista File del Gruppo':
        'Group File List',
    'Elenco dei file assegnati al gruppo. Clicca per selezionare una clip.':
        'List of files assigned to the group. Click to select a clip.',
    '🔒 File vincolati al gruppo per evitare inserimenti accidentali o file estranei.':
        '🔒 Files locked to the group to avoid accidental or foreign insertions.',
    '🖥️ ANTEPRIMA MULTI-LAYER & TRASPORTO':
        '🖥️ MULTI-LAYER PREVIEW & TRANSPORT',
    '▶ SCHERMO ANTEPRIMA SANDBOX\nComposizione Multi-Layer sincronizzata':
        '▶ SANDBOX PREVIEW SCREEN\nSynchronised Multi-Layer Composition',
    '⏮ Inizio':
        '⏮ Start',
    "Riavvolgi all'Inizio":
        'Rewind to Start',
    'Porta la testina di riproduzione al secondo zero.':
        'Moves the playhead to second zero.',
    'Play o Pausa Anteprima Gruppo':
        'Play or Pause Group Preview',
    'Avvia o mette in pausa la riproduzione sincronizzata multi-canale.':
        'Starts or pauses synchronised multi-channel playback.',
    '🛠️ MODIFICATORI CLIP ATTIVA':
        '🛠️ ACTIVE CLIP MODIFIERS',
    'Nessuna clip selezionata':
        'No clip selected',
    '⏱ TIMELINE DELLE 3 TRACCE (Layer 3 Sopra ➔ Layer 1 Sfondo)':
        '⏱ 3-TRACK TIMELINE (Layer 3 Top ➔ Layer 1 Background)',
    '🧲 Snap a griglia (0.25s)':
        '🧲 Snap to grid (0.25s)',
    'Canvas Timeline a 3 Layer':
        '3-Layer Timeline Canvas',
    'Compositore visivo a 3 layer per allineare temporalmente i file del gruppo.':
        "3-layer visual compositor to align the group's files in time.",
    'L3 · OVERLAY / FOTO':
        'L3 · OVERLAY / PHOTO',
    'Traccia superiore (Overlay)':
        'Top track (Overlay)',
    'Traccia intermedia':
        'Middle track',
    'L1 · SFONDO / BASE':
        'L1 · BACKGROUND / BASE',
    'Traccia di fondo (Background)':
        'Bottom track (Background)',
    'Layer 1 (Sfondo)':
        'Layer 1 (Background)',
    'Layer 2 (Intermedio)':
        'Layer 2 (Middle)',
    'Avvio (s):':
        'Start (s):',
    'Taglio IN:':
        'Trim IN:',
    'Opacità:':
        'Opacity:',
    "<h3>Architettura Hardware & Prestazioni BlindCue</h3><p><b>Profilo Attivo:</b> <b style='color:#00bcd4;'>{}</b> ({})</p><p><b>Processore (CPU):</b> {}<br/>• Core / Thread rilevati: <b>{} core</b></p><p><b>Memoria RAM di Sistema:</b><br/>• Totale: <b>{} GB</b> ({} MB)<br/>• Disponibile: <b>{} GB</b> ({} MB)</p><p><b>Scheda Video (GPU):</b> {}<br/>• Accelerazione Hardware: <b>{}</b><br/>• Schermi Rilevati: <b>{}</b><br/>• Piattaforma: <b>{} ({})</b></p><hr/><h4>Ottimizzazioni per la Massima Stabilità Live:</h4><ul><li><b>GPU Offloading:</b> Compositing Layer 0..3 su GPU tramite Wayland EGL/OpenGL. Zero carico di ridisegno pixel sulla CPU.</li><li><b>Decodifica Video Hardware:</b> QtMultimedia e FFmpeg interrogano automaticamente VA-API / NVDEC per frame zero-copy.</li><li><b>Protezione GC Live:</b> In modalità LIVE il Garbage Collector di Python viene posticipato per prevenire micro-lag durante le Cue.</li><li><b>Isolamento Threading:</b> Worker asincroni limitati per garantire latenza istantanea su UI e Audio.</li></ul><p style='color: #00e676;'><b>Risultato:</b> Stabilità assoluta garantita sia su portatili da 4GB di RAM che su workstation multi-core.</p>":
        "<h3>BlindCue Hardware Architecture & Performance</h3><p><b>Active Profile:</b> <b style='color:#00bcd4;'>{}</b> ({})</p><p><b>Processor (CPU):</b> {}<br/>• Cores / Threads detected: <b>{} cores</b></p><p><b>System RAM:</b><br/>• Total: <b>{} GB</b> ({} MB)<br/>• Available: <b>{} GB</b> ({} MB)</p><p><b>Graphics Card (GPU):</b> {}<br/>• Hardware Acceleration: <b>{}</b><br/>• Screens Detected: <b>{}</b><br/>• Platform: <b>{} ({})</b></p><hr/><h4>Optimisations for Maximum Live Stability:</h4><ul><li><b>GPU Offloading:</b> Layer 0..3 compositing on the GPU via Wayland EGL/OpenGL. Zero pixel redraw load on the CPU.</li><li><b>Hardware Video Decoding:</b> QtMultimedia and FFmpeg automatically query VA-API / NVDEC for zero-copy frames.</li><li><b>Live GC Protection:</b> In LIVE mode Python's Garbage Collector is postponed to prevent micro-lag during cues.</li><li><b>Threading Isolation:</b> Limited asynchronous workers to guarantee instant UI and audio latency.</li></ul><p style='color: #00e676;'><b>Result:</b> Rock-solid stability on 4GB RAM laptops and multi-core workstations alike.</p>",
    'Scelta manuale operatore':
        'Manual operator choice',
    'BlindCue — Info Hardware & Accelerazione':
        'BlindCue — Hardware & Acceleration Info',
    'Auto (RAM {}GB / {} Core: profilo salva-memoria attivo)':
        'Auto (RAM {}GB / {} Cores: memory-saving profile active)',
    'Auto (RAM {}GB / {} Core: massime prestazioni e multi-screen)':
        'Auto (RAM {}GB / {} Cores: maximum performance and multi-screen)',
    'Auto (RAM {}GB / {} Core: bilanciamento standard)':
        'Auto (RAM {}GB / {} Cores: standard balance)',
    'Display Principale':
        'Main Display',
    'Disattivazione... {}s':
        'Deactivating... {}s',
    'Attivazione... {}s':
        'Activating... {}s',
    'Native (Automatico)':
        'Native (Automatic)',
    '1:1 (Quadrato)':
        '1:1 (Square)',
    'L1: Sfondo':
        'L1: Background',
    'Layer 1 (Default): Livello di sfondo o base scena':
        'Layer 1 (Default): background or scene base layer',
    'L2: Principale':
        'L2: Main',
    'Layer 2: Livello multimediale intermedio (sopra L1)':
        'Layer 2: middle media layer (above L1)',
    'Layer 3: Livello superiore in primo piano (grafica, loghi, titoli)':
        'Layer 3: top foreground layer (graphics, logos, titles)',
    'Attende GO manuale (default)':
        'Waits for manual GO (default)',
    'Avvia la successiva dopo Pre+Durata+Post':
        'Starts the next one after Pre+Duration+Post',
    'Avvia insieme la successiva sul GO':
        'Starts the next one together on GO',
    '⇉ Simultaneo':
        '⇉ Simultaneous',
    'Fire All: tutti i media del gruppo partono contemporaneamente sul GO.':
        "Fire All: all the group's media start at the same time on GO.",
    '⤵ Sequenziale':
        '⤵ Sequential',
    'Cascata: un solo GO lancia tutta la sequenza interna rispettando i ritardi Pre/Durata/Post.':
        'Cascade: a single GO launches the whole internal sequence honouring the Pre/Duration/Post delays.',
    '⏹ Passo-Passo':
        '⏹ Step-by-Step',
    "Capitolo teatrale: ogni pressione manuale di GO avanza di un elemento all'interno della scena.":
        'Theatre chapter: every manual GO press advances one item inside the scene.',
    '🎲 Random / Var.':
        '🎲 Random / Var.',
    'Sceglie a caso un elemento del gruppo evitando la ripetizione immediata.':
        'Picks a random group item avoiding immediate repetition.',
    '🔁 Loop Scena':
        '🔁 Loop Scene',
    'Cicla continuamente tutti gli elementi interni finché non viene dato lo stop.':
        'Cycles all inner items continuously until stopped.',
    'ISPETTORE CUE (Nessuna cue selezionata)':
        'CUE INSPECTOR (No cue selected)',
    'Cursore orizzontale da {} a {}.':
        'Horizontal slider from {} to {}.',
    'Pannello Ispettore Cue - Schede':
        'Cue Inspector Panel - Tabs',
    'Schede proprietà: Info e Tempi, Video e Foto, Audio e Tagli, Gruppo.':
        'Property tabs: Info and Timing, Video and Photo, Audio and Trims, Group.',
    '1 · IDENTITÀ IN COPIONE & COLORE GRUPPO':
        '1 · SCRIPT IDENTITY & GROUP COLOUR',
    'I box scuri sono modificabili; usa un colore per dividere scene o atti in Scaletta.':
        'Dark boxes are editable; use a colour to split scenes or acts in the Cue List.',
    'es. Q-2, Q-9a, Sc.1...':
        'e.g. Q-2, Q-9a, Sc.1...',
    'Sigla di copione: resta legata alla cue anche se riordini la scaletta':
        'Script call-out: stays tied to the cue even if you reorder the list',
    'Sigla Q Copione':
        'Script Q Label',
    'Identificativo o sigla di copione della cue.':
        'Script identifier or label of the cue.',
    'Titolo descrittivo in scaletta...':
        'Descriptive title in the cue list...',
    'Nome Cue':
        'Cue Name',
    'Titolo o etichetta descrittiva della cue nella scaletta.':
        'Title or descriptive label of the cue in the list.',
    'Attacco battuta, luci, note tecniche...':
        'Line cue, lights, technical notes...',
    'Note di Regia':
        "Director's Notes",
    "Note tecniche o didascalie per l'operatore di regia.":
        'Technical notes or captions for the operator.',
    'Colore:':
        'Colour:',
    '📁 In Scena':
        '📁 In Scene',
    '⏏ Estrai dal Gruppo':
        '⏏ Remove from Group',
    "Rimuove questa cue dal gruppo e la sposta all'esterno della scena (Ctrl+Shift+G)":
        'Removes this cue from the group and moves it outside the scene (Ctrl+Shift+G)',
    '2 · LAYER DI USCITA (SOVRAPPOSIZIONE)':
        '2 · OUTPUT LAYER (STACKING)',
    'Ordine visivo sullo schermo: L3 (sopra) → L2 → L1 → L0 Tappo di sicurezza.':
        'Visual order on screen: L3 (top) → L2 → L1 → L0 Safety Cover.',
    'Proiettore:':
        'Projector:',
    '3 · TEMPI DI INCASTRO (PRE · DURATA · POST)':
        '3 · TIMING (PRE · DURATION · POST)',
    'GO  ▶  [⏳ Pre]  ▶  [▶ Media / Durata]  ▶  [⏱ Post]':
        'GO  ▶  [⏳ Pre]  ▶  [▶ Media / Duration]  ▶  [⏱ Post]',
    'Ritardo di partenza dopo il GO per incastrare la cue con altri layer':
        'Start delay after GO to fit the cue with other layers',
    'Ritardo di Partenza Pre-Delay':
        'Start Delay Pre-Delay',
    "Secondi di ritardo dopo il GO prima dell'avvio della cue.":
        'Seconds of delay after GO before the cue starts.',
    'Attesa extra dopo la fine del media prima di uscire o passare alla successiva':
        'Extra wait after the media ends before leaving or moving to the next one',
    'Attesa Finale Post-Delay':
        'Final Wait Post-Delay',
    'Secondi di attesa dopo il termine del media.':
        'Seconds of wait after the media ends.',
    'Durata di permanenza in Live delle immagini statiche (0 = infinita)':
        'How long still images stay Live (0 = forever)',
    'Durata Immagine Hold Time':
        'Image Hold Time',
    'Durata in secondi per le immagini statiche (0 = infinita).':
        'Duration in seconds for still images (0 = forever).',
    'Solo immagini (0 = ∞)':
        'Images only (0 = ∞)',
    'Dopo:':
        'After:',
    '🎯 Cue · Tempi':
        '🎯 Cue · Timing',
    "Suggerimento: puoi anche trascinare il riquadro o gli 8 bordi direttamente sull'Anteprima Pre-Viz 16:9.":
        'Tip: you can also drag the frame or its 8 edges directly on the 16:9 Pre-Viz Preview.',
    '1 · POSIZIONAMENTO, ZOOM & TRASPARENZA':
        '1 · POSITION, ZOOM & TRANSPARENCY',
    'Superficie:':
        'Surface:',
    'Assegna la cue a uno schermo virtuale o superficie di proiezione/mapping':
        'Assign the cue to a virtual screen or projection/mapping surface',
    '📐 Gestisci...':
        '📐 Manage...',
    'Apri lo Studio Superfici di Proiezione & Video Mapping (F7)':
        'Open the Projection Surfaces & Video Mapping Studio (F7)',
    'Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx)':
        'Horizontal offset (-1.00 = left, 0.00 = centre, +1.00 = right)',
    'Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso)':
        'Vertical offset (-1.00 = top, 0.00 = centre, +1.00 = bottom)',
    'Sposta a sinistra (-0.01)':
        'Move left (-0.01)',
    'Sposta in alto (-0.01)':
        'Move up (-0.01)',
    'Sposta in basso (+0.01)':
        'Move down (+0.01)',
    'Sposta a destra (+0.01)':
        'Move right (+0.01)',
    '⌖ Centro':
        '⌖ Centre',
    'Ripristina posizione al centro (0.00, 0.00)':
        'Reset position to the centre (0.00, 0.00)',
    'Scala:':
        'Scale:',
    'Ripristina scala a 1.0x':
        'Reset scale to 1.0x',
    'Ripristina opacità al 100%':
        'Reset opacity to 100%',
    'Formato:':
        'Aspect:',
    'Forza le proporzioni del riquadro in Anteprima e Live':
        'Forces the frame proportions in Preview and Live',
    '2 · RITAGLIO BORDI (CROP)':
        '2 · EDGE CROP',
    'Scegli % oppure pixel reali della sorgente per tagliare i bordi.':
        'Choose % or real source pixels to crop the edges.',
    'Imposta il ritaglio in percentuale (0.0% – 99.0%)':
        'Set the crop as a percentage (0.0% – 99.0%)',
    'Imposta il ritaglio esatto in pixel rispetto alla risoluzione del file':
        'Set the exact crop in pixels relative to the file resolution',
    'Rimuove il ritaglio e mostra il fotogramma intero':
        'Removes the crop and shows the full frame',
    'Ritaglio bordo sinistro':
        'Left edge crop',
    'Ritaglio bordo destro':
        'Right edge crop',
    'Ritaglio bordo superiore':
        'Top edge crop',
    'Ritaglio bordo inferiore':
        'Bottom edge crop',
    '3 · ROTAZIONE':
        '3 · ROTATION',
    'Ruota immagine o video. Per le immagini compare anche il ritaglio poligonale.':
        'Rotate image or video. For images the polygonal crop also appears.',
    'Rotazione:':
        'Rotation:',
    'Rotazione in gradi attorno al centro del riquadro (-180° … +180°). 0° = dritto.':
        'Rotation in degrees around the frame centre (-180° … +180°). 0° = straight.',
    'Ruota di 90° in senso antiorario':
        'Rotate 90° counter-clockwise',
    "Riporta l'immagine dritta (0°)":
        'Set the image straight (0°)',
    'Ruota di 90° in senso orario':
        'Rotate 90° clockwise',
    '✂ Disegna maschera…':
        '✂ Draw mask…',
    "Ritaglia l'immagine lungo un percorso poligonale disegnato a mano":
        'Crop the image along a hand-drawn polygonal path',
    '✖ Rimuovi':
        '✖ Remove',
    "Rimuove la maschera poligonale e mostra l'immagine intera":
        'Removes the polygonal mask and shows the full image',
    'Nessuna maschera':
        'No mask',
    '🖼 Video · Foto':
        '🖼 Video · Photo',
    "Suggerimento: Dissolvenze (Fade In/Out) attive anche sulle Immagini; inviluppi avanzati e Sezioni A/B/C nella Forma d'Onda.":
        'Tip: Fades (Fade In/Out) also work on Images; advanced envelopes and A/B/C Sections in the Waveform.',
    '1 · VOLUME PRINCIPALE (AUDIO / VIDEO)':
        '1 · MAIN VOLUME (AUDIO / VIDEO)',
    "Livello base del media; puoi disegnare variazioni nel tempo direttamente sulla Forma d'Onda.":
        'Base level of the media; you can draw changes over time directly on the Waveform.',
    'Ripristina volume al 100%':
        'Reset volume to 100%',
    '2 · DISSOLVENZE (FADE IN / OUT)':
        '2 · FADES (FADE IN / OUT)',
    "Applicate dolcemente all'ingresso e all'uscita su Audio, Video e Immagini a durata.":
        'Applied smoothly at the start and end of Audio, Video and timed Images.',
    'Dissolvenza in Entrata Fade-In':
        'Fade-In',
    'Durata in secondi della dissolvenza in ingresso da nero o silenzio.':
        'Duration in seconds of the fade-in from black or silence.',
    'Dissolvenza in Uscita Fade-Out':
        'Fade-Out',
    'Durata in secondi della dissolvenza in chiusura a nero o silenzio.':
        'Duration in seconds of the closing fade to black or silence.',
    '3 · TAGLIO TEMPORALE (PUNTI IN / OUT)':
        '3 · TIME TRIM (IN / OUT POINTS)',
    'Imposta dove inizia e finisce la traccia (tasti rapidi [I] / [O] sulla Testina della Timeline).':
        'Set where the track starts and ends (shortcuts [I] / [O] on the Timeline Playhead).',
    'Punto di Inizio In-Point':
        'Start Point In-Point',
    'Posizione iniziale di riproduzione in minuti, secondi e centesimi.':
        'Initial playback position in minutes, seconds and hundredths.',
    'Punto di Fine Out-Point':
        'End Point Out-Point',
    'Posizione finale di taglio o fine riproduzione.':
        'Final trim or end-of-playback position.',
    'Ripristina IN a 0.00s e OUT a Fine':
        'Reset IN to 0.00s and OUT to End',
    '🔁  4 · RIPETI CUE IN LOOP':
        '🔁  4 · LOOP CUE',
    '5 · LIVELLAMENTO & LOUDNESS (EBU R128)':
        '5 · LEVELLING & LOUDNESS (EBU R128)',
    'Calcola il volume percepito (LUFS) per livellare tracce troppo basse o troppo alte senza distorsione.':
        'Measures perceived loudness (LUFS) to level tracks that are too quiet or too loud without distortion.',
    '📊 Loudness: Non analizzato':
        '📊 Loudness: Not analysed',
    '🔍 Analizza':
        '🔍 Analyse',
    'Analizza il volume percepito EBU R128 in background con FFmpeg':
        'Analyse EBU R128 perceived loudness in the background with FFmpeg',
    '🎚 Applica Guadagno EBU R128 (-16 LUFS) per questo file':
        '🎚 Apply EBU R128 Gain (-16 LUFS) to this file',
    "Applica l'offset di guadagno non distruttivo sul player per pareggiare il volume con le altre cue.":
        'Applies the non-destructive gain offset on the player to match the volume with the other cues.',
    '🛠 Ottimizza Dinamica (Compressore / Limiter)':
        '🛠 Optimise Dynamics (Compressor / Limiter)',
    "Per file complessi o registrati male: applica il compressore broadcast EBU R128 a due passate con True-Peak Limiter per appiattire gli sbalzi e proteggere l'impianto.":
        'For complex or badly recorded files: applies the two-pass EBU R128 broadcast compressor with a True-Peak Limiter to flatten jumps and protect the sound system.',
    '↺ Ripristina Originale':
        '↺ Restore Original',
    "Annulla l'ottimizzazione e torna al file media originale":
        'Undo the optimisation and go back to the original media file',
    '🎵 Audio · Tagli':
        '🎵 Audio · Trims',
    '1 · IDENTITÀ SCENA / GRUPPO & COLORE':
        '1 · SCENE / GROUP IDENTITY & COLOUR',
    'I gruppi organizzano più media in una singola riga collassabile in Scaletta e Live.':
        'Groups organise several media into one collapsible row in the Cue List and Live.',
    'es. G-1, Atto 1, Scena A...':
        'e.g. G-1, Act 1, Scene A...',
    'Sigla di copione del gruppo: resta legata al gruppo se riordini la scaletta':
        'Group script call-out: stays tied to the group if you reorder the list',
    'Titolo scena o sequenza...':
        'Scene or sequence title...',
    'Note di regia o indicazioni palco per il gruppo...':
        "Director's notes or stage directions for the group...",
    'Attesa prima di avviare il gruppo alla pressione del GO.':
        'Wait before starting the group when GO is pressed.',
    "Attesa al termine dell'esecuzione prima di passare alla cue successiva.":
        'Wait after execution ends before moving to the next cue.',
    '2 · COMPORTAMENTO AL GO (MODALITÀ SCENA)':
        '2 · BEHAVIOUR ON GO (SCENE MODE)',
    'Determina come vengono eseguiti i media contenuti nel gruppo quando si preme GO.':
        'Determines how the media in the group run when GO is pressed.',
    '3 · ELEMENTI INTERNI AL GRUPPO':
        '3 · ITEMS INSIDE THE GROUP',
    'Lista dei media appartenenti a questo gruppo. Usa i pulsanti per espandere o gestire i membri.':
        'List of media belonging to this group. Use the buttons to expand or manage members.',
    '📁 0 cue nel gruppo':
        '📁 0 cues in the group',
    '▶ Collassa / ▼ Espandi':
        '▶ Collapse / ▼ Expand',
    'Mostra o nascondi i figli del gruppo nella tabella Scaletta':
        "Show or hide the group's children in the Cue List table",
    '✕ Rimuovi Cue':
        '✕ Remove Cue',
    'Rimuove la cue selezionata dalla lista dal gruppo (torna al livello principale)':
        'Removes the selected cue from the group list (back to the main level)',
    '🔓 Sciogli Gruppo':
        '🔓 Ungroup',
    'Elimina il contenitore del gruppo e rilascia tutte le sue cue in scaletta':
        'Deletes the group container and releases all its cues into the list',
    '🎬  APRI STUDIO TIMELINE DEL GRUPPO (3 LAYER)':
        '🎬  OPEN GROUP TIMELINE STUDIO (3 LAYERS)',
    'Studio Timeline Multi-Track':
        'Multi-Track Timeline Studio',
    'Apre la finestra di composizione multi-traccia a 3 layer per sincronizzare i file del gruppo.':
        "Opens the 3-layer multi-track composition window to sync the group's files.",
    'Apre la finestra extra Studio Timeline per sincronizzare visivamente i file del gruppo\nsulle 3 tracce layer (L1, L2, L3) con righello millisecondi, tagli e anteprima multi-canale.':
        "Opens the extra Timeline Studio window to visually sync the group's files\non the 3 layer tracks (L1, L2, L3) with a millisecond ruler, trims and multi-channel preview.",
    '📁 Gruppo · Scena':
        '📁 Group · Scene',
    'Non definita':
        'Not defined',
    '📊 {} LUFS | Picco: {} dBFS | Auto-Gain: {}{} dB':
        '📊 {} LUFS | Peak: {} dBFS | Auto-Gain: {}{} dB',
    'Q (Copione):':
        'Q (Script):',
    'Nome Cue:':
        'Cue Name:',
    'Note Regia:':
        "Director's Notes:",
    'A · Schermo 1':
        'A · Screen 1',
    "Questa cue viene proiettata dall'uscita A (primo proiettore).":
        'This cue is projected from output A (first projector).',
    'B · Schermo 2':
        'B · Screen 2',
    "Questa cue viene proiettata dall'uscita B (secondo proiettore indipendente).":
        'This cue is projected from output B (second independent projector).',
    'Durata Img:':
        'Image Time:',
    'Unità:':
        'Unit:',
    'Sinistra:':
        'Left:',
    'Destra:':
        'Right:',
    'Alto:':
        'Top:',
    'Basso:':
        'Bottom:',
    'Ripetizioni:':
        'Repetitions:',
    '∞ Continuo (Infinito)':
        '∞ Continuous (Infinite)',
    'Ripeti 2 volte':
        'Repeat 2 times',
    'Ripeti 3 volte':
        'Repeat 3 times',
    'Ripeti 4 volte':
        'Repeat 4 times',
    'Ripeti 5 volte':
        'Repeat 5 times',
    'Ripeti 10 volte':
        'Repeat 10 times',
    'Personalizzato...':
        'Custom...',
    'Nome Gruppo:':
        'Group Name:',
    'Manuale':
        'Manual',
    'Maschera: {} punti':
        'Mask: {} points',
    "ISPETTORE CUE — {} [{}] '{}'":
        "CUE INSPECTOR — {} [{}] '{}'",
    'Seleziona una cue':
        'Select a cue',
    '0 s = Infinita in Live':
        '0 s = Infinite in Live',
    "Immagine selezionata: trascina il riquadro o gli 8 bordi nell'Anteprima Pre-Viz 16:9.":
        'Image selected: drag the frame or its 8 edges in the 16:9 Pre-Viz Preview.',
    'Nota: Cue Immagine — Fade In/Out e inviluppo Opacità attivi. Volume, Tagli e Loop valgono per Audio/Video.':
        'Note: Image Cue — Fade In/Out and Opacity envelope active. Volume, Trims and Loop apply to Audio/Video.',
    'ISPETTORE CUE — Selezione Mista ({} cue)':
        'CUE INSPECTOR — Mixed Selection ({} cues)',
    '⚠ Selezione mista ({}): seleziona solo file dello stesso tipo per modifiche comuni.':
        '⚠ Mixed selection ({}): select only files of the same type for common edits.',
    'ISPETTORE CUE — {} {} (Modifica Multipla)':
        'CUE INSPECTOR — {} {} (Multiple Edit)',
    'Layer misti (clicca L1/L2/L3 per uniformare)':
        'Mixed layers (click L1/L2/L3 to unify)',
    '⚡ MODIFICA MULTIPLA: {} file {} selezionati • {}.\nOgni parametro modificato verrà applicato a tutti gli elementi selezionati.':
        '⚡ MULTIPLE EDIT: {} {} files selected • {}.\nEvery changed parameter will be applied to all selected items.',
    '(Multiplo)':
        '(Multiple)',
    '[{} file {} selezionati]':
        '[{} {} files selected]',
    '▼ Espandi Gruppo in Scaletta':
        '▼ Expand Group in Cue List',
    '▶ Collassa Gruppo in Scaletta':
        '▶ Collapse Group in Cue List',
    'Schermo':
        'Screen',
    "Usa IN / OUT o Forma d'Onda":
        'Use IN / OUT or Waveform',
    'Nota: Cue Audio selezionata — Posizione, Zoom, Opacità e Ritaglio sono attivi solo per Video e Immagini.':
        'Note: Audio Cue selected — Position, Zoom, Opacity and Crop are active only for Video and Images.',
    "Regola Volume, Fade, punti IN/OUT o Loop; usa la Forma d'Onda sotto per curve e Sezioni A/B/C.":
        'Adjust Volume, Fade, IN/OUT points or Loop; use the Waveform below for curves and A/B/C Sections.',
    'Usa IN / OUT del video':
        "Use the video's IN / OUT",
    "Video selezionato: trascina posizione/crop sull'Anteprima Pre-Viz e attiva MIRROR LIVE per calibrare sul proiettore.":
        'Video selected: drag position/crop on the Pre-Viz Preview and enable MIRROR LIVE to calibrate on the projector.',
    'Regola Volume traccia video, Fade In/Out, punti IN/OUT e Loop (o Sezioni nella Timeline).':
        'Adjust video track Volume, Fade In/Out, IN/OUT points and Loop (or Sections in the Timeline).',
    '📁 Questa cue appartiene a una Scena / Gruppo':
        '📁 This cue belongs to a Scene / Group',
    'BUIO TOTALE':
        'TOTAL BLACKOUT',
    'STOP IMMEDIATO':
        'IMMEDIATE STOP',
    'Scaletta Regia LIVE Show':
        'LIVE Show Control Cue List',
    '▶ Fai partire subito questa Cue (GO Forzato)':
        '▶ Start this Cue now (Forced GO)',
    '🎯 Imposta come Prossima Cue (Standby)':
        '🎯 Set as Next Cue (Standby)',
    '← 🛠 Torna a Progetto  [F5]':
        '← 🛠 Back to Project  [F5]',
    'Torna alla vista Progetto per modificare file, crop, fade o tempi (senza interrompere il Live)':
        'Back to Project view to edit files, crop, fades or timing (without interrupting Live)',
    '● MODALITÀ LIVE (SHOW MODE)':
        '● LIVE MODE (SHOW MODE)',
    "Azzera Cronometro Spettacolo e riarma l'avvio automatico al prossimo 1° GO":
        'Reset the Show Stopwatch and re-arm auto start on the next 1st GO',
    'Nessuna cue pronta in scaletta':
        'No cue ready in the list',
    '⏭ Esci da Loop Sezione':
        '⏭ Exit Section Loop',
    '🔒 CONTROLLI LAYER BLOCCATI (Protezione di Sicurezza Regia)\nDi default le barre e i controlli dei layer sono protetti per evitare spostamenti o tagli accidentali.\nPer sbloccare scrub, riavvolgimento e pausa dei singoli layer: tieni premuto per 1,2 secondi.\nQuando sbloccato, un singolo click istantaneo riattiva subito il blocco.':
        '🔒 LAYER CONTROLS LOCKED (Control Safety Protection)\nBy default the layer bars and controls are protected against accidental moves or cuts.\nTo unlock scrub, rewind and pause of single layers: hold for 1.2 seconds.\nWhen unlocked, a single instant click re-engages the lock.',
    'Blocco di Sicurezza Layer':
        'Layer Safety Lock',
    'Protezione controlli layer Live. Tieni premuto 1,2 secondi per sbloccare, tocca per ribloccare.':
        'Live layer control protection. Hold 1.2 seconds to unlock, tap to lock again.',
    'Congela tutti i layer LIVE (Audio, Video, Pre-Delay, Post-Delay e Immagini temporizzate) per ripartire poi dallo stesso istante':
        'Freezes all LIVE layers (Audio, Video, Pre-Delay, Post-Delay and timed Images) to restart later from the same instant',
    'Pausa o Riprendi Tutto':
        'Pause or Resume All',
    'Congela o riprende tutti i layer multimediali attivi.':
        'Freezes or resumes all active media layers.',
    '▶   GO  —  PROSSIMA CUE':
        '▶   GO  —  NEXT CUE',
    'GO - Avvia Cue in Standby':
        'GO - Start Standby Cue',
    'Manda in esecuzione la cue pronta in standby. Tasto di scelta rapida: Spazio.':
        'Runs the cue ready in standby. Keyboard shortcut: Space.',
    'Tempi · Sequenza':
        'Timing · Sequence',
    'Layer / Stato':
        'Layer / Status',
    '🔒\nBLOCCO\nLAYER\n(Tieni 1,2s)':
        '🔒\nLAYER\nLOCK\n(Hold 1.2s)',
    '🔓\nLAYER\nATTIVI\n(Click = 🔒)':
        '🔓\nLAYERS\nACTIVE\n(Click = 🔒)',
    '▶  RIPRENDI TUTTO  [IN PAUSA]':
        '▶  RESUME ALL  [PAUSED]',
    '▼ Espandi Gruppo':
        '▼ Expand Group',
    '▶ Collassa Gruppo':
        '▶ Collapse Group',
    '[{} sez.]':
        '[{} sect.]',
    'Cronometro Spettacolo in corso (avvio auto al 1° GO o manuale) — Clicca per PAUSA (non ferma i media)':
        'Show Stopwatch running (auto start at 1st GO or manual) — Click to PAUSE (does not stop the media)',
    "Esegui cue in Standby: {} '{}'\nScorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]":
        "Run Standby cue: {} '{}'\nMain keyboard shortcut: [ SPACE BAR ]",
    'Esegui prossima cue\nScorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]':
        'Run next cue\nMain keyboard shortcut: [ SPACE BAR ]',
    'Cronometro Spettacolo in PAUSA — Clicca per RIPRENDERE o usa ↺ per azzerare e riarmare':
        'Show Stopwatch PAUSED — Click to RESUME or use ↺ to reset and re-arm',
    'Durata Spettacolo (Cronometro): parte in automatico al 1° GO oppure clicca qui ora per avviare nelle filate/prove':
        'Show Duration (Stopwatch): starts automatically at the 1st GO or click here now to start for run-throughs/rehearsals',
    '[Scena]':
        '[Scene]',
    '⤵ Auto-GO al termine':
        '⤵ Auto-GO at end',
    '⏹ MANUALE':
        '⏹ MANUAL',
    '⇉ + Cue successiva simultanea':
        '⇉ + Next cue simultaneous',
    '⏪ Salta Indietro di 10s':
        '⏪ Skip Back 10s',
    '⏪ Salta Indietro di 5s':
        '⏪ Skip Back 5s',
    '⏩ Salta Avanti di 10s':
        '⏩ Skip Forward 10s',
    '⏮ Riavvia da Inizio Cue (In-Point)':
        '⏮ Restart from Cue Start (In-Point)',
    'Controllo emissione in tempo reale sui 3 livelli live:':
        'Real-time output control on the 3 live layers:',
    'Proiettore A:':
        'Projector A:',
    "Schermo fisico su cui viene proiettata l'uscita A.":
        'Physical screen on which output A is projected.',
    'Proiettore uscita A':
        'Output A projector',
    'Proiettore B:':
        'Projector B:',
    "Schermo fisico su cui viene proiettata l'uscita B.":
        'Physical screen on which output B is projected.',
    'Proiettore uscita B':
        'Output B projector',
    'USCITA B — secondo proiettore indipendente':
        'OUTPUT B — second independent projector',
    '⏹ Master Blackout (Tappo) — [ Ctrl+B ]':
        '⏹ Master Blackout (Cover) — [ Ctrl+B ]',
    "Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B":
        'Stops all output and shows Layer 0 (Cover) — Safety shortcut: Ctrl+B',
    "Arresta immediatamente l'output di tutti i layer e torna allo sfondo tappo. Scorciatoia: Ctrl+B.":
        'Immediately stops the output of all layers and returns to the cover background. Shortcut: Ctrl+B.',
    'Tappo (L0): Logo BlindCue (Predefinito)':
        'Cover (L0): BlindCue Logo (Default)',
    '📁 Cambia Tappo…':
        '📁 Change Cover…',
    "Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)":
        'Select a custom image for Layer 0 (festival poster, event logo, black)',
    'Ripristina il logo predefinito di BlindCue come Layer 0':
        'Restore the default BlindCue logo as Layer 0',
    'Logo BlindCue (Predefinito)':
        'BlindCue Logo (Default)',
    '▶ Riprendi Riproduzione':
        '▶ Resume Playback',
    'Monitor Uscita Layer Live (L3 Sopra → L1 Sfondo)':
        'Live Layer Output Monitor (L3 Top → L1 Background)',
    'Live Output Status (Monitor Uscita Schermo Esterno)':
        'Live Output Status (External Screen Output Monitor)',
    'Salta indietro di 10s su {} (utile nelle prove per ripetere la battuta)':
        'Skip back 10s on {} (useful in rehearsals to repeat the line)',
    'Sposta indietro di 10 secondi la testina del {}.':
        'Moves the {} playhead back 10 seconds.',
    'Metti in Pausa {} (utile durante le prove)':
        'Pause {} (useful during rehearsals)',
    'Riprendi riproduzione (Layer attualmente in Pausa)':
        'Resume playback (Layer currently Paused)',
    'Metti in Pausa (utile durante le prove)':
        'Pause (useful during rehearsals)',
    'Dissolvenza in uscita e arresto del contenuto su {}.\nLa durata è quella del Fade Out della cue (minimo 0.2 s).\nPROTEZIONE LIVE: tieni premuto 0.6 secondi per confermare, così un clic involontario non taglia nulla.':
        "Fade out and stop the content on {}.\nThe duration is the cue's Fade Out (minimum 0.2 s).\nLIVE PROTECTION: hold for 0.6 seconds to confirm, so an accidental click cuts nothing.",
    'Dissolve in uscita e ferma il contenuto sul {} usando il Fade Out della cue. Richiede 0.6 secondi di pressione.':
        "Fades out and stops the content on {} using the cue's Fade Out. Requires a 0.6 second press.",
    'Dissolvenza in uscita e arresto del contenuto su {}.\nLa durata è quella del Fade Out della cue (minimo 0.2 s).':
        "Fade out and stop the content on {}.\nThe duration is the cue's Fade Out (minimum 0.2 s).",
    'Salta indietro di 10s su Layer {} (prove)':
        'Skip back 10s on Layer {} (rehearsals)',
    'Metti in Pausa Layer {} (prove)':
        'Pause Layer {} (rehearsals)',
    "Estratta cue '{}' dal gruppo (spostata sopra la scena)":
        "Removed cue '{}' from the group (moved above the scene)",
    "Deleted: {} '{}' (Ctrl+Z per ripristinare)":
        "Deleted: {} '{}' (Ctrl+Z to restore)",
    'Eliminate {} cue selezionate (Ctrl+Z per ripristinare)':
        'Deleted {} selected cues (Ctrl+Z to restore)',
    "Estratta cue '{}' dal gruppo (spostata sotto la scena)":
        "Removed cue '{}' from the group (moved below the scene)",
    '— Nessun file selezionato —':
        '— No file selected —',
    'Tempi: ':
        'Timing: ',
    'MODALITÀ PROGETTO — Modifica cue e anteprima riabilitate':
        'PROJECT MODE — Cue editing and preview re-enabled',
    'Punti envelope azzerati':
        'Envelope points reset',
    'Creato taglio sezione a {}s ({} sezioni)':
        'Created section cut at {}s ({} sections)',
    'Salta':
        'Skip',
    'Sezioni azzerate: ripristinato il file originale':
        'Sections reset: original file restored',
    'Spazio insufficiente per dividere ancora in questo punto':
        'Not enough room to split again at this point',
    '∞ Infinito':
        '∞ Infinite',
    'Ritorno a file intero (modalità normale)':
        'Back to whole file (normal mode)',
    'Sezione unita':
        'Section merged',
    "Creato Gruppo Scena: '{}'":
        "Created Scene Group: '{}'",
    "Sciolto Gruppo: '{}'":
        "Ungrouped: '{}'",
    "Estratta cue '{}' dal gruppo (spostata all'esterno)":
        "Removed cue '{}' from the group (moved outside)",
    'Nuova Scena / Gruppo':
        'New Scene / Group',
    'Studio Timeline Gruppo':
        'Group Timeline Studio',
    "Il gruppo '{}' non contiene ancora file multimediali.\n\nAggiungi prima delle tracce audio, video o immagini al gruppo nella scaletta principale\nper poterle allineare e sincronizzare sulla timeline a 3 layer.":
        "Group '{}' does not contain any media files yet.\n\nFirst add audio, video or image tracks to the group in the main cue list\nso you can align and sync them on the 3-layer timeline.",
    "Studio Timeline: Gruppo '{}' sincronizzato con successo ({} file allineati sui layer)":
        "Timeline Studio: Group '{}' synced successfully ({} files aligned on the layers)",
    'Punto IN spostato sulla testina: {}s':
        'IN point moved to the playhead: {}s',
    'Punti IN e OUT ripristinati: IN = 0.00s, OUT = Fine':
        'IN and OUT points reset: IN = 0.00s, OUT = End',
    'Punto OUT impostato sulla fine del file (Fine)':
        'OUT point set to the end of the file (End)',
    'Testina prima di IN: OUT impostato al minimo ({}s)':
        'Playhead before IN: OUT set to the minimum ({}s)',
    'OUT aggiornato':
        'OUT updated',
    'Punto OUT spostato sulla testina: {}s':
        'OUT point moved to the playhead: {}s',
    'Seleziona Immagine di Tappo (Layer 0)':
        'Select Cover Image (Layer 0)',
    'Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)':
        'Images (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;All files (*)',
    'Tappo (Layer 0) ripristinato al logo predefinito':
        'Cover (Layer 0) restored to the default logo',
    'Larghezze standard dei pannelli ripristinate':
        'Standard panel widths restored',
    '🔒 Pannelli Bloccati':
        '🔒 Panels Locked',
    '🔓 Pannelli Sbloccati (Trascina bordi)':
        '🔓 Panels Unlocked (Drag edges)',
    'Layout bloccato: le larghezze dei 3 pannelli principali sono fisse':
        'Layout locked: the widths of the 3 main panels are fixed',
    'Layout sbloccato: trascina i divisori verticali per adattare i pannelli a piacere':
        'Layout unlocked: drag the vertical dividers to resize the panels as you like',
    'Silenzioso (Muto)':
        'Silent (Muted)',
    'Ascolto Attivo':
        'Listening Active',
    '{} arrestato e rimosso dal Live':
        '{} stopped and removed from Live',
    "Compressione dinamica e normalizzazione EBU R128 per '{}' in corso...":
        "Dynamic compression and EBU R128 normalisation for '{}' in progress...",
    "File originale ripristinato per '{}'":
        "Original file restored for '{}'",
    'MODALITÀ JAM / CONTEST ATTIVA — Auto-Gain EBU R128 (-16 LUFS) abilitato su tutti i canali':
        'JAM / CONTEST MODE ACTIVE — EBU R128 Auto-Gain (-16 LUFS) enabled on all channels',
    'MODALITÀ JAM / CONTEST DISATTIVATA — Ripristinati livelli originali delle cue':
        'JAM / CONTEST MODE OFF — Original cue levels restored',
    "Scansione Loudness EBU R128 per '{}' in corso...":
        "EBU R128 Loudness scan for '{}' in progress...",
    "Calcolo guadagno EBU R128 per '{}'...":
        "Calculating EBU R128 gain for '{}'...",
    "File sorgente non trovato per l'ottimizzazione dinamica.":
        'Source file not found for dynamic optimisation.',
    "Dinamica ottimizzata con successo per '{}' (-16 LUFS, Limiter -1.5 dBFS)":
        "Dynamics optimised successfully for '{}' (-16 LUFS, Limiter -1.5 dBFS)",
    "Analisi Loudness per '{}': {} LUFS (Peak {} dBFS → Gain {}{} dB)":
        "Loudness analysis for '{}': {} LUFS (Peak {} dBFS → Gain {}{} dB)",
    'Apri &recenti':
        'Open &Recent',
    '&Modifica':
        '&Edit',
    '↶ &Annulla':
        '↶ &Undo',
    '↷ &Ripeti':
        '↷ &Redo',
    '🎚 Modalità &Jam / Contest (Auto-Gain EBU R128)':
        '🎚 &Jam / Contest Mode (EBU R128 Auto-Gain)',
    'Abilita il livellamento automatico EBU R128 (-16 LUFS) per contest, jam session e file non calibrati.':
        'Enables automatic EBU R128 levelling (-16 LUFS) for contests, jam sessions and uncalibrated files.',
    '🎭 Modalità &LIVE (Show Mode)':
        '🎭 &LIVE Mode (Show Mode)',
    '🎨 &Tema Interfaccia':
        '🎨 Interface &Theme',
    '🔔 &Segnali Acustici Operatore (Earcons)':
        '🔔 Operator &Audio Cues (Earcons)',
    'Accessibilità Regia: Emette un discreto segnale sonoro di conferma ad ogni GO, STOP e PAUSA.\nUtile per operatori non vedenti o per chi guarda il palco senza guardare il monitor.':
        'Control accessibility: plays a discreet confirmation sound on every GO, STOP and PAUSE.\nUseful for blind operators or for those watching the stage instead of the monitor.',
    '📐 &Studio Superfici di Proiezione & Mapping…':
        '📐 Projection &Surfaces & Mapping Studio…',
    'Gestisci schermi virtuali, keystone a 4 angoli e configurazioni multi-proiettore':
        'Manage virtual screens, 4-corner keystone and multi-projector setups',
    '👁 &Mostra Guide sul Proiettore Live':
        '👁 &Show Guides on the Live Projector',
    'Proietta mire ottiche, griglia di precisione e contorni delle superfici sul palco':
        'Projects test patterns, a precision grid and surface outlines on stage',
    '🔒 &Blocca Larghezza Pannelli':
        '🔒 &Lock Panel Widths',
    'GO (Next Cue) — [ SPAZIO ]':
        'GO (Next Cue) — [ SPACE ]',
    'Caricamento Rapido (Drag && Drop)':
        'Quick Load (Drag && Drop)',
    '⚙ Dispositivi · Uscite':
        '⚙ Devices · Outputs',
    'Configura Master Audio Sala, Cuffia Regia (PFL), Schermo Live e Profilo Hardware (Eco/Pro).':
        'Configure House Audio Master, Control Headphones (PFL), Live Screen and Hardware Profile (Eco/Pro).',
    'Dispositivi e Uscite Hardware':
        'Devices and Hardware Outputs',
    'Apre il pannello di configurazione delle uscite audio sala, monitor cuffia, schermo video live e profili prestazionali.':
        'Opens the configuration panel for house audio outputs, headphone monitor, live video screen and performance profiles.',
    '🔒 Layout: Bloccato':
        '🔒 Layout: Locked',
    'Blocca o sblocca le larghezze dei 3 pannelli principali (Scaletta, Anteprima, Ispettore).\nDi default è bloccato per evitare spostamenti accidentali; clicca per ridimensionare a piacere.':
        'Lock or unlock the widths of the 3 main panels (Cue List, Preview, Inspector).\nLocked by default to avoid accidental moves; click to resize as you like.',
    'Blocca Larghezza Pannelli':
        'Lock Panel Widths',
    'Attiva o disattiva il blocco delle larghezze dei pannelli di regia per prevenire spostamenti accidentali.':
        'Enables or disables the control panel width lock to prevent accidental moves.',
    'Modalità Jam / Contest (Default: OFF).\nPROTEZIONE REGIA: Tieni premuto per 5 secondi per attivare.\nQuando attiva, applica automaticamente il livellamento sonoro EBU R128 (-16 LUFS)\nsu tutti i media per evitare salti improvvisi di volume durante contest o jam session.\nPer disattivare: tieni premuto 1.5 secondi.':
        'Jam / Contest Mode (Default: OFF).\nCONTROL PROTECTION: Hold for 5 seconds to activate.\nWhen active, automatically applies EBU R128 sound levelling (-16 LUFS)\nto all media to avoid sudden volume jumps during contests or jam sessions.\nTo deactivate: hold for 1.5 seconds.',
    'Modalità Jam e Contest Livellamento Audio':
        'Jam and Contest Audio Levelling Mode',
    'Attiva o disattiva il livellamento automatico EBU R128 a -16 LUFS. Richiede una pressione continua di 5 secondi per attivare.':
        'Turns automatic EBU R128 levelling at -16 LUFS on or off. Requires a continuous 5-second press to activate.',
    "Controllo Remoto LAN per Smartphone/Tablet (Web) e OSC.\nClicca per mostrare il QR Code, l'indirizzo IP e le opzioni di comando.":
        'LAN Remote Control for Smartphone/Tablet (Web) and OSC.\nClick to show the QR Code, the IP address and the command options.',
    'Controllo Remoto LAN Web e OSC':
        'LAN Web and OSC Remote Control',
    'Mostra il codice QR per smartphone e la configurazione del server web e OSC.':
        'Shows the QR code for smartphones and the web server and OSC configuration.',
    'Imposta Immagine di &Tappo (Layer 0)…':
        'Set &Cover Image (Layer 0)…',
    '&Ripristina Tappo Predefinito':
        '&Restore Default Cover',
    '⚙️ &Dispositivi & Hardware (Audio / Video / Profilo)…':
        '⚙️ &Devices & Hardware (Audio / Video / Profile)…',
    '📡 &Controllo Remoto LAN (Web & OSC)…':
        '📡 LAN &Remote Control (Web & OSC)…',
    '↺ &Ripristina Larghezze Standard':
        '↺ &Restore Standard Widths',
    '&Info Hardware & Accelerazione…':
        'Hardware & Acceleration &Info…',
    'Nessun progetto recente':
        'No recent projects',
    'Svuota elenco recenti':
        'Clear recent list',
    '🎚 Jam: OFF (Tieni 5s)':
        '🎚 Jam: OFF (Hold 5s)',
    '🎚 Jam Mode: ATTIVO':
        '🎚 Jam Mode: ON',
    '{}. {}  (non trovato)':
        '{}. {}  (not found)',
    'BlindCue — Ripristino Sessione (Crash Recovery)':
        'BlindCue — Session Restore (Crash Recovery)',
    'È stata rilevata una sessione precedente interrotta o non salvata!\n\n• Data ultimo autosave: {}\n• Cue recuperabili: {}\n\nVuoi ripristinare il progetto da dove era stato interrotto?':
        'A previous interrupted or unsaved session was detected!\n\n• Last autosave date: {}\n• Recoverable cues: {}\n\nDo you want to restore the project from where it was interrupted?',
    'Nuovo show creato':
        'New show created',
    'Apri Show BlindCue':
        'Open BlindCue Show',
    'BlindCue Show (*.blindcue *.json);;Tutti i file (*)':
        'BlindCue Show (*.blindcue *.json);;All files (*)',
    'Salva Show Con Nome':
        'Save Show As',
    'Salvataggio show':
        'Saving show',
    'Vuoi copiare i file audio/video dentro la cartella dello show?\n\nSì: archivio portatile, lo show si apre anche su un altro PC.\nNo: salva solo i collegamenti ai file originali (nessuna copia).\n\nIn entrambi i casi i file originali non vengono mai modificati.':
        'Do you want to copy the audio/video files into the show folder?\n\nYes: portable archive, the show also opens on another PC.\nNo: saves only links to the original files (no copy).\n\nIn both cases the original files are never modified.',
    'Sessione ripristinata con successo ({} cue)':
        'Session restored successfully ({} cues)',
    'Nuovo Show':
        'New Show',
    'Ci sono modifiche non salvate nel progetto corrente.\nVuoi salvarle prima di creare un nuovo show?':
        'There are unsaved changes in the current project.\nDo you want to save them before creating a new show?',
    'Apri Show':
        'Open Show',
    'Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?':
        'There are unsaved changes.\nDo you want to save before opening another show?',
    'Caricato: {} ({} cue)':
        'Loaded: {} ({} cues)',
    'Chiusura BlindCue':
        'Closing BlindCue',
    'Ci sono modifiche non salvate nel progetto.\nVuoi salvare prima di uscire?':
        'There are unsaved changes in the project.\nDo you want to save before quitting?',
    '\n… e altre {} cue':
        '\n… and {} more cues',
    'Salvato {} con {} file media copiati':
        'Saved {} with {} media files copied',
    '— Inattivo / Nero —':
        '— Idle / Black —',
    'Nuovo Spettacolo':
        'New Show',
    '{} Cue ({} scene)':
        '{} Cues ({} scenes)',
    'PROGETTAZIONE: LIVE MIRROR ATTIVO (Modifiche visibili sullo schermo esterno)':
        'DESIGN: LIVE MIRROR ON (Changes visible on the external screen)',
    'LIVE MIRROR DISATTIVATO — Anteprima isolata (Pronto per lo spettacolo)':
        'LIVE MIRROR OFF — Isolated preview (Ready for the show)',
    'Selezione mista: {} cue':
        'Mixed selection: {} cues',
    'BLACKOUT — Output ripristinato a Layer 0 (Tappo)':
        'BLACKOUT — Output reset to Layer 0 (Cover)',
    '🚨 PANIC (0ms) — STOP TOTALE ESEGUITO':
        '🚨 PANIC (0ms) — TOTAL STOP EXECUTED',
    'Scaletta vuota — Aggiungi prima dei file multimediali':
        'Empty cue list — Add some media files first',
    "LIVE → {} '{}' (Layer {}) | Standby: {} '{}'":
        "LIVE → {} '{}' (Layer {}) | Standby: {} '{}'",
    "LIVE → {} '{}' (Layer {}) — Fine scaletta (premi GO per rilanciare)":
        "LIVE → {} '{}' (Layer {}) — End of list (press GO to restart)",
    '↶ Annulla (Ctrl+Z) — Stato precedente ripristinato ({} nel registro)':
        '↶ Undo (Ctrl+Z) — Previous state restored ({} in history)',
    '↷ Ripeti — Modifica ripristinata ({} ripetibili)':
        '↷ Redo — Change restored ({} redoable)',
    'BlindCue – [{}{}] – Director Panel v{}':
        'BlindCue – [{}{}] – Director Panel v{}',
    'Nessuna operazione da annullare':
        'Nothing to undo',
    'Nessuna operazione da ripetere':
        'Nothing to redo',
    'zoom {}%  ·  rotellina = zoom · centrale = sposta · Ctrl+0 = 100%':
        'zoom {}%  ·  wheel = zoom · middle = pan · Ctrl+0 = 100%',
    'Maschera poligonale immagine':
        'Polygonal image mask',
    'Clic per aggiungere un punto · trascina un punto per spostarlo · clic destro per eliminarlo (minimo 3 punti).\nRotellina del mouse = zoom sul cursore · trascina con il tasto centrale per spostarti · Ctrl+0 = 100%.\nLa linea tratteggiata segue il cursore e mostra il lato successivo: il poligono si chiude da solo.\nIl file originale non viene mai modificato: la maschera viene salvata nel progetto.':
        'Click to add a point · drag a point to move it · right click to delete it (minimum 3 points).\nMouse wheel = zoom at the cursor · drag with the middle button to pan · Ctrl+0 = 100%.\nThe dashed line follows the cursor and shows the next side: the polygon closes by itself.\nThe original file is never modified: the mask is saved in the project.',
    '0 punti':
        '0 points',
    'Svuota':
        'Clear',
    'Riduci zoom (Ctrl+−)':
        'Zoom out (Ctrl+−)',
    'Aumenta zoom (Ctrl++)':
        'Zoom in (Ctrl++)',
    "Torna all'immagine intera (Ctrl+0)":
        'Back to the whole image (Ctrl+0)',
    'Bordo sfumato':
        'Feathered edge',
    'Ammorbidisce il contorno della maschera: 0 = taglio netto.\nLa sfumatura è proporzionata al frame, quindi identica sul proiettore e in Pre-Viz.':
        'Softens the mask outline: 0 = sharp cut.\nThe feathering is proportional to the frame, so it is identical on the projector and in Pre-Viz.',
    'Applica':
        'Apply',
    '{} punti':
        '{} points',
    'Nessun punto':
        'No points',
    'Immagine non disponibile':
        'Image not available',
    '📐 CALIBRAZIONE SUPERFICI LIVE · Premi F7 per Chiudere':
        '📐 LIVE SURFACE CALIBRATION · Press F7 to Close',
    'BlindCue – Live Output [Monitor Simulato]':
        'BlindCue – Live Output [Simulated Monitor]',
    'GIUNZIONE 50% (DUAL)':
        '50% JOIN (DUAL)',
    ' · ⭕ Ellisse':
        ' · ⭕ Ellipse',
    ' · 🔲 Buco':
        ' · 🔲 Hole',
    '⭕ BUCO ELLITTICO':
        '⭕ ELLIPTICAL HOLE',
    '⭕ SAGOMA ELLISSE':
        '⭕ ELLIPSE SHAPE',
    '🔲 BUCO / FORATURA':
        '🔲 HOLE / CUTOUT',
    '🔲 SAGOMA INTERNA':
        '🔲 INNER SHAPE',
    '🎵 RIPRODUZIONE AUDIO IN ANTEPRIMA (PRE-VIZ)':
        '🎵 AUDIO PLAYBACK IN PREVIEW (PRE-VIZ)',
    'Pre-ascolto attivo in cuffia • Monitor sala mutato':
        'Headphone pre-listen active • House monitor muted',
    "Premi ▶ Play sotto l'anteprima per pre-ascoltare in cuffia":
        'Press ▶ Play under the preview to pre-listen in the headphones',
    '🎬 VIDEO CARICATO IN PRE-VIZ — PREMI PLAY':
        '🎬 VIDEO LOADED IN PRE-VIZ — PRESS PLAY',
    'ANTEPRIMA PRE-VIZ (Sandbox)':
        'PRE-VIZ PREVIEW (Sandbox)',
    'Riproduci anteprima / Pre-viz':
        'Play preview / Pre-viz',
    "Metti in pausa l'anteprima":
        'Pause the preview',
    'Arresta anteprima e riavvolgi':
        'Stop preview and rewind',
    "Se attivo (default), l'anteprima è muta. Clicca per ascoltare l'audio su richiesta.":
        'When on (default), the preview is muted. Click to listen to the audio on demand.',
    "Modalità Progettazione: se ATTIVO, le modifiche a Crop, Scala e Posizione vengono proiettate in tempo reale sullo schermo LIVE per calibrare il videoproiettore/schermo.\nIn Spettacolo dal vivo: lasciare DISATTIVATO per isolare completamente l'anteprima.":
        'Design Mode: when ON, changes to Crop, Scale and Position are projected in real time on the LIVE screen to calibrate the projector/screen.\nDuring a live show: leave it OFF to fully isolate the preview.',
    '🔊 CUFFIA: ON':
        '🔊 HEADPHONES: ON',
    "\n<b>Indirizzo OSC:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br>\n• <b style='color:#4ade80;'>/go</b> oppure <b>/cue/go</b> &nbsp;→&nbsp; Esegue GO sulla cue in Standby<br>\n• <b style='color:#f87171;'>/panic</b> &nbsp;→&nbsp; Arresto immediato 0ms (Tutti i livelli)<br>\n• <b style='color:#f87171;'>/stop</b> oppure <b>/blackout</b> &nbsp;→&nbsp; Blackout live (Ritorno a Layer 0)<br>\n• <b style='color:#fbbf24;'>/pause</b> oppure <b>/resume</b> &nbsp;→&nbsp; Mette in pausa o riprende l'emissione<br>\n• <b style='color:#38bdf8;'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Sposta la selezione della scaletta<br>\n• <b style='color:#38bdf8;'>/cue/&lt;numero&gt;/go</b> &nbsp;→&nbsp; Esegue subito la cue indicata (es. <i>/cue/3/go</i>)<br>\n• <b style='color:#a855f7;'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Autentica l'IP per inviare comandi protetti\n        ":
        "\n<b>OSC Address:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br>\n• <b style='color:#4ade80;'>/go</b> or <b>/cue/go</b> &nbsp;→&nbsp; Runs GO on the Standby cue<br>\n• <b style='color:#f87171;'>/panic</b> &nbsp;→&nbsp; Immediate 0ms stop (All layers)<br>\n• <b style='color:#f87171;'>/stop</b> or <b>/blackout</b> &nbsp;→&nbsp; Live blackout (Back to Layer 0)<br>\n• <b style='color:#fbbf24;'>/pause</b> or <b>/resume</b> &nbsp;→&nbsp; Pauses or resumes the output<br>\n• <b style='color:#38bdf8;'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Moves the cue list selection<br>\n• <b style='color:#38bdf8;'>/cue/&lt;number&gt;/go</b> &nbsp;→&nbsp; Runs the given cue at once (e.g. <i>/cue/3/go</i>)<br>\n• <b style='color:#a855f7;'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Authenticates the IP to send protected commands\n        ",
    '📡 Controllo Remoto LAN (Web & OSC) — BlindCUE':
        '📡 LAN Remote Control (Web & OSC) — BlindCUE',
    '📡 CONTROLLO REMOTO IN RETE LOCALE (LAN REGIA)':
        '📡 LOCAL NETWORK REMOTE CONTROL (CONTROL LAN)',
    'Telecomando Operatore (GO/Pause/Panic), Monitor Regista (Sola Lettura) e Server OSC per automazione.':
        'Operator Remote (GO/Pause/Panic), Director Monitor (Read Only) and OSC Server for automation.',
    '🔴 SERVIZI REMOTI: DISATTIVATI (Avvia)':
        '🔴 REMOTE SERVICES: OFF (Start)',
    '📱 Telecomando Operatore (Master LIVE)':
        '📱 Operator Remote (LIVE Master)',
    '👁️ Monitor Regista (Sola Lettura)':
        '👁️ Director Monitor (Read Only)',
    '🎛️ Automazione OSC && Porte':
        '🎛️ OSC Automation && Ports',
    '🛡️ SICUREZZA REGIA — PROTEZIONE PIN (ANTI-BURLONE)':
        '🛡️ CONTROL SECURITY — PIN PROTECTION (ANTI-PRANKSTER)',
    'Proteggi con Codice PIN a 6 Cifre':
        'Protect with a 6-Digit PIN Code',
    'PIN Attuale:':
        'Current PIN:',
    '🎲 Nuovo PIN Casuale':
        '🎲 New Random PIN',
    'Genera un nuovo codice PIN casuale a 6 cifre e revoca le sessioni precedenti':
        'Generates a new random 6-digit PIN code and revokes previous sessions',
    '⛔ Disconnetti Tutti':
        '⛔ Disconnect All',
    "Sbatte fuori all'istante tutti i dispositivi connessi":
        'Kicks out all connected devices instantly',
    'Includi PIN nel codice QR (Accesso immediato con fotocamera)':
        'Include the PIN in the QR code (Instant camera access)',
    "💡 <b>Massima Tranquillità in Teatro:</b> Inquadrando il monitor con lo smartphone si entra all'istante senza digitare nulla. Chiunque altro sulla LAN che tenti di accedere via browser troverà il tastierino PIN casuale a 6 cifre con blocco forzatura dopo 5 errori.":
        '💡 <b>Peace of Mind in the Theatre:</b> Scanning the monitor with a smartphone gets you in instantly without typing anything. Anyone else on the LAN trying to connect via browser will get the random 6-digit PIN keypad with a lockout after 5 errors.',
    '📱 Client Web connessi: 0':
        '📱 Web clients connected: 0',
    'Chiudi':
        'Close',
    'Inquadra con Smartphone\nper aprire il Telecomando LIVE':
        'Scan with a Smartphone\nto open the LIVE Remote',
    '📱 TELECOMANDO MASTER LIVE (OPERATORE)':
        '📱 LIVE MASTER REMOTE (OPERATOR)',
    "Ideale per il tecnico sul palco o in sala durante le prove e il montaggio. Offre il controllo completo sull'emissione dei media.":
        'Ideal for the technician on stage or in the hall during rehearsals and set-up. Gives full control over the media output.',
    'Indirizzo Web:':
        'Web Address:',
    '📋 Copia Link':
        '📋 Copy Link',
    '🌐 Apri nel Browser':
        '🌐 Open in Browser',
    'Inquadra con Tablet / iPad\nper aprire il Monitor Regia':
        'Scan with a Tablet / iPad\nto open the Control Monitor',
    '👁️ MONITOR REGISTA && DIRETTORE DI SCENA (SOLA LETTURA)':
        '👁️ DIRECTOR && STAGE MANAGER MONITOR (READ ONLY)',
    'Interfaccia di sola visualizzazione passiva per tablet, iPad o computer del regista e del direttore di scena. Mostra in tempo reale come lavorano i 3 layer e la scaletta, garantendo zero rischi.':
        "Passive view-only interface for the director's and stage manager's tablet, iPad or computer. Shows in real time how the 3 layers and the cue list are working, with zero risk.",
    'Indirizzo Monitor:':
        'Monitor Address:',
    '📋 Copia Link Monitor':
        '📋 Copy Monitor Link',
    '🗣️ <b>Come collegare il regista che si trova in platea:</b>':
        '🗣️ <b>How to connect the director sitting in the audience:</b>',
    "1. <b>A voce / Intercom (se digita a mano):</b> Digli di collegarsi al Wi-Fi del teatro, aprire il browser (Safari, Chrome o Edge) e digitare l'indirizzo IP con la porta e <code>/monitor</code> (oppure <code>/regia</code>). Inserirà poi il PIN a 6 cifre visualizzato in basso.":
        '1. <b>By voice / Intercom (if typing by hand):</b> Tell them to join the theatre Wi-Fi, open the browser (Safari, Chrome or Edge) and type the IP address with the port and <code>/monitor</code> (or <code>/regia</code>). They will then enter the 6-digit PIN shown below.',
    '2. <b>Via Messaggio / WhatsApp / Email:</b> Clicca su <b>[ 📋 Copia Link Monitor ]</b> e incollaglielo in chat. Il link copiato include già il token PIN autorizzato: al regista basterà toccare il link per entrare subito senza digitare nulla!':
        '2. <b>Via Message / WhatsApp / Email:</b> Click <b>[ 📋 Copy Monitor Link ]</b> and paste it in the chat. The copied link already includes the authorised PIN token: the director just taps the link to get in without typing anything!',
    '⚙ CONFIGURAZIONE PORTE DI RETE && PROTOCOLLI':
        '⚙ NETWORK PORTS && PROTOCOLS CONFIGURATION',
    'Abilita Servizio Web (Telecomando && Monitor Regia)':
        'Enable Web Service (Remote && Control Monitor)',
    'Porta Web:':
        'Web Port:',
    'Abilita Server OSC UDP':
        'Enable UDP OSC Server',
    'Porta OSC UDP:':
        'UDP OSC Port:',
    '🔄 Applica Nuove Porte':
        '🔄 Apply New Ports',
    '🎛 PRONTUARIO COMANDI OSC (QLab / Mixer Luci / TouchOSC)':
        '🎛 OSC COMMAND REFERENCE (QLab / Lighting Desk / TouchOSC)',
    'Ultima attività: Nessun comando ricevuto':
        'Last activity: No command received',
    '✓ Disconnessi!':
        '✓ Disconnected!',
    '✅ <b>Pulsante GO tattile gigante</b> con vibrazione aptica':
        '✅ <b>Giant touch GO button</b> with haptic vibration',
    '✅ <b>Monitor Cue in onda</b> con barra countdown in tempo reale':
        '✅ <b>On-air Cue Monitor</b> with real-time countdown bar',
    '✅ <b>Pulsanti di emergenza:</b> Pausa/Riprendi, Blackout e PANIC 0ms':
        '✅ <b>Emergency buttons:</b> Pause/Resume, Blackout and PANIC 0ms',
    '✅ <b>Scaletta completa:</b> navigazione rapida e lancio diretto [ ▶ GO ] per singola Cue':
        '✅ <b>Full cue list:</b> quick navigation and direct [ ▶ GO ] launch for each Cue',
    '👁️ <b>Panoramica 3 Layer Live:</b> stato simultaneo di Layer 1 (Fondo), Layer 2 (Medio) e Layer 3 (Overlay)':
        '👁️ <b>3 Live Layers Overview:</b> simultaneous status of Layer 1 (Background), Layer 2 (Middle) and Layer 3 (Overlay)',
    '👁️ <b>Prossimo Lancio in Standby:</b> Q in attesa, destinazione layer, fade e tempi di transizione':
        '👁️ <b>Next Launch in Standby:</b> waiting Q, target layer, fade and transition times',
    '👁️ <b>Scaletta Dinamica Completa:</b> stato live, tipi media, tempi ed avanzamento':
        '👁️ <b>Full Dynamic Cue List:</b> live status, media types, timing and progress',
    "🔒 <b style='color:#f87171;'>Zero comandi e zero click:</b> nessun pulsante interattivo, nessun rischio di errore accidentale":
        "🔒 <b style='color:#f87171;'>Zero commands and zero clicks:</b> no interactive buttons, no risk of accidental errors",
    '🟢 SERVIZI: ATTIVI{} (Arresta)':
        '🟢 SERVICES: ON{} (Stop)',
    '🔴 SERVIZI REMOTI: OFF (Avvia)':
        '🔴 REMOTE SERVICES: OFF (Start)',
    'QR Code\nNon disponibile':
        'QR Code\nNot available',
    '✓ Copiato!':
        '✓ Copied!',
    'Rimuovi questa sezione e uniscila alla adiacente':
        'Remove this section and merge it with the adjacent one',
    'OUT/Fine':
        'OUT/End',
    'Sezione {} ({}s – {})\nClicca per saltare subito qui':
        'Section {} ({}s – {})\nClick to jump here now',
    'Ripetizioni o salto automatico per la Sezione {} (default: x1)':
        'Repetitions or automatic skip for Section {} (default: x1)',
    'Fine File':
        'End of File',
    '{} (Copia)':
        '{} (Copy)',
    'BlindCue – Studio Superfici di Proiezione, Mapping & Maschere':
        'BlindCue – Projection Surfaces, Mapping & Masks Studio',
    'Studio Superfici di Proiezione, Mapping & Maschere':
        'Projection Surfaces, Mapping & Masks Studio',
    'Schermi virtuali, keystone 4 angoli, maschere circolari, forature sagomate e mascherature PNG':
        'Virtual screens, 4-corner keystone, circular masks, shaped cutouts and PNG masking',
    '👁 Mostra Guide sul Proiettore Live (F7)':
        '👁 Show Guides on the Live Projector (F7)',
    'SUPERFICI DEFINITE':
        'DEFINED SURFACES',
    '＋ Nuova':
        '＋ New',
    '⎘ Duplica':
        '⎘ Duplicate',
    '✕ Elimina':
        '✕ Delete',
    'GEOMETRIA & PRESET':
        'GEOMETRY & PRESETS',
    '⬛ Rettangolare':
        '⬛ Rectangular',
    '⬡ Prospettiva (4 Angoli)':
        '⬡ Perspective (4 Corners)',
    '— Seleziona Preset Rapido —':
        '— Select Quick Preset —',
    "REGOLAZIONE FINE & UNITA'":
        'FINE ADJUSTMENT & UNITS',
    '％ Percentuale (%)':
        '％ Percentage (%)',
    '🎭 MASCHERA & RITAGLIO (MASK)':
        '🎭 MASK & CROP',
    'Nessuna (Piena)':
        'None (Full)',
    '⭕ Ellisse / Cerchio':
        '⭕ Ellipse / Circle',
    '🔲 Rettangolo / Finestra (Cutout)':
        '🔲 Rectangle / Window (Cutout)',
    '🖼 Maschera Immagine PNG':
        '🖼 PNG Image Mask',
    'Comportamento / Direzione:':
        'Behaviour / Direction:',
    "🔘 Proietta all'Interno (Sagoma)":
        '🔘 Project Inside (Shape)',
    '🔲 Buca al Centro (Foratura)':
        '🔲 Hole in the Centre (Cutout)',
    '📁 Scegli Immagine PNG...':
        '📁 Choose PNG Image...',
    '✕ Rimuovi':
        '✕ Remove',
    'Nessun file selezionato':
        'No file selected',
    '👁 Evidenzia Bordo Maschera sul Proiettore Live':
        '👁 Highlight Mask Edge on the Live Projector',
    '🖥 MULTI-PROIETTORE & SPAN':
        '🖥 MULTI-PROJECTOR & SPAN',
    'Per 2 o 3 proiettori affiancati, estendi il desktop nel sistema operativo e usa lo Span:':
        'For 2 or 3 side-by-side projectors, extend the desktop in the operating system and use Span:',
    'Estendi su Tutti i Monitor Esterni (Span)':
        'Extend over All External Monitors (Span)',
    '💡 Mouse: trascina i vertici o il riquadro. Trascina direttamente il buco sul canvas. Bordo Guida: proietta il contorno esatto sul palco per allinearlo al millimetro.':
        '💡 Mouse: drag the vertices or the frame. Drag the hole directly on the canvas. Guide Edge: projects the exact outline on stage to align it to the millimetre.',
    'Le modifiche sono applicate in tempo reale al motore di riproduzione.':
        'Changes are applied in real time to the playback engine.',
    'Salva & Chiudi':
        'Save & Close',
    'Superficie':
        'Surface',
    'Seleziona Immagine Maschera (PNG / Immagine)':
        'Select Mask Image (PNG / Image)',
    'Immagini (*.png *.jpg *.jpeg *.bmp *.webp);;Tutti i file (*.*)':
        'Images (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*.*)',
    'Nome:':
        'Name:',
    'C1 · Alto SX (TL)':
        'C1 · Top Left (TL)',
    'C2 · Alto DX (TR)':
        'C2 · Top Right (TR)',
    'C3 · Basso DX (BR)':
        'C3 · Bottom Right (BR)',
    'C4 · Basso SX (BL)':
        'C4 · Bottom Left (BL)',
    'Forma:':
        'Shape:',
    'Sfumatura Bordo (Feather):':
        'Edge Softness (Feather):',
    'Netto (0px)':
        'Sharp (0px)',
    'Morbido (15px)':
        'Soft (15px)',
    'Vignetta (35px)':
        'Vignette (35px)',
    'Larghezza:':
        'Width:',
    'Altezza:':
        'Height:',
    'Multi-Monitor Esteso':
        'Extended Multi-Monitor',
    "La finestra di uscita è stata estesa su tutti i monitor ({}×{} px).\nI preset 'Doppio Proiettore' mapperanno automaticamente ciascuna metà dello schermo!":
        "The output window has been extended over all monitors ({}×{} px).\nThe 'Dual Projector' presets will automatically map each half of the screen!",
    'Monitor Singolo Rilevato':
        'Single Monitor Detected',
    'È presente un solo schermo collegato. Per usare lo spanning multi-proiettore, collega un secondo monitor/proiettore alle uscite HDMI o DisplayPort.':
        'Only one screen is connected. To use multi-projector spanning, connect a second monitor/projector to the HDMI or DisplayPort outputs.',
    '🔲 Buco: {}, {} px · Dim: {} × {} px':
        '🔲 Hole: {}, {} px · Size: {} × {} px',
    'Pos: {}, {} px · Dim: {} × {} px':
        'Pos: {}, {} px · Size: {} × {} px',
    'Angolo Attivo:':
        'Active Corner:',
    '▲ ALTO / TOP ▲':
        '▲ TOP ▲',
    '▼ BASSO ▼':
        '▼ BOTTOM ▼',
    '◀ SX':
        '◀ L',
    'DX ▶':
        'R ▶',
    'L0 TAPPO • {}×{} ({})':
        'L0 COVER • {}×{} ({})',
    'Obsidian Slate (Regia Pro · Predefinito)':
        'Obsidian Slate (Pro Control · Default)',
    'Tema scuro broadcast calibrato per ambienti di regia con luce soffusa. Morbido e riposante.':
        'Dark broadcast theme calibrated for dimly lit control rooms. Soft and restful.',
    'Carbon Monocromo (100% Scala di Grigi · Bianco Puro)':
        'Carbon Mono (100% Greyscale · Pure White)',
    'Architettura al 100% in scala di grigi senza alcun colore: solo seta bianca, argento e grafite per la massima chiarezza e accessibilità assoluta.':
        '100% greyscale design without any colour: just white silk, silver and graphite for maximum clarity and absolute accessibility.',
    'Warm Amber Studio (Caldo Analogico · Valvolare)':
        'Warm Amber Studio (Warm Analogue · Valve)',
    'Palette calda e organica ispirata ai banchi audio analogici valvolari: toni caffè tostato, accenti ambra dorata e rame per il massimo comfort visivo.':
        'Warm, organic palette inspired by analogue valve audio desks: roasted coffee tones, golden amber and copper accents for maximum visual comfort.',
    'Nessun Colore (Predefinito)':
        'No Colour (Default)',
    'Rosso — Atto / Effetto':
        'Red — Act / Effect',
    'Ambra — Dialogo / Luce Calda':
        'Amber — Dialogue / Warm Light',
    'Verde — Musica / Ambiente':
        'Green — Music / Ambience',
    'Ciano — Video / Proiezione':
        'Cyan — Video / Projection',
    'Blu — Cambio Scena':
        'Blue — Scene Change',
    'Viola — Sogno / Atmosfera':
        'Purple — Dream / Atmosphere',
    'Magenta — Evento Speciale':
        'Magenta — Special Event',
    'Curva Fade IN / OUT':
        'Fade IN / OUT Curve',
    "Forma d'Onda e Automazioni (Timeline)":
        'Waveform and Automation (Timeline)',
    '↦ IN Testina':
        '↦ IN at Playhead',
    'Imposta il punto IN esattamente sulla testina di lettura (Scorciatoia: I)':
        'Sets the IN point exactly at the playhead (Shortcut: I)',
    'OUT Testina ↤':
        'OUT at Playhead ↤',
    'Imposta il punto OUT esattamente sulla testina di lettura (Scorciatoia: O)':
        'Sets the OUT point exactly at the playhead (Shortcut: O)',
    'Testina: --:--.--':
        'Playhead: --:--.--',
    'Ripristina IN a 0.00s e OUT a Fine file':
        'Reset IN to 0.00s and OUT to the End of file',
    "Modifica la curva Volume sulla forma d'onda":
        'Edit the Volume curve on the waveform',
    '👁 Opacità':
        '👁 Opacity',
    "Modifica l'opacità lungo il file video sulla stessa timeline":
        'Edit the opacity along the video file on the same timeline',
    'Finestra temporale visiva per immagini a durata infinita':
        'Visual time window for infinite-duration images',
    'Forma della rampa Fade IN / OUT (Logaritmica consigliata per audio)':
        'Fade IN / OUT ramp shape (Logarithmic recommended for audio)',
    '⟲ Reset Punti':
        '⟲ Reset Points',
    'Elimina tutti i punti sulla linea Volume/Opacità':
        'Deletes all points on the Volume/Opacity line',
    '✂ Dividi':
        '✂ Split',
    'Dividi virtualmente il file alla testina in sezioni A, B, C...':
        'Virtually splits the file at the playhead into sections A, B, C...',
    '⏭ Esci Loop':
        '⏭ Exit Loop',
    'Salta immediatamente fuori dalla sezione ripetuta verso la successiva':
        'Immediately jumps out of the repeated section to the next one',
    '↺ Reset Sez.':
        '↺ Reset Sect.',
    'Rimuovi tutte le sezioni virtuali e torna al file intero':
        'Remove all virtual sections and go back to the whole file',
    "Zoom indietro forma d'onda (rotella giù)":
        'Zoom out waveform (wheel down)',
    "Zoom forma d'onda — clicca per ripristinare 1.0× (o doppio clic / Ctrl+0)":
        'Waveform zoom — click to reset 1.0× (or double click / Ctrl+0)',
    "Zoom avanti forma d'onda (rotella su)":
        'Zoom in waveform (wheel up)',
    "Nessuna forma d'onda caricata":
        'No waveform loaded',
    'OUT: Fine':
        'OUT: End',
    'Vista {}s':
        'View {}s',
    'Opacità':
        'Opacity',
    'Layer comune: L{}':
        'Common layer: L{}',
    'Fade: {}':
        'Fade: {}',
    'Logaritmica':
        'Logarithmic',
    '🖥️ <b>CPU:</b> {} Core ({}) | 💾 <b>RAM:</b> {} GB (Disp: {} GB) | 🎮 <b>GPU:</b> {}':
        '🖥️ <b>CPU:</b> {} cores ({}) | 💾 <b>RAM:</b> {} GB (free: {} GB) | 🎮 <b>GPU:</b> {}',
    'VA-API Attiva':
        'VA-API active',
    'PRONTO':
        'READY',
    'ATTESA':
        'WAITING',
    'Testina: {}':
        'Playhead: {}',
    '💡 {}':
        '💡 {}',
    '📁 {} cue nel gruppo · Durata stimata: {}':
        '📁 {} cues in the group · Estimated duration: {}',
    ' (Manuale)':
        ' (Manual)',
    # ── strings found by a runtime crawl of every widget and dialog ──
    'Colore Cue: {}':
        'Cue colour: {}',
    'Colore Scena: {}':
        'Scene colour: {}',
    'Posizione: #{}':
        'Position: #{}',
    'Q (Copione): {}':
        'Q (script): {}',
    'Nome: {}':
        'Name: {}',
    'Note di Regia: {}':
        'Notes: {}',
    'File: {}':
        'File: {}',
    '⚠️ ATTENZIONE: {}':
        '⚠️ WARNING: {}',
    'Blocco manuale':
        'Stop (manual GO)',
    'Auto-GO a fine cue':
        'Auto-GO at cue end',
    'Simultanea con successiva':
        'Together with next',
    'Durata {}':
        'Duration {}',
    '{} | {}':
        '{} | {}',
    'STUDIO COMPOSITORE TIMELINE · {}':
        'TIMELINE STUDIO · {}',
    '⏱ Durata Scena: {}':
        '⏱ Scene length: {}',
    'Web: {} | OSC: {}':
        'Web: {} | OSC: {}',
    'Nessuna azione web ricevuta':
        'no web commands yet',
    '⬛ Schermo Intero (Default)':
        '⬛ Full screen (default)',
    '⬛  Schermo Intero (Default)':
        '⬛  Full screen (default)',
    'Dissolvenza in uscita {}':
        'Fade out: {}',
    'Pausa o Riprendi {}':
        'Pause or resume: {}',
    'Riavvolgi 10 secondi {}':
        'Back 10 s: {}',
    'Regolazione Opacità':
        'Opacity adjustment',
    'Regolazione Scala':
        'Scale adjustment',
    'Regolazione Volume':
        'Volume adjustment',
    'Ripristina Opacità':
        'Reset opacity',
    'Ripristina Scala':
        'Reset scale',
    'Ripristina Volume':
        'Reset volume',
    'Layer 0':
        'Layer 0',
    # ── user manual window (Help → User manual, F1) ──
    '📖 Manuale utente':
        '📖 User manual',
    'BlindCue – Manuale utente':
        'BlindCue – User manual',
    '⌂ Indice':
        '⌂ Contents',
    '← Indietro':
        '← Back',
    '🌐 Apri nel browser':
        '🌐 Open in browser',
    'Manuale non trovato: {}':
        'Manual not found: {}',
    # ── device settings dialog ──
    'Uscita video non applicata':
        'Video output not applied',
    'La modalità selezionata non è applicabile con gli schermi attuali.\nCollega il proiettore esterno richiesto e riprova.':
        'The selected mode cannot be used with the current screens.\nConnect the required external projector and try again.',
    'Proiettori coinvolti: ':
        'Projectors used: ',
    'Schermi coinvolti: ':
        'Screens used: ',
    # ── second launch while the program is already running ──
    'BlindCue è già in esecuzione ma non risponde.\n\nPotrebbe essere ancora in fase di avvio. Se la sua finestra non compare, chiudi BlindCue già aperto e riavvia il programma.':
        'BlindCue is already running but does not respond.\n\nIt may still be starting. If its window does not appear, close the running BlindCue and start the program again.',
    # ── text cues, crossfade and the cue list (feature PRs) ──
    'In basso':
        'Bottom',
    'Al centro':
        'Center',
    'In alto':
        'Top',
    'Cue di testo (didascalia)':
        'Text cue (caption)',
    'Scrivi il testo da mostrare sul proiettore…':
        'Type the text shown on the projector…',
    'Grassetto':
        'Bold',
    'Fascia scura dietro il testo':
        'Dark band behind the text',
    'Ombra':
        'Shadow',
    'Testo:':
        'Text:',
    'Dimensione carattere:':
        'Font size:',
    'Colore del testo:':
        'Text colour:',
    'Posizione sullo schermo:':
        'Position on screen:',
    'Suggerimento: la didascalia va sul Layer 3 (sopra video e foto). Fade In/Out, posizione e crossfade si impostano nell\'Inspector come per una foto.':
        'Tip: the caption goes on Layer 3 (on top of video and photos). Fade In/Out, position and crossfade are set in the Inspector like for a photo.',
    'Anteprima (proiettore):':
        'Preview (projector):',
    'Colore del testo':
        'Text colour',
    '+ Testo':
        '+ Text',
    'Aggiungi una didascalia sullo schermo (cue di testo, Layer 3)':
        'Add an on-screen caption (text cue, Layer 3)',
    'Aggiungi Testo':
        'Add Text',
    '✏ Modifica testo…':
        '✏ Edit text…',
    'Cue di testo':
        'Text cue',
    'Il cue selezionato non è un cue di testo. Aggiungine uno con il pulsante "+ Testo".':
        'The selected cue is not a text cue. Add one with the "+ Text" button.',
    'Crossfade: l\'immagine mostrata ora sul layer di questo cue sfuma nel nuovo cue nel tempo indicato (0 = stacco netto). Se lo usi, imposta il Fade In a 0.':
        'Crossfade: the picture currently shown on this cue\'s layer dissolves into this cue over the given time (0 = hard cut). Set Fade In to 0 when using it.',
    # ── speakers remembered per computer (feature PR) ──
    'Predefinito di sistema, segue il sistema (ora: {})':
        'System default output (now: {})',
    '{} (non collegato)':
        '{} (not connected)',
    'Uscita audio scelta non collegata ({}): suona l\'uscita predefinita ({})':
        'Chosen audio output not connected ({}): playing on the default output ({})',
    'Uscita audio scelta di nuovo collegata: {}':
        'Chosen audio output connected again: {}',
    # ── strings from 3157c0a (PANIC on ESC twice, VA-API, OSC, bundle masks) ──
    '<b>Indirizzo OSC:</b> <span style=\'color:#38bdf8;\'>{}</span><br>• <b style=\'color:#4ade80;\'>/go</b> oppure <b>/cue/go</b> &nbsp;→&nbsp; Esegue GO sulla cue in Standby<br>• <b style=\'color:#f87171;\'>/panic</b> &nbsp;→&nbsp; Arresto immediato 0ms (Tutti i livelli)<br>• <b style=\'color:#f87171;\'>/stop</b> oppure <b>/blackout</b> &nbsp;→&nbsp; Blackout live (Ritorno a Layer 0)<br>• <b style=\'color:#fbbf24;\'>/pause</b> / <b>/resume</b> / <b>/pause_toggle</b> &nbsp;→&nbsp; Pausa, ripresa o toggle<br>• <b style=\'color:#38bdf8;\'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Sposta la selezione della scaletta<br>• <b style=\'color:#38bdf8;\'>/cue/&lt;numero&gt;/go</b> &nbsp;→&nbsp; Esegue subito la cue indicata (es. <i>/cue/3/go</i>)<br>• <b style=\'color:#a855f7;\'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Autentica l\'IP per inviare comandi protetti':
        '<b>OSC Address:</b> <span style=\'color:#38bdf8;\'>{}</span><br>• <b style=\'color:#4ade80;\'>/go</b> or <b>/cue/go</b> &nbsp;→&nbsp; Runs GO on the Standby cue<br>• <b style=\'color:#f87171;\'>/panic</b> &nbsp;→&nbsp; Immediate 0ms stop (All layers)<br>• <b style=\'color:#f87171;\'>/stop</b> or <b>/blackout</b> &nbsp;→&nbsp; Live blackout (Back to Layer 0)<br>• <b style=\'color:#fbbf24;\'>/pause</b> / <b>/resume</b> / <b>/pause_toggle</b> &nbsp;→&nbsp; Pause, resume or toggle<br>• <b style=\'color:#38bdf8;\'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Moves the cue list selection<br>• <b style=\'color:#38bdf8;\'>/cue/&lt;number&gt;/go</b> &nbsp;→&nbsp; Runs the given cue at once (e.g. <i>/cue/3/go</i>)<br>• <b style=\'color:#a855f7;\'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Authenticates the IP to send protected commands',
    'Attiva (VA-API / Hardware Decode)':
        'Active (VA-API / Hardware Decode)',
    'EMERGENZA (0ms): Taglia immediatamente Audio, Video e Immagini su tutti i layer. Mostra Nero assoluto se il Tappo è quello di calibrazione (o Tappo personalizzato se impostato).\nDa tastiera: premi ESC due volte entro 0,6s (protezione anti-tocco accidentale).':
        'EMERGENCY (0ms): Immediately cuts Audio, Video and Images on all layers. Shows pure black if the cover is the calibration one (or the custom cover if set).\nFrom the keyboard: press ESC twice within 0.6 s (protection against accidental presses).',
    'Layer 0 (Tappo)':
        'Layer 0 (cover)',
    'Maschera superficie \'{}\'':
        'Surface mask \'{}\'',
    'OpenGL / EGL (solo compositing, decode CPU)':
        'OpenGL / EGL (compositing only, CPU decoding)',
    'Software Renderer (nessuna accelerazione GPU)':
        'Software Renderer (no GPU acceleration)',
    '⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms) — oppure clicca il pulsante PANIC':
        '⚠ Press ESC again within 0.6 s for PANIC (0ms) — or click the PANIC button',
    '🔒 Controlli Layer Protetti — Sblocca con il Lucchetto (1,2s)':
        '🔒 Layer Controls Protected — Unlock with the Padlock (1.2s)',
    '🚨  PANIC  —  STOP TOTALE   [ ESC ×2 ]':
        '🚨  PANIC  —  TOTAL STOP   [ ESC ×2 ]',
    'GO ignorato: secondo GO entro {} ms':
        'GO ignored: second GO within {} ms',
    '&Dissolvenza totale (Fade All)':
        '&Fade All',
    'Dissolvenza totale in {} s':
        'Fading everything out in {} s',
    '🔉 DISSOLVI [⇧ESC]':
        '🔉 FADE ALL [⇧ESC]',
    '⚠  TASTIERA NON SUL PANNELLO REGIA — SPAZIO ed ESC non arrivano a BlindCue. Clicca qui per riprenderla.':
        '⚠  KEYBOARD IS NOT ON THE DIRECTOR PANEL — SPACE and ESC do not reach BlindCue. Click here to take it back.',
    '⚠ Tastiera non sul pannello regia: SPAZIO ed ESC non arrivano a BlindCue':
        '⚠ Keyboard is not on the director panel: SPACE and ESC do not reach BlindCue',
    '{} pronta — premi GO per avviarla (il doppio clic in LIVE non avvia)':
        '{} ready — press GO to start it (a double-click does not start cues in LIVE)',
    '⛔ Esclusiva: blocca il GO finché è in onda':
        '⛔ Exclusive: blocks GO while it plays',
    "Mentre questa cue è in onda il GO manuale viene rifiutato (anche da remoto), così un GO dato per errore non la copre. Ctrl+Spazio forza comunque il GO.\nAttenzione: un'immagine senza durata resta in onda finché non viene fermata.":
        'While this cue is live a manual GO is refused (also from the remote), so a GO given by mistake cannot cover it. Ctrl+Space still forces the GO.\nNote: an image without a duration stays live until it is stopped.',
    "GO bloccato: '{}' è esclusiva ed è in onda — Ctrl+Spazio per forzare":
        "GO blocked: '{}' is exclusive and still live — Ctrl+Space to force",
    'GO &forzato (ignora cue esclusiva)':
        '&Forced GO (ignores exclusive cue)',
    'Dissolvenza totale: audio, video e immagini su tutti i layer sfumano insieme, poi si fermano. Il prossimo GO riparte dalla cue avviata a mano che è stata fermata.':
        'Fade All: audio, video and images on every layer fade out together, then stop. The next GO starts again from the hand-started cue that was stopped.',
    '+ Azione':
        '+ Action',
    'Aggiungi Azione':
        'Add Action',
    'Aggiungi una cue senza file: ferma, dissolve, cambia livello o opacità di altre cue, oppure mostra una nota per la regia':
        'Add a cue without a file: it stops, fades, re-levels or dims other cues, or shows a note to the operator',
    '🔉 Dissolvi e ferma':
        '🔉 Fade out and stop',
    '⏹ Ferma subito':
        '⏹ Stop at once',
    '🔁 Rilascia loop':
        '🔁 Release loop',
    '🎚 Cambio livello':
        '🎚 Level change',
    '🌓 Opacità layer':
        '🌓 Layer opacity',
    '📝 Nota per la regia':
        '📝 Note for the operator',
    '☑ Checklist prima dello spettacolo':
        '☑ Pre-show checklist',
    'Ferma subito':
        'Stop at once',
    'Rilascia loop':
        'Release loop',
    'Cambio livello':
        'Level change',
    'Opacità layer':
        'Layer opacity',
    'Nota per la regia':
        'Note for the operator',
    'Checklist prima dello spettacolo':
        'Pre-show checklist',
    'Microfoni accesi':
        'Microphones on',
    'Proiettore acceso':
        'Projector on',
    'Telefono in silenzioso':
        'Phone on silent',
    '⚡ Azione':
        '⚡ Action',
    'Durata: scheda Azione':
        'Duration: Action tab',
    'Azione:':
        'Action:',
    'Su cosa:':
        'Acts on:',
    'Modo:':
        'Mode:',
    'Livello:':
        'Level:',
    'Variazione:':
        'Change:',
    'Durata:':
        'Duration:',
    'Curva:':
        'Curve:',
    'Voci:':
        'Items:',
    'Tipo di azione':
        'Action type',
    'Su cosa agisce':
        'What it acts on',
    "Cue su cui agisce l'azione":
        'Cues the action acts on',
    'Testo della nota':
        'Note text',
    'Voci della checklist, una per riga':
        'Checklist items, one per line',
    'Tutto ciò che è in onda':
        'Everything playing',
    'Un layer':
        'One layer',
    'Cue scelte':
        'Chosen cues',
    'Uscita A':
        'Output A',
    'Uscita B':
        'Output B',
    'Conta solo con due proiettori indipendenti':
        'Only matters with two independent projectors',
    "Spunta le cue su cui agisce l'azione (un gruppo = tutte le sue cue)":
        'Tick the cues the action acts on (a group = all its cues)',
    'Assoluto (%)':
        'Absolute (%)',
    'Relativo (dB)':
        'Relative (dB)',
    '0 = subito':
        '0 = at once',
    "Es. Aspetta l'ingresso di Anna, poi GO":
        "E.g. Wait for Anna's entrance, then GO",
    'Una voce per riga':
        'One item per line',
    'Ambra':
        'Amber',
    'Rosso — attenzione':
        'Red — attention',
    'Verde':
        'Green',
    'Blu':
        'Blue',
    'Viola':
        'Purple',
    'Grigio chiaro':
        'Light grey',
    'Abbassa audio e immagine delle cue scelte nel tempo indicato, poi le ferma. Il loro Post-Delay e Auto-GO non partono.':
        'Fades the sound and picture of the chosen cues over the given time, then stops them. Their Post-Delay and Auto-GO do not run.',
    'Ferma subito le cue scelte, anche quelle in attesa del Pre-Delay.':
        'Stops the chosen cues at once, also those waiting for their Pre-Delay.',
    'La cue in loop finisce il giro in corso e poi prosegue: passa alla sezione successiva o termina normalmente (con Post-Delay e Auto-GO).':
        'The looping cue finishes the current pass and goes on: to the next section, or it ends normally (with Post-Delay and Auto-GO).',
    'Cambia il volume di ciò che suona, senza fermarlo. Assoluto: come se il Volume della cue fosse quello indicato. Relativo: più o meno dB rispetto ad ora.':
        'Changes the volume of what is playing without stopping it. Absolute: as if the cue Volume were the given value. Relative: that many dB louder or quieter than now.',
    'Rende più o meno trasparente tutto il layer (immagini e video). La cue successiva sullo stesso layer riparte piena.':
        'Makes the whole layer (pictures and videos) more or less transparent. The next cue on that layer starts at full opacity.',
    'Mostra il testo in cima alla finestra di regia (non sul proiettore). Non blocca il GO; sparisce al GO successivo o con ✕.':
        'Shows the text at the top of the director window (not on the projector). It does not block GO; it goes away at the next GO or with ✕.',
    'Lista da spuntare prima dello spettacolo: compare con il GO e anche entrando in LIVE finché non è tutta spuntata. Le spunte non vengono salvate.':
        'A list to tick before the show: it appears on GO and also when entering LIVE until everything is ticked. Ticks are not saved.',
    'nessuna cue scelta':
        'no cue chosen',
    'tutto in onda':
        'everything playing',
    'Nota: {}':
        'Note: {}',
    'Nota (vuota)':
        'Note (empty)',
    'Checklist: {} voci':
        'Checklist: {} items',
    'Dissolvi in {} s: {}':
        'Fade out in {} s: {}',
    'Rilascia loop: {}':
        'Release loop: {}',
    'Livello {} dB in {} s: {}':
        'Level {} dB in {} s: {}',
    'Livello {}% in {} s: {}':
        'Level {}% in {} s: {}',
    'Opacità {}% in {} s: {}':
        'Opacity {}% in {} s: {}',
    '⚡ {}':
        '⚡ {}',
    'Azione: {}':
        'Action: {}',
    "Azione {} '{}': nessun bersaglio in onda, niente da fare":
        "Action {} '{}': none of its targets is playing, nothing to do",
    "AZIONE → {} '{}': {}":
        "ACTION → {} '{}': {}",
    'Checklist: {} di {} spuntate':
        'Checklist: {} of {} ticked',
    '✕ Chiudi':
        '✕ Close',
    'Nascondi la nota (non ferma niente)':
        'Hide the note (stops nothing)',
    'Dissolvi e ferma':
        'Fade out and stop',
    '? cue eliminata dalla scaletta':
        '? cue deleted from the list',
    'Stop: {}':
        'Stop: {}',
    'GO: avvia la cue indicata sul pulsante [SPAZIO]':
        'GO: starts the cue named on the button [SPACE]',
    'Da dove parte lo spettacolo?':
        'Where does the show start?',
    "Dall'inizio: {}":
        'From the top: {}',
    'Riprendi da: {}':
        'Resume from: {}',
    'Dalla cue selezionata: {}':
        'From the selected cue: {}',
    '⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms)':
        '⚠ Press ESC again within 0.6 s for PANIC (0 ms)',
    "Aggiunta dopo '{}', alla fine della catena Simultanea / Auto-GO o del gruppo":
        "Added after '{}', at the end of the Simultaneous / Auto-GO chain or group",
    '▶ GO: {}':
        '▶ GO: {}',
    "La cue selezionata non è l'inizio della scaletta.\nDa quale cue deve partire il GO?":
        'The selected cue is not the top of the list.\nWhich cue should GO start from?',
    'La selezione è cambiata da quando hai lasciato LIVE.\nDa quale cue deve partire il GO?':
        'The selection changed since you left LIVE.\nWhich cue should GO start from?',
    'File non supportati, ignorati: {}':
        'Unsupported files skipped: {}',
    '⌨ Clicca qui: la tastiera è altrove — GO: {}':
        '⌨ Click here: the keyboard is in another window — GO: {}',
    '⚠ File mancante — GO: {}':
        '⚠ File missing — GO: {}',
    "⏳ GO in attesa (Ctrl+Spazio per forzare): '{}' è esclusiva":
        "⏳ GO waits (Ctrl+Space forces it): '{}' is exclusive",
    '↻ Già in onda, riparte — GO: {}':
        '↻ Already playing, restarts — GO: {}',
    'Elenco scaletta ad alto contrasto per il live. Frecce Su e Giù per standby, Spazio per il GO, Esc due volte per il Panic.':
        'High-contrast cue list for live. Up and Down arrows for standby, Space for GO, Esc twice for PANIC.',
    'MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC ×2 = PANIC]':
        'LIVE MODE ACTIVE — Simplified control interface [ESC ×2 = PANIC]',
    'Sessione precedente messa da parte: {}':
        'Previous session set aside (not deleted): {}',
    'Lo spettacolo è in corso.\nChiudere il programma ferma tutto ciò che è in onda.':
        'The show is running.\nClosing the program stops everything on air.',
    'Resta nel programma':
        'Stay in the program',
    'Chiudi il programma':
        'Close the program',
    '○ Preparazione':
        '○ Preparation',
    '○ PREPARAZIONE':
        '○ PREPARATION',
    '○ Preparazione  (tieni 1,5 s)':
        '○ Preparation  (hold 1.5 s)',
    '● Spettacolo':
        '● Show',
    '● SPETTACOLO':
        '● SHOW',
    'Modalità preparazione (attiva)':
        'Preparation mode (on)',
    'Modalità spettacolo (attiva)':
        'Show mode (on)',
    'Entra nello spettacolo':
        'Enter the show',
    'Entra nello spettacolo [F5]':
        'Enter the show [F5]',
    'Torna alla preparazione: tieni premuto 1,5 secondi':
        'Back to preparation: hold for 1.5 seconds',
    'Tieni premuto 1,5 s per tornare alla preparazione (ciò che è in onda continua). Da tastiera: Ctrl+Maiusc+F5':
        'Hold 1.5 s to go back to preparation (what plays keeps playing). Keyboard: Ctrl+Shift+F5',
    'Dissolvenza totale: tutto ciò che è in onda sfuma e si ferma [Maiusc+Esc]':
        'Fade all: everything on air fades out and stops [Shift+Esc]',
    'PANIC: ferma subito tutto (0 ms) [Esc due volte]':
        'PANIC: stops everything at once (0 ms) [Esc twice]',
    'Termina lo spettacolo…':
        'End the show…',
    'Termina lo spettacolo':
        'End the show',
    'Tornare alla preparazione? Ciò che è in onda continua a suonare.':
        'Go back to preparation? What plays keeps playing.',
    'Resta nello spettacolo':
        'Stay in the show',
    'Torna alla preparazione':
        'Back to preparation',
    'Per uscire dallo spettacolo: tieni premuto «○ Preparazione» per 1,5 s oppure Ctrl+Maiusc+F5':
        'To leave the show: hold "○ Preparation" for 1.5 s or press Ctrl+Shift+F5',
    'Nello spettacolo la scaletta non cambia: per modificarla torna alla preparazione (tieni premuto «○ Preparazione»)':
        'In the show the list does not change: to edit it go back to preparation (hold "○ Preparation")',
    'Nello spettacolo le cue non cambiano: per modificarle torna alla preparazione':
        'In the show cues do not change: to edit them go back to preparation',
    'Annulla non serve nello spettacolo: lo spettacolo non è stato cambiato':
        'Undo is not needed in the show: the show has not been changed',
    'Volume generale dello spettacolo':
        'Master volume of the show',
    'Volume generale di tutto ciò che suona [Ctrl+↑ / Ctrl+↓]':
        'Master volume of everything that plays [Ctrl+↑ / Ctrl+↓]',
    'Silenzia':
        'Mute',
    '🔇 SILENZIATO':
        '🔇 MUTED',
    "Silenzia tutto (l'anteprima resta) [Ctrl+M]":
        'Mute everything (the preview stays) [Ctrl+M]',
    '🔇 Tutto silenziato (volume generale) — Ctrl+M per riattivare':
        '🔇 Everything muted (master volume) — Ctrl+M to unmute',
    'Volume generale {} %':
        'Master volume {} %',
    'Lo spettacolo era in corso: si torna nello spettacolo.':
        'The show was running: the program goes back into the show.',
    'Riprendi: prossima {}':
        'Resume: next {}',
    "Ripeti l'ultima: {}":
        'Play the last one again: {}',
    "Dall'inizio":
        'From the top',
    'Apri senza ripristinare':
        'Open without restoring',
    '✓ ULTIMA':
        '✓ LAST',
    '· {} fa':
        '· {} ago',
    '+ {} insieme':
        '+ {} together',
    '· manuale (GO)':
        '· by hand (GO)',
    '· parte da sola tra {}':
        '· starts by itself in {}',
    '· parte da sola dopo {}':
        '· starts by itself after {}',
    "↶ Annulla l'ultimo GO":
        '↶ Undo last GO',
    'sfumo {} (1 s)':
        'fade out {} (1 s)',
    'tolgo {} dallo schermo':
        'take {} off the screen',
    "l'immagine {} torna":
        'picture {} comes back',
    '{} non è ancora partita: la annullo':
        '{} has not started yet: cancel it',
    '{} è già finita':
        '{} has already ended',
    '{} interrotta: non torna da sola':
        '{} was cut off and will not come back by itself',
    "l'azione {} resta":
        'action {} stays',
    'prossima di nuovo {}':
        'next again {}',
    'Annullo:':
        'Undo:',
    '↶ Annulla GO {} · {}':
        '↶ Undo GO {} · {}',
    'Questo GO non si annulla (azione)':
        'This GO cannot be undone (action)',
    'Annulla GO {} ({} s)':
        'Undo GO {} ({} s)',
    'Nessun GO da annullare':
        'No GO to undo',
    '↶ GO {} annullato':
        '↶ GO {} undone',
    'GO {} annullato · prossima: {}':
        'GO {} undone · next: {}',
    'Prima dello spettacolo':
        'Before the show',
    '✓ SÌ':
        '✓ YES',
    '✗ NO':
        '✗ NO',
    '– NON VERIFICATO':
        '– NOT CHECKED',
    '↻ Ricontrolla':
        '↻ Check again',
    '{} (schermo {})':
        '{} (screen {})',
    '(non salvato)':
        '(not saved)',
    'modifiche non salvate':
        'unsaved changes',
    'Immagine: {}':
        'Picture: {}',
    "L'immagine va sullo schermo del portatile: proiettore non trovato. Se gli schermi sono duplicati, premi Win+P → Estendi.":
        'The picture goes to the laptop screen: no projector found. If the screens are duplicated, press Win+P → Extend.',
    "L'immagine va sullo schermo del portatile, anche se c'è un altro schermo.":
        'The picture goes to the laptop screen, although another screen is connected.',
    'Mostra i numeri degli schermi':
        'Show screen numbers',
    'Scegli lo schermo…':
        'Choose the screen…',
    'Volume generale 100 %, senza silenziamento':
        'Master volume 100 %, not muted',
    'Volume generale {} % · SILENZIATO':
        'Master volume {} % · MUTED',
    'Riporta a 100 %':
        'Back to 100 %',
    '{} (scelte qui)':
        '{} (pinned)',
    'Audio: {} – si sente in sala':
        'Sound: {} – heard in the hall',
    "Le casse scelte '{}' non sono collegate: suona l'uscita predefinita di Windows.":
        "The chosen speakers '{}' are not connected: the Windows default output plays.",
    'Scegli le casse…':
        'Choose the speakers…',
    'Audio: {} – il tono non si sente in sala':
        'Sound: {} – the tone is not heard in the hall',
    '▶ Tono di prova':
        '▶ Test tone',
    'Sì, si sente':
        'Yes, heard',
    'Non si sente':
        'Not heard',
    'Audio: {} – il tono non è disponibile, qualcosa suona. Si sente in sala?':
        'Sound: {} – no test tone, something is playing. Is it heard in the hall?',
    'Audio: {} – si sente in sala?':
        'Sound: {} – heard in the hall?',
    'Audio: {} – suona il tono di prova e ascolta in sala':
        'Sound: {} – play the test tone and listen in the hall',
    'Tutti i file al loro posto ({})':
        'All files in place ({})',
    'File mancanti ({}): {}':
        'Missing files ({}): {}',
    'Mostra nella lista':
        'Show in the list',
    "Portatile collegato all'alimentatore":
        'Laptop on mains power',
    "Portatile a batteria ({} %): collega l'alimentatore":
        'Laptop on battery ({} %): plug in the charger',
    'Lo spettacolo non ha una checklist':
        'The show has no checklist',
    'Aggiungi la checklist predefinita':
        'Add the default checklist',
    'Spettacolo: {}':
        'Show: {}',
    '▶ Inizia: {}':
        '▶ Start: {}',
    'Problemi: {}. Puoi iniziare lo stesso.':
        'Problems: {}. You can start anyway.',
    'Tutto pronto.':
        'All ready.',
    'Torna allo spettacolo':
        'Back to the show',
    'Resta in Preparazione':
        'Stay in Preparation',
    'proiettore':
        'projector',
    'alimentatore':
        'charger',
    'Controllo prima dello spettacolo: problemi: {}':
        'Check before the show: problems: {}',
    'Checklist predefinita aggiunta in cima alla scaletta':
        'Default checklist added at the top of the list',
    'Alimentatore collegato al portatile':
        'Charger plugged into the laptop',
    'Notifiche disattivate (Windows: Non disturbare)':
        'Notifications off (Windows: Do not disturb)',
    'Altri programmi chiusi (Teams, browser, OneDrive)':
        'Other programs closed (Teams, browser, OneDrive)',
    'Schermo del portatile abbassato':
        'Laptop screen dimmed',
    'Amplificatore e casse accesi, manopola come alla prova':
        'Amplifier and speakers on, knob as at the rehearsal',
    'Copia dello spettacolo su chiavetta (File → Salva con nome, portatile)':
        'Copy of the show on a USB stick (File → Save as, portable)',
    'Telefono del telecomando carico, nella stessa rete':
        'Remote-control phone charged, on the same network',
    'file':
        'files',
    'audio':
        'sound',
    'volume':
        'volume',
    'checklist':
        'checklist',
    'Pronto. Non verificato: {}.':
        'Ready. Not checked: {}.',
    'Sfuma':
        'Fade out',
    'Sfuma e ferma questa cue (non sposta il GO)':
        'Fade out and stop this cue (the GO stays where it is)',
    'Pausa / riprendi questa cue':
        'Pause / resume this cue',
    'Il loop finisce dopo questo giro':
        'The loop ends after this pass',
    'Ora in onda':
        'Now playing',
    'ORA IN ONDA':
        'NOW PLAYING',
    'Niente in onda.':
        'Nothing is playing.',
    'parte tra {}':
        'starts in {}',
    'PAUSA':
        'PAUSED',
    'attesa {}':
        'waits {}',
    'LOOP ∞':
        'LOOP ∞',
    'tempo: {}':
        'time: {}',
    'finisce – il prossimo GO è tuo':
        'ends soon – the next GO is yours',
    '✓ suonata':
        '✓ played',
    'in pausa':
        'paused',
    'in onda':
        'on air',
    'prossima':
        'next',
    'in attesa':
        'waiting',
    'pronta':
        'ready',
    'Indietro di 10 s (tieni premuto)':
        'Back 10 s (hold)',
    'Avanti di 10 s (tieni premuto)':
        'Forward 10 s (hold)',
    'Livello di questa cue (Ctrl+clic = livello della cue)':
        "Level of this cue (Ctrl+click = the cue's own level)",
    'Livello di questa cue':
        'Level of this cue',
    '{} a {} % ({} s) da {}':
        '{} to {} % ({} s) by {}',
    'Auto-GO dopo {} di nuovo attivo':
        'Auto-GO after {} works again',
    'Auto-GO dopo {} fermato: la prossima aspetta il GO':
        'Auto-GO after {} held: the next cue waits for a GO',
    'Auto-GO fermato: {} aspetta il GO':
        'Auto-GO held: {} waits for a GO',
    'Trattieni':
        'Hold',
    'Riprendi Auto-GO':
        'Let Auto-GO run',
    "L'Auto-GO aspetta il GO: la prossima cue non parte da sola":
        'The Auto-GO waits for a GO: the next cue does not start by itself',
    '· aspetta il GO (Auto-GO fermato)':
        '· waits for a GO (Auto-GO held)',
    '▾ ANTEPRIMA USCITA':
        '▾ OUTPUT PREVIEW',
    '▸ ANTEPRIMA USCITA':
        '▸ OUTPUT PREVIEW',
    'ANTEPRIMA USCITA':
        'OUTPUT PREVIEW',
    "Anteprima dell'uscita":
        'Output preview',
    '◐ Prova':
        '◐ Rehearsal',
    '◐ PROVA':
        '◐ REHEARSAL',
    'Prova: lo spettacolo come in scena, con piccole correzioni [Maiusc+F5]':
        'Rehearsal: the show as on stage, with small fixes [Shift+F5]',
    '◐ Prova  (tieni 1,5 s)':
        '◐ Rehearsal  (hold 1.5 s)',
    'Tieni premuto 1,5 s per passare alla prova (ciò che è in onda continua)':
        'Hold for 1.5 s to go to the rehearsal (what plays keeps playing)',
    'Passa alla prova: tieni premuto 1,5 secondi':
        'Go to the rehearsal: hold for 1.5 seconds',
    'Modalità prova (attiva)':
        'Rehearsal mode (on)',
    'Passa alla prova':
        'Go to the rehearsal',
    'Correzioni della prova':
        'Rehearsal fixes',
    'Chiudi le correzioni (le modifiche restano)':
        'Close the fixes (the changes stay)',
    'Chiudi le correzioni':
        'Close the fixes',
    'Nome':
        'Name',
    'Note':
        'Notes',
    'Livello della cue':
        'Level of the cue',
    'Livello':
        'Level',
    'Entra':
        'Fade in',
    'Inizio':
        'Start',
    'Fine':
        'End',
    'fine':
        'end',
    'Poi':
        'Then',
    'Manuale (GO)':
        'By hand (GO)',
    'Insieme alla successiva':
        'Together with the next',
    'Rivedi':
        'Review',
    'Altre impostazioni → Preparazione':
        'More settings → Preparation',
    'Si cambia quando la cue non suona':
        'Changes when the cue does not play',
    'nome':
        'name',
    'note':
        'notes',
    'livello':
        'level',
    'entrata':
        'fade in',
    'sfumatura':
        'fade out',
    'inizio':
        'start',
    'poi':
        'then',
    'Prova: lo spettacolo con piccole correzioni (✎). Ciò che suona continua.':
        'Rehearsal: the show with small fixes (✎). What plays keeps playing.',
    "✎ CORREGGI {} '{}'":
        "✎ FIXING {} '{}'",
    'Modifiche della prova: {}':
        'Rehearsal changes: {}',
    'Prova: {} {} {} → {}':
        'Rehearsal: {} {} {} → {}',
    'Modifiche della prova':
        'Rehearsal changes',
    'Nessuna modifica nella prova.':
        'No changes from the rehearsal.',
    'Correggi questa cue (prova)':
        'Fix this cue (rehearsal)',
    'Correggi questa cue':
        'Fix this cue',
    'Ferma subito questa cue':
        'Stop this cue at once',
    'Salta a 5 s dalla fine (per provare il finale)':
        'Jump to 5 s before the end (to rehearse the ending)',
    'Salva livello':
        'Save level',
    'Il livello corretto diventa quello della cue':
        "The corrected level becomes the cue's own",
    'Nella prova si correggono solo livello, tempi e note. Aggiungere, togliere e spostare: clicca «○ Preparazione»':
        'In the rehearsal you fix only levels, times and notes. To add, delete or move: click “○ Preparation”',
    'Spettacolo: {} · modifiche della prova: {}':
        'Show: {} · rehearsal changes: {}',
    'Annulla modifica':
        'Undo',
    'Entra (dissolvenza in entrata)':
        'Fade in',
    'Sfuma (dissolvenza in uscita)':
        'Fade out',
    'Inizio (dove parte il file)':
        'Start (where the file begins)',
    'Fine (dove si ferma; «fine» = fine del file)':
        'End (where it stops; “end” = end of the file)',
    'Da / a':
        'From / to',
    'PIN per uscire dallo spettacolo:':
        'PIN to leave the show:',
    'Invio – esci':
        'Enter – leave',
    'Inserisci il PIN per uscire dallo spettacolo (GO e PANIC funzionano)':
        'Type the PIN to leave the show (GO and PANIC work)',
    'Hai dimenticato il PIN? Chiudi il programma (File → Esci): lo spettacolo si riapre in Preparazione.':
        'Forgot the PIN? Close the program (File → Quit): the show opens again in Preparation.',
    'PIN sbagliato.':
        'Wrong PIN.',
    'Il PIN si cambia in Preparazione':
        'The PIN is changed in Preparation',
    'PIN di uscita dallo spettacolo':
        'Exit PIN of the show',
    '4 cifre per uscire dallo spettacolo su questo computer (vuoto = basta tenere premuto 1,5 s):':
        '4 digits to leave the show on this computer (empty = holding for 1.5 s is enough):',
    'Il PIN deve avere 4 cifre':
        'The PIN must have 4 digits',
    'PIN di uscita impostato':
        'Exit PIN set',
    'PIN di uscita tolto':
        'Exit PIN removed',
    'PIN di uscita dallo spettacolo…':
        'Exit PIN of the show…',
    '{} torna da {}':
        '{} comes back from {}',
    'Cuffie collegate: i suoni per la regia sono spenti (GO, blocchi, cambio di modalità)':
        'Headphones connected: the operator sounds are off (GO, refusals, mode changes)',
    'Accendi':
        'Turn on',
    'I suoni per la regia tacciono: le cuffie sono le casse del pubblico':
        'The operator sounds keep quiet: the headphones are the audience speakers',
    '⚠ Impossibile riprodurre{} (L{}): file mancante, danneggiato o non supportato':
        '⚠ Cannot play{} (L{}): file missing, damaged or not supported',
    'Tieni premuto più a lungo (1,5 s) per uscire dallo spettacolo':
        'Hold longer (1.5 s) to leave the show',
    'Nessuna immagine nella scaletta':
        'The show has no pictures',
    "Nessun'altra immagine in questa direzione":
        'No more pictures that way',
    "✋ Aspetta l'OK: parte solo dopo la conferma":
        '✋ Waits for an OK: starts only after it is confirmed',
    "Il GO su questa cue la prepara e aspetta l'OK: Invio sulla lista, il pulsante OK o il GO del telecomando nel telefono. Se nel frattempo parte un'altra cue, l'attesa decade.":
        'A GO on this cue only arms it and waits for an OK: Enter on the list, the OK button or GO on the phone remote. If another cue starts meanwhile, the wait lapses.',
    "✋ {} aspetta l'OK: Invio, il pulsante OK o il GO del telefono":
        '✋ {} waits for an OK: Enter, the OK button or GO on the phone',
    "Nessuna cue aspetta l'OK":
        'No cue is waiting for an OK',
    "Aspetta l'OK: Invio o il pulsante OK (il GO non basta)":
        'Waiting for the OK: Enter or the OK button (GO is not enough)',
    'Conferma: la cue parte adesso (anche Invio sulla lista)':
        'Confirm: the cue starts now (also Enter on the list)',
    "· ✋ aspetta l'OK":
        '· ✋ waits for the OK',
    'Livello di uscita':
        'Output level',
    'Le modifiche della prova si rivedono nella prova o in preparazione':
        'Rehearsal changes are reviewed in the rehearsal or in preparation',
    'Annullato: {} {} {} → {}':
        'Undone: {} {} {} → {}',
    'Nessuna correzione della prova da annullare':
        'No rehearsal fix to undo',
    "Nella prova Ctrl+Z annulla l'ultima correzione; ripeti in preparazione":
        'In the rehearsal Ctrl+Z undoes the last fix; redo in preparation',
    'Sfuma: solo la cue di questa scheda':
        'Fade out: only the cue of this card',
    'Partenza annullata: la cue non parte':
        'Start cancelled: the cue will not start',
    'Annulla partenza':
        'Cancel start',
    'La cue non partirà':
        'The cue will not start',
    '○ Preparazione (1,5 s)':
        '○ Preparation (1.5 s)',
    '◐ Prova (1,5 s)':
        '◐ Rehearsal (1.5 s)',
    'La scaletta è nascosta: torna alla lista per modificarla':
        'The list is hidden: go back to it to change it',
    'Tieni premuto per saltare di 10 s (1,5 s nello spettacolo)':
        'Hold to jump 10 s (1.5 s in the show)',
    'IN:':
        'Start:',
    'OUT:':
        'End:',
    '▾ Più impostazioni':
        '▾ More settings',
    '▴ Meno impostazioni':
        '▴ Fewer settings',
    'Mostra tutte le schede di questa cue nello stesso posto. Il layout della finestra non cambia.':
        'Shows all the settings of this cue in the same place. The window layout does not change.',
    '◐ Transizioni':
        '◐ Transitions',
    'parte {} s dopo il GO':
        'starts {} s after GO',
    'aspetta {} s dopo la fine':
        'waits {} s after its end',
    'il GO aspetta che finisca':
        'GO waits until it ends',
    "aspetta l'OK":
        'waits for an OK',
    'suona in loop':
        'plays in a loop',
    'si ripete {}×':
        'repeats {}×',
    'sezioni: {}':
        'sections: {}',
    'il volume cambia nel tempo':
        'the level changes over time',
    'volume livellato':
        'levelled loudness',
    'immagine modificata (ritaglio, posizione o opacità)':
        'changed picture (crop, position or opacity)',
    'sul proiettore B':
        'on projector B',
    'Questa cue ha anche: {}':
        'This cue also has: {}',
    '▦ Layout della finestra':
        '▦ Window layout',
    '&Semplice – lista, GO e impostazioni di base':
        '&Lite – list, GO and the basic settings',
    "&Esteso – in più la forma d'onda e tutte le schede":
        '&Medium – plus the waveform and every tab',
    '&Completo – tutto, anche i layer e il caricamento rapido':
        '&Full – everything, also the layers and quick add',
    '↺ Ripristina layout':
        '↺ Restore layout',
    'Quanti pannelli mostra la preparazione (lo spettacolo non cambia)':
        'How many panels the preparation shows (the show does not change)',
    'Semplice':
        'Lite',
    'Esteso':
        'Medium',
    'Completo':
        'Full',
    'Layout: {} ▾':
        'Layout: {} ▾',
    'Layout della finestra: {}':
        'Window layout: {}',
    'Il layout {} si vede tornando in preparazione':
        'The {} layout shows when you go back to preparation',
    'Layout: {}':
        'Layout: {}',
    'Ripristinato il layout {}: larghezze dei pannelli e impostazioni della cue':
        'Layout {} restored: default panel widths and cue settings',
    'Standby: {} [{}]':
        'Next: {} [{}]',
    "All'avvio sfuma le altre:":
        'On start, fade the others:',
    'no':
        'no',
    'Quando questa cue parte, gli altri suoni e video in onda sfumano in questi secondi (cambio di musica con una sola cue). Una musica sullo stesso layer sfuma invece di essere tagliata. 0 = no.':
        'When this cue starts, the other sounds and videos on air fade out over these seconds (a change of music with one cue). Music on the same layer fades out instead of being cut. 0 = no.',
    "all'avvio sfuma le altre in {} s":
        'on start fades the others over {} s',
    "🎵 Effetto a richiesta (fuori dall'ordine del GO)":
        '🎵 Effect on demand (outside the GO order)',
    'Il GO lo salta; parte dal suo tasto o dalla sua piastrella in «Ora in onda», su un lettore libero, senza spostare il GO e senza fermare ciò che suona.':
        'GO skips it; it starts from its key or its tile in "Now playing", on a free player, without moving GO and without stopping what plays.',
    'Tasto:':
        'Key:',
    "Una lettera o una cifra; nella prova e nello spettacolo fa partire l'effetto. Più cue sullo stesso tasto partono una dopo l'altra (passi).":
        'A letter or a digit; in the rehearsal and the show it starts the effect. Several cues on the same key start one after the other (steps).',
    "Tasto dell'effetto":
        'Effect key',
    'Avvia (di nuovo = da capo)':
        'Start (again = from the top)',
    'Avvia / ferma':
        'Start / stop',
    'Suona finché tieni premuto':
        'Plays while the key is held',
    'effetto a richiesta (tasto {})':
        'effect on demand (key {})',
    "Effetto: {} '{}' (il GO resta su {})":
        "Effect: {} '{}' (GO stays on {})",
    'Nessun effetto da ripetere':
        'No effect to repeat',
    "Tutti i lettori degli effetti sono occupati: '{}' lascia il posto":
        "All effect players are busy: '{}' gives way",
    "↻ Ripeti l'ultimo effetto  [Ctrl+R]":
        '↻ Repeat the last effect  [Ctrl+R]',
    "Nessun lettore libero per l'effetto '{}': non parte":
        "No free player for the effect '{}': it does not start",
    "🤖 L'assistente AI può modificare lo spettacolo":
        '🤖 The AI assistant may change the show',
    'Un assistente AI su questo computer (Claude Desktop o un altro client MCP) può leggere lo spettacolo aperto e modificarlo nella preparazione. Ogni modifica si annulla con Ctrl+Z.':
        'An AI assistant on this computer (Claude Desktop or another MCP client) can read the open show and change it in Preparation. Ctrl+Z undoes every change.',
    "🤖 Modifiche dall'assistente AI…":
        '🤖 Changes from the AI assistant…',
    'Assistente AI: impossibile aprire il collegamento locale':
        'AI assistant: the local link cannot be opened',
    '🤖 Assistente AI collegabile: può modificare lo spettacolo nella preparazione':
        '🤖 The AI assistant can connect: it changes the show in Preparation',
    '🤖 Assistente AI: {}':
        '🤖 AI assistant: {}',
    'salvato lo spettacolo':
        'saved the show',
    "Nessuna modifica dall'assistente.":
        'No changes from the assistant.',
    "Modifiche dall'assistente AI":
        'Changes from the AI assistant',
    'Ogni modifica è un passo di Annulla (Ctrl+Z).':
        'Every change is one Undo step (Ctrl+Z).',
    '(nuovo spettacolo non salvato)':
        '(new show, not saved)',
    'aggiunta la cue':
        'added the cue',
    'aggiunta la didascalia':
        'added the caption',
    "aggiunta l'azione":
        'added the action',
    'aggiunta la scena':
        'added the scene',
    'modificata la cue':
        'changed the cue',
    'spostata la cue':
        'moved the cue',
    'eliminate le cue':
        'deleted cues',
    '🤖 Assistente AI…':
        '🤖 AI assistant…',
    'Assistente AI (MCP)':
        'AI assistant (MCP)',
    "Un assistente AI (per esempio Claude Desktop) può preparare lo spettacolo per te: crea la scaletta da una cartella di file, aggiunge didascalie, scene e note per l'operatore. Lavora solo nelle cartelle che scegli, non suona niente e non cambia mai uno spettacolo in corso. Ai fornitori di AI arrivano i nomi delle cue, le note e i nomi dei file, non il contenuto dei file.":
        'An AI assistant (for example Claude Desktop) can prepare the show for you: it builds the cue list from a folder of files and adds captions, scenes and notes for the operator. It works only in the folders you choose, plays nothing and never changes a running show. The AI provider receives cue names, notes and file names, not the content of the files.',
    "1. Aggiungi l'assistente a Claude Desktop (una volta per computer):":
        '1. Add the assistant to Claude Desktop (once per computer):',
    'Aggiungi a Claude Desktop…':
        'Add to Claude Desktop…',
    "Crea il file dell'estensione e lo apre: Claude Desktop chiede quali cartelle l'assistente può usare.":
        'Makes the extension file and opens it: Claude Desktop asks which folders the assistant may use.',
    'Copia le impostazioni per altri programmi':
        'Copy the settings for other programs',
    'Impostazioni «mcpServers» (JSON) per Claude Code, Cursor e altri client MCP.':
        '"mcpServers" settings (JSON) for Claude Code, Cursor and other MCP clients.',
    "2. Se vuoi che l'assistente modifichi lo spettacolo aperto qui (si vede subito, Ctrl+Z annulla), permettilo:":
        '2. If the assistant should change the show open here (you see it at once, Ctrl+Z undoes), allow it:',
    "L'assistente AI può modificare lo spettacolo (solo nella preparazione)":
        'The AI assistant may change the show (only in Preparation)',
    "Modifiche dall'assistente…":
        'Changes from the assistant…',
    'Impossibile creare il file: {}':
        'The file cannot be made: {}',
    'Creato {}. Se Claude Desktop non si è aperto, trascina questo file nella sua finestra (Impostazioni → Estensioni).':
        'Made {}. If Claude Desktop did not open, drag this file into its window (Settings → Extensions).',
    "Creato {} e aperto: conferma l'installazione in Claude Desktop e scegli le cartelle.":
        'Made {} and opened it: confirm the installation in Claude Desktop and choose the folders.',
    'Impostazioni copiate (cartella: {}). Incollale nella configurazione del client MCP.':
        "Settings copied (folder: {}). Paste them into the MCP client's configuration.",
    'Partenza:':
        'Start:',
    'con il GO':
        'with GO',
    "dopo l'avvio di":
        'after the start of',
    'dopo la fine di':
        'after the end of',
    'prima della fine di':
        'before the end of',
    'Partenza della cue':
        'Start of the cue',
    "Con il GO: come sempre. Le altre scelte fanno partire questa cue da sola rispetto a un'altra (il GO la salta): N s dopo il suo avvio, N s dopo la sua fine, o N s prima della sua fine.":
        'With GO: as always. The other choices start this cue by itself relative to another one (GO skips it): N s after its start, N s after its end, or N s before its end.',
    'Cue di riferimento':
        'Reference cue',
    'Secondi rispetto alla cue di riferimento':
        'Seconds relative to the reference cue',
    "Non possibile: quella cue parte già da questa (si avvierebbero a vicenda all'infinito).":
        'Not possible: that cue already starts from this one (they would start each other forever).',
    "parte da sola rispetto a un'altra cue":
        'starts by itself relative to another cue',
    'Partenze relative fermate: le cue si avviano a vicenda in un ciclo':
        'Relative starts stopped: the cues start each other in a loop',
    '↪ Salta a una cue':
        '↪ Jump to a cue',
    '📞 Chiama una cue':
        '📞 Call a cue',
    '⏩ Sposta la riproduzione':
        '⏩ Move the playback',
    'Salto: avvia la cue scelta (il GO prosegue da lì) oppure la mette soltanto come prossimo GO. «Al massimo» limita le ripetizioni (per esempio una scena ripetuta due volte).':
        "Jump: starts the chosen cue (GO goes on from there) or only makes it the next GO. 'At most' limits the repeats (e.g. a scene played twice).",
    "Avvia la cue scelta senza spostare il GO, come un effetto. Le cue «solo su chiamata» sono fuori dall'ordine del GO.":
        "Starts the chosen cue without moving GO, like an effect. 'Call only' cues are outside the GO order.",
    'Sposta la riproduzione delle cue scelte che stanno suonando: a una posizione del file, avanti o indietro di N secondi, oppure a N secondi dalla fine.':
        'Moves the playback of the chosen cues that are playing: to a position in the file, N seconds forward or back, or to N seconds before the end.',
    'Cue del salto o della chiamata':
        'Cue of the jump or call',
    'Come:':
        'How:',
    'Avviala subito':
        'Start it now',
    'Solo come prossimo GO':
        'Only as the next GO',
    'sempre':
        'always',
    '0 = salta sempre; N = al massimo N volte, poi il GO prosegue':
        '0 = always jump; N = at most N times, then GO goes on',
    'Al massimo:':
        'At most:',
    'Dove:':
        'Where:',
    'Alla posizione':
        'To the position',
    'Avanti o indietro di':
        'Forward or back by',
    'A N secondi dalla fine':
        'To N seconds before the end',
    'Secondi:':
        'Seconds:',
    'Chiama: {}':
        'Call: {}',
    'Salta e avvia{}: {}':
        'Jump and start{}: {}',
    'Prossimo GO{}: {}':
        'Next GO{}: {}',
    ' (al massimo {}×)':
        ' (at most {}×)',
    'Vai a {} s: {}':
        'Go to {} s: {}',
    'Vai a {} s dalla fine: {}':
        'Go to {} s before the end: {}',
    'Sposta di {} s: {}':
        'Move by {} s: {}',
    'Salta a una cue':
        'Jump to a cue',
    'Chiama una cue':
        'Call a cue',
    'Sposta la riproduzione':
        'Move the playback',
    "Salto o chiamata senza una cue valida: '{}'":
        "Jump or call without a valid cue: '{}'",
    "Salto '{}' già fatto {} volte: il GO prosegue":
        "Jump '{}' done {} times already: GO goes on",
    'Chiamata: {}':
        'Called: {}',
    'Salto: {}':
        'Jump: {}',
    'Prossimo GO: {}':
        'Next GO: {}',
    "📞 Solo su chiamata (fuori dall'ordine del GO)":
        '📞 Call only (outside the GO order)',
    "La avvia soltanto un'azione «Chiama una cue» (o un salto); il GO la salta.":
        "Only a 'Call a cue' action (or a jump) starts it; GO skips it.",
    'Chiamata o salto da: {}':
        'Called or jumped to from: {}',
    'solo su chiamata':
        'call only',
    '⊘ ESCLUSA':
        '⊘ OFF',
    'Cue esclusa in questa versione: non parte':
        'Cue off in this version: it does not start',
    '⊘ Escludi / includi in questa versione':
        '⊘ Switch off / on in this version',
    '🎭 Versioni dello spettacolo':
        '🎭 Versions of the show',
    'Spettacolo completo':
        'Full show',
    'Salva come nuova versione…':
        'Save as a new version…',
    'Elimina la versione «{}»':
        "Delete the version '{}'",
    'Versione: {}':
        'Version: {}',
    'Nuova versione dello spettacolo':
        'New version of the show',
    'Nome della versione (per esempio «ridotta», «secondo cast»):':
        "Name of the version (e.g. 'short', 'second cast'):",
    '{} è usata da: {}':
        '{} is used by: {}',
    'Incluse {} cue':
        '{} cues on',
    'Escluse {} cue':
        '{} cues off',
    'Attenzione: ':
        'Careful: ',
    'Versione: {} · {} cue escluse':
        'Version: {} · {} cues off',
    'insieme':
        'together',
    'Nello spettacolo non si salta: usa la prova':
        'No jumping in the show: use the rehearsal',
    'opacità {}%':
        'opacity {}%',
    'Prova da {}.':
        'Rehearsal from {}.',
    'Prima di questa cue restano in onda:':
        'Before this cue these stay on:',
    'Prima di questa cue non resta niente in onda.':
        'Nothing stays on before this cue.',
    'Ora suona qualcosa: verrà fermato.':
        'Something plays now: it will be stopped.',
    'Prova da qui':
        'Rehearse from here',
    '▶ Prepara la scena':
        '▶ Set the scene',
    'Scena pronta: il prossimo GO è {}':
        'Scene ready: the next GO is {}',
    '⏯ Prova da qui (prepara la scena)':
        '⏯ Rehearse from here (set the scene)',
    'Conto alla rovescia':
        'Countdown',
    '⏳ Conto alla rovescia':
        '⏳ Countdown',
    '⏳ Conto alla rovescia…':
        '⏳ Countdown (interval)…',
    '🖥 Conto alla rovescia grande (quinte)':
        '🖥 Big countdown (backstage)',
    '⏹ Ferma il conto alla rovescia':
        '⏹ Stop the countdown',
    'Ferma il conto alla rovescia':
        'Stop the countdown',
    'Conto alla rovescia {}: {}':
        'Countdown {}: {}',
    'Intervallo':
        'Interval',
    "Minuti (per esempio l'intervallo):":
        'Minutes (e.g. the interval):',
    'Fine del conto alla rovescia: {}':
        'Countdown over: {}',
    'la volta scorsa a {}':
        'last time at {}',
    "Avvia un conto alla rovescia (per esempio l'intervallo) sulla barra di stato e nella finestra grande per le quinte (menu Show). Il testo è il titolo; 0 minuti lo ferma.":
        'Starts a countdown (e.g. the interval) on the status bar and in the big backstage window (Show menu). The text is the title; 0 minutes stops it.',
    'ferma':
        'stop',
    'Tempo rimanente':
        'Time left',
    'Piano orario sospeso':
        'Time plan on hold',
    'Piano orario attivo':
        'Time plan running',
    '(sospeso)':
        '(on hold)',
    "'{}' saltata: più di un minuto di ritardo sull'orario {}":
        "'{}' skipped: more than a minute after {}",
    'Alle {}: {}':
        'At {}: {}',
    '🕐 Piano orario anche nella prova':
        '🕐 Time plan in the rehearsal too',
    'Alle ore:':
        'At:',
    "2.6: la cue parte da sola a quest'ora durante lo spettacolo (il GO la salta). Più di un minuto in ritardo: saltata. Vuoto = con il GO.":
        'The cue starts by itself at this time during the show (GO skips it). More than a minute late: skipped. Empty = with GO.',
    'Ora di partenza della cue':
        'Start time of the cue',
    'parte alle {}':
        'starts at {}',
    'al segno di':
        'on the mark of',
    'Segno della cue di riferimento':
        'Mark of the reference cue',
    'Segni:':
        'Marks:',
    'Segni della cue':
        'Marks of the cue',
    'Elimina il segno scelto (non se una cue parte da lì)':
        'Delete the chosen mark (not when a cue starts from it)',
    "Quella cue non ha segni: mettine uno sulla sua forma d'onda (◆ Segno).":
        'That cue has no marks: put one on its waveform (◆ Mark).',
    '◆ Segno':
        '◆ Mark',
    'Mette un segno sulla testina (Ctrl+K: anche sulla cue in onda, per esempio battendo a tempo in prova). Una cue può partire «al segno».':
        "Puts a mark at the playhead (Ctrl+K: also on the cue playing, e.g. tapping in time in a rehearsal). A cue can start 'on the mark'.",
    'Segno: scegli una cue audio o video':
        'Mark: choose an audio or video cue',
    'Segno: nessuna posizione (fai partire la cue o sposta la testina)':
        'Mark: no position (start the cue or move the playhead)',
    'Segno ◆{} a {} s':
        'Mark ◆{} at {} s',
    'Il segno ◆{} è usato da {}: non si può eliminare':
        'Mark ◆{} is used by {}: it cannot be deleted',
    'Cerca: nome, Q, note, file…  (Invio: primo risultato, Esc: chiudi)':
        'Find: name, Q, notes, file…  (Enter: first match, Esc: close)',
    'Cerca nella scaletta':
        'Find in the list',
    'Cerca una cue':
        'Find a cue',
    'Nome, Q, note o file:':
        'Name, Q, notes or file:',
    'Trovate {} cue su {}':
        'Found {} of {} cues',
    "Nessuna cue trovata: '{}'":
        "No cue found: '{}'",
    "'{}' ha sezioni: le cue che partono sui suoi segni non partono":
        "'{}' has sections: cues starting on its marks will not start",
    'segni':
        'marks',
    '⌛ Attendi, poi la successiva':
        '⌛ Wait, then the next one',
    '▶ Riprendi':
        '▶ Resume',
    '⏱ Cronometro':
        '⏱ Stopwatch',
    "Un'attesa visibile nella scaletta: dopo i secondi indicati parte la cue successiva, senza GO. Pausa generale la trattiene, PANIC la annulla.":
        'A wait you can see in the list: after the given seconds the next cue starts, without GO. Pause All holds it, PANIC cancels it.',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano.':
        'Pauses the chosen cues that are playing (sound and video); the others go on.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate.':
        'Lets the chosen paused cues play on from where they stopped.',
    'Cronometro sulla barra di stato (per esempio la durata di un atto): avvia, ferma (si riprende da lì) o azzera. PANIC non lo tocca.':
        'A stopwatch on the status bar (for example how long an act takes): start, stop (it goes on from there) or reset. PANIC leaves it alone.',
    'Avvia':
        'Start',
    'Ferma':
        'Stop',
    'Azzera':
        'Reset',
    'Cronometro:':
        'Stopwatch:',
    'Cronometro':
        'Stopwatch',
    'Attendi {} s, poi la successiva':
        'Wait {} s, then the next one',
    'Cronometro: avvia':
        'Stopwatch: start',
    'Cronometro: ferma':
        'Stopwatch: stop',
    'Cronometro: azzera':
        'Stopwatch: reset',
    'Pausa: {}':
        'Pause: {}',
    'Riprendi: {}':
        'Resume: {}',
    'Attendi':
        'Wait',
    'Pausa':
        'Pause',
    'Riprendi':
        'Resume',
    'Partenza relativa persa (cue di riferimento eliminata): {} ora parte con il GO':
        'Relative start lost (its reference cue was deleted): {} now starts with GO',
    'Palco':
        'Stage',
    'Sala':
        'Hall',
    'Spie (ascolto palco)':
        'Foldback (stage monitors)',
    'Muto':
        'Mute',
    'uscita predefinita':
        'default output',
    "'{}': {} non disponibile, suona su: {}":
        "'{}': {} not available, plays on: {}",
    'Uscita:':
        'Output:',
    'Dove suona questa cue. Quale altoparlante è Palco, Sala o Spie su questo computer si sceglie in Dispositivi → Uscite audio. Muto: un video senza il suo audio.':
        'Where this cue plays. Which speakers are the Stage, the Hall or the Foldback on this computer is chosen in Show → Audio outputs. Mute: a video without its sound.',
    'Uscita audio della cue':
        'Audio output of the cue',
    'Uscite audio di questo computer':
        'Audio outputs of this computer',
    "Ogni cue suona su un'uscita: Palco, Sala o Spie (ascolto per gli attori). Qui si sceglie quale altoparlante è ognuna su questo computer; lo spettacolo non cambia su un altro computer.":
        'Every cue plays on one output: Stage, Hall or Foldback (for the performers). Here you choose which speakers each one is on this computer; the show does not change on another computer.',
    'Uscita':
        'Output',
    'Se manca':
        'If missing',
    'Regolazione':
        'Trim',
    '▶ Prova':
        '▶ Test',
    'Dispositivo: {}':
        'Device: {}',
    'Se manca: {}':
        'If missing: {}',
    'Regolazione: {}':
        'Trim: {}',
    'Prova: {}':
        'Test: {}',
    'Predefinito di sistema':
        'System default',
    '— non impostata —':
        '— not set —',
    'muto':
        'muted',
    'muto (nessun suono)':
        'muted (no sound)',
    'Durante lo spettacolo le uscite non si cambiano e non si provano.':
        'During the show the outputs are not changed or tested.',
    '▶ Prova tutte in ordine':
        '▶ Test them all in turn',
    'Esporta…':
        'Export…',
    'Importa…':
        'Import…',
    'Esporta le uscite audio':
        'Export the audio outputs',
    'Importa le uscite audio':
        'Import the audio outputs',
    'Esportato: {}':
        'Exported: {}',
    'Non è una mappa di uscite audio: {}':
        'This is not an audio output map: {}',
    'Uscita predefinita':
        'Default output',
    'Come il Palco':
        'Like the Stage',
    '🔊 Uscite audio (Palco / Sala / Spie)…':
        '🔊 Audio outputs (Stage / Hall / Foldback)…',
    'Uscite audio: {}':
        'Audio outputs: {}',
    'Uscite audio non impostate o scollegate: {}':
        'Audio outputs not set or unplugged: {}',
    'Uscite audio…':
        'Audio outputs…',
    'Dispositivo':
        'Device',
    'Playlist ({} brani)':
        'Playlist ({} tracks)',
    'Playlist':
        'Playlist',
    "{} file audio: farne una playlist (una riga che li suona uno dopo l'altro)?":
        '{} audio files: make them a playlist (one row that plays them one after another)?',
    'Una playlist':
        'One playlist',
    'Cue separate':
        'Separate cues',
    'Playlist non leggibile: {}':
        'Cannot read the playlist: {}',
    "Playlist '{}': {} brani":
        "Playlist '{}': {} tracks",
    'non trovati o in streaming: {}':
        'not found or streams: {}',
    'Importa playlist':
        'Import a playlist',
    '🎵 Importa playlist (.m3u)…':
        '🎵 Import a playlist (.m3u)…',
    '{} non collegato ({}): suona su {}':
        '{} not connected ({}): plays on {}',
    'lo stesso dispositivo del pubblico':
        'the same device as the audience',
    'Le spie usano lo stesso dispositivo del pubblico: la traccia privata si sente in sala.':
        "The foldback uses the audience's device: the private track will be heard in the hall.",
    'Qualcosa suona: la prova non parte.':
        'Something is playing: no test.',
    'Sostituire le uscite audio di questo computer con quelle del file?':
        'Replace the audio outputs of this computer with the ones in the file?',
    'uscite audio':
        'audio outputs',
    'Addormenta in {} s: {}':
        'Put to sleep in {} s: {}',
    'Risveglia in {} s: {}':
        'Wake up in {} s: {}',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano. Con una durata la musica si addormenta: sfuma e poi si ferma.':
        'Pauses the chosen cues that are playing (sound and video); the others go on. With a duration the music goes to sleep: it fades out, then stops.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate. Con una durata la musica si risveglia: entra piano fino al livello di prima.':
        'Lets the chosen paused cues play on from where they stopped. With a duration the music wakes up: it fades in to the level it had.',
    "Taglia il silenzio all'inizio e alla fine: IN e OUT dove il suono comincia e finisce davvero (sotto -40 dB rispetto al picco).":
        'Cut the silence at the start and the end: IN and OUT where the sound really starts and ends (below -40 dB from the peak).',
    "Taglia il silenzio all'inizio e alla fine":
        'Cut the silence at the start and the end',
    "Taglia il silenzio: forma d'onda non ancora pronta o file muto":
        'Cut the silence: the waveform is not ready yet or the file is silent',
    'Silenzio tagliato (sotto {} dB): IN {} s, OUT {}':
        'Silence cut (below {} dB): IN {} s, OUT {}',
    'Una playlist non può stare dentro una scena: aggiunte cue separate':
        'A playlist cannot be inside a scene: separate cues added',
    'Dissolvenza:':
        'Fade:',
    'subito':
        'at once',
    '0 = subito; più secondi = la musica si addormenta / si risveglia piano':
        '0 = at once; more seconds = the music goes to sleep / wakes up slowly',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano. Con una dissolvenza la musica si addormenta: sfuma e poi si ferma.':
        'Pauses the chosen cues that are playing (sound and video); the others go on. With a fade the music goes to sleep: it fades out, then stops.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate. Con una dissolvenza la musica si risveglia: entra piano fino al livello di prima.':
        'Lets the chosen paused cues play on from where they stopped. With a fade the music wakes up: it fades in to the level it had.',
    'Tempo:':
        'Tempo:',
    'Velocità di riproduzione: 100 % = come registrato (per adattare la musica a una coreografia).':
        'Playback speed: 100 % = as recorded (to fit the music to a choreography).',
    'Tempo della cue in percento':
        'Tempo of the cue in percent',
    "Mantieni l'intonazione":
        'Keep the pitch',
    "Più veloce o più lento senza cambiare l'altezza delle note.":
        'Faster or slower without changing the pitch of the notes.',
    "📋 Copia il layout dell'immagine":
        '📋 Copy the picture layout',
    '📌 Incolla il layout sulle selezionate':
        '📌 Paste the layout onto the selected',
    "Layout: scegli un'immagine o un video":
        'Layout: choose a picture or a video',
    "Layout copiato da '{}'":
        "Layout copied from '{}'",
    "Prima copia il layout di un'immagine o di un video":
        'First copy the layout of a picture or a video',
    'Layout incollato su {} cue':
        'Layout pasted onto {} cues',
    '🎞 Foto con questa musica':
        '🎞 Photos to this music',
    'Foto con musica: seleziona almeno due immagini e un solo audio':
        'Photos to music: select at least two pictures and one sound',
    'Foto con musica: non dentro una scena':
        'Photos to music: not inside a scene',
    "Foto con musica: durata di '{}' sconosciuta":
        "Photos to music: the length of '{}' is not known",
    'Foto: {}':
        'Photos: {}',
    "Foto con musica: {} immagini da {} s su '{}' ({} s)":
        "Photos to music: {} pictures of {} s to '{}' ({} s)",
    "Foto con musica: '{}' ha un loop o sezioni":
        "Photos to music: '{}' has a loop or sections",
    'Foto con musica: troppe immagini (almeno 1 s ciascuna)':
        'Photos to music: too many pictures (at least 1 s each)',
    'Copione:':
        'Script:',
    'pag.':
        'p.',
    'Pagina del copione':
        'Page of the script',
    'Battuta su cui parte…':
        'The line it comes on…',
    'Battuta su cui parte la cue':
        'The line the cue comes on',
    '📄 Esporta la scaletta (CSV)…':
        '📄 Export the cue list (CSV)…',
    '🖨 Stampa la scaletta per la regia…':
        '🖨 Print the cue list for the operator…',
    '🖨 Stampa la scaletta per il suggeritore…':
        '🖨 Print the cue list for the prompter…',
    'Tipo':
        'Type',
    'Layer':
        'Layer',
    'Pagina':
        'Page',
    'Battuta':
        'Line',
    'File':
        'File',
    'Esporta la scaletta':
        'Export the cue list',
    'Scaletta esportata: {}':
        'Cue list exported: {}',
    'regia':
        'operator',
    'suggeritore':
        'prompter',
    'Spettacolo':
        'Show',
    'Stampa con Ctrl+P (orizzontale per molte colonne).':
        'Print with Ctrl+P (landscape for many columns).',
    'Scaletta aperta nel browser: stampa con Ctrl+P':
        'Cue list opened in the browser: print with Ctrl+P',
    'Rinumera le Q':
        'Renumber the Q',
    '🔢 Rinumera le Q…':
        '🔢 Renumber the Q…',
    'Le cue selezionate lanciate con GO ({})':
        'The selected cues started by GO ({})',
    'Tutte le cue lanciate con GO ({})':
        'All the cues started by GO ({})',
    'Prefisso:':
        'Prefix:',
    'Primo numero:':
        'First number:',
    'Passo:':
        'Step:',
    'Passo 10 lascia spazio per le cue aggiunte dopo (Q10, Q15, Q20)':
        'A step of 10 leaves room for cues added later (Q10, Q15, Q20)',
    'Prima':
        'Before',
    'Dopo':
        'After',
    'Q rinumerate: {}':
        'Q renumbered: {}',
    '📥 Importa cue da un altro spettacolo…':
        '📥 Import cues from another show…',
    'Importa cue da un altro spettacolo':
        'Import cues from another show',
    'Spunta le cue da importare (una scena porta le sue cue):':
        'Tick the cues to import (a scene brings its cues):',
    "'{}': partenza relativa a una cue non importata – parte con il GO":
        "'{}': start relative to a cue not imported – it starts with GO",
    "'{}': {} cue bersaglio non importate":
        "'{}': {} target cues not imported",
    "'{}': file non trovato":
        "'{}': file not found",
    "Importate {} cue da '{}'":
        "Imported {} cues from '{}'",
    'Esclusa':
        'Off',
    '⚠ Già usate da altre cue: {} – due cue avrebbero la stessa Q':
        '⚠ Already used by other cues: {} – two cues would have the same Q',
    "'{}': legata a una cue non importata (Simult. / Auto-GO) – ora parte con il GO":
        "'{}': tied to a cue not imported (Simult. / Auto-GO) – it now starts with GO",
    "'{}': era esclusa in quello spettacolo – qui è inclusa":
        "'{}': it was switched off in that show – here it is on",
    "'{}': il suo tasto è già usato da un effetto di questo spettacolo":
        "'{}': its key is already used by an effect of this show",
    "'{}': parte a un'ora del giorno":
        "'{}': it starts at a time of day",
    "'{}': parte solo da un'azione, che non è stata importata":
        "'{}': only an action starts it, and that action was not imported",
    '… e altre {}':
        '… and {} more',
    '🔢 Identifica':
        '🔢 Identify',
    "Mostra per qualche secondo un grande numero su ogni schermo (lo stesso numero dell'elenco)":
        'Shows a big number on every screen for a few seconds (the same number as in the list)',
    'Identifica gli schermi':
        'Identify the screens',
    'Qualcosa è in onda: il numero coprirebbe il proiettore davanti al pubblico. Riprova quando nulla è in onda.':
        'Something is on air: the number would cover the projector in front of the audience. Try again when nothing is on air.',
    'Regia':
        'Director',
    'Proiettore / esterno':
        'Projector / external',
    'Schermo {}':
        'Screen {}',
    "parte dopo una cue che non c'è più":
        'starts after a cue that is no longer there',
    'le sue cue bersaglio non ci sono più: non fa nulla':
        'its target cues are gone: it does nothing',
    "salta o chiama una cue che non c'è":
        'jumps to or calls a cue that is not there',
    'scena senza nulla da suonare':
        'a scene with nothing to play',
    'parte solo se chiamata, ma nessuna azione la chiama':
        'starts only when called, but no action calls it',
    'Da sistemare nella lista ({}): {}':
        'To fix in the list ({}): {}',
    "Cue a un'ora del giorno: {} – l'orologio del computer segna {}. È giusto?":
        'Cues at a time of day: {} – the computer clock says {}. Is that right?',
    'Poco spazio libero sul disco dello spettacolo: {} MB – il salvataggio può non riuscire':
        "Little free space on the show's disk: {} MB – saving may fail",
    'ℹ Informazioni sullo spettacolo…':
        'ℹ Show info…',
    'Informazioni sullo spettacolo':
        'Show info',
    'Titolo:':
        'Title:',
    'Autore / regia:':
        'Author / director:',
    'Note:':
        'Notes:',
    'Cue: {} · GO: {} · video {} · audio {} · immagini {} · testi {} · scene {} · azioni {} · effetti {} · escluse {} · file mancanti {}':
        'Cues: {} · GO: {} · video {} · audio {} · pictures {} · captions {} · scenes {} · actions {} · effects {} · switched off {} · missing files {}',
    'Informazioni sullo spettacolo salvate con lo spettacolo':
        'The info is saved with the show',
    '⌨ Tasti e telecomando di presentazione…':
        '⌨ Keys and presenter remote…',
    'Tasti e telecomando di presentazione':
        'Keys and presenter remote',
    'Tasti in più per questo computer, attivi nella prova e nello spettacolo. I tasti del programma restano (Spazio = GO, Esc due volte = PANIC). Un telecomando di presentazione funziona come una tastiera: premi i suoi pulsanti qui sotto.':
        "Extra keys for this computer, active in the rehearsal and the show. The program's keys stay (Space = GO, Esc twice = PANIC). A presenter remote works like a keyboard: press its buttons below.",
    'Funzione':
        'Function',
    'Tasti':
        'Keys',
    'Aggiungi un tasto…':
        'Add a key…',
    'Togli':
        'Remove',
    '🎯 Procedura guidata del telecomando…':
        '🎯 Remote wizard…',
    'Telecomando di presentazione (tasti tipici)':
        'Presenter remote (usual keys)',
    'Predefiniti (nessun tasto in più)':
        'Defaults (no extra keys)',
    'Premi un tasto':
        'Press a key',
    'Interrompi':
        'Stop',
    'Premi il tasto o il pulsante del telecomando per: {}':
        "Press the key or the remote's button for: {}",
    'Premi sul telecomando il pulsante per: {}':
        "Press the remote's button for: {}",
    '⚠ {}: il programma lo usa già ({})':
        '⚠ {}: the program already uses it ({})',
    '⚠ {}: assegnato a due funzioni – vale la prima':
        '⚠ {}: given to two functions – the first one counts',
    "⚠ {}: è il tasto di un effetto di questo spettacolo – vale l'effetto":
        '⚠ {}: it is the key of an effect of this show – the effect counts',
    'Tasti aggiuntivi salvati per questo computer':
        'Extra keys saved for this computer',
    'Cue precedente (solo selezione)':
        'Previous cue (selection only)',
    'Cue successiva (solo selezione)':
        'Next cue (selection only)',
    'Pausa tutto / riprendi':
        'Pause all / resume',
    'Sfuma tutto':
        'Fade all',
    'PANIC (2×)':
        'PANIC (2×)',
    'Selezione':
        'Selection',
    'Punto IN':
        'IN point',
    'Punto OUT':
        'OUT point',
    'Elimina':
        'Delete',
    '📁 Nuovo spettacolo da una cartella…':
        '📁 New show from a folder…',
    '📋 Importa una scaletta (CSV)…':
        '📋 Import a cue list (CSV)…',
    'Nuovo spettacolo da una cartella':
        'New show from a folder',
    'Nella cartella non ci sono video, suoni o immagini.':
        'The folder has no videos, sounds or pictures.',
    '{} file in ordine di nome. Come aggiungerli?':
        '{} files in name order. How should they be added?',
    'Una scena (un GO per elemento)':
        'One scene (one GO per item)',
    "Nuovo spettacolo: {} file da '{}'":
        "New show: {} files from '{}'",
    'Importa una scaletta (CSV)':
        'Import a cue list (CSV)',
    'Il file non è una scaletta: serve una prima riga con i nomi delle colonne (almeno Nome o File).':
        'The file is not a cue list: the first line must name the columns (at least Name or File).',
    'Nessuna riga da importare':
        'No rows to import',
    "Importate {} righe da '{}'":
        "Imported {} rows from '{}'",
    'senza file (da collegare): {}':
        'without a file (to attach): {}',
    'Salva prima lo spettacolo, poi fissalo':
        'Save the show first, then pin it',
    "Spettacolo fissato in 'Apri recenti'":
        "Show pinned in 'Open recent'",
    'Spettacolo non più fissato':
        'Show unpinned',
    '📌 Non fissare più questo spettacolo':
        '📌 Unpin this show',
    '📌 Fissa questo spettacolo in cima':
        '📌 Pin this show on top',
    '📂 Scegli il file…':
        '📂 Choose the file…',
    '🔎 Cerca i file mancanti in una cartella…':
        '🔎 Find missing files in a folder…',
    '🔎 Cerca in una cartella…':
        '🔎 Look in a folder…',
    'Cerca i file mancanti in una cartella':
        'Find missing files in a folder',
    'Tutti i file sono al loro posto':
        'All files are in place',
    'Cue senza file: {} – clic destro → Scegli il file…':
        'Cues without a file: {} – right click → Choose the file…',
    'Nessuno dei {} file mancanti è in questa cartella.':
        'None of the {} missing files is in this folder.',
    'File ritrovati: {} di {}':
        'Files found: {} of {}',
    'Nomi trovati più volte (usato il primo): {}':
        'Names found more than once (the first one is used): {}',
    'Scegli una cue video, audio o immagine':
        'Choose a video, sound or picture cue',
    "Scegli il file per '{}'":
        "Choose the file for '{}'",
    'Formato non supportato: {}':
        'Format not supported: {}',
    "'{}' suona ora: {}":
        "'{}' now plays: {}",
    '🕘 Storia delle modifiche…':
        '🕘 History of changes…',
    '🕘 Ripristina una copia di sicurezza…':
        '🕘 Restore a backup…',
    'Storia delle modifiche':
        'History of changes',
    'Le modifiche che Ctrl+Z può annullare, la più recente in alto:':
        'The changes Ctrl+Z can take back, the newest on top:',
    'Nessuna modifica da annullare':
        'No changes to undo',
    '↶ Annulla fino a qui (compresa)':
        '↶ Undo back to here (this one too)',
    'Annullate {} modifiche (Ctrl+Y le ripete)':
        '{} changes undone (Ctrl+Y redoes them)',
    'Aggiunte {} cue ({}…)':
        '{} cues added ({}…)',
    'Aggiunta {}':
        'Added {}',
    'Eliminate {} cue ({}…)':
        '{} cues deleted ({}…)',
    'Eliminata {}':
        'Deleted {}',
    'Cue sostituite ({}…)':
        'Cues replaced ({}…)',
    'Ordine cambiato ({}…)':
        'Order changed ({}…)',
    '{}: {} campi ({})':
        '{}: {} fields ({})',
    '{} cue cambiate: {}':
        '{} cues changed: {}',
    '{} cue cambiate':
        '{} cues changed',
    'Nessuna differenza nella lista':
        'No difference in the list',
    'Ripristina una copia di sicurezza':
        'Restore a backup',
    'Lo spettacolo non è ancora salvato: non ha copie di sicurezza':
        'The show is not saved yet: it has no backups',
    'Ancora nessuna copia: il programma ne fa una a ogni salvataggio.':
        'No copy yet: the program makes one at every save.',
    "La scaletta com'era al salvataggio delle:":
        'The cue list as it was when saved at:',
    'Scaletta ripristinata dalla copia delle {} (Ctrl+Z torna indietro)':
        'Cue list restored from the copy of {} (Ctrl+Z goes back)',
    'layer':
        'layer',
    'inclusa':
        'on',
    'scena':
        'scene',
    'modo della scena':
        'scene mode',
    'colore':
        'colour',
    'dissolvenza':
        'crossfade',
    'tempo':
        'tempo',
    'pagina':
        'page',
    'battuta':
        'line',
    'tasto':
        'key',
    'effetto':
        'effect',
    'ora':
        'time',
    'azione':
        'action',
    'testo':
        'text',
    'marcatori':
        'markers',
    'uscita audio':
        'audio output',
    'Scena':
        'Scene',
    '{} file: farne una scena (un GO per elemento)?':
        '{} files: make them one scene (one GO per item)?',
    'Una scena':
        'One scene',
    'Scena ({} elementi)':
        'Scene ({} items)',
    '❚❚  Pausa':
        '❚❚  Pause',
    '❚❚  PAUSA TUTTO':
        '❚❚  PAUSE ALL',
    '❚❚ SHOW IN PAUSA':
        '❚❚ SHOW PAUSED',
    '❚❚ Metti in Pausa (Prove)':
        '❚❚ Pause (Rehearsals)',
    '❚❚ TRACCIA AUDIO IN STANDBY':
        '❚❚ AUDIO TRACK IN STANDBY',
    '❚❚ PAUSA':
        '❚❚ PAUSED',
    '❚❚ Sospendi il piano orario':
        '❚❚ Hold the time plan',
    '❚❚ Pausa':
        '❚❚ Pause',
    "Annulla l'ultimo GO":
        'Undo the last GO',
    '❚❚ &Pausa / riprendi tutto':
        '❚❚ &Pause / resume all',
    'Sfuma la scena':
        'Fade the scene',
    'Sfuma e ferma tutto ciò che la scena suona o mostra; il GO va dopo la scena':
        'Fades and stops everything the scene plays or shows; GO moves past the scene',
    '⏬ Sfuma la scena':
        '⏬ Fade the scene',
    'Tempo del pulsante Sfuma':
        'Fade button time',
    'Secondi di «Sfuma» su una scheda o una scena (vale il Fade Out della cue, se ne ha uno):':
        "Seconds of “Fade” on a card or a scene (the cue's own fade-out wins when it has one):",
    '«Sfuma» dura ora {} s':
        '“Fade” now takes {} s',
    '⏬ Tempo del pulsante Sfuma…':
        '⏬ Fade button time…',
    "Scena '{}' in dissolvenza":
        "Scene '{}' fading out",
    "Dissolvenza incrociata: ciò che c'è ora sul layer di questo cue (immagine o suono) sfuma mentre questo cue entra, nel tempo indicato (0 = stacco netto).":
        "Crossfade: what is now on this cue's layer (picture or sound) fades while this cue comes in, over this time (0 = a cut).",
    '＋ Aggiungi file…':
        '＋ Add files…',
    'Video, suoni e immagini – anche più file insieme (o trascinali sulla lista)':
        'Videos, sounds and pictures – several at once too (or drag them onto the list)',
    'Aggiungi file':
        'Add files',
    'Aggiungi video':
        'Add a video',
    'Aggiungi audio':
        'Add a sound',
    'Aggiungi immagine':
        'Add a picture',
    'Video, suoni e immagini':
        'Videos, sounds and pictures',
    'Modifica cue':
        'Edit cue',
    'Dati della cue':
        'Cue',
    "Che cosa fa l'azione si sceglie nel pannello a destra (scheda «⚡ Azione»).":
        'What the action does is chosen in the panel on the right (tab “⚡ Action”).',
    'Come suona la scena':
        'How the scene plays',
    "Il file non c'è":
        'The file is missing',
    "Il file non c'è: scegline un altro con il menu della cue.":
        "The file is missing: choose another in the cue's menu (right click).",
    'Suono':
        'Sound',
    'Film':
        'Video',
    "Forma d'onda: trascina l'inizio e la fine":
        'Waveform: drag the start and the end',
    "Forma d'onda in caricamento…":
        'Loading the waveform…',
    '▶ Ascolta':
        '▶ Listen',
    "Ascolta dall'inizio scelto (in cuffia, se è scelta)":
        'Listen from the chosen start (in the headphones, if chosen)',
    '⇤ Inizio qui':
        '⇤ Start here',
    "L'inizio va dove si trova ora la riproduzione":
        'The start goes where the playback is now',
    'Fine qui ⇥':
        'End here ⇥',
    'La fine va dove si trova ora la riproduzione':
        'The end goes where the playback is now',
    'fine del file':
        'end of the file',
    '↺ Tutto il file':
        '↺ Whole file',
    'In loop':
        'Loop',
    'Immagine':
        'Picture',
    'Tempo sullo schermo':
        'Time on screen',
    'Dimensione':
        'Size',
    'Posizione':
        'Position',
    '✏ Cambia il testo…':
        '✏ Change the text…',
    'Passaggi':
        'Transitions',
    "La fine deve stare dopo l'inizio":
        'The end must come after the start',
    'Scegli prima una cue nella lista':
        'Choose a cue in the list first',
    "'{}' modificata":
        "'{}' changed",
    '✏ Modifica…':
        '✏ Edit…',
    'Modifica la cue scelta: inizio e fine, volume, passaggi (anche doppio clic o Invio)':
        'Edit the chosen cue: start and end, volume, transitions (also a double-click or Enter)',
    'Modifica la cue':
        'Edit the cue',
    'Tappo (quando non va niente)':
        'Cover (when nothing plays)',
    '⬛ Nero':
        '⬛ Black',
    '🖼 Immagine o logo…':
        '🖼 Picture or logo…',
    '🎞 Video in loop (senza suono)…':
        '🎞 Looping video (no sound)…',
    '▦ Schema di prova (solo in preparazione)':
        '▦ Test pattern (Preparation only)',
    'Tappo: nero':
        'Cover: black',
    'Tappo: schema di prova (solo in preparazione)':
        'Cover: test pattern (Preparation only)',
    'Tappo: {}':
        'Cover: {}',
    'File non valido':
        'Invalid file',
    'Impossibile usare questo file come tappo.':
        'This file cannot be used as the cover.',
    'Immagine del tappo':
        'Cover picture',
    'Video del tappo':
        'Cover video',
    'Tutti i file':
        'All files',
    'Tappo (L0): nero':
        'Cover (L0): black',
    'Tappo (L0): schema di prova (solo in preparazione)':
        'Cover (L0): test pattern (Preparation only)',
    'Tappo (L0): 🎞 {} (in loop)':
        'Cover (L0): 🎞 {} (loop)',
    'Tappo (L0): {}':
        'Cover (L0): {}',
    "Che cosa mostra il proiettore quando non va niente: nero, un'immagine o un logo, un video in loop":
        'What the projector shows when nothing plays: black, a picture or logo, a looping video',
    'Tappo nero (predefinito)':
        'Black cover (default)',
    '📥 Importa':
        '📥 Import',
    '🖨 Esporta e stampa':
        '🖨 Export and print',
    '🛟 Copie e file mancanti':
        '🛟 Backups and missing files',
    '🔌 Dispositivi':
        '🔌 Devices',
    '⚙ Impostazioni dello spettacolo':
        '⚙ Running settings',
    '⏳ Tempo':
        '⏳ Time',
    '🤖 Assistente AI':
        '🤖 AI assistant',
    '🔀 Dissolvenza incrociata per le selezionate…':
        '🔀 Crossfade for the selected…',
    'Dissolvenza incrociata':
        'Crossfade',
    'Secondi di dissolvenza incrociata (0 = taglio):':
        'Crossfade seconds (0 = cut):',
    "Dissolvenza incrociata: seleziona almeno un'immagine":
        'Crossfade: select at least one picture',
    'Dissolvenza incrociata di {} s su {} immagini':
        'Crossfade of {} s on {} pictures',
    '💻 Impostazioni di questo computer':
        '💻 Settings of this computer',
    '💾 Salva in un file…':
        '💾 Save to a file…',
    '📂 Carica da un file…':
        '📂 Load from a file…',
    'Impostazioni':
        'Settings',
    'Salva le impostazioni di questo computer':
        'Save the settings of this computer',
    'Impostazioni di questo computer':
        'Settings of this computer',
    'Impostazioni salvate ({} valori): {}':
        'Settings saved ({} values): {}',
    'Le impostazioni si caricano nella preparazione, non durante lo spettacolo':
        'Settings are loaded in Preparation, not during the show',
    'Carica le impostazioni di un altro computer':
        'Load the settings of another computer',
    'Impossibile caricare il file: {}':
        'Cannot load the file: {}',
    'non è un file di impostazioni di BlindCue':
        'it is not a settings file of the program',
    'il file viene da una versione più nuova del programma':
        'the file comes from a newer version of the program',
    'il file non contiene impostazioni':
        'the file holds no settings',
    'Il file ha le stesse impostazioni di questo computer.':
        'The file has the same settings as this computer.',
    'Cambiare queste impostazioni di questo computer?\n\n{}\n\nAlcune valgono dopo il riavvio del programma.':
        'Change these settings of this computer?\n\n{}\n\nSome take effect after the program restarts.',
    'Caricate {} impostazioni: riavvia il programma perché valgano tutte':
        '{} settings loaded: restart the program so that all of them take effect',
    'Audio: altoparlanti e uscite':
        'Sound: speakers and outputs',
    'Schermi e proiettore':
        'Screens and projector',
    'Tasti e telecomando':
        'Keys and remote',
    'Aspetto, lingua, suoni per la regia':
        'Look, language, operator sounds',
    'Conduzione dello spettacolo':
        'Running the show',
    "Per aprire '{}' termina prima lo spettacolo":
        "To open '{}', end the show first",
    '🛠 Il file':
        '🛠 The file',
    '📂 Mostra nella cartella':
        '📂 Show in its folder',
    '✎ Apri con il programma predefinito':
        '✎ Open with the default program',
    '✎ Apri con {}':
        '✎ Open with {}',
    '➕ Aggiungi un programma…':
        '➕ Add a program…',
    'il programma predefinito':
        'the default program',
    "'{}' aperto con {}: quando torni qui le modifiche si vedono subito":
        "'{}' opened with {}: when you come back here the changes show at once",
    "Impossibile aprire '{}' con {}":
        "Cannot open '{}' with {}",
    'Scegli un programma':
        'Choose a program',
    'Programmi':
        'Programs',
    'Programma aggiunto: {}':
        'Program added: {}',
    "'{}' è cambiato: forma d'onda e durata aggiornate":
        "'{}' changed: waveform and length read again",
    'Spettacolo di prova':
        'Practice show',
    '🎓 Spettacolo di prova':
        '🎓 Practice show',
    'Impossibile preparare lo spettacolo di prova: {}':
        'Cannot prepare the practice show: {}',
    'Spettacolo di prova pronto: entra nella Prova (Maiusc+F5) e premi Spazio':
        'Practice show ready: enter the Rehearsal (Shift+F5) and press Space',
    'Benvenuto':
        'Welcome',
    'Questo è lo spettacolo di prova. Premi la barra spaziatrice (GO) per passare alla cue successiva. Le note come questa le vedi solo tu, mai il pubblico.':
        'This is the practice show. Press the space bar (GO) to move to the next cue. Notes like this one are only for you, never for the audience.',
    "Musica d'apertura":
        'Opening music',
    'Sfondo: il bosco':
        'Backdrop: the forest',
    'Atto I – Nel bosco':
        'Act I – In the forest',
    'Campanello (tasto D)':
        'Bell (key D)',
    'Il sipario si apre':
        'The curtain opens',
    'Scena: il castello':
        'Scene: the castle',
    'Sfondo: il castello':
        'Backdrop: the castle',
    'Atto II – Il castello':
        'Act II – The castle',
    'Temporale':
        'Storm',
    'Pagina iniziale':
        'Start page',
    '🏠 Pagina iniziale':
        '🏠 Start page',
    'Che cosa vuoi fare?':
        'What do you want to do?',
    '＋ Nuovo spettacolo':
        '＋ New show',
    '📁 Nuovo spettacolo da una cartella di file…':
        '📁 New show from a folder of files…',
    '🎓 Spettacolo di prova (per imparare)':
        '🎓 Practice show (to learn)',
    '📂 Apri uno spettacolo…':
        '📂 Open a show…',
    'Aperti di recente':
        'Opened recently',
    'Primi passi':
        'First steps',
    'Suono: scegli gli altoparlanti e prova se si sentono.':
        'Sound: choose the speakers and check that you hear them.',
    '🔊 Altoparlanti e uscite…':
        '🔊 Speakers and outputs…',
    'Proiettore: collegalo e controlla quale schermo è quale.':
        'Projector: connect it and check which screen is which.',
    '🔢 Mostra i numeri degli schermi':
        '🔢 Show the screen numbers',
    '🖥 Scegli il proiettore…':
        '🖥 Choose the projector…',
    'File: aggiungi video, suoni e immagini (o trascinali sulla lista).':
        'Files: add videos, sounds and pictures (or drag them onto the list).',
    'GO: entra nella Prova (Maiusc+F5) e premi la barra spaziatrice. Esc due volte = PANIC.':
        'GO: enter the Rehearsal (Shift+F5) and press the space bar. Esc twice = PANIC.',
    '📖 Manuale (F1)':
        '📖 Manual (F1)',
    "Mostra questa pagina all'avvio":
        'Show this page at start',
    'Vai alla scaletta →':
        'Go to the cue list →',
    '🖨 Promemoria da stampare':
        '🖨 Cheat sheet to print',
    'Promemoria da stampare':
        'Cheat sheet to print',
    'promemoria':
        'cheat sheet',
    'Spazio':
        'Space',
    'GO – la cue successiva':
        'GO – the next cue',
    'Esc due volte (entro 0,6 s)':
        'Esc twice (within 0.6 s)',
    'PANIC – ferma subito tutto':
        'PANIC – stops everything at once',
    'Maiusc+Esc':
        'Shift+Esc',
    'Sfuma tutto (dolcemente)':
        'Fade out everything (gently)',
    'Blackout: il tappo sul proiettore':
        'Blackout: the cover on the projector',
    'Scegli la prossima cue':
        'Choose the next cue',
    'Ctrl+Spazio':
        'Ctrl+Space',
    'GO forzato (anche se una cue esclusiva sta suonando)':
        'Forced GO (even while an exclusive cue plays)',
    'Maiusc+F5':
        'Shift+F5',
    'Prova':
        'Rehearsal',
    'Tieni premuto «Preparazione» 1,5 s':
        'Hold «Preparation» for 1.5 s',
    'Esci dallo spettacolo':
        'Leave the show',
    'Durante lo spettacolo':
        'During the show',
    'Effetti di questo spettacolo':
        'Effects of this show',
    'Tasti aggiuntivi di questo computer':
        'Extra keys of this computer',
    'Se qualcosa non va':
        'When something does not work',
    "Non si sente niente: guarda il volume in alto (e «Silenzia»), poi l'amplificatore e i cavi; nella pagina «Prima dello spettacolo» c'è il tono di prova.":
        'Nothing can be heard: check the volume at the top (and «Mute»), then the amplifier and the cables; the «Before the show» page has a test tone.',
    "Sul proiettore non c'è niente o c'è il desktop: Win+P → «Estendi», poi Dispositivi → scegli il proiettore.":
        'Nothing on the projector, or the desktop: Win+P → «Extend», then Devices → choose the projector.',
    'Lo Spazio non fa niente: clicca nella finestra del programma (la striscia rossa dice che la tastiera è altrove).':
        "Space does nothing: click into the program's window (the red strip says the keyboard is elsewhere).",
    'Suona qualcosa che non deve: «Sfuma» sulla sua scheda, Maiusc+Esc per tutto, Esc due volte solo in emergenza.':
        'Something plays that should not: «Fade» on its card, Shift+Esc for everything, Esc twice only in an emergency.',
    'Il programma si è chiuso: riaprilo e scegli «Riprendi: la successiva».':
        'The program closed: open it again and choose «Resume: the next one».',
    'Stampa con Ctrl+P e tienila accanto al portatile.':
        'Print it with Ctrl+P and keep it next to the laptop.',
    'Promemoria aperto nel browser: stampalo con Ctrl+P':
        'Cheat sheet opened in the browser: print it with Ctrl+P',
    'automatico':
        'automatic',
    'Effetto':
        'Effect',
    'Fine dello spettacolo':
        'End of the show',
    'Durata':
        'Length',
    'GO a mano':
        'GO by hand',
    'Partenze automatiche':
        'Automatic starts',
    'Effetti':
        'Effects',
    'Pause':
        'Pauses',
    'GO annullati':
        'GOs undone',
    'Rapporto dello spettacolo':
        'Show report',
    'In breve':
        'In short',
    'Che cosa è successo':
        'What happened',
    'Cue con GO mai partite':
        'Cues with a GO that never played',
    "📋 Rapporto dell'ultimo spettacolo":
        '📋 Report of the last show',
    'Nessun rapporto: si scrive alla fine dello spettacolo (non della prova)':
        'No report yet: it is written when a show ends (not a rehearsal)',
    'Creato {}. In Claude Desktop: Impostazioni → Estensioni (o «App desktop» → Estensioni → Gestisci) → Impostazioni avanzate → «Installa estensione…» e scegli questo file, poi indica le cartelle. Se non funziona: «Copia le impostazioni per altri programmi» e in Claude Desktop Impostazioni → Sviluppatore → Modifica configurazione.':
        'Created {}. In Claude Desktop: Settings → Extensions (or «Desktop app» → Extensions → Manage) → Advanced settings → «Install Extension…» and choose this file, then pick the folders. If that does not work: «Copy the settings for other programs» and in Claude Desktop Settings → Developer → Edit Config.',
    "Un assistente AI (per esempio Claude Desktop) può preparare lo spettacolo per te: crea la scaletta da una cartella di file, aggiunge didascalie, scene e note per l'operatore. Trova i file su tutti i dischi di questo computer (anche su una chiavetta USB; le cartelle si possono limitare in Claude), non suona niente, non cancella i media e non cambia mai uno spettacolo in corso. Ai fornitori di AI arrivano i nomi delle cue, le note e i nomi dei file, non il contenuto dei file.":
        'An AI assistant (for example Claude Desktop) can prepare the show for you: it builds the cue list from a folder of files and adds captions, scenes and notes for the operator. It finds files on every drive of this computer (also a USB stick; the folders can be limited in Claude), plays nothing, deletes no media and never changes a show that is running. AI providers receive the cue names, the notes and the file names, not the contents of the files.',
    "Impostazioni copiate: l'assistente può usare tutti i dischi di questo computer (anche una chiavetta USB). Incollale nella configurazione del client MCP.":
        "Settings copied: the assistant may use every drive of this computer (also a USB stick). Paste them into the MCP client's configuration.",
    'N. (Q)':
        'No. (Q)',
    'Numero della cue nel copione (Q), per esempio 12 o 12a':
        'Cue number in the script (Q), e.g. 12 or 12a',
    '▦ Nascondi la mira':
        '▦ Hide the test pattern',
    '▦ Mostra la mira sul proiettore':
        '▦ Show the test pattern on the projector',
    '▶  Anteprima':
        '▶  Preview',
    '⏹  Ferma anteprima':
        '⏹  Stop the preview',
    'Ora in onda – si sente in sala':
        'On air – heard in the room',
    'ORA IN ONDA – si sente in sala':
        'ON AIR – heard in the room',
    '🔍 Mostra il pezzo':
        '🔍 Show the piece',
    '↔ Tutto il file':
        '↔ Whole file',
    "Ingrandisce la forma d'onda tra l'inizio e la fine scelti; di nuovo: tutto il file":
        'Zooms the waveform between the chosen start and end; again: the whole file',
    'Nascondi questi avvisi (tornano se cambiano)':
        'Hide these warnings (they come back if they change)',
    'Nascondi gli avvisi':
        'Hide the warnings',
    'Nessun avviso':
        'No warnings',
    'ultimo fotogramma':
        'last frame',
    "Alla fine resta l'ultimo fotogramma":
        'Keep the last frame at the end',
    "Il video si ferma sull'ultimo fotogramma, che resta sullo schermo finché un'altra cue prende il suo layer o lo sfumi (Sfuma, Sfuma tutto, Blackout). Non con il loop infinito.":
        'The video stops on its last frame, which stays on the screen until another cue takes its layer or you fade it (Fade, Fade All, Blackout). Not with an endless loop.',
    'Dissolvenza':
        'Dissolve',
    'Scorrimento':
        'Slide',
    "Come entra l'immagine: in dissolvenza sopra la precedente, oppure scorrendo da destra mentre la precedente esce a sinistra.":
        'How the picture comes in: dissolving over the previous one, or sliding in from the right while the previous one leaves to the left.',
    "Tipo di passaggio dell'immagine":
        'Kind of picture passage',
    '⚠ Tempo sullo schermo troppo breve: almeno {} s (passaggi + 0,5 s)':
        '⚠ Time on screen too short: at least {} s (passages + 0.5 s)',
    '⚠ almeno {} s':
        '⚠ at least {} s',
    'immagine sullo schermo meno dei suoi passaggi + 0,5 s':
        'picture on the screen shorter than its passages + 0.5 s',
    '🔢 Identifica gli schermi':
        '🔢 Identify the screens',
    '🖥 Porta le uscite in primo piano':
        '🖥 Bring the outputs to the front',
    'Le finestre di uscita tornano sul loro schermo e sopra le altre finestre':
        'The output windows go back to their screens, on top of the other windows',
    '🧹 Pulisci le uscite':
        '🧹 Clear the outputs',
    'Immagini, video e ultimi fotogrammi sfumano dai proiettori; il suono continua':
        'Pictures, videos and last frames fade from the projectors; the sound plays on',
    'Uscite in primo piano: {}':
        'Outputs in front: {}',
    'Nessuna uscita aperta':
        'No output window is open',
    'Uscite pulite: immagini e video sfumano, il suono continua':
        'Outputs cleared: pictures and videos fade, the sound plays on',
    'Qualcosa è in onda: i numeri degli schermi non compaiono ora':
        'Something is on air: the screen numbers are not shown now',
    '🖼 Miniature nella lista':
        '🖼 Thumbnails in the list',
    'Una piccola immagine di foto e video nella lista; su un computer lento meglio spenta':
        'A small picture of photos and videos in the list; better off on a slow computer',
    'Miniature nella lista: accese':
        'Thumbnails in the list: on',
    'Miniature nella lista: spente':
        'Thumbnails in the list: off',
    'Nessun media in onda':
        'Nothing playing',
    'PROSSIMO IN STANDBY':
        'NEXT',
    '— Nessuna cue —':
        '— no cue —',
    'SCALETTA LIVE':
        'CUE LIST',
    'REGIA PROTETTA':
        'CONTROLS LOCKED',
    'Inserisci il PIN a 6 cifre per sbloccare i comandi live sul palco.':
        'Enter the 6-digit PIN to unlock the show controls.',
    'IN ONDA':
        'PLAYING',
    'IN ATTESA (PRE)':
        'WAITING TO START',
    'IN ATTESA (POST)':
        'WAITING FOR THE NEXT',
    'Sessione scaduta o non autorizzata':
        'Session expired or not allowed',
    'IN PAUSA':
        'PAUSED',
    'Media Live':
        'Playing',
    '— Fine Scaletta —':
        '— End of the list —',
    'DISCONNESSO':
        'DISCONNECTED',
    'Sessione revocata: reinserisci il PIN':
        'Access revoked: enter the PIN again',
    'PIN errato':
        'Wrong PIN',
    'Errore di connessione alla regia':
        'No connection to the show computer',
    'BlindCUE · Monitor Regia':
        'BlindCUE · director monitor',
    'Monitor Regia · Sola Lettura':
        'Director monitor · read only',
    '● Livelli di Emissione in Tempo Reale (3 Layer)':
        '● Output layers live (3 layers)',
    'LAYER 1 (FONDO)':
        'LAYER 1 (BACKGROUND)',
    'LAYER 2 (MEDIO)':
        'LAYER 2 (MIDDLE)',
    '● Uscita B — Proiettore Indipendente (Layer B·1..B·3)':
        '● Output B — separate projector (layers B·1..B·3)',
    'PROSSIMA CUE IN STANDBY (PROSSIMO LANCIO)':
        'NEXT CUE (NEXT GO)',
    '— Nessuna cue in standby —':
        '— no next cue —',
    'SCALETTA COMPLETA DELLO SPETTACOLO':
        'FULL CUE LIST',
    'STATO':
        'STATE',
    'Q #':
        'No.',
    'TITOLO CUE & NOTE':
        'CUE & NOTES',
    'TIPO':
        'TYPE',
    'DURATA':
        'LENGTH',
    'AVANZAMENTO':
        'THEN',
    '🔒 Interfaccia passiva di monitoraggio per la Direzione Artistica e di Scena · Nessun comando attivo abilitato · BlindCUE Native':
        '🔒 Read-only monitor for the director and the stage manager · no commands · BlindCUE Native',
    'Inserisci il PIN a 6 cifre per accedere alla visualizzazione del Monitor Regia.':
        'Enter the 6-digit PIN to open the director monitor.',
    '🖼 IMMAGINE':
        '🖼 IMAGE',
    '📁 GRUPPO':
        '📁 GROUP',
    '⚡ AZIONE':
        '⚡ ACTION',
    'Tutte le cue eseguite':
        'All cues played',
    '○ PRONTA':
        '○ READY',
    '● IN ONDA':
        '● PLAYING',
    'Simultanea':
        'Together',
    'PIN di regia richiesto':
        'PIN required',
    'PIN errato.':
        'Wrong PIN.',
    'Troppi tentativi errati. Blocco temporaneo per {}s.':
        'Too many wrong attempts. Locked for {} s.',
    'BlindCUE (Protetto)':
        'BlindCUE (protected)',
    'Pagina non trovata o richiesta non valida.':
        'Page not found or invalid request.',
    'Torna al telecomando':
        'Back to the remote',
    'Ora del computer':
        "Computer's clock",
    'Prossima cue a orario':
        'Next cue at a time of day',
    'Tieni premuto {} per tornare alla preparazione (ciò che è in onda continua). Da tastiera: Ctrl+Maiusc+F5':
        'Hold {} to go back to preparation (what plays keeps playing). Keyboard: Ctrl+Shift+F5',
    'Torna alla preparazione: tieni premuto {}':
        'Back to preparation: hold for {}',
    'Tieni premuto {} per passare alla prova (ciò che è in onda continua)':
        'Hold for {} to go to the rehearsal (what plays keeps playing)',
    'Passa alla prova: tieni premuto {}':
        'Go to the rehearsal: hold for {}',
    'Per uscire dallo spettacolo: tieni premuto «○ Preparazione» per {} oppure Ctrl+Maiusc+F5':
        'To leave the show: hold "○ Preparation" for {} or press Ctrl+Shift+F5',
    'Tieni premuto più a lungo ({}) per uscire dallo spettacolo':
        'Hold longer ({}) to leave the show',
    'Tieni premuto per saltare di 10 s ({} nello spettacolo)':
        'Hold to jump 10 s ({} in the show)',
    'Tieni premuto «Preparazione» {}':
        'Hold «Preparation» for {}',
    '4 cifre per uscire dallo spettacolo su questo computer (vuoto = basta tenere premuto {}):':
        '4 digits to leave the show on this computer (empty = holding for {} is enough):',
    '✋ Tempo per tenere premuto':
        '✋ Hold time',
    '{} (predefinito)':
        '{} (default)',
    'Il tempo per tenere premuto si cambia in Preparazione':
        'The hold time is changed in Preparation',
    'Tenere premuto: {} su questo computer':
        'Hold time: {} on this computer',
    'Avvia (di nuovo = niente finché suona)':
        'Start (again = nothing while it plays)',
    "Effetto già in corso: '{}' (non riparte)":
        "Effect already playing: '{}' (not restarted)",
    '➕ Aggiungi':
        '➕ Add',
}
