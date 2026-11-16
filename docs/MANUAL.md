# Manuale Utente e di Riferimento — BlindCue

Guida completa per chi usa BlindCue in scena: tecnici di regia, operatori audio/video, direttori di scena e assistenti.

Per l'architettura interna e lo sviluppo vedi invece l'**[Architettura](ARCHITECTURE.md)**.

---

## Indice

1. [Prima di iniziare](#1-prima-di-iniziare)
2. [Installazione e primo avvio](#2-installazione-e-primo-avvio)
3. [L'interfaccia di regia](#3-linterfaccia-di-regia)
4. [Le due modalità: Progetto e LIVE](#4-le-due-modalità-progetto-e-live)
5. [Le cue](#5-le-cue)
6. [Tempi e avanzamento](#6-tempi-e-avanzamento)
7. [Gruppi e scene](#7-gruppi-e-scene)
8. [Forma d'onda, IN/OUT, fade ed envelope](#8-forma-donda-inout-fade-ed-envelope)
9. [Sezioni virtuali](#9-sezioni-virtuali)
10. [Audio: routing, loudness e Jam Mode](#10-audio-routing-loudness-e-jam-mode)
11. [Superfici di proiezione e video mapping](#11-superfici-di-proiezione-e-video-mapping)
12. [Layer 0, blackout e guide di calibrazione](#12-layer-0-blackout-e-guide-di-calibrazione)
13. [Controllo remoto: Web e OSC](#13-controllo-remoto-web-e-osc)
14. [Salvataggio, autosave e recupero](#14-salvataggio-autosave-e-recupero)
15. [Scorciatoie](#scorciatoie)
16. [Emergenze in scena](#16-emergenze-in-scena)
17. [Risoluzione dei problemi](#17-risoluzione-dei-problemi)
18. [Domande frequenti](#18-domande-frequenti)

---

## 1. Prima di iniziare

### Il principio

BlindCue separa due ambienti che non devono mai mescolarsi:

- **Regia** (monitor dell'operatore): scaletta, ispettore, anteprima, forma d'onda.
- **Uscita** (proiettore o display di scena): solo i contenuti in onda, a tutto schermo e senza bordi.

Il pubblico vede soltanto l'uscita. Qualsiasi cosa accada sul monitor di regia resta invisibile alla sala.

### Cosa ti serve

| Elemento | Consigliato |
|---|---|
| Computer | Linux (Wayland o X11); funziona anche su macOS e Windows |
| Monitor | Due schermi (regia + uscita). Con un solo schermo l'uscita diventa una finestra flottante |
| Cavo video | HDMI, DisplayPort o adattatore verso il proiettore |
| Audio | Scheda audio o interfaccia con uscita master verso la sala |
| Cuffie | Collegate a un'uscita diversa dal master, per il pre-ascolto PFL |

### La regola d'oro degli schermi

Nel sistema operativo imposta sempre **"Estendi schermo"** (desktop esteso). **Mai "Duplica"**: in duplicazione la regia e il pubblico vedono la stessa cosa, e lo spettacolo mostra l'interfaccia.

---

## 2. Installazione e primo avvio

### Un solo comando per tutti i sistemi

```bash
git clone https://github.com/diego-costanzo/BlinCUE.git
cd BlinCUE
python3 setup.py
```

Si apre una finestra con i colori di BlindCue che spiega cosa verrà fatto, mostra l'avanzamento e alla fine offre **Avvia BlindCue**. Non richiede password: BlindCue viene installato **nella cartella del tuo utente**.

| Sistema | Dove finisce | Come si avvia |
|---|---|---|
| **Linux** | `~/.local/share/blindcue` | comando `blindcue` oppure icona nel menu applicazioni |
| **macOS** | `~/Applications/BlindCue.app` | icona nel Launchpad o nel Finder |
| **Windows** | `%LOCALAPPDATA%\Programs\BlindCue` | icona sul Desktop e nel menu Start |

Il programma viene copiato nella sua cartella definitiva: il repository scaricato serve solo per l'installazione. **I tuoi progetti non vengono spostati** e l'autosave resta in `~/.config/blindcue`, quindi un aggiornamento non tocca il lavoro fatto.

### Linux senza finestra grafica

```bash
./setup/linux/install.sh
./setup/linux/run.sh
```

L'installer controlla Python, RAM, spazio disco, rete, server audio, display e GPU, installa i pacchetti mancanti e conclude con uno smoke test. Opzioni utili:

```bash
./setup/linux/install.sh --check     # solo diagnostica
./setup/linux/install.sh --yes       # non interattivo
./setup/linux/install.sh --no-sudo   # senza privilegi di root
./setup/linux/install.sh --no-gpu    # senza driver VA-API
```

### macOS

```bash
./setup/macos/install.command
./setup/macos/run.command
```

Crea `~/Applications/BlindCue.app` con icona e voce nel Launchpad. Al primo avvio macOS può chiedere conferma (bundle non firmato): tasto destro sull'icona → **Apri**.

### Windows

Esegui `setup\windows\install.bat`, poi avvia dall'icona **BlindCue** sul Desktop o nel menu Start (`setup\windows\run.bat` per la diagnostica da terminale).

### Aggiornare o rimuovere

```bash
python3 setup.py            # aggiorna: riscarica le dipendenze solo se serve
python3 uninstall.py        # disinstalla: programma, collegamenti e icona
python3 uninstall.py --purge  # disinstalla anche impostazioni e autosave
```

La disinstallazione non lascia tracce nel sistema, ma **non tocca i tuoi progetti `.blindcue`**. Con `--purge` vengono rimossi anche impostazioni e autosave: se hai un lavoro non salvato, esportalo prima. Dalla finestra dell'installer la stessa operazione è nel pulsante **Rimuovi**, con la conferma richiesta.

### Opzioni da riga di comando

| Opzione | Effetto |
|---|---|
| `--output-screen N` | Forza lo schermo di uscita (indice 0-based) |
| `--debug` | Log dettagliato per la diagnosi (non usarlo in spettacolo) |

Senza opzioni, BlindCue sceglie automaticamente il primo schermo diverso dal primario.

### Il primo avvio

1. Collega il proiettore **prima** di avviare BlindCue.
2. Controlla che l'uscita mostri il reticolo di calibrazione (Layer 0): significa che la finestra di scena è attiva.
3. Apri **`Show` → `⚙️ Dispositivi & Hardware`** e verifica il routing audio.
4. Se hai più schermi, controlla che l'uscita sia sul proiettore; altrimenti aprila e seleziona lo schermo corretto.

---

## 3. L'interfaccia di regia

La schermata principale è divisa in sei zone:

```text
┌───────────────┬─────────────────────────┬──────────────────┐
│ 1. Scaletta   │ 2. Anteprima Pre-Viz    │ 3. Ispettore     │
│    (cue list) │    + pulsante GO        │    (proprietà)   │
├───────────────┴─────────────────────────┴──────────────────┤
│ 4. Forma d'onda  │ 5. Stato Live    │ 6. Drop Zone         │
└────────────────────────────────────────────────────────────┘
```

1. **Scaletta** — l'ordine delle cue, con badge di stato, sigla di copione e indicatori di conflitto layer.
2. **Anteprima Pre-Viz** — monitor 16:9 per l'anteprima muta (in cuffia) e il pulsante **GO**.
3. **Ispettore** — tutte le proprietà della cue selezionata, divise in schede.
4. **Forma d'onda** — IN/OUT, fade, envelope a keyframe, sezioni.
5. **Stato Live** — cosa c'è in onda su ogni layer, con controlli rapidi.
6. **Drop Zone** — trascina qui file audio, video e immagini per crearne cue.

Tutte e sei le zone servono a **lavorare sul materiale**: guardarlo, ascoltarlo, ritagliarlo, spostarlo, decidere dove va. È il "banco di lavoro" del progetto ed è la schermata che vedi all'avvio. Nella modalità LIVE questa scrivania sparisce e resta la consolle essenziale: la differenza tra le due è spiegata in §4.

In fondo alla finestra, la **status bar** mostra: hardware e profilo attivo, pulsante `⚙ Dispositivi · Uscite`, blocco layout, `🎚 Jam`, `📡 Remoto` e il messaggio di stato.

### Stato di ogni cue

| Badge | Significato |
|---|---|
| **OFFLINE** | File mancante o percorso non valido |
| **LOADED** | Pronta, non in onda |
| **LIVE** | In onda adesso |
| **PREVIZ** | In anteprima, non in sala |

I conflitti di layer (due cue che si contendono lo stesso layer) sono segnalati già in fase di progetto.

### Anteprima Pre-Viz (PFL)

Il monitor centrale è **muto in sala**: serve a te, in cuffia. I pulsanti sotto il monitor sono:

- **▶ / ⏸ / ⏹** — riproduci, pausa, stop dell'anteprima.
- **🔗 MIRROR LIVE: OFF / 🔴 MIRROR: ON** — quando attivo, il monitor mostra ciò che è realmente in onda.
- **🔊 CUFFIA: ON / 🔒 MUTE: ON** — abilita o silenzia il pre-ascolto in cuffia.

L'anteprima **non** interferisce mai con il master di sala.

---

## 4. Le due modalità: Progetto e LIVE

BlindCue ha due anime, e quindi due schermate. Si passa dall'una all'altra con **`F5`** (o `Ctrl+L`), oppure con il pulsante in cima alla scaletta.

> **In una frase.** Il **Progetto** è il laboratorio dove prepari il materiale: guardi, ascolti, misuri, ritagli, sposti, decidi. Il **LIVE** è la consolle: il laboratorio si chiude a chiave e resta soltanto ciò che serve per mandare in onda.

### La schermata di avvio è il banco di lavoro

Quando apri BlindCue ti trovi davanti al progetto, non alla scena. È una distinzione voluta: quasi tutto il lavoro di una regia video/audio non è "premere GO", ma **capire che cosa c'è dentro ai file** che ti hanno consegnato e sistemarli abbastanza da poterli usare.

Normalmente questo significa aprire un editor video, un editor audio, un programma per le immagini, esportare, salvare una copia, riportarla dentro… e rifarlo la volta dopo. BlindCue ribalta il flusso: **trascini il file grezzo, lo guardi nell'anteprima e lo aggiusti da lì**, con gli strumenti che servono davvero in scena. Non è un coltellino svizzero con mille lame: è un coltellino svizzero con *le lame giuste*, e tutte lavorano senza mai toccare il file originale.

### Video e immagini: prima guarda, poi decidi

Seleziona una cue e l'anteprima **Pre-Viz** te la mostra nel formato reale (16:9), muta, in cuffia. Da lì capisci subito se il materiale è utilizzabile e che cosa conviene fargli.

| Cosa vuoi ottenere | Dove si fa | Effetto |
|---|---|---|
| **Vedere** che cosa contiene il file | Anteprima Pre-Viz | Anteprima muta, senza mandare nulla in sala |
| **Ritagliare** (crop) | Ispettore → `🖼 Video · Foto` → Crop | In percentuale o in **pixel**, con commutatore |
| **Ritagliare a mano** | Maniglie sull'anteprima | Trascini i bordi dell'area visibile |
| **Spostare / centrare** | Posizione **X / Y** | Offset dell'immagine nella superficie |
| **Rimpicciolire / ingrandire** | **Scala** | Adatta il contenuto all'area disponibile |
| **Radrizzare o ruotare** | **Rotazione** (gradi, ±90° rapidi) | Gira l'immagine o il video sul posto, attorno al centro visibile |
| **Ritagliare una forma irregolare** | **Maschera poligonale** (solo immagini) | Clic per disegnare i vertici, trascina per spostarli, clic destro per eliminarli |
| **Ammorbidire** | **Opacità** | Dissolve il contenuto sopra gli altri layer |
| **Adattare a schermi non standard** | **Aspect ratio forzato** | Evita bande nere o stiramenti |
| **Mandare su una parte precisa della scena** | **Superficie** (vedi §11) | Un proiettore, una metà, una vela, un pilastro |
| **Farlo durare di più** | **Loop** e numero di ripetizioni | Ripete il media senza toccare il file |
| **Immagine ferma con dissolvenza** | **Hold Time** + timeline virtuale | Anche una foto può avere fade ed envelope |

Quell'ultima riga è un dettaglio che pochi si aspettano: un'**immagine** non ha una durata propria, quindi BlindCue le assegna una timeline virtuale di 10 secondi. Puoi disegnarci sopra la dissolvenza e l'envelope di opacità esattamente come su un video. In scena è la differenza tra "la foto appare di colpo" e "la foto entra come una vera transizione".

### Audio: ascolta, misura, sistema

L'audio è la parte dove il lavoro di rifinitura si sente di più, e dove BlindCue concentra gli strumenti più utili.

| Cosa vuoi ottenere | Dove si fa | Effetto |
|---|---|---|
| **Ascoltare senza mandare in sala** | Pre-ascolto PFL in cuffia | Il master di sala resta intatto |
| **Tagliare l'inizio e la fine** | Forma d'onda → **IN / OUT**, oppure `I` / `O` | Aggancio al playhead al campione |
| **Entrare e uscire morbidi** | **Fade In / Fade Out** + curva | Logaritmica, S-Curve o lineare |
| **Disegnare il volume nel tempo** | **Envelope** a keyframe | Ducking, crescendo, dissolvenze irregolari |
| **Ripetere una parte** | **Sezioni virtuali** (vedi §9) | Loop N volte o vamp infinito |
| **Sapere quanto è forte un brano** | Tasto destro → **Analizza Loudness (EBU R128)** | LUFS integrato e True Peak |
| **Pareggiare volumi diversi** | **Normalizza cue** | Offset di guadagno, senza toccare il file |
| **Compattare la dinamica** | **Ottimizza dinamica** | Crea una copia limitata a −1.5 dBFS |
| **Tornare indietro** | **Ripristina originale** | Riaggancia il file di partenza |
| **Contest e jam non calibrati** | `🎚 Jam` (tieni premuto 5 s) | Livellamento automatico a −16 LUFS |

Il punto è che queste operazioni non richiedono di convertire nulla prima: il brano con tre secondi di silenzio in testa si sistema con un IN point, non con un export; la canzone troppo bassa si normalizza con un guadagno sul player.

### Scene: comporre più cose insieme

Quando una cue non basta più e serve una **scena** (video + musica + grafica che entrano insieme), crei un **Gruppo** e lo apri nello **Studio Timeline**: tre tracce, clip da spostare, bordi da tirare, layer da assegnare, anteprima sincronizzata. Anche qui: si modificano i *parametri* delle cue, non i file.

### Perché "non distruttivo" è la parola chiave

Questa è la garanzia che rende il banco di lavoro sicuro da usare anche sotto pressione:

| Azione | Il file originale | Che cosa viene scritto davvero |
|---|---|---|
| Crop, posizione, scala, opacità | **Intatto** | Un parametro nel progetto |
| Rotazione e maschera poligonale | **Intatto** | Un angolo e una lista di punti nel progetto |
| Cambio IN / OUT | **Intatto** | Un parametro nel progetto |
| Fade, envelope, sezioni, loop | **Intatto** | Un parametro nel progetto |
| Normalizza cue | **Intatto** | Un guadagno applicato dal player |
| Ottimizza dinamica | **Intatto** | Una **copia** ottimizzata nella cache |
| Cambio immagine di Layer 0 | **Intatto** | Un percorso salvato nella configurazione |
| Eliminazione di una cue | **Intatto** | La cue sparisce dalla scaletta, non dal disco |

Tutto vive nel file di progetto `.blindcue` (§14), che è **JSON leggibile**: puoi aprirlo con un editor di testo, confrontarlo, copiarlo, ripararlo. E se sbagli, `Ctrl+Z` torna indietro fino a **40 passaggi**; in più l'autosave ogni 30 secondi ti copre anche da una chiusura accidentale.

**Quello che BlindCue non fa, di proposito.** Non è un editor video o audio: non esporta, non ricodifica e non taglia il materiale in modo definitivo. Puoi ruotare un'immagine o un video e ritagliare un'immagine lungo un poligono, ma il risultato resta una **vista** sul file originale: nessun byte viene riscritto. Se ti serve un file fisicamente ruotato, tagliato o convertito da consegnare a qualcun altro, serve un editor esterno. BlindCue ti risparmia il giro tutte le volte che devi solo *adattare* il materiale alla scena — che è la grande maggioranza delle volte.

Una differenza voluta: la **maschera poligonale** esiste solo per le immagini. Su un video andrebbe ricalcolata a ogni fotogramma, e in live questo significa spendere CPU per qualcosa che non deve mai far tremare la proiezione. La rotazione invece vale per entrambi, perché è una trasformazione che la scheda video applica senza costo misurabile.

### Il passaggio al LIVE: il laboratorio si chiude a chiave

Premi **`F5`** e la finestra cambia natura. Spariscono i pannelli di lavoro e compare la consolle:

- la scaletta diventa **grande e ad alto contrasto**, leggibile a distanza;
- al centro il **clock di sistema**, a destra il **cronometro dello spettacolo** (parte al primo GO, si azzera e si riarma; non ferma i media, misura solo la durata della replica);
- **ispettore, forma d'onda e trascinamento delle cue non ci sono più**: non puoi cambiare crop, fade o layer per sbaglio;
- le barre dei layer sono **bloccate di default** (`🔒 BLOCCO LAYER`): per usarle devi tenere premuto **1,2 secondi**; un singolo click le riblocca subito;
- i tasti **Fade Out** dei singoli layer richiedono **0,6 secondi** di pressione: abbastanza per non tagliare un layer con un tocco involontario, abbastanza poco per restare reattivi in scena;
- i comandi che svuotano o cancellano non sono più raggiungibili;
- BlindCue alza le soglie del **garbage collector di Python** per tutta la durata del LIVE: meno raccolte di memoria, quindi meno micro-pause proprio durante i GO;
- restano a portata di mano solo **GO**, **PAUSA TUTTO** e **PANIC**.

| | Modalità **Progetto** | Modalità **LIVE** |
|---|---|---|
| A cosa serve | Preparare, correggere, ascoltare | Mandare in onda |
| Scaletta | Compatta, modificabile | Grande, alto contrasto, protetta |
| Proprietà delle cue | Tutte accessibili | Non accessibili |
| Layer live | Comandi attivi | Bloccati (sblocco con pressione 3 s) |
| Comandi distruttivi | Disponibili (con Undo) | Rimossi dall'interfaccia |
| Tasti principali | `F5`, `Ctrl+S`, `Ctrl+Z` | `Spazio` = GO, `ESC` = PANIC |

Il motivo di tanta severità è semplice: in scena le mani si muovono in fretta, il buio non aiuta e un clic sbagliato si vede dal pubblico. Meglio scoprire che *non puoi* toccare qualcosa, che scoprire troppo tardi di averlo toccato.

Tornare in Progetto (`F5`) non interrompe quello che è in onda: puoi riaprire il laboratorio anche a sipario alzato, ma è una manovra da fare solo se sai esattamente perché la stai facendo.

---

## 5. Le cue


### Tipi di cue

| Tipo | Sigla | Comportamento |
|---|---|---|
| **Video** | VID | Riproduzione con decodifica hardware, crop, opacità, posizione, superfici |
| **Audio** | AUD | Riproduzione con fade, envelope di volume, routing |
| **Immagine** | IMG | Grafica statica con durata (hold) e fade |
| **Gruppo** | GRP | Contenitore di altre cue (una scena) |

### Creare una cue

Hai tre strade:

1. **Drag & drop** di file nella Drop Zone in basso a destra.
2. **Pulsante di aggiunta media** nel pannello scaletta.
3. **Doppio clic** su una cella della scaletta per modificarla.

Le cue vengono inserite nella posizione corrente e ricevono un `cue_id` stabile.

### La sigla di copione (Q)

Ogni cue ha una **sigla** (es. `Q-2`, `Q-9a`, o testo libero). È separata dal nome e **resta legata alla cue quando riordini la scaletta**: serve a ritrovarla seguendo il copione.

### L'ispettore

Quattro schede, che cambiano in base al tipo di cue:

#### 🎯 Cue · Tempi

- **Q** e **Nome**.
- **Layer** di destinazione (1, 2, 3).
- **Pre-Delay**: attesa dopo il GO prima che la cue parta davvero.
- **Post-Delay**: attesa dopo la fine del media prima del rilascio del layer.
- **Hold Time** (immagini): per quanto resta in onda; `0` = infinita.
- **Fade In / Fade Out** e **curva** di dissolvenza.
- **Modalità di avanzamento**: manuale, auto-follow, simultanea.

#### 🖼 Video · Foto

- **Posizione X / Y** e **scala**.
- **Opacità** del layer.
- **Crop** in percentuale o in pixel, con pulsante di commutazione.
- **Rotazione** in gradi, con scorciatoie ±90° e ritorno a 0°.
- **Maschera poligonale** (solo immagini): disegni i vertici, BlindCue ritaglia la proiezione. Nell'editor: clic sinistro aggiunge un vertice, trascina un nodo per spostarlo, **clic destro** lo elimina; **rotellina** (o `Ctrl++` / `Ctrl+-`) per lo zoom fino a 8×, **tasto centrale** per spostarti, `Ctrl+0` per tornare al 100%. Zoom e spostamento cambiano solo la vista: la selezione non viene mai persa. Lo slider **Sfumatura** ammorbidisce il bordo (0 = taglio netto) e la resa è identica in Pre-Viz e in proiezione.
- **Aspect ratio** forzato.
- **Superficie** di destinazione (vedi §11).
- **Loop** e numero di ripetizioni.

#### 🎵 Audio · Tagli

- **Volume** della cue.
- **IN / OUT** del media.
- Fade e analisi del volume (loudness).
- Normalizzazione, ottimizzazione dinamica, ripristino dell'originale.

#### 📁 Gruppo · Scena

- Modalità del gruppo.
- Pre/Post-Delay del gruppo.
- Collassa/espandi i figli, estrai un figlio, sciogli il gruppo.
- Apre lo **Studio Timeline** per comporre la scena.

### Note di scena

Ogni cue ha un campo **Note** libero: usalo per promemoria operativi ("entra sull'ultima battuta di X"). Non viene mai proiettato.

---

## 6. Tempi e avanzamento

### La sequenza temporale di una cue

```text
[ GO ]
  │
  ▼
┌────────────┐    ┌──────────────────────┐    ┌────────────┐
│ Pre-Delay  │──▶ │   Riproduzione       │──▶ │ Post-Delay │──▶ rilascio layer
│ (es. 2 s)  │    │   (durata del media) │    │ (es. 1 s)  │    o auto-follow
└────────────┘    └──────────────────────┘    └────────────┘
```

Durante il **Pre-Delay** la cue è già stata "lanciata" ma non è ancora LIVE: il badge mostra l'attesa. Questo permette di incastrare più layer con precisione millimetrica.

### Le tre modalità di avanzamento

| Modalità | Simbolo | Comportamento |
|---|---|---|
| **Manuale / Blocco** | ⏹ | Esegue la cue e si ferma in standby sulla successiva. Serve un nuovo GO |
| **Auto-Follow** | ⤵ | A fine cue (Pre + durata + Post) parte da sola la successiva |
| **Simultanea** | ⇉ | Parte insieme alla cue successiva, che parte insieme alla sua successiva, e così via |

La **catena simultanea** è utile per mandare in onda più layer con un solo GO: ogni cue della catena occupa un layer diverso.

### Pausa globale

**PAUSA TUTTO** congela tutti i layer, i timer di Pre/Post-Delay e le dissolvenze, **senza perdere il punto**: alla ripresa si riparte esattamente da dove si era fermato, senza drift. È pensata per pause impreviste a scena aperta.

---

## 7. Gruppi e scene

Seleziona più cue e premi **`Ctrl+G`** per raggrupparle in una scena. Il gruppo diventa una cue contenitore con i figli annidati.

### Le cinque modalità di gruppo

| Modalità | Simbolo | Comportamento |
|---|---|---|
| **Simultaneo** | ⇉ | Tutti i figli partono insieme al GO |
| **Sequenziale** | ⤵ | I figli si concatenano uno dopo l'altro |
| **Passo-Passo** | ⏹ | Ogni GO fa avanzare di un figlio |
| **Random** | 🎲 | Sceglie un figlio a caso |
| **Loop** | 🔁 | Cicla continuamente i figli |

### Operazioni sui gruppi

- **Collassa / Espandi** (`▶` / `▼`): mostra o nasconde i figli in scaletta.
- **Estrai figlio** (`Ctrl+Shift+G`): toglie la cue selezionata dal gruppo e la riporta al livello principale.
- **Sciogli gruppo**: elimina il contenitore e rilascia tutte le cue in scaletta.
- **Studio Timeline**: apre l'editor multi-traccia della scena.

### Studio Timeline

L'editor delle scene mostra **tre tracce** (Layer 3 in alto, Layer 1 in fondo). Puoi:

- spostare i clip nel tempo;
- cambiarne la durata trascinando i bordi (trim IN/OUT);
- assegnare ogni clip a un layer;
- vedere la composizione sincronizzata in un monitor di anteprima.

Le modifiche sono **non distruttive**: cambiano i parametri delle cue del gruppo, non i file originali.

---

## 8. Forma d'onda, IN/OUT, fade ed envelope

### Forma d'onda

La forma d'onda mostra i picchi del file audio o della traccia video.

| Azione | Come |
|---|---|
| Zoom orizzontale (1x–32x) | Rotella del mouse, ancorata al cursore |
| Scorrere quando sei in zoom | `Shift` + rotella, oppure trascinamento con tasto centrale |
| Spostare il playhead | Clic sulla forma d'onda |
| Impostare IN / OUT | Trascina i marcatori, oppure `I` / `O` per agganciarli al playhead |

I pulsanti **Snap IN** e **Snap OUT** agganciano il punto al playhead con precisione campione.

### Fade

Ogni cue ha **Fade In** e **Fade Out** in secondi, con tre curve:

| Curva | Sensazione |
|---|---|
| **Logaritmica** | Naturale, quella che l'orecchio percepisce come uniforme (default) |
| **S-Curve** | Morbida in entrata e in uscita, ideale per la musica |
| **Lineare** | Proporzionale, prevedibile |

I valori si inseriscono numericamente oppure si trascinano direttamente sulla forma d'onda.

### Envelope a keyframe

L'envelope permette di disegnare l'andamento di **volume** (audio) o **opacità** (video/immagini) nel tempo:

- attiva la modalità envelope nella forma d'onda;
- aggiungi punti nell'istante desiderato e trascinali al livello voluto;
- il player interpola linearmente tra i punti, moltiplicando il valore per il fade di ingresso/uscita.

Utile per ducking manuale, crescendo, dissolvenze non lineari.

---

## 9. Sezioni virtuali

Una sezione è una **porzione riutilizzabile** di un cue audio o video, senza tagliare il file.

- **Dividi** il media in sezioni (A, B, C…).
- **Loop N volte**: la sezione si ripete un numero finito di volte.
- **Vamp infinito** (`loops = 0`): la sezione continua finché non premi **Interrompi Loop**.
- **Salta** una sezione (`skip`) per non eseguirla.
- **Salto manuale**: durante l'esecuzione puoi passare a un'altra sezione; il cambio avviene **senza buco nero** grazie ai deck A/B.
- **Rimuovi / Unisci** le sezioni per tornare indietro.

La modalità di ogni sezione (loop, vamp, salta) viene rispettata **a ogni passaggio**: al primo giro, nelle ripetizioni, dopo un replay da EOF, quando sposti il playhead sulla forma d'onda e quando salti manualmente a un'altra sezione. Non serve riapplicare nulla: il taglio fa parte del cue, non del singolo passaggio.

Le sezioni sono la risposta al problema classico del teatro: "questa musica deve continuare finché l'attore non esce". Metti il vamp in loop, poi interrompi quando serve.

---

## 10. Audio: routing, loudness e Jam Mode

### Routing

Apri **`Show` → `⚙️ Dispositivi & Hardware`**:

- **Master Sala**: il dispositivo che va al mixer o all'impianto.
- **Pre-ascolto PFL / Cuffia**: il dispositivo delle tue cuffie.

Sono indipendenti: puoi ascoltare in cuffia senza mandare nulla in sala.

BlindCUE interroga il sistema operativo a ogni apertura del pannello e mostra tutte le **schede audio di uscita** collegate. Un normale computer ha **una sola uscita stereo**: in quel caso il selettore cuffia viene disattivato con un avviso, perché il pre-ascolto PFL finirebbe sullo stesso impianto del pubblico. Collega una seconda scheda (USB, DAC, interfaccia audio) e il selettore si riattiva da solo: il monitor cuffia torna disponibile.

### Profilo hardware

| Profilo | Quando usarlo |
|---|---|
| **Auto** | Rilevamento automatico (consigliato) |
| **🍃 Eco** | Muletto, ≤ 4 GB RAM, macchine lente |
| **⚡ Standard** | Bilanciato per live |
| **🚀 Performance** | Workstation multi-core |

Il profilo regola quanti worker in background possono girare. **In tutti i profili BlindCue lascia sempre almeno un core libero al sistema** (due su macchine con 4+ core): è una scelta deliberata per non causare drop di frame o glitch audio.

### Analisi del volume (EBU R128)

Tasto destro su una cue audio → **Analizza Loudness (EBU R128)**. Il software calcola:

- **LUFS integrato** — il volume percepito complessivo;
- **True Peak** — il picco reale, in dBFS.

Il confronto tra tracce registrate a volumi diversi diventa oggettivo.

### Normalizzazione e dinamica

- **Normalizza cue**: applica un offset di guadagno **non distruttivo** sul player, senza toccare il file.
- **Ottimizza dinamica**: crea una versione ottimizzata con limitazione di picco (−1.5 dBFS). Il file originale resta intatto.
- **Ripristina originale**: annulla l'ottimizzazione e torna al file di partenza.

### Modalità Jam / Contest

Per contest, jam session e file non calibrati. Quando è attiva, applica automaticamente il livellamento **EBU R128 a −16 LUFS** a tutte le cue.

Si attiva **tenendo premuto 5 secondi** il pulsante `🎚 Jam` nella status bar o la voce nel menu `Show`, e si disattiva tenendo premuto 1.5 secondi. La pressione prolungata è intenzionale: evita attivazioni accidentali in scena.

---

## 11. Superfici di proiezione e video mapping

Apri con **`F7`** (`View` → `📐 Studio Superfici di Proiezione & Mapping`).

### Configurare le uscite video (uno o più proiettori)

Apri **`⚙ Dispositivi · Uscite`** e scegli la **Modalità Uscita**. Il comportamento è sempre esplicito: non viene mai indovinato.

| Modalità | Cosa fa | Quando usarla |
|---|---|---|
| **Singolo schermo** | Una sola uscita, sul proiettore selezionato | Setup base, teatro con un proiettore, prove |
| **Superficie unica (span)** | Una sola tela continua che copre **tutti** gli schermi esterni | Due proiettori affiancati che formano un unico schermo |
| **Due uscite indipendenti** | Due finestre di uscita separate, ciascuna con i propri 3 layer | Due proiettori che mostrano contenuti diversi nello stesso momento |

**Come funziona lo span.** BlindCUE calcola l'area che unisce i proiettori esterni e vi mappa la finestra di uscita: il desktop esteso mostra un'unica immagine senza bordi nel mezzo. La regia resta sempre sul monitor primario, che non viene mai incluso. La scelta viene salvata nel progetto e ricordata al riavvio.

**Come funzionano le due uscite indipendenti.** BlindCUE apre **due** finestre di proiezione: l'uscita **A** sul primo schermo esterno e l'uscita **B** sul secondo. Ogni uscita ha i propri tre layer, quindi puoi avere fino a **sei contenuti simultanei** (tre per proiettore). La regia resta sul monitor primario. La modalità richiede **due proiettori esterni oltre al monitor di regia** (tre display in totale): se ne manca uno, BlindCue non attiva la modalità e torna alla singola uscita, senza mai lasciare il proiettore nero.

**Quale proiettore alimenta A e quale B.** Quando sono collegati **due proiettori esterni**, nel pannello dei layer compare in alto una riga con **Proiettore A** e **Proiettore B**: scegli lì lo schermo fisico di ciascuna uscita. La scelta viene salvata e ricordata al riavvio; se scegli lo stesso proiettore per entrambe, BlindCUE li scambia automaticamente. Con un solo proiettore la riga non compare: l'uscita A va lì e non c'è nulla da scegliere. Con nessun proiettore esterno l'uscita si apre in finestra sul monitor di regia, per le prove.

**Come assegnare una cue all'uscita B.** Seleziona una cue (o più cue) e, nell'ispettore nella scheda **Video · Foto**, usa **Proiettore: A · Schermo 1 / B · Schermo 2**. Il selettore compare solo quando la modalità Due uscite indipendenti è attiva. In tabella le cue dell'uscita B mostrano il badge `B·L2` accanto al numero di layer; nel pannello live compaiono le righe dedicate all'uscita B. I conflitti di layer sono calcolati separatamente per A e per B: `A·L2` e `B·L2` possono convivere senza problemi.

**Limite di Linux/Wayland.** Su Wayland un compositore può rifiutare una finestra che attraversa due uscite. Se i proiettori non si uniscono, avvia la sessione in **X11** (o usa un compositore che consente lo spanning): il dialogo mostra un avviso quando rileva questa condizione.

**Immagini diverse sui due proiettori (dentro lo span).** Con la superficie unica puoi già ottenere contenuti distinti: crea due superfici in `F7` — una per la metà sinistra, una per la destra — e assegna ogni cue alla superficie corretta nell'ispettore. Attenzione: i **tre layer sono condivisi** tra le due aree, quindi puoi avere al massimo tre contenuti simultanei in totale, non tre per proiettore. Se ti servono due proiezioni **davvero indipendenti** (tre layer ciascuna), usa la modalità **Due uscite indipendenti** descritta sopra.

### A cosa serve

Dividere l'uscita in più **schermi virtuali** e deformare l'immagine per adattarla a superfici reali.

### Le due modalità

| Modalità | Uso |
|---|---|
| **Rettangolo** | Split screen, picture-in-picture, più proiettori su desktop esteso |
| **Quad (4 punti)** | Keystone / corner pin su pareti inclinate, vele, pilastri, scenografie irregolari |

In modalità Quad trascini i quattro vertici dell'area di proiezione: l'immagine viene deformata prospetticamente per combaciare con la superficie fisica.

### Maschere

Puoi ritagliare la proiezione con una maschera:

- **Nessuna**;
- **Ellisse** (cerchi, ovali);
- **Foro** rettangolare interno;
- **Immagine PNG** personalizzata.

Con **inverti maschera** e **feather** (morbidezza del bordo) puoi evitare di proiettare su un volto, su un'attrezzatura o su un'apertura di scena.

### Soft edge blend

Per affiancare due proiettori, imposta il **blend** sinistro e destro: la zona di sovrapposizione sfuma, eliminando la riga luminosa centrale.

### Assegnare una cue a una superficie

Nell'ispettore, scheda **Video · Foto** → **Superficie**. Ogni cue sceglie dove essere proiettata.

---

## 12. Layer 0, blackout e guide di calibrazione

### Layer 0 (Tappo)

Quando nessun media è in onda, il proiettore mostra il **Layer 0**. Per default è un **reticolo tecnico** utile per:

- mettere a fuoco l'ottica;
- regolare il keystone del proiettore;
- centrare il fascio.

Puoi sostituirlo con un'immagine di **blackout totale** o con il logo del teatro:

- **`Show` → `Imposta Immagine di Tappo (Layer 0)…`**
- **`Show` → `Ripristina Tappo Predefinito`**

### Blackout

**`Ctrl+B`** dissolve tutti i layer verso il tappo di sicurezza. È il "buio concordato", diverso dal Panic.

### Panic

**`ESC`** in modalità LIVE è il **taglio a 0 ms**: audio e video spariscono istantaneamente e si torna al nero assoluto. Da usare solo per emergenze reali.

### Guide di calibrazione

**`Shift+F7`** attiva/disattiva sul proiettore un overlay con:

- griglia di calibrazione al 10% con mirino centrale;
- contorni numerati delle superfici virtuali;
- banner di stato.

Serve ad allineare fisicamente le ottiche con la scena illuminata.

---

## 13. Controllo remoto: Web e OSC

I servizi di rete sono **spenti per default**. Si attivano da **`F8`** (`Show` → `📡 Controllo Remoto LAN`).

### Attivare i servizi

Nel dialogo, il pulsante in alto mostra lo stato:

- **🔴 SERVIZI REMOTI: OFF (Avvia)** → clicca per attivare;
- **🟢 ATTIVI** → servizi in esecuzione.

### Telecomando operatore (smartphone)

1. Apri la scheda **📱 Telecomando Operatore**.
2. Inquadra il **QR code** con lo smartphone (stessa rete Wi-Fi del computer).
3. Il browser si apre già autenticato e mostra un **GO tattile grande**, più i comandi essenziali.

### Monitor regista (sola lettura)

Nella scheda **👁️ Monitor Regista** trovi un secondo QR code e il pulsante **📋 Copia Link Monitor**. Il link si può incollare in chat: il regista vede la scaletta e i layer in tempo reale **senza alcun pulsante attivo**. Impossibile causare errori da lì.

### Sicurezza PIN

- PIN a **6 cifre**, generabile con **🎲 Nuovo PIN Casuale**.
- **Includi PIN nel QR**: accesso immediato con la fotocamera.
- Dopo **5 errori** l'accesso viene bloccato.
- **⛔ Disconnetti Tutti** revoca le sessioni attive.

Attiva il PIN se il Wi-Fi del teatro è condiviso con il pubblico.

### Automazione OSC

Scheda **🎛️ Automazione OSC && Porte**. Porta UDP default **53000**.

| Comando | Effetto |
|---|---|
| `/go`, `/cue/go`, `/blindcue/go [id]` | GO sullo standby, o sulla cue indicata |
| `/stop`, `/blackout`, `/cue/stop` | Blackout verso il tappo |
| `/panic`, `/cue/panic` | Stop immediato |
| `/pause`, `/resume`, `/pause_toggle` | Pausa/ripresa globale |
| `/next`, `/prev` | Cue successiva/precedente |
| `/cue/<id>/go` | Lancia una cue specifica |
| `/cue/<id>/select` | Seleziona una cue |
| `/volume <0.0–1.0>` | Volume master |

OSC supporta PIN opzionale e whitelist di indirizzi IP.

---

## 14. Salvataggio, autosave e recupero

### Formato

I progetti sono file **JSON** con estensione **`.blindcue`**: leggibili, ispezionabili e riparabili con un editor di testo. Nessun formato binario chiuso.

### Salvataggio

| Comando | Scorciatoia |
|---|---|
| Nuovo spettacolo | `Ctrl+N` |
| Apri | `Ctrl+O` |
| Salva | `Ctrl+S` |
| Salva con nome | `Ctrl+Shift+S` |

Il salvataggio è **atomico**: se manca la corrente durante la scrittura, il file precedente resta intatto.

### Autosave e Crash Recovery

- **Autosave ogni 30 secondi** (e a ogni modifica) in `~/.config/blindcue/autosave.json`.
- Se BlindCue si chiude in modo anomalo, al riavvio propone il **ripristino** dell'ultima sessione.
- Alla chiusura regolare l'autosave viene marcato come pulito e il prompt non compare.

> **Dove salva l'autosave?** Solo in `~/.config/blindcue/autosave.json`: **non scrive mai** nel tuo file `.blindcue`. Il file di progetto viene toccato esclusivamente quando premi `Ctrl+S` o scegli **Salva con nome**. L'autosave serve come rete di sicurezza dopo un crash o una chiusura accidentale; dopo il ripristino conviene salvare subito con un nome per fissare il lavoro.

### Apri recenti

Sotto **File → Apri recenti** trovi gli ultimi **5 progetti** aperti o salvati, dal più recente. Il percorso completo appare nel tooltip; se un file è stato spostato o cancellato la voce resta visibile con l'etichetta `(non trovato)` e, selezionandola, viene rimossa dall'elenco con un avviso. In fondo al sottomenu c'è **Svuota elenco recenti**. L'elenco vive nelle impostazioni dell'applicazione, non nel progetto, quindi non viaggia con il file `.blindcue`.

### Undo / Redo

Fino a **40 passaggi**, con `Ctrl+Z` / `Ctrl+Shift+Z` / `Ctrl+Y`. Anche le operazioni distruttive (eliminazione, raggruppamento) sono annullabili.

---

<a id="scorciatoie"></a>
## 15. Scorciatoie

### Spettacolo

| Tasto | Azione |
|---|---|
| `SPAZIO` | GO — esegue la cue in standby |
| `ESC` | PANIC in LIVE; stop anteprima in Progetto |
| `Ctrl+B` | Blackout verso il tappo |
| `F5` / `Ctrl+L` | Entra/esci dalla Modalità LIVE |

### Editing scaletta

| Tasto | Azione |
|---|---|
| `Del` / `Backspace` | Elimina le cue selezionate |
| `Alt+↑` / `Alt+↓` | Sposta la cue su o giù |
| `Ctrl+G` | Raggruppa in scena |
| `Ctrl+Shift+G` | Estrai la cue dal gruppo |
| `F2` | Modifica la sigla di copione (Q) nella cella selezionata |
| `Ctrl+Z` | Annulla |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Ripeti |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` | Nuovo / Apri / Salva / Salva con nome |

### Forma d'onda

| Tasto | Azione |
|---|---|
| `I` | Aggancia IN al playhead |
| `O` | Aggancia OUT al playhead |
| Rotella | Zoom 1x–32x ancorato al cursore |
| `Shift` + rotella | Scorri in orizzontale |
| Tasto centrale + trascina | Panoramica |

### Finestre e strumenti

| Tasto | Azione |
|---|---|
| `F7` | Studio superfici di proiezione e mapping |
| `Shift+F7` | Guide di calibrazione sul proiettore |
| `F8` | Controllo remoto LAN (Web e OSC) |

---

## 16. Emergenze in scena

| Situazione | Azione | Effetto |
|---|---|---|
| La battuta arriva prima del previsto | `SPAZIO` | La cue in standby parte subito |
| Pausa imprevista a scena aperta | **PAUSA TUTTO** | Congela tutto senza perdere il punto |
| Scena finita, serve buio concordato | `Ctrl+B` | Dissolvenza morbida verso il tappo |
| Guasto o emergenza reale | `ESC` | Taglio a 0 ms, nero assoluto |

**Differenza fondamentale**: il **Blackout** dissolve; il **Panic** taglia. Il primo è parte dello spettacolo, il secondo è un'emergenza.

---

## 17. Risoluzione dei problemi

### Dove trovo il log di BlindCue

BlindCue scrive un log rotante (massimo 2 MB, con 3 copie storiche) nella cartella dati dell'utente:

| Sistema | Percorso |
|---|---|
| Linux | `~/.local/share/BlindCue/blindcue.log` |
| macOS | `~/Library/Application Support/BlindCue/blindcue.log` |
| Windows | `%APPDATA%\BlindCue\blindcue.log` |

Il log è la prima cosa da guardare dopo un blocco o un comportamento anomalo: contiene anche le **eccezioni non gestite** (interfaccia e thread di servizio) con lo stack completo. Avvia con `--debug` solo per una diagnosi approfondita: il livello DEBUG rallenta l'interfaccia.

### Il proiettore mostra il desktop

- **Causa**: schermo duplicato, oppure uscita non assegnata al secondo monitor.
- **Soluzione**: imposta "Estendi schermo" nel sistema operativo, poi verifica in `⚙ Dispositivi · Uscite` che lo schermo di uscita sia quello del proiettore.

### I due proiettori non si uniscono in una superficie unica

- **Causa**: il compositore Wayland non consente a una finestra di attraversare due uscite, oppure l'opzione è attiva ma c'è un solo schermo esterno.
- **Soluzione**: controlla l'avviso nel dialogo `⚙ Dispositivi · Uscite`; avvia la sessione in X11 se serve lo span; verifica che entrambi i proiettori siano in "Estendi schermo" e non duplicati.

### Su Linux non parte: `could not load the Qt platform plugin "xcb"`

- **Causa**: mancano le librerie runtime Qt `xcb`.
- **Soluzione**: rilancia `python3 setup.py` (le installa automaticamente), oppure installa a mano `libxcb-cursor0` e `libxkbcommon-x11-0` (nomi variabili per distribuzione).

### L'app si apre ma non vedo l'uscita

- Con un solo schermo l'uscita è una finestra flottante: cerca la finestra, oppure usa `--output-screen 0`.
- Su Wayland alcuni compositori richiedono di autorizzare la finestra a schermo intero: controlla le impostazioni del compositore.

### Una cue è rossa e dice OFFLINE

- **Causa**: file spostato, rinominato, o su un supporto scollegato.
- **Soluzione**: ricollega il supporto, oppure seleziona la cue e aggiorna il percorso con **Sfoglia…**.

### L'audio in sala non si sente, in cuffia sì

- **Causa**: dispositivo master errato o volume a zero.
- **Soluzione**: controlla il routing in `⚙ Dispositivi · Uscite` e il volume generale.

### Il telefono non si collega al telecomando

- **Causa**: reti Wi-Fi diverse, firewall, o servizi spenti.
- **Soluzione**: stessa LAN per entrambi i dispositivi; apri TCP `8080` e UDP `53000` nel firewall; verifica che i servizi siano su **🟢 ATTIVI**.

### Mancano waveform, loudness o normalizzazione

- **Causa**: FFmpeg non installato.
- **Soluzione**: rilancia l'installer (lo installa), oppure installa `ffmpeg` e riavvia. All'avvio BlindCue scrive un avviso esplicito nel log.

### Il video scatta durante lo spettacolo

- Verifica di non avere analisi pesanti in corso (waveform/loudness).
- Passa al profilo **Eco** o **Standard**.
- Controlla che il driver GPU sia aggiornato: su Linux serve VA-API.
- Chiudi browser e applicazioni pesanti sul computer di regia.

### Ho perso le modifiche per un crash

- Riavvia BlindCue: al boot propone il **ripristino dall'autosave**. Accetta e salva subito con un nome.

### Il reticolo di calibrazione resta sempre visibile

- Non è un errore: è il Layer 0 che compare quando non c'è nulla in onda.
- Per cambiarlo o rimuoverlo: `Show` → `Imposta Immagine di Tappo`.

---

## 18. Domande frequenti

**Devo assolutamente avere due schermi?**
No, ma è fortemente consigliato. Con un solo schermo l'uscita diventa una finestra flottante e il pubblico potrebbe vedere il desktop.

**Posso usare due proiettori con contenuti diversi?**
Sì. In `⚙ Dispositivi · Uscite` scegli **Due uscite indipendenti**: servono due proiettori esterni oltre al monitor di regia. Ogni uscita ha tre layer propri e le cue si assegnano ad A o B dall'ispettore. Se invece vuoi un'unica immagine continua sui due proiettori, usa **Superficie unica (span)**.

Se la modalità Due uscite indipendenti **non** è attiva, le cue assegnate all'uscita B vengono proiettate sull'uscita A: nulla va perso e nulla finisce su una finestra invisibile. Disattivando la modalità duale mentre un contenuto è in onda sull'uscita B, BlindCue lo interrompe e lo segnala nella barra di stato, per non lasciare audio senza controlli.

**BlindCue manda dati su internet?**
No. Non c'è alcun servizio cloud. I servizi Web e OSC sono locali e spenti finché non li attivi.

**Posso usarlo su Windows o macOS?**
Sì. Nasce per Linux, ma la stessa base gira su macOS (Apple Silicon e Intel) e Windows 10/11.

**I file originali vengono modificati?**
No. Normalizzazione, crop, tagli, fade, envelope e sezioni sono tutti **non distruttivi**. L'ottimizzazione dinamica crea una copia e conserva l'originale.

**Cosa succede se due cue occupano lo stesso layer?**
BlindCue segnala il conflitto in fase di progetto. A runtime, la cue nuova prende il layer e la precedente viene declassata a LOADED.

**Tre layer sono sufficienti?**
Per la grande maggioranza degli spettacoli sì: ogni layer gestisce video e immagine in modo indipendente, con crossfade A/B. Con le superfici virtuali puoi anche dividere lo stesso layer su più aree di proiezione.

**Posso pilotarlo da un mixer luci?**
Sì, via OSC. Qualsiasi consolle o software che invii pacchetti OSC può lanciare GO, blackout, Panic e cue specifiche.

**Come faccio un backup dello spettacolo?**
Copia il file `.blindcue`. Contiene scaletta, tempi, fade, superfici e percorsi dei media. Conserva anche i file media nella stessa struttura di cartelle, oppure usa percorsi assoluti.
