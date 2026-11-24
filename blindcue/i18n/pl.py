"""Polish UI translations for BlindCue.

Keys are the original UI strings found in the source code (mostly Italian).
Placeholders ``{}`` mark variable parts; the translation must contain the
same number of ``{}`` (or ``{0}``, ``{1}``... to reorder them).
Generated from the translation sheets; edit freely.
"""

T: dict[str, str] = {
    'Loudness scan failed or file has no audio.':
        'Analiza głośności nie powiodła się albo plik nie ma dźwięku.',
    'Ottimizzazione dinamica fallita.':
        'Optymalizacja dynamiki nie powiodła się.',
    'No audio data decoded.':
        'Nie zdekodowano danych audio.',
    'Nessun secondo schermo rilevato: la superficie unica richiede almeno un proiettore esterno.':
        'Nie wykryto drugiego ekranu: wspólna powierzchnia wymaga co najmniej jednego zewnętrznego projektora.',
    "Su Wayland un'unica finestra che copre due uscite può essere rifiutata dal compositore. Se i due proiettori non si uniscono, usa X11 oppure la modalità due uscite indipendenti.":
        'W Wayland jedno okno na dwa wyjścia może zostać odrzucone przez kompozytor. Jeśli projektory się nie połączą, użyj X11 albo trybu dwóch niezależnych wyjść.',
    'La doppia uscita indipendente richiede due proiettori esterni (oltre al monitor di regia). Con un solo schermo esterno usa la modalità singola o la superficie unica.':
        'Dwa niezależne wyjścia wymagają dwóch zewnętrznych projektorów (oprócz monitora reżyserki). Przy jednym ekranie zewnętrznym użyj trybu pojedynczego albo wspólnej powierzchni.',
    'Predefinito di Sistema':
        'Domyślne systemowe',
    'Audio Device':
        'Urządzenie audio',
    'Doppia uscita non disponibile':
        'Podwójne wyjście niedostępne',
    'Span non applicabile':
        'Rozciągnięcie (span) niedostępne',
    'Doppia uscita persa: schermo esterno rimosso':
        'Utracono podwójne wyjście: odłączono ekran zewnętrzny',
    'Configurazione doppia uscita fallita':
        'Konfiguracja podwójnego wyjścia nie powiodła się',
    'Logaritmica (Naturale)':
        'Logarytmiczna (naturalna)',
    'S-Curve Morbida':
        'Łagodna krzywa S',
    'Lineare':
        'Liniowa',
    "Impossibile avviare '{}': file danneggiato o codec non supportato":
        "Nie można uruchomić '{}': plik uszkodzony lub nieobsługiwany kodek",
    'con due uscite attive il limite fluido è 1 video per uscita':
        'przy dwóch aktywnych wyjściach płynny limit to 1 wideo na wyjście',
    'oltre 3 video il proiettore perde fluidità':
        'powyżej 3 filmów projektor traci płynność',
    '{} video su uscita A':
        '{} wideo na wyjściu A',
    '{} video su uscita B':
        '{} wideo na wyjściu B',
    'ATTENZIONE: Errore Live L{} ({})':
        'UWAGA: błąd Live L{} ({})',
    '⚠ Carico video elevato: ':
        '⚠ Duże obciążenie wideo: ',
    'Uscita B disattivata: interrotti ':
        'Wyjście B wyłączone: zatrzymano ',
    'Layer {} · Uscita B':
        'Warstwa {} · Wyjście B',
    'Conflitto {}: {} elementi ({}) condividono il {} in modalità simultanea. Assegna layer differenti (L1, L2, L3).':
        'Konflikt {}: {} elementy ({}) współdzielą {} w trybie „Wszystko naraz”. Przypisz różne warstwy (L1, L2, L3).',
    "Conflitto {}: Viene attivato in simultanea con {} nel gruppo '{}' sullo stesso {}. Assegna un layer differente (L1, L2, L3).":
        "Konflikt {}: uruchamiane równocześnie z {} w grupie '{}' na tym samym {}. Przypisz inną warstwę (L1, L2, L3).",
    'Conflitto {}: Avvio simultaneo (Follow Simultaneo) con {} sullo stesso {}. Assegna un layer differente (L1, L2, L3).':
        'Konflikt {}: start „Razem” z {} na tym samym {}. Przypisz inną warstwę (L1, L2, L3).',
    'Singolo schermo':
        'Jeden ekran',
    'Superficie unica (span)':
        'Wspólna powierzchnia (span)',
    'Due uscite indipendenti':
        'Dwa niezależne wyjścia',
    '{}: file non trovato ({})':
        '{}: nie znaleziono pliku ({})',
    '{}: copia non riuscita ({})':
        '{}: kopiowanie nie powiodło się ({})',
    'Schermo Intero (Default)':
        'Pełny ekran (domyślnie)',
    'Schermo Intero (100%)':
        'Pełny ekran (100%)',
    'Proiezione a schermo intero standard sul monitor / proiettore selezionato':
        'Standardowa projekcja na pełnym ekranie wybranego monitora / projektora',
    'Doppio Proiettore: Metà Sinistra (0% – 50%)':
        'Dwa projektory: lewa połowa (0% – 50%)',
    'Occupa il primo proiettore in una configurazione desktop estesa a 2 proiettori':
        'Zajmuje pierwszy projektor w pulpicie rozszerzonym na 2 projektory',
    'Doppio Proiettore: Metà Destra (50% – 100%)':
        'Dwa projektory: prawa połowa (50% – 100%)',
    'Occupa il secondo proiettore in una configurazione desktop estesa a 2 proiettori':
        'Zajmuje drugi projektor w pulpicie rozszerzonym na 2 projektory',
    'Doppio Proiettore: Span Panoramico (0% – 100%)':
        'Dwa projektory: panorama (0% – 100%)',
    'Si estende su entrambi i proiettori affiancati come un unico grande fondale panoramico':
        'Rozciąga się na oba projektory obok siebie jako jedno duże panoramiczne tło',
    'Triplo Proiettore: Sinistra (1/3)':
        'Trzy projektory: lewy (1/3)',
    'Occupa il proiettore 1/3 in configurazione a 3 schermi affiancati':
        'Zajmuje projektor 1/3 w układzie 3 ekranów obok siebie',
    'Triplo Proiettore: Centro (2/3)':
        'Trzy projektory: środkowy (2/3)',
    'Occupa il proiettore centrale in configurazione a 3 schermi affiancati':
        'Zajmuje środkowy projektor w układzie 3 ekranów obok siebie',
    'Triplo Proiettore: Destra (3/3)':
        'Trzy projektory: prawy (3/3)',
    'Occupa il proiettore 3/3 in configurazione a 3 schermi affiancati':
        'Zajmuje projektor 3/3 w układzie 3 ekranów obok siebie',
    'Picture-in-Picture (PiP Basso DX)':
        'Obraz w obrazie (PiP prawy dolny róg)',
    "Riquadro d'angolo per sovrapporre una seconda immagine o video sopra il fondale":
        'Okienko w rogu do nałożenia drugiego obrazu lub filmu na tło',
    'Quadro 4:3 Centrale':
        'Kadr 4:3 na środku',
    'Area classica 4:3 centrata su schermo 16:9 con bande laterali pulite':
        'Klasyczny obszar 4:3 na środku ekranu 16:9 z czystymi pasami po bokach',
    'Colonna / Scenografia SX':
        'Kolumna / scenografia lewa',
    'Superficie verticale ideale per banner o colonna scenica sinistra':
        'Pionowa powierzchnia na baner lub lewą kolumnę sceniczną',
    'Colonna / Scenografia DX':
        'Kolumna / scenografia prawa',
    'Superficie verticale ideale per banner o colonna scenica destra':
        'Pionowa powierzchnia na baner lub prawą kolumnę sceniczną',
    '{} da {} (tot: {})':
        '{} z {} (razem: {})',
    'Nessun comando ricevuto':
        'Nie odebrano żadnego polecenia',
    '⏹ Blocco':
        '⏹ Stop',
    '⏹ Blocco (Default): esegue solo la cue selezionata (Pre+Durata+Post) e attende GO manuale.':
        '⏹ Stop (domyślnie): odtwarza tylko zaznaczony cue (Pre+Czas+Post) i czeka na ręczne GO.',
    '⤵ Auto-GO':
        '⤵ Auto-GO',
    '⤵ GO Automatico: al termine di Pre-Delay + Durata + Post-Delay avvia automaticamente la cue successiva.':
        '⤵ Automatyczne GO: po Pre-Delay + Czas + Post-Delay następny cue startuje sam.',
    '⇉ Simult.':
        '⇉ Razem',
    '⇉ Simultanea: al GO avvia subito insieme la cue successiva (che rispetta comunque il proprio Pre-Delay).':
        '⇉ Razem z następnym: przy GO od razu startuje też następny cue (z zachowaniem jego Pre-Delay).',
    'SCALETTA CUE (Sequence List)':
        'LISTA CUE (kolejność)',
    '0 Cue':
        '0 cue',
    'Standby: Nessuna':
        'Następny: brak',
    '🎭 VAI IN LIVE':
        '🎭 PRZEJDŹ DO LIVE',
    'Apri la modalità semplificata LIVE (Show Mode) centrata su Scaletta, GO, PAUSA TUTTO e PANIC [F5 / Ctrl+L]':
        'Otwórz uproszczony tryb LIVE (Show Mode): lista cue, GO, PAUZA WSZYSTKO i PANIC [F5 / Ctrl+L]',
    'Modalità LIVE Show':
        'Tryb LIVE (przedstawienie)',
    'Passa alla schermata di regia semplificata per il live.':
        'Przełącz na uproszczony ekran prowadzenia przedstawienia.',
    'Scaletta delle Cue':
        'Lista cue',
    'Elenco sequenziale delle scene e dei media. Naviga con freccia Su e Giù, premi Spazio per il GO.':
        'Kolejna lista scen i mediów. Strzałki w górę i w dół wybierają, Spacja = GO.',
    '+ Video':
        '+ Wideo',
    'Aggiungi file video alla scaletta':
        'Dodaj plik wideo do listy cue',
    'Aggiungi Video':
        'Dodaj wideo',
    'Apre la finestra di selezione per aggiungere un file video alla scaletta.':
        'Otwiera okno wyboru pliku wideo do dodania do listy cue.',
    '+ Audio':
        '+ Audio',
    'Aggiungi file audio alla scaletta':
        'Dodaj plik audio do listy cue',
    'Aggiungi Audio':
        'Dodaj audio',
    'Apre la finestra di selezione per aggiungere un file audio alla scaletta.':
        'Otwiera okno wyboru pliku audio do dodania do listy cue.',
    '+ Foto':
        '+ Zdjęcie',
    'Aggiungi immagine / foto statica (Layer 1-3)':
        'Dodaj zdjęcie / obraz statyczny (warstwa 1-3)',
    'Aggiungi Foto o Immagine':
        'Dodaj zdjęcie lub obraz',
    'Apre la finestra di selezione per aggiungere una foto o grafica statica alla scaletta.':
        'Otwiera okno wyboru zdjęcia lub grafiki do dodania do listy cue.',
    '+ Gruppo':
        '+ Grupa',
    'Crea un gruppo di cue / scena (Ctrl+G)':
        'Utwórz grupę cue / scenę (Ctrl+G)',
    'Aggiungi Gruppo o Scena':
        'Dodaj grupę lub scenę',
    'Crea un nuovo contenitore di gruppo o scena sincronizzata.':
        'Tworzy nowy kontener grupy lub zsynchronizowanej sceny.',
    '▲ Su':
        '▲ W górę',
    'Sposta la cue in alto (Alt+↑)':
        'Przesuń cue w górę (Alt+↑)',
    '▼ Giù':
        '▼ W dół',
    'Sposta la cue in basso (Alt+↓)':
        'Przesuń cue w dół (Alt+↓)',
    '🗑 Elimina':
        '🗑 Usuń',
    'Rimuovi la cue dalla scaletta (Canc)':
        'Usuń cue z listy (Del)',
    '⏹ Blocco: attende il prossimo GO manuale':
        '⏹ Stop: czeka na następne ręczne GO',
    'Selezione multipla mista — clicca una modalità per applicarla a tutte':
        'Mieszane zaznaczenie — kliknij tryb, aby zastosować go do wszystkich',
    'Seleziona una o più cue per scegliere Blocco / Auto-GO / Simultanea':
        'Zaznacz jeden lub więcej cue, aby wybrać Stop / Auto-GO / Razem',
    '⇉ SIMULT':
        '⇉ RAZEM',
    '⤵ CASCATA':
        '⤵ KASKADA',
    '⏹ PASSO':
        '⏹ KROK',
    '🎲 RND':
        '🎲 LOS',
    '🔁 LOOP':
        '🔁 PĘTLA',
    'Numero progressivo di posizione in scaletta (doppio click = GO)':
        'Numer pozycji na liście (dwuklik = GO)',
    'Richiamo copione Q (doppio click per modificare)':
        'Oznaczenie Q ze scenariusza (dwuklik, aby edytować)',
    'Nome personalizzato scena / file (doppio click per rinominare; Ctrl/Shift+Click per selezione multipla)':
        'Własna nazwa sceny / pliku (dwuklik, aby zmienić; Ctrl/Shift+klik = zaznaczanie wielu)',
    '🎨 Colore Scena / Gruppo':
        '🎨 Kolor sceny / grupy',
    'Nome / Media':
        'Nazwa / media',
    '🎬 MULTI-TRACK':
        '🎬 WIELOŚCIEŻKA',
    '{} Cue':
        '{} cue',
    '📁 Raggruppa in Scena (Ctrl+G)':
        '📁 Zgrupuj w scenę (Ctrl+G)',
    '🎬 Apri Studio Timeline Gruppo…':
        '🎬 Otwórz studio osi czasu grupy…',
    '▶ / ▼ Espandi o Collassa Gruppo':
        '▶ / ▼ Rozwiń lub zwiń grupę',
    '🔓 Sciogli Gruppo (Ctrl+Shift+G)':
        '🔓 Rozgrupuj (Ctrl+Shift+G)',
    '⤵ AUTO':
        '⤵ AUTO',
    '⏏ Estrai dal Gruppo (Ctrl+Shift+G)':
        '⏏ Wyjmij z grupy (Ctrl+Shift+G)',
    '⇉ SIM':
        '⇉ RAZ',
    'Configurazione Hardware & Uscite di Regia':
        'Konfiguracja sprzętu i wyjść',
    '⚙️ Dispositivi di Uscita & Ottimizzazione Hardware':
        '⚙️ Urządzenia wyjściowe i optymalizacja sprzętu',
    '⚡ Profilo Hardware · Modalità Adattiva':
        '⚡ Profil sprzętowy · tryb adaptacyjny',
    'Profilo Prestazioni:':
        'Profil wydajności:',
    'Auto (Consigliato — Rilevamento Intelligente)':
        'Auto (zalecane — inteligentne wykrywanie)',
    '🍃 Eco (Muletto / <=4GB RAM / Risparmio Risorse)':
        '🍃 Eko (starszy sprzęt / <=4GB RAM / oszczędzanie zasobów)',
    '⚡ Standard (Bilanciato per Live)':
        '⚡ Standard (zbalansowany do występów)',
    '🚀 Performance (Workstation Multi-Core / Pro)':
        '🚀 Wydajność (wielordzeniowa stacja robocza / Pro)',
    '🔊 Routing Uscite Audio di Regia':
        '🔊 Kierowanie wyjść audio',
    '🔊 Master Spettacolo (Impianto Sala / PA Pubblico):':
        '🔊 Główne wyjście (nagłośnienie sali / publiczność):',
    '🎧 Pre-Ascolto / Monitor (Cuffia Tecnico / PFL):':
        '🎧 Odsłuch / monitor (słuchawki operatora / PFL):',
    "💡 <i>Suggerimento:</i> Assegna la Cuffia per ascoltare in anteprima i brani nell'Ispettore o nella Scaletta senza che il pubblico in sala senta nulla. Se usi una sola scheda, entrambi usano l'uscita predefinita.":
        '💡 <i>Wskazówka:</i> Przypisz słuchawki, aby odsłuchiwać utwory w Inspektorze lub na liście cue bez słyszenia ich przez publiczność. Przy jednej karcie dźwiękowej oba używają wyjścia domyślnego.',
    '🖥️ Uscita Video Live (Proiettore / Display Esterno)':
        '🖥️ Wyjście wideo Live (projektor / ekran zewnętrzny)',
    'Schermo Live Output:':
        'Ekran wyjścia Live:',
    '🔄 Rileva':
        '🔄 Wykryj',
    'Modalità Uscita:':
        'Tryb wyjścia:',
    '🖥️ Singolo schermo (una sola uscita)':
        '🖥️ Jeden ekran (jedno wyjście)',
    '🖥️🖥️ Superficie unica — span su più proiettori':
        '🖥️🖥️ Wspólna powierzchnia — rozciągnięta na kilka projektorów',
    '🖥️ ⇄ 🖥️ Due uscite indipendenti (contenuti diversi)':
        '🖥️ ⇄ 🖥️ Dwa niezależne wyjścia (różne treści)',
    "💡 BlindCue proietta solo sugli schermi esterni al monitor di regia. Con un solo proiettore tutto va lì; con due proiettori puoi scegliere quale alimenta l'uscita A e quale l'uscita B dal pannello dei layer.":
        '💡 BlindCue wyświetla obraz tylko na ekranach innych niż monitor reżyserki. Przy jednym projektorze wszystko trafia na niego; przy dwóch w panelu warstw wybierasz, który obsługuje wyjście A, a który B.',
    'Annulla':
        'Anuluj',
    '✓ Applica e Salva':
        '✓ Zastosuj i zapisz',
    "Due uscite separate e indipendenti: ogni proiettore ha i propri 3 layer. Assegna ogni cue all'uscita A o B nell'Ispettore.":
        'Dwa oddzielne, niezależne wyjścia: każdy projektor ma własne 3 warstwy. Przypisz każdy cue do wyjścia A lub B w Inspektorze.',
    "I proiettori esterni saranno uniti in un'unica tela continua.":
        'Zewnętrzne projektory zostaną połączone w jedną ciągłą powierzchnię.',
    'Nessun dispositivo rilevato (Default)':
        'Nie wykryto urządzenia (domyślne)',
    "⚠️ Nessuna uscita audio rilevata dal sistema operativo: l'audio userà l'impianto predefinito.":
        '⚠️ System nie wykrył żadnego wyjścia audio: dźwięk użyje urządzenia domyślnego.',
    ' (Predefinito)':
        ' (domyślne)',
    '⚠️ Una sola uscita audio rilevata: il pre-ascolto in cuffia richiede una seconda scheda audio collegata (USB/DAC). Senza di essa il monitor PFL userebbe lo stesso impianto del pubblico.':
        '⚠️ Wykryto tylko jedno wyjście audio: odsłuch w słuchawkach wymaga drugiej karty dźwiękowej (USB/DAC). Bez niej odsłuch PFL szedłby na to samo nagłośnienie co dla publiczności.',
    ' [Primario / Regia]':
        ' [główny / reżyserka]',
    ' [Esterno / Proiettore]':
        ' [zewnętrzny / projektor]',
    '🍃 <b>Modalità ECO / Muletto:</b> Limitazione thread di calcolo a 2 core, gestione memoria leggera, protezione RAM <= 4GB (perfetta per portatili datati come MacBook Air 2014).':
        '🍃 <b>Tryb EKO / starszy sprzęt:</b> obliczenia ograniczone do 2 rdzeni, oszczędne zarządzanie pamięcią, ochrona przy RAM do 4 GB (idealny dla starszych laptopów, np. MacBook Air 2014).',
    'Proiettori coinvolti: {}.':
        'Użyte projektory: {}.',
    'Nessun proiettore esterno rilevato.':
        'Nie wykryto zewnętrznego projektora.',
    'Schermi coinvolti: {}.':
        'Użyte ekrany: {}.',
    'Nessuno schermo esterno rilevato.':
        'Nie wykryto ekranu zewnętrznego.',
    '🚀 <b>Modalità PERFORMANCE:</b> Multi-threading completo (fino a 8+ core), precaricamento istantaneo e massime prestazioni per workstation con GPU dedicata.':
        '🚀 <b>Tryb WYDAJNOŚĆ:</b> pełna wielowątkowość (do 8+ rdzeni), natychmiastowe wczytywanie i maksymalna wydajność dla stacji z osobną kartą graficzną.',
    '⚡ <b>Modalità STANDARD:</b> Bilanciamento ottimale tra consumo di risorse e fluidità live.':
        '⚡ <b>Tryb STANDARD:</b> optymalna równowaga między zużyciem zasobów a płynnością na żywo.',
    'Trascina qui file multimediali\n(Video, Audio, Immagini)\nper aggiungerli alla regia':
        'Przeciągnij tutaj pliki\n(wideo, audio, obrazy),\naby dodać je do pokazu',
    "🎬 Studio Timeline Compositore Gruppo — '{}'":
        "🎬 Studio osi czasu grupy — '{}'",
    'Montaggio multi-traccia non distruttivo (Layer 1, 2, 3) · Modifica solo i file del gruppo':
        'Nieniszcząca edycja wielościeżkowa (warstwy 1, 2, 3) · zmienia tylko pliki grupy',
    '⏱ Durata Scena: 00:00.00':
        '⏱ Czas sceny: 00:00.00',
    '↺ Annulla':
        '↺ Anuluj',
    'Annulla Modifiche Timeline':
        'Odrzuć zmiany osi czasu',
    'Chiude lo studio senza salvare le modifiche apportate alla timeline.':
        'Zamyka studio bez zapisywania zmian na osi czasu.',
    '✓ Salva e Sincronizza nel Gruppo':
        '✓ Zapisz i zsynchronizuj z grupą',
    'Salva e Sincronizza nel Gruppo':
        'Zapisz i zsynchronizuj z grupą',
    "Salva ritardi, layer, tagli e dissolvenze all'interno delle cue del gruppo.":
        'Zapisuje opóźnienia, warstwy, przycięcia i przejścia w cue grupy.',
    '📦 ELEMENTI DEL GRUPPO ({} file)':
        '📦 ELEMENTY GRUPY (plików: {})',
    'Lista File del Gruppo':
        'Lista plików grupy',
    'Elenco dei file assegnati al gruppo. Clicca per selezionare una clip.':
        'Lista plików przypisanych do grupy. Kliknij, aby wybrać klip.',
    '🔒 File vincolati al gruppo per evitare inserimenti accidentali o file estranei.':
        '🔒 Pliki zablokowane w grupie, aby uniknąć przypadkowego dodania obcych plików.',
    '🖥️ ANTEPRIMA MULTI-LAYER & TRASPORTO':
        '🖥️ PODGLĄD WIELOWARSTWOWY I STEROWANIE',
    '▶ SCHERMO ANTEPRIMA SANDBOX\nComposizione Multi-Layer sincronizzata':
        '▶ EKRAN PODGLĄDU (PIASKOWNICA)\nzsynchronizowana kompozycja wielowarstwowa',
    '⏮ Inizio':
        '⏮ Początek',
    "Riavvolgi all'Inizio":
        'Przewiń na początek',
    'Porta la testina di riproduzione al secondo zero.':
        'Ustawia głowicę odtwarzania na zerowej sekundzie.',
    '▶  Play':
        '▶  Odtwórz',
    'Play o Pausa Anteprima Gruppo':
        'Odtwórz lub wstrzymaj podgląd grupy',
    'Avvia o mette in pausa la riproduzione sincronizzata multi-canale.':
        'Uruchamia lub wstrzymuje zsynchronizowane odtwarzanie wielokanałowe.',
    '🛠️ MODIFICATORI CLIP ATTIVA':
        '🛠️ USTAWIENIA AKTYWNEGO KLIPU',
    'Nessuna clip selezionata':
        'Nie wybrano klipu',
    '⏱ TIMELINE DELLE 3 TRACCE (Layer 3 Sopra ➔ Layer 1 Sfondo)':
        '⏱ OŚ CZASU 3 ŚCIEŻEK (warstwa 3 na wierzchu ➔ warstwa 1 tło)',
    '🧲 Snap a griglia (0.25s)':
        '🧲 Przyciągaj do siatki (0,25 s)',
    '🔍 - Zoom Out':
        '🔍 - Pomniejsz',
    '🔍 + Zoom In':
        '🔍 + Powiększ',
    'Canvas Timeline a 3 Layer':
        'Oś czasu 3 warstw',
    'Compositore visivo a 3 layer per allineare temporalmente i file del gruppo.':
        'Wizualny kompozytor 3 warstw do wyrównania plików grupy w czasie.',
    'L3 · OVERLAY / FOTO':
        'L3 · NAKŁADKA / ZDJĘCIE',
    'Traccia superiore (Overlay)':
        'Górna ścieżka (nakładka)',
    'L2 · VIDEO / AUDIO 2':
        'L2 · WIDEO / AUDIO 2',
    'Traccia intermedia':
        'Środkowa ścieżka',
    'L1 · SFONDO / BASE':
        'L1 · TŁO / PODSTAWA',
    'Traccia di fondo (Background)':
        'Dolna ścieżka (tło)',
    'Layer:':
        'Warstwa:',
    'Layer 1 (Sfondo)':
        'Warstwa 1 (tło)',
    'Layer 2 (Intermedio)':
        'Warstwa 2 (środek)',
    'Layer 3 (Overlay)':
        'Warstwa 3 (nakładka)',
    'Avvio (s):':
        'Start (s):',
    'Taglio IN:':
        'Przycięcie IN:',
    'Fade In:':
        'Pojawianie:',
    'Fade Out:':
        'Wygaszanie:',
    'Volume:':
        'Głośność:',
    'Opacità:':
        'Krycie:',
    '{} | 🖥️ CPU: {}C | 💾 RAM: {}GB | 🎮 GPU: {} ({})':
        '{} | 🖥️ CPU: {}C | 💾 RAM: {}GB | 🎮 GPU: {} ({})',
    "<h3>Architettura Hardware & Prestazioni BlindCue</h3><p><b>Profilo Attivo:</b> <b style='color:#00bcd4;'>{}</b> ({})</p><p><b>Processore (CPU):</b> {}<br/>• Core / Thread rilevati: <b>{} core</b></p><p><b>Memoria RAM di Sistema:</b><br/>• Totale: <b>{} GB</b> ({} MB)<br/>• Disponibile: <b>{} GB</b> ({} MB)</p><p><b>Scheda Video (GPU):</b> {}<br/>• Accelerazione Hardware: <b>{}</b><br/>• Schermi Rilevati: <b>{}</b><br/>• Piattaforma: <b>{} ({})</b></p><hr/><h4>Ottimizzazioni per la Massima Stabilità Live:</h4><ul><li><b>GPU Offloading:</b> Compositing Layer 0..3 su GPU tramite Wayland EGL/OpenGL. Zero carico di ridisegno pixel sulla CPU.</li><li><b>Decodifica Video Hardware:</b> QtMultimedia e FFmpeg interrogano automaticamente VA-API / NVDEC per frame zero-copy.</li><li><b>Protezione GC Live:</b> In modalità LIVE il Garbage Collector di Python viene posticipato per prevenire micro-lag durante le Cue.</li><li><b>Isolamento Threading:</b> Worker asincroni limitati per garantire latenza istantanea su UI e Audio.</li></ul><p style='color: #00e676;'><b>Risultato:</b> Stabilità assoluta garantita sia su portatili da 4GB di RAM che su workstation multi-core.</p>":
        "<h3>Sprzęt i wydajność BlindCue</h3><p><b>Aktywny profil:</b> <b style='color:#00bcd4;'>{}</b> ({})</p><p><b>Procesor (CPU):</b> {}<br/>• Wykryte rdzenie / wątki: <b>{}</b></p><p><b>Pamięć RAM:</b><br/>• Razem: <b>{} GB</b> ({} MB)<br/>• Dostępne: <b>{} GB</b> ({} MB)</p><p><b>Karta graficzna (GPU):</b> {}<br/>• Akceleracja sprzętowa: <b>{}</b><br/>• Wykryte ekrany: <b>{}</b><br/>• Platforma: <b>{} ({})</b></p><hr/><h4>Optymalizacje dla stabilności na żywo:</h4><ul><li><b>Odciążenie GPU:</b> składanie warstw 0..3 na karcie graficznej (EGL/OpenGL). Procesor nie przerysowuje pikseli.</li><li><b>Sprzętowe dekodowanie wideo:</b> QtMultimedia i FFmpeg same korzystają z VA-API / NVDEC.</li><li><b>Ochrona GC na żywo:</b> w trybie LIVE odśmiecanie pamięci Pythona jest odkładane, by uniknąć mikroprzycięć podczas cue.</li><li><b>Izolacja wątków:</b> ograniczona liczba wątków w tle, aby interfejs i dźwięk reagowały natychmiast.</li></ul><p style='color: #00e676;'><b>Efekt:</b> stabilna praca zarówno na laptopach z 4 GB RAM, jak i na wielordzeniowych stacjach.</p>",
    'Scelta manuale operatore':
        'Ręczny wybór operatora',
    '🍃 ECO':
        '🍃 EKO',
    'BlindCue — Info Hardware & Accelerazione':
        'BlindCue — informacje o sprzęcie i akceleracji',
    'About BlindCue':
        'O programie BlindCue',
    "<h2>{}</h2><p><b>Version {}</b></p><p>Cue player for live shows: video, audio, images and text on a projector.</p><p>Based on <b>{}</b> by {} (MIT licence)<br><a href='{}'>{}</a></p><p>Polish version: <a href='{}'>{}</a></p>":
        "<h2>{}</h2><p><b>Wersja {}</b></p><p>Program do prowadzenia przedstawień: wideo, dźwięk, zdjęcia i napisy na projektorze.</p><p>Na podstawie programu <b>{}</b> autorstwa {} (licencja MIT)<br><a href='{}'>{}</a></p><p>Wersja polska: <a href='{}'>{}</a></p>",
    'Auto (RAM {}GB / {} Core: profilo salva-memoria attivo)':
        'Auto (RAM {}GB / {} rdzeni: aktywny profil oszczędzania pamięci)',
    '🚀 PRO':
        '🚀 PRO',
    '⚡ STD':
        '⚡ STD',
    'Apple Metal / GPU ({})':
        'Apple Metal / GPU ({})',
    'Auto (RAM {}GB / {} Core: massime prestazioni e multi-screen)':
        'Auto (RAM {}GB / {} rdzeni: maksymalna wydajność i wiele ekranów)',
    'Auto (RAM {}GB / {} Core: bilanciamento standard)':
        'Auto (RAM {}GB / {} rdzeni: standardowa równowaga)',
    'Software Renderer':
        'Renderowanie programowe',
    'Display Principale':
        'Główny ekran',
    'Disattivazione... {}s':
        'Wyłączanie... {}s',
    'Attivazione... {}s':
        'Włączanie... {}s',
    'Native (Automatico)':
        'Natywne (automatycznie)',
    '16:9 (Widescreen)':
        '16:9 (panoramiczny)',
    '4:3 (Standard)':
        '4:3 (standardowy)',
    '21:9 (Ultrawide)':
        '21:9 (ultraszeroki)',
    '1:1 (Quadrato)':
        '1:1 (kwadrat)',
    'L1: Sfondo':
        'L1: Tło',
    'Layer 1 (Default): Livello di sfondo o base scena':
        'Warstwa 1 (domyślna): tło lub podstawa sceny',
    'L2: Principale':
        'L2: Główna',
    'Layer 2: Livello multimediale intermedio (sopra L1)':
        'Warstwa 2: środkowa warstwa mediów (nad L1)',
    'L3: Overlay':
        'L3: Nakładka',
    'Layer 3: Livello superiore in primo piano (grafica, loghi, titoli)':
        'Warstwa 3: wierzchnia warstwa (grafiki, logo, napisy)',
    'Attende GO manuale (default)':
        'Czeka na ręczne GO (domyślnie)',
    'Avvia la successiva dopo Pre+Durata+Post':
        'Uruchamia następny po Pre+Czas+Post',
    'Avvia insieme la successiva sul GO':
        'Uruchamia następny razem przy GO',
    '⇉ Simultaneo':
        '⇉ Wszystko naraz',
    'Fire All: tutti i media del gruppo partono contemporaneamente sul GO.':
        'Wszystko naraz: wszystkie media grupy startują jednocześnie przy GO.',
    '⤵ Sequenziale':
        '⤵ Po kolei',
    'Cascata: un solo GO lancia tutta la sequenza interna rispettando i ritardi Pre/Durata/Post.':
        'Kaskada: jedno GO uruchamia całą sekwencję z zachowaniem opóźnień Pre/Czas/Post.',
    '⏹ Passo-Passo':
        '⏹ Krok po kroku',
    "Capitolo teatrale: ogni pressione manuale di GO avanza di un elemento all'interno della scena.":
        'Rozdział teatralny: każde ręczne GO przechodzi o jeden element w scenie.',
    '🎲 Random / Var.':
        '🎲 Losowo',
    'Sceglie a caso un elemento del gruppo evitando la ripetizione immediata.':
        'Wybiera losowy element grupy, unikając powtórzenia pod rząd.',
    '🔁 Loop Scena':
        '🔁 Zapętl scenę',
    'Cicla continuamente tutti gli elementi interni finché non viene dato lo stop.':
        'Odtwarza w kółko wszystkie elementy, aż do zatrzymania.',
    'ISPETTORE CUE (Nessuna cue selezionata)':
        'INSPEKTOR CUE (nie wybrano cue)',
    'Cursore orizzontale da {} a {}.':
        'Suwak poziomy od {} do {}.',
    'Pannello Ispettore Cue - Schede':
        'Panel Inspektora cue - karty',
    'Schede proprietà: Info e Tempi, Video e Foto, Audio e Tagli, Gruppo.':
        'Karty właściwości: info i czasy, wideo i zdjęcia, audio i przycięcia, grupa.',
    '1 · IDENTITÀ IN COPIONE & COLORE GRUPPO':
        '1 · OZNACZENIE ZE SCENARIUSZA I KOLOR',
    'I box scuri sono modificabili; usa un colore per dividere scene o atti in Scaletta.':
        'Ciemne pola można edytować; kolorem rozdzielisz sceny lub akty na liście cue.',
    'es. Q-2, Q-9a, Sc.1...':
        'np. Q-2, Q-9a, Sc.1...',
    'Sigla di copione: resta legata alla cue anche se riordini la scaletta':
        'Oznaczenie ze scenariusza: zostaje przy cue nawet po zmianie kolejności',
    'Sigla Q Copione':
        'Oznaczenie Q',
    'Identificativo o sigla di copione della cue.':
        'Identyfikator lub oznaczenie cue ze scenariusza.',
    'Titolo descrittivo in scaletta...':
        'Opisowy tytuł na liście cue...',
    'Nome Cue':
        'Nazwa cue',
    'Titolo o etichetta descrittiva della cue nella scaletta.':
        'Tytuł lub opis cue na liście.',
    'Attacco battuta, luci, note tecniche...':
        'Kwestia, światła, uwagi techniczne...',
    'Note di Regia':
        'Uwagi reżyserskie',
    "Note tecniche o didascalie per l'operatore di regia.":
        'Uwagi techniczne lub podpowiedzi dla operatora.',
    'Colore:':
        'Kolor:',
    '📁 In Scena':
        '📁 W scenie',
    '⏏ Estrai dal Gruppo':
        '⏏ Wyjmij z grupy',
    "Rimuove questa cue dal gruppo e la sposta all'esterno della scena (Ctrl+Shift+G)":
        'Usuwa ten cue z grupy i przenosi go poza scenę (Ctrl+Shift+G)',
    '2 · LAYER DI USCITA (SOVRAPPOSIZIONE)':
        '2 · WARSTWA WYJŚCIA (KOLEJNOŚĆ)',
    'Ordine visivo sullo schermo: L3 (sopra) → L2 → L1 → L0 Tappo di sicurezza.':
        'Kolejność na ekranie: L3 (wierzch) → L2 → L1 → L0 zaślepka bezpieczeństwa.',
    'Proiettore:':
        'Projektor:',
    '3 · TEMPI DI INCASTRO (PRE · DURATA · POST)':
        '3 · CZASY (PRE · CZAS TRWANIA · POST)',
    'GO  ▶  [⏳ Pre]  ▶  [▶ Media / Durata]  ▶  [⏱ Post]':
        'GO  ▶  [⏳ Pre]  ▶  [▶ Media / Czas]  ▶  [⏱ Post]',
    'Ritardo di partenza dopo il GO per incastrare la cue con altri layer':
        'Opóźnienie startu po GO, aby zgrać cue z innymi warstwami',
    'Ritardo di Partenza Pre-Delay':
        'Opóźnienie startu (Pre-Delay)',
    "Secondi di ritardo dopo il GO prima dell'avvio della cue.":
        'Sekundy opóźnienia po GO przed startem cue.',
    'Attesa extra dopo la fine del media prima di uscire o passare alla successiva':
        'Dodatkowe czekanie po końcu mediów przed przejściem do następnego',
    'Attesa Finale Post-Delay':
        'Czekanie końcowe (Post-Delay)',
    'Secondi di attesa dopo il termine del media.':
        'Sekundy czekania po zakończeniu mediów.',
    'Durata di permanenza in Live delle immagini statiche (0 = infinita)':
        'Jak długo zdjęcia zostają na ekranie Live (0 = bez końca)',
    'Durata Immagine Hold Time':
        'Czas wyświetlania obrazu',
    'Durata in secondi per le immagini statiche (0 = infinita).':
        'Czas w sekundach dla zdjęć (0 = bez końca).',
    'Solo immagini (0 = ∞)':
        'Tylko obrazy (0 = ∞)',
    'Dopo:':
        'Potem:',
    '🎯 Cue · Tempi':
        '🎯 Cue · czasy',
    "Suggerimento: puoi anche trascinare il riquadro o gli 8 bordi direttamente sull'Anteprima Pre-Viz 16:9.":
        'Wskazówka: ramkę i jej 8 krawędzi możesz też przeciągać bezpośrednio w podglądzie Pre-Viz 16:9.',
    '1 · POSIZIONAMENTO, ZOOM & TRASPARENZA':
        '1 · POZYCJA, ZOOM I PRZEZROCZYSTOŚĆ',
    'Superficie:':
        'Ekran:',
    'Assegna la cue a uno schermo virtuale o superficie di proiezione/mapping':
        'Przypisz cue do ekranu wirtualnego lub powierzchni projekcji/mappingu',
    '📐 Gestisci...':
        '📐 Zarządzaj...',
    'Apri lo Studio Superfici di Proiezione & Video Mapping (F7)':
        'Otwórz studio powierzchni projekcji i mappingu wideo (F7)',
    'Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx)':
        'Przesunięcie poziome (-1,00 = lewo, 0,00 = środek, +1,00 = prawo)',
    'Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso)':
        'Przesunięcie pionowe (-1,00 = góra, 0,00 = środek, +1,00 = dół)',
    'Sposta a sinistra (-0.01)':
        'Przesuń w lewo (-0,01)',
    'Sposta in alto (-0.01)':
        'Przesuń w górę (-0,01)',
    'Sposta in basso (+0.01)':
        'Przesuń w dół (+0,01)',
    'Sposta a destra (+0.01)':
        'Przesuń w prawo (+0,01)',
    '⌖ Centro':
        '⌖ Środek',
    'Ripristina posizione al centro (0.00, 0.00)':
        'Przywróć pozycję na środek (0,00, 0,00)',
    'Scala:':
        'Skala:',
    'Ripristina scala a 1.0x':
        'Przywróć skalę 1,0x',
    'Ripristina opacità al 100%':
        'Przywróć krycie 100%',
    'Formato:':
        'Format:',
    'Forza le proporzioni del riquadro in Anteprima e Live':
        'Wymusza proporcje kadru w podglądzie i na Live',
    '2 · RITAGLIO BORDI (CROP)':
        '2 · PRZYCIĘCIE KRAWĘDZI (CROP)',
    'Scegli % oppure pixel reali della sorgente per tagliare i bordi.':
        'Wybierz % albo rzeczywiste piksele źródła, aby przyciąć krawędzie.',
    'Imposta il ritaglio in percentuale (0.0% – 99.0%)':
        'Ustaw przycięcie w procentach (0,0% – 99,0%)',
    'Imposta il ritaglio esatto in pixel rispetto alla risoluzione del file':
        'Ustaw dokładne przycięcie w pikselach względem rozdzielczości pliku',
    '⟲ Reset':
        '⟲ Reset',
    'Rimuove il ritaglio e mostra il fotogramma intero':
        'Usuwa przycięcie i pokazuje cały kadr',
    'Ritaglio bordo sinistro':
        'Przycięcie lewej krawędzi',
    'Ritaglio bordo destro':
        'Przycięcie prawej krawędzi',
    'Ritaglio bordo superiore':
        'Przycięcie górnej krawędzi',
    'Ritaglio bordo inferiore':
        'Przycięcie dolnej krawędzi',
    '3 · ROTAZIONE':
        '3 · OBRÓT',
    'Ruota immagine o video. Per le immagini compare anche il ritaglio poligonale.':
        'Obróć obraz lub wideo. Dla obrazów pojawia się też przycięcie wielokątne.',
    'Rotazione:':
        'Obrót:',
    'Rotazione in gradi attorno al centro del riquadro (-180° … +180°). 0° = dritto.':
        'Obrót w stopniach wokół środka kadru (-180° … +180°). 0° = prosto.',
    'Ruota di 90° in senso antiorario':
        'Obróć o 90° w lewo',
    "Riporta l'immagine dritta (0°)":
        'Wyprostuj obraz (0°)',
    'Ruota di 90° in senso orario':
        'Obróć o 90° w prawo',
    '✂ Disegna maschera…':
        '✂ Narysuj maskę…',
    "Ritaglia l'immagine lungo un percorso poligonale disegnato a mano":
        'Przytnij obraz wzdłuż ręcznie narysowanego wielokąta',
    '✖ Rimuovi':
        '✖ Usuń',
    "Rimuove la maschera poligonale e mostra l'immagine intera":
        'Usuwa maskę wielokątną i pokazuje cały obraz',
    'Nessuna maschera':
        'Brak maski',
    '🖼 Video · Foto':
        '🖼 Wideo · zdjęcie',
    "Suggerimento: Dissolvenze (Fade In/Out) attive anche sulle Immagini; inviluppi avanzati e Sezioni A/B/C nella Forma d'Onda.":
        'Wskazówka: przejścia (Fade In/Out) działają też dla obrazów; zaawansowane obwiednie i sekcje A/B/C są w widoku przebiegu.',
    '1 · VOLUME PRINCIPALE (AUDIO / VIDEO)':
        '1 · GŁOŚNOŚĆ GŁÓWNA (AUDIO / WIDEO)',
    "Livello base del media; puoi disegnare variazioni nel tempo direttamente sulla Forma d'Onda.":
        'Podstawowy poziom mediów; zmiany w czasie możesz rysować bezpośrednio na przebiegu.',
    'Ripristina volume al 100%':
        'Przywróć głośność 100%',
    '2 · DISSOLVENZE (FADE IN / OUT)':
        '2 · PRZEJŚCIA (FADE IN / OUT)',
    "Applicate dolcemente all'ingresso e all'uscita su Audio, Video e Immagini a durata.":
        'Łagodnie stosowane na początku i końcu audio, wideo i obrazów z czasem.',
    'Dissolvenza in Entrata Fade-In':
        'Pojawianie (Fade-In)',
    'Durata in secondi della dissolvenza in ingresso da nero o silenzio.':
        'Czas w sekundach pojawiania się z czerni lub ciszy.',
    'Dissolvenza in Uscita Fade-Out':
        'Wygaszanie (Fade-Out)',
    'Durata in secondi della dissolvenza in chiusura a nero o silenzio.':
        'Czas w sekundach wygaszania do czerni lub ciszy.',
    '3 · TAGLIO TEMPORALE (PUNTI IN / OUT)':
        '3 · PRZYCIĘCIE CZASU (PUNKTY IN / OUT)',
    'Imposta dove inizia e finisce la traccia (tasti rapidi [I] / [O] sulla Testina della Timeline).':
        'Ustaw, gdzie ścieżka się zaczyna i kończy (skróty [I] / [O] na głowicy osi czasu).',
    'Punto di Inizio In-Point':
        'Punkt początku (In)',
    'Posizione iniziale di riproduzione in minuti, secondi e centesimi.':
        'Pozycja startu w minutach, sekundach i setnych.',
    'Punto di Fine Out-Point':
        'Punkt końca (Out)',
    'Posizione finale di taglio o fine riproduzione.':
        'Pozycja końca przycięcia lub odtwarzania.',
    'Ripristina IN a 0.00s e OUT a Fine':
        'Przywróć IN na 0,00 s i OUT na koniec',
    '🔁  4 · RIPETI CUE IN LOOP':
        '🔁  4 · ZAPĘTL CUE',
    '5 · LIVELLAMENTO & LOUDNESS (EBU R128)':
        '5 · WYRÓWNANIE GŁOŚNOŚCI (EBU R128)',
    'Calcola il volume percepito (LUFS) per livellare tracce troppo basse o troppo alte senza distorsione.':
        'Mierzy odczuwaną głośność (LUFS), aby wyrównać zbyt ciche lub zbyt głośne ścieżki bez zniekształceń.',
    '📊 Loudness: Non analizzato':
        '📊 Głośność: nie zbadano',
    '🔍 Analizza':
        '🔍 Zbadaj',
    'Analizza il volume percepito EBU R128 in background con FFmpeg':
        'Zbadaj odczuwaną głośność EBU R128 w tle za pomocą FFmpeg',
    '🎚 Applica Guadagno EBU R128 (-16 LUFS) per questo file':
        '🎚 Zastosuj wzmocnienie EBU R128 (-16 LUFS) do tego pliku',
    "Applica l'offset di guadagno non distruttivo sul player per pareggiare il volume con le altre cue.":
        'Stosuje nieniszczącą korektę wzmocnienia w odtwarzaczu, aby wyrównać głośność z innymi cue.',
    '🛠 Ottimizza Dinamica (Compressore / Limiter)':
        '🛠 Optymalizuj dynamikę (kompresor / limiter)',
    "Per file complessi o registrati male: applica il compressore broadcast EBU R128 a due passate con True-Peak Limiter per appiattire gli sbalzi e proteggere l'impianto.":
        'Dla trudnych lub źle nagranych plików: stosuje dwuprzebiegowy kompresor EBU R128 z limiterem True-Peak, aby spłaszczyć skoki i chronić nagłośnienie.',
    '↺ Ripristina Originale':
        '↺ Przywróć oryginał',
    "Annulla l'ottimizzazione e torna al file media originale":
        'Cofnij optymalizację i wróć do oryginalnego pliku',
    '🎵 Audio · Tagli':
        '🎵 Audio · przycięcia',
    '1 · IDENTITÀ SCENA / GRUPPO & COLORE':
        '1 · OZNACZENIE SCENY / GRUPY I KOLOR',
    'I gruppi organizzano più media in una singola riga collassabile in Scaletta e Live.':
        'Grupy łączą kilka mediów w jeden zwijany wiersz na liście cue i w trybie Live.',
    'es. G-1, Atto 1, Scena A...':
        'np. G-1, Akt 1, Scena A...',
    'Sigla di copione del gruppo: resta legata al gruppo se riordini la scaletta':
        'Oznaczenie grupy ze scenariusza: zostaje przy grupie po zmianie kolejności',
    'Titolo scena o sequenza...':
        'Tytuł sceny lub sekwencji...',
    'Note di regia o indicazioni palco per il gruppo...':
        'Uwagi reżyserskie lub wskazówki sceniczne dla grupy...',
    'Pre-Wait:':
        'Pre-Wait:',
    'Attesa prima di avviare il gruppo alla pressione del GO.':
        'Czekanie przed startem grupy po naciśnięciu GO.',
    'Post-Wait:':
        'Post-Wait:',
    "Attesa al termine dell'esecuzione prima di passare alla cue successiva.":
        'Czekanie po zakończeniu przed przejściem do następnego cue.',
    '2 · COMPORTAMENTO AL GO (MODALITÀ SCENA)':
        '2 · DZIAŁANIE PRZY GO (TRYB SCENY)',
    'Determina come vengono eseguiti i media contenuti nel gruppo quando si preme GO.':
        'Określa, jak odtwarzane są media grupy po naciśnięciu GO.',
    '3 · ELEMENTI INTERNI AL GRUPPO':
        '3 · ELEMENTY GRUPY',
    'Lista dei media appartenenti a questo gruppo. Usa i pulsanti per espandere o gestire i membri.':
        'Lista mediów w tej grupie. Przyciskami rozwiniesz grupę lub zarządzisz elementami.',
    '📁 0 cue nel gruppo':
        '📁 0 cue w grupie',
    '▶ Collassa / ▼ Espandi':
        '▶ Zwiń / ▼ Rozwiń',
    'Mostra o nascondi i figli del gruppo nella tabella Scaletta':
        'Pokaż lub ukryj elementy grupy na liście cue',
    '✕ Rimuovi Cue':
        '✕ Usuń cue',
    'Rimuove la cue selezionata dalla lista dal gruppo (torna al livello principale)':
        'Usuwa zaznaczony cue z grupy (wraca na poziom główny)',
    '🔓 Sciogli Gruppo':
        '🔓 Rozgrupuj',
    'Elimina il contenitore del gruppo e rilascia tutte le sue cue in scaletta':
        'Usuwa kontener grupy i zostawia wszystkie jej cue na liście',
    '🎬  APRI STUDIO TIMELINE DEL GRUPPO (3 LAYER)':
        '🎬  OTWÓRZ STUDIO OSI CZASU GRUPY (3 WARSTWY)',
    'Studio Timeline Multi-Track':
        'Studio osi czasu (wielościeżkowe)',
    'Apre la finestra di composizione multi-traccia a 3 layer per sincronizzare i file del gruppo.':
        'Otwiera okno kompozycji 3 warstw do synchronizacji plików grupy.',
    'Apre la finestra extra Studio Timeline per sincronizzare visivamente i file del gruppo\nsulle 3 tracce layer (L1, L2, L3) con righello millisecondi, tagli e anteprima multi-canale.':
        'Otwiera dodatkowe okno studia osi czasu do wizualnej synchronizacji plików grupy\nna 3 ścieżkach warstw (L1, L2, L3) z linijką milisekund, przycięciami i podglądem wielokanałowym.',
    '📁 Gruppo · Scena':
        '📁 Grupa · scena',
    'Non definita':
        'Nieokreślona',
    '📊 {} LUFS | Picco: {} dBFS | Auto-Gain: {}{} dB':
        '📊 {} LUFS | Szczyt: {} dBFS | Auto-wzmocnienie: {}{} dB',
    'Q (Copione):':
        'Q (scenariusz):',
    'Nome Cue:':
        'Nazwa cue:',
    'Note Regia:':
        'Uwagi:',
    'A · Schermo 1':
        'A · Ekran 1',
    "Questa cue viene proiettata dall'uscita A (primo proiettore).":
        'Ten cue jest wyświetlany na wyjściu A (pierwszy projektor).',
    'B · Schermo 2':
        'B · Ekran 2',
    "Questa cue viene proiettata dall'uscita B (secondo proiettore indipendente).":
        'Ten cue jest wyświetlany na wyjściu B (drugi, niezależny projektor).',
    'Pre-Delay:':
        'Opóźnienie:',
    'Post-Delay:':
        'Czekaj po:',
    'Durata Img:':
        'Czas obrazu:',
    'Pos X:':
        'Poz. X:',
    'Pos Y:':
        'Poz. Y:',
    'Unità:':
        'Jednostka:',
    'Sinistra:':
        'Lewo:',
    'Destra:':
        'Prawo:',
    'Alto:':
        'Góra:',
    'Basso:':
        'Dół:',
    'Ripetizioni:':
        'Powtórzenia:',
    '∞ Continuo (Infinito)':
        '∞ Ciągle (bez końca)',
    'Ripeti 2 volte':
        'Powtórz 2 razy',
    'Ripeti 3 volte':
        'Powtórz 3 razy',
    'Ripeti 4 volte':
        'Powtórz 4 razy',
    'Ripeti 5 volte':
        'Powtórz 5 razy',
    'Ripeti 10 volte':
        'Powtórz 10 razy',
    'Personalizzato...':
        'Własne...',
    'Nome Gruppo:':
        'Nazwa grupy:',
    'Manuale':
        'Ręcznie',
    'Maschera: {} punti':
        'Maska: {} punktów',
    "ISPETTORE CUE — {} [{}] '{}'":
        "INSPEKTOR CUE — {} [{}] '{}'",
    'Seleziona una cue':
        'Wybierz cue',
    '0 s = Infinita in Live':
        '0 s = bez końca na Live',
    "Immagine selezionata: trascina il riquadro o gli 8 bordi nell'Anteprima Pre-Viz 16:9.":
        'Wybrano obraz: przeciągnij ramkę lub jej 8 krawędzi w podglądzie Pre-Viz 16:9.',
    'Nota: Cue Immagine — Fade In/Out e inviluppo Opacità attivi. Volume, Tagli e Loop valgono per Audio/Video.':
        'Uwaga: cue z obrazem — działają Fade In/Out i obwiednia krycia. Głośność, przycięcia i pętla dotyczą audio/wideo.',
    'ISPETTORE CUE — Selezione Mista ({} cue)':
        'INSPEKTOR CUE — mieszane zaznaczenie ({} cue)',
    '⚠ Selezione mista ({}): seleziona solo file dello stesso tipo per modifiche comuni.':
        '⚠ Mieszane zaznaczenie ({}): zaznacz pliki jednego typu, aby edytować je razem.',
    'ISPETTORE CUE — {} {} (Modifica Multipla)':
        'INSPEKTOR CUE — {} {} (edycja wielu)',
    'Layer misti (clicca L1/L2/L3 per uniformare)':
        'Różne warstwy (kliknij L1/L2/L3, aby ujednolicić)',
    '⚡ MODIFICA MULTIPLA: {} file {} selezionati • {}.\nOgni parametro modificato verrà applicato a tutti gli elementi selezionati.':
        '⚡ EDYCJA WIELU: zaznaczono {} plików {} • {}.\nKażda zmieniona wartość zostanie zastosowana do wszystkich zaznaczonych.',
    '(Multiplo)':
        '(wiele)',
    '[{} file {} selezionati]':
        '[zaznaczono {} plików {}]',
    '▼ Espandi Gruppo in Scaletta':
        '▼ Rozwiń grupę na liście',
    '▶ Collassa Gruppo in Scaletta':
        '▶ Zwiń grupę na liście',
    'Schermo':
        'Ekran',
    "Usa IN / OUT o Forma d'Onda":
        'Użyj IN / OUT lub przebiegu',
    'Nota: Cue Audio selezionata — Posizione, Zoom, Opacità e Ritaglio sono attivi solo per Video e Immagini.':
        'Uwaga: wybrano cue audio — pozycja, zoom, krycie i przycięcie działają tylko dla wideo i obrazów.',
    "Regola Volume, Fade, punti IN/OUT o Loop; usa la Forma d'Onda sotto per curve e Sezioni A/B/C.":
        'Ustaw głośność, przejścia, punkty IN/OUT lub pętlę; przebieg poniżej służy do krzywych i sekcji A/B/C.',
    'Usa IN / OUT del video':
        'Użyj IN / OUT filmu',
    "Video selezionato: trascina posizione/crop sull'Anteprima Pre-Viz e attiva MIRROR LIVE per calibrare sul proiettore.":
        'Wybrano wideo: przeciągnij pozycję/przycięcie w podglądzie Pre-Viz i włącz MIRROR LIVE, aby skalibrować na projektorze.',
    'Regola Volume traccia video, Fade In/Out, punti IN/OUT e Loop (o Sezioni nella Timeline).':
        'Ustaw głośność ścieżki wideo, Fade In/Out, punkty IN/OUT i pętlę (lub sekcje na osi czasu).',
    '📁 Questa cue appartiene a una Scena / Gruppo':
        '📁 Ten cue należy do sceny / grupy',
    'BUIO TOTALE':
        'CAŁKOWITA CZERŃ',
    'STOP IMMEDIATO':
        'NATYCHMIASTOWY STOP',
    'Scaletta Regia LIVE Show':
        'Lista cue do prowadzenia LIVE',
    '▶ Fai partire subito questa Cue (GO Forzato)':
        '▶ Uruchom ten cue teraz (wymuszone GO)',
    '🎯 Imposta come Prossima Cue (Standby)':
        '🎯 Ustaw jako następny cue (standby)',
    '← 🛠 Torna a Progetto  [F5]':
        '← 🛠 Wróć do projektu  [F5]',
    'Torna alla vista Progetto per modificare file, crop, fade o tempi (senza interrompere il Live)':
        'Wróć do widoku projektu, aby edytować pliki, przycięcia, przejścia lub czasy (bez przerywania Live)',
    '● MODALITÀ LIVE (SHOW MODE)':
        '● TRYB LIVE (PRZEDSTAWIENIE)',
    "Azzera Cronometro Spettacolo e riarma l'avvio automatico al prossimo 1° GO":
        'Wyzeruj stoper przedstawienia i uzbrój automatyczny start przy pierwszym GO',
    '▶ STANDBY':
        '▶ NASTĘPNY',
    'Nessuna cue pronta in scaletta':
        'Brak gotowego cue na liście',
    '⏭ Esci da Loop Sezione':
        '⏭ Wyjdź z pętli sekcji',
    '🔒 CONTROLLI LAYER BLOCCATI (Protezione di Sicurezza Regia)\nDi default le barre e i controlli dei layer sono protetti per evitare spostamenti o tagli accidentali.\nPer sbloccare scrub, riavvolgimento e pausa dei singoli layer: tieni premuto per 1,2 secondi.\nQuando sbloccato, un singolo click istantaneo riattiva subito il blocco.':
        '🔒 STEROWANIE WARSTWAMI ZABLOKOWANE (ochrona przed pomyłką)\nDomyślnie paski i przyciski warstw są chronione przed przypadkowym przesunięciem lub ucięciem.\nAby odblokować przewijanie i pauzę pojedynczych warstw: przytrzymaj 1,2 sekundy.\nPo odblokowaniu jedno kliknięcie od razu znowu blokuje.',
    'Blocco di Sicurezza Layer':
        'Blokada bezpieczeństwa warstw',
    'Protezione controlli layer Live. Tieni premuto 1,2 secondi per sbloccare, tocca per ribloccare.':
        'Ochrona sterowania warstwami Live. Przytrzymaj 1,2 s, aby odblokować; dotknij, aby zablokować.',
    'Congela tutti i layer LIVE (Audio, Video, Pre-Delay, Post-Delay e Immagini temporizzate) per ripartire poi dallo stesso istante':
        'Zamraża wszystkie warstwy LIVE (audio, wideo, Pre-Delay, Post-Delay i obrazy z czasem), by potem ruszyć od tego samego momentu',
    'Pausa o Riprendi Tutto':
        'Pauza lub wznowienie wszystkiego',
    'Congela o riprende tutti i layer multimediali attivi.':
        'Zamraża lub wznawia wszystkie aktywne warstwy mediów.',
    '▶   GO  —  PROSSIMA CUE':
        '▶   GO  —  NASTĘPNY CUE',
    'GO - Avvia Cue in Standby':
        'GO - uruchom cue w standby',
    'Manda in esecuzione la cue pronta in standby. Tasto di scelta rapida: Spazio.':
        'Uruchamia cue gotowy w standby. Skrót klawiszowy: Spacja.',
    'Media / Cue':
        'Media / cue',
    'Tempi · Sequenza':
        'Czasy · kolejność',
    'Layer / Stato':
        'Warstwa / stan',
    '🔒\nBLOCCO\nLAYER\n(Tieni 1,2s)':
        '🔒\nBLOKADA\nWARSTW\n(trzymaj\n1,2 s)',
    '🔓\nLAYER\nATTIVI\n(Click = 🔒)':
        '🔓\nWARSTWY\nAKTYWNE\n(klik = 🔒)',
    '▶  RIPRENDI TUTTO  [IN PAUSA]':
        '▶  WZNÓW WSZYSTKO  [PAUZA]',
    '▼ Espandi Gruppo':
        '▼ Rozwiń grupę',
    '▶ Collassa Gruppo':
        '▶ Zwiń grupę',
    '[{} sez.]':
        '[{} sekc.]',
    'Cronometro Spettacolo in corso (avvio auto al 1° GO o manuale) — Clicca per PAUSA (non ferma i media)':
        'Stoper przedstawienia działa (start przy pierwszym GO lub ręcznie) — kliknij, aby ZATRZYMAĆ (media grają dalej)',
    "Esegui cue in Standby: {} '{}'\nScorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]":
        "Uruchom cue w standby: {} '{}'\nGłówny skrót klawiszowy: [ SPACJA ]",
    'Esegui prossima cue\nScorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]':
        'Uruchom następny cue\nGłówny skrót klawiszowy: [ SPACJA ]',
    'Cronometro Spettacolo in PAUSA — Clicca per RIPRENDERE o usa ↺ per azzerare e riarmare':
        'Stoper przedstawienia ZATRZYMANY — kliknij, aby WZNOWIĆ, albo użyj ↺, aby wyzerować',
    'Durata Spettacolo (Cronometro): parte in automatico al 1° GO oppure clicca qui ora per avviare nelle filate/prove':
        'Czas przedstawienia (stoper): startuje sam przy pierwszym GO albo kliknij tutaj, aby uruchomić na próbie',
    '[Scena]':
        '[Scena]',
    '⤵ Auto-GO al termine':
        '⤵ Auto-GO na końcu',
    '🔁 Loop':
        '🔁 Pętla',
    '⏹ MANUALE':
        '⏹ RĘCZNIE',
    '⇉ + Cue successiva simultanea':
        '⇉ + następny cue razem',
    '⏪ Salta Indietro di 10s':
        '⏪ Cofnij o 10 s',
    '⏪ Salta Indietro di 5s':
        '⏪ Cofnij o 5 s',
    '⏩ Salta Avanti di 10s':
        '⏩ Do przodu o 10 s',
    '⏮ Riavvia da Inizio Cue (In-Point)':
        '⏮ Od początku cue (punkt In)',
    'Controllo emissione in tempo reale sui 3 livelli live:':
        'Sterowanie wyjściem na żywo na 3 warstwach:',
    'Proiettore A:':
        'Projektor A:',
    "Schermo fisico su cui viene proiettata l'uscita A.":
        'Fizyczny ekran, na którym wyświetlane jest wyjście A.',
    'Proiettore uscita A':
        'Projektor wyjścia A',
    'Proiettore B:':
        'Projektor B:',
    "Schermo fisico su cui viene proiettata l'uscita B.":
        'Fizyczny ekran, na którym wyświetlane jest wyjście B.',
    'Proiettore uscita B':
        'Projektor wyjścia B',
    'USCITA B — secondo proiettore indipendente':
        'WYJŚCIE B — drugi, niezależny projektor',
    '⏹ Master Blackout (Tappo) — [ Ctrl+B ]':
        '⏹ Wygaszenie główne (zaślepka) — [ Ctrl+B ]',
    "Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B":
        'Zatrzymuje cały obraz i pokazuje warstwę 0 (zaślepkę) — skrót bezpieczeństwa: Ctrl+B',
    'Master Blackout':
        'Wygaszenie główne',
    "Arresta immediatamente l'output di tutti i layer e torna allo sfondo tappo. Scorciatoia: Ctrl+B.":
        'Natychmiast zatrzymuje obraz na wszystkich warstwach i wraca do zaślepki. Skrót: Ctrl+B.',
    'Tappo (L0): Logo BlindCue (Predefinito)':
        'Zaślepka (L0): logo BlindCue (domyślne)',
    '📁 Cambia Tappo…':
        '📁 Zmień zaślepkę…',
    "Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)":
        'Wybierz własny obraz dla warstwy 0 (plakat, logo wydarzenia, czerń)',
    '🔄 Reset':
        '🔄 Reset',
    'Ripristina il logo predefinito di BlindCue come Layer 0':
        'Przywróć domyślne logo BlindCue jako warstwę 0',
    'Logo BlindCue (Predefinito)':
        'Logo BlindCue (domyślne)',
    '▶ Riprendi Riproduzione':
        '▶ Wznów odtwarzanie',
    'Monitor Uscita Layer Live (L3 Sopra → L1 Sfondo)':
        'Podgląd warstw Live (L3 wierzch → L1 tło)',
    'Live Output Status (Monitor Uscita Schermo Esterno)':
        'Stan wyjścia Live (podgląd ekranu zewnętrznego)',
    'Salta indietro di 10s su {} (utile nelle prove per ripetere la battuta)':
        'Cofnij o 10 s na {} (przydatne na próbach, by powtórzyć kwestię)',
    'Sposta indietro di 10 secondi la testina del {}.':
        'Cofa głowicę {} o 10 sekund.',
    'Metti in Pausa {} (utile durante le prove)':
        'Wstrzymaj {} (przydatne podczas prób)',
    'Riprendi riproduzione (Layer attualmente in Pausa)':
        'Wznów odtwarzanie (warstwa wstrzymana)',
    'Metti in Pausa (utile durante le prove)':
        'Pauza (przydatne podczas prób)',
    '∞ LOOP':
        '∞ PĘTLA',
    'Dissolvenza in uscita e arresto del contenuto su {}.\nLa durata è quella del Fade Out della cue (minimo 0.2 s).\nPROTEZIONE LIVE: tieni premuto 0.6 secondi per confermare, così un clic involontario non taglia nulla.':
        'Wygaś i zatrzymaj treść na {}.\nCzas to Fade Out danego cue (minimum 0,2 s).\nOCHRONA LIVE: przytrzymaj 0,6 sekundy, aby potwierdzić — przypadkowe kliknięcie niczego nie utnie.',
    'Dissolve in uscita e ferma il contenuto sul {} usando il Fade Out della cue. Richiede 0.6 secondi di pressione.':
        'Wygasza i zatrzymuje treść na {} według Fade Out cue. Wymaga przytrzymania 0,6 s.',
    'Fade Out':
        'Wygaś',
    'Dissolvenza in uscita e arresto del contenuto su {}.\nLa durata è quella del Fade Out della cue (minimo 0.2 s).':
        'Wygaś i zatrzymaj treść na {}.\nCzas to Fade Out danego cue (minimum 0,2 s).',
    'Salta indietro di 10s su Layer {} (prove)':
        'Cofnij o 10 s na warstwie {} (próby)',
    'Metti in Pausa Layer {} (prove)':
        'Wstrzymaj warstwę {} (próby)',
    'Video (*.mp4 *.mkv *.avi *.mov *.webm)':
        'Wideo (*.mp4 *.mkv *.avi *.mov *.webm)',
    'Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)':
        'Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)',
    'Image (*.png *.jpg *.jpeg *.bmp *.gif *.webp)':
        'Obrazy (*.png *.jpg *.jpeg *.bmp *.gif *.webp)',
    "Estratta cue '{}' dal gruppo (spostata sopra la scena)":
        "Wyjęto cue '{}' z grupy (przeniesiono nad scenę)",
    "Deleted: {} '{}' (Ctrl+Z per ripristinare)":
        "Usunięto: {} '{}' (Ctrl+Z, aby przywrócić)",
    'Eliminate {} cue selezionate (Ctrl+Z per ripristinare)':
        'Usunięto zaznaczone cue: {} (Ctrl+Z, aby przywrócić)',
    "Estratta cue '{}' dal gruppo (spostata sotto la scena)":
        "Wyjęto cue '{}' z grupy (przeniesiono pod scenę)",
    '— Nessun file selezionato —':
        '— nie wybrano pliku —',
    'Tempi: ':
        'Czasy: ',
    'MODALITÀ PROGETTO — Modifica cue e anteprima riabilitate':
        'PRZYGOTOWANIE — edycja cue i podgląd znowu dostępne',
    'Punti envelope azzerati':
        'Wyzerowano punkty obwiedni',
    'Creato taglio sezione a {}s ({} sezioni)':
        'Utworzono cięcie sekcji w {}s (sekcji: {})',
    'Salta':
        'Pomiń',
    'Sezioni azzerate: ripristinato il file originale':
        'Wyzerowano sekcje: przywrócono oryginalny plik',
    'Spazio insufficiente per dividere ancora in questo punto':
        'Za mało miejsca, by jeszcze raz podzielić w tym punkcie',
    '∞ Infinito':
        '∞ Bez końca',
    'Ritorno a file intero (modalità normale)':
        'Powrót do całego pliku (tryb normalny)',
    'Sezione unita':
        'Sekcja scalona',
    "Creato Gruppo Scena: '{}'":
        "Utworzono grupę sceny: '{}'",
    "Sciolto Gruppo: '{}'":
        "Rozgrupowano: '{}'",
    "Estratta cue '{}' dal gruppo (spostata all'esterno)":
        "Wyjęto cue '{}' z grupy (przeniesiono poza nią)",
    'Nuova Scena / Gruppo':
        'Nowa scena / grupa',
    'Studio Timeline Gruppo':
        'Studio osi czasu grupy',
    "Il gruppo '{}' non contiene ancora file multimediali.\n\nAggiungi prima delle tracce audio, video o immagini al gruppo nella scaletta principale\nper poterle allineare e sincronizzare sulla timeline a 3 layer.":
        "Grupa '{}' nie zawiera jeszcze plików multimedialnych.\n\nNajpierw dodaj do grupy ścieżki audio, wideo lub obrazy na głównej liście cue,\naby wyrównać je i zsynchronizować na osi czasu 3 warstw.",
    "Studio Timeline: Gruppo '{}' sincronizzato con successo ({} file allineati sui layer)":
        "Studio osi czasu: grupa '{}' zsynchronizowana (wyrównano plików: {})",
    'Punto IN spostato sulla testina: {}s':
        'Punkt IN przesunięty na głowicę: {}s',
    'Punti IN e OUT ripristinati: IN = 0.00s, OUT = Fine':
        'Przywrócono punkty IN i OUT: IN = 0,00 s, OUT = koniec',
    'Punto OUT impostato sulla fine del file (Fine)':
        'Punkt OUT ustawiony na koniec pliku',
    'Testina prima di IN: OUT impostato al minimo ({}s)':
        'Głowica przed IN: OUT ustawiony na minimum ({}s)',
    'OUT aggiornato':
        'Zaktualizowano OUT',
    'Punto OUT spostato sulla testina: {}s':
        'Punkt OUT przesunięty na głowicę: {}s',
    'Seleziona Immagine di Tappo (Layer 0)':
        'Wybierz obraz zaślepki (warstwa 0)',
    'Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)':
        'Obrazy (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Wszystkie pliki (*)',
    'Tappo (Layer 0) ripristinato al logo predefinito':
        'Zaślepka (warstwa 0) przywrócona do domyślnego logo',
    'Larghezze standard dei pannelli ripristinate':
        'Przywrócono standardowe szerokości paneli',
    '🔒 Pannelli Bloccati':
        '🔒 Panele zablokowane',
    '🔓 Pannelli Sbloccati (Trascina bordi)':
        '🔓 Panele odblokowane (przeciągnij krawędzie)',
    'Layout bloccato: le larghezze dei 3 pannelli principali sono fisse':
        'Układ zablokowany: szerokości 3 głównych paneli są stałe',
    'Layout sbloccato: trascina i divisori verticali per adattare i pannelli a piacere':
        'Układ odblokowany: przeciągnij pionowe podziałki, aby dopasować panele',
    'Silenzioso (Muto)':
        'Cisza (wyciszone)',
    'Ascolto Attivo':
        'Odsłuch aktywny',
    '{} arrestato e rimosso dal Live':
        '{} zatrzymano i usunięto z Live',
    "Compressione dinamica e normalizzazione EBU R128 per '{}' in corso...":
        "Trwa kompresja dynamiki i normalizacja EBU R128 dla '{}'...",
    "File originale ripristinato per '{}'":
        "Przywrócono oryginalny plik dla '{}'",
    'MODALITÀ JAM / CONTEST ATTIVA — Auto-Gain EBU R128 (-16 LUFS) abilitato su tutti i canali':
        'TRYB JAM / KONKURS AKTYWNY — auto-wzmocnienie EBU R128 (-16 LUFS) na wszystkich kanałach',
    'MODALITÀ JAM / CONTEST DISATTIVATA — Ripristinati livelli originali delle cue':
        'TRYB JAM / KONKURS WYŁĄCZONY — przywrócono oryginalne poziomy cue',
    "Scansione Loudness EBU R128 per '{}' in corso...":
        "Trwa pomiar głośności EBU R128 dla '{}'...",
    "Calcolo guadagno EBU R128 per '{}'...":
        "Obliczanie wzmocnienia EBU R128 dla '{}'...",
    "File sorgente non trovato per l'ottimizzazione dinamica.":
        'Nie znaleziono pliku źródłowego do optymalizacji dynamiki.',
    "Dinamica ottimizzata con successo per '{}' (-16 LUFS, Limiter -1.5 dBFS)":
        "Zoptymalizowano dynamikę dla '{}' (-16 LUFS, limiter -1,5 dBFS)",
    "Analisi Loudness per '{}': {} LUFS (Peak {} dBFS → Gain {}{} dB)":
        "Analiza głośności dla '{}': {} LUFS (szczyt {} dBFS → wzmocnienie {}{} dB)",
    '&File':
        '&Plik',
    'Apri &recenti':
        'Otwórz &ostatnie',
    '&Modifica':
        '&Edycja',
    '↶ &Annulla':
        '↶ &Cofnij',
    '↷ &Ripeti':
        '↷ &Ponów',
    '&Show':
        '&Sterowanie',
    '🎚 Modalità &Jam / Contest (Auto-Gain EBU R128)':
        '🎚 Tryb &Jam / konkurs (auto-wzmocnienie EBU R128)',
    'Abilita il livellamento automatico EBU R128 (-16 LUFS) per contest, jam session e file non calibrati.':
        'Włącza automatyczne wyrównanie EBU R128 (-16 LUFS) dla konkursów, jam session i nieskalibrowanych plików.',
    '&View':
        '&Widok',
    '🎭 Modalità &LIVE (Show Mode)':
        '🎭 Tryb &LIVE (przedstawienie)',
    '🎨 &Tema Interfaccia':
        '🎨 &Motyw interfejsu',
    '🔔 &Segnali Acustici Operatore (Earcons)':
        '🔔 &Sygnały dźwiękowe operatora',
    'Accessibilità Regia: Emette un discreto segnale sonoro di conferma ad ogni GO, STOP e PAUSA.\nUtile per operatori non vedenti o per chi guarda il palco senza guardare il monitor.':
        'Dostępność: przy każdym GO, STOP i PAUZIE odtwarza dyskretny dźwięk potwierdzenia.\nPrzydatne dla niewidomych operatorów lub gdy patrzysz na scenę zamiast na monitor.',
    '📐 &Studio Superfici di Proiezione & Mapping…':
        '📐 Studio &powierzchni projekcji i mappingu…',
    'Gestisci schermi virtuali, keystone a 4 angoli e configurazioni multi-proiettore':
        'Zarządzaj ekranami wirtualnymi, korekcją trapezu 4 narożników i układami wielu projektorów',
    '👁 &Mostra Guide sul Proiettore Live':
        '👁 &Pokaż linie pomocnicze na projektorze',
    'Proietta mire ottiche, griglia di precisione e contorni delle superfici sul palco':
        'Wyświetla plansze testowe, siatkę i obrysy powierzchni na scenie',
    '🔒 &Blocca Larghezza Pannelli':
        '🔒 &Zablokuj szerokość paneli',
    '&Help':
        'Pomo&c',
    'GO (Next Cue) — [ SPAZIO ]':
        'GO (następny cue) — [ SPACJA ]',
    'Caricamento Rapido (Drag && Drop)':
        'Szybkie dodawanie (przeciągnij i upuść)',
    '⚙ Dispositivi · Uscite':
        '⚙ Urządzenia · wyjścia',
    'Configura Master Audio Sala, Cuffia Regia (PFL), Schermo Live e Profilo Hardware (Eco/Pro).':
        'Ustaw główne audio sali, słuchawki operatora (PFL), ekran Live i profil sprzętu (Eko/Pro).',
    'Dispositivi e Uscite Hardware':
        'Urządzenia i wyjścia sprzętowe',
    'Apre il pannello di configurazione delle uscite audio sala, monitor cuffia, schermo video live e profili prestazionali.':
        'Otwiera panel ustawień wyjść audio sali, odsłuchu w słuchawkach, ekranu wideo Live i profili wydajności.',
    '🔒 Layout: Bloccato':
        '🔒 Układ: zablokowany',
    'Blocca o sblocca le larghezze dei 3 pannelli principali (Scaletta, Anteprima, Ispettore).\nDi default è bloccato per evitare spostamenti accidentali; clicca per ridimensionare a piacere.':
        'Blokuje lub odblokowuje szerokości 3 głównych paneli (lista cue, podgląd, inspektor).\nDomyślnie zablokowane, by uniknąć przypadkowych zmian; kliknij, aby zmieniać rozmiar.',
    'Blocca Larghezza Pannelli':
        'Zablokuj szerokość paneli',
    'Attiva o disattiva il blocco delle larghezze dei pannelli di regia per prevenire spostamenti accidentali.':
        'Włącza lub wyłącza blokadę szerokości paneli, aby zapobiec przypadkowym zmianom.',
    'Modalità Jam / Contest (Default: OFF).\nPROTEZIONE REGIA: Tieni premuto per 5 secondi per attivare.\nQuando attiva, applica automaticamente il livellamento sonoro EBU R128 (-16 LUFS)\nsu tutti i media per evitare salti improvvisi di volume durante contest o jam session.\nPer disattivare: tieni premuto 1.5 secondi.':
        'Tryb jam / konkurs (domyślnie: WYŁ.).\nOCHRONA: przytrzymaj 5 sekund, aby włączyć.\nGdy aktywny, automatycznie wyrównuje głośność EBU R128 (-16 LUFS)\nwe wszystkich mediach, by uniknąć nagłych skoków głośności podczas konkursów lub jam session.\nAby wyłączyć: przytrzymaj 1,5 sekundy.',
    'Modalità Jam e Contest Livellamento Audio':
        'Tryb wyrównania głośności jam / konkurs',
    'Attiva o disattiva il livellamento automatico EBU R128 a -16 LUFS. Richiede una pressione continua di 5 secondi per attivare.':
        'Włącza lub wyłącza automatyczne wyrównanie EBU R128 do -16 LUFS. Włączenie wymaga przytrzymania przez 5 sekund.',
    '📡 Remoto: OFF':
        '📡 Zdalnie: WYŁ.',
    "Controllo Remoto LAN per Smartphone/Tablet (Web) e OSC.\nClicca per mostrare il QR Code, l'indirizzo IP e le opzioni di comando.":
        'Zdalne sterowanie w sieci LAN ze smartfona/tabletu (przeglądarka) i OSC.\nKliknij, aby pokazać kod QR, adres IP i opcje poleceń.',
    'Controllo Remoto LAN Web e OSC':
        'Zdalne sterowanie LAN (web i OSC)',
    'Mostra il codice QR per smartphone e la configurazione del server web e OSC.':
        'Pokazuje kod QR dla smartfona oraz ustawienia serwera web i OSC.',
    'Ready — No show loaded':
        'Gotowy — nie wczytano przedstawienia',
    '&New Show':
        '&Nowe przedstawienie',
    '&Open Show…':
        '&Otwórz przedstawienie…',
    '&Save Show':
        '&Zapisz przedstawienie',
    'Save Show &As…':
        'Zapisz &jako…',
    '&Quit':
        'Za&kończ',
    '&GO (Next Cue)':
        '&GO (następny cue)',
    '&Blackout':
        '&Wygaszenie (blackout)',
    'Imposta Immagine di &Tappo (Layer 0)…':
        'Ustaw obraz &zaślepki (warstwa 0)…',
    '&Ripristina Tappo Predefinito':
        '&Przywróć domyślną zaślepkę',
    '⚙️ &Dispositivi & Hardware (Audio / Video / Profilo)…':
        '⚙️ &Urządzenia i sprzęt (audio / wideo / profil)…',
    '📡 &Controllo Remoto LAN (Web & OSC)…':
        '📡 &Zdalne sterowanie LAN (web i OSC)…',
    '↺ &Ripristina Larghezze Standard':
        '↺ &Przywróć standardowe szerokości',
    '&Info Hardware & Accelerazione…':
        '&Informacje o sprzęcie i akceleracji…',
    '&About BlindCue':
        '&O programie BlindCue',
    'Nessun progetto recente':
        'Brak ostatnich projektów',
    'Svuota elenco recenti':
        'Wyczyść listę ostatnich',
    '🎚 Jam: OFF (Tieni 5s)':
        '🎚 Jam: WYŁ. (trzymaj 5 s)',
    '🎚 Jam Mode: ATTIVO':
        '🎚 Tryb jam: WŁ.',
    '{}. {}  (non trovato)':
        '{}. {}  (nie znaleziono)',
    'BlindCue — Ripristino Sessione (Crash Recovery)':
        'BlindCue — przywracanie sesji (po awarii)',
    'È stata rilevata una sessione precedente interrotta o non salvata!\n\n• Data ultimo autosave: {}\n• Cue recuperabili: {}\n\nVuoi ripristinare il progetto da dove era stato interrotto?':
        'Wykryto poprzednią przerwaną lub niezapisaną sesję!\n\n• Data ostatniego autozapisu: {}\n• Cue do odzyskania: {}\n\nCzy przywrócić projekt od miejsca przerwania?',
    'Nuovo show creato':
        'Utworzono nowe przedstawienie',
    'Apri Show BlindCue':
        'Otwórz przedstawienie BlindCue',
    'BlindCue Show (*.blindcue *.json);;Tutti i file (*)':
        'Przedstawienie BlindCue (*.blindcue *.json);;Wszystkie pliki (*)',
    'Salva Show Con Nome':
        'Zapisz przedstawienie jako',
    'BlindCue Show (*.blindcue);;JSON File (*.json)':
        'Przedstawienie BlindCue (*.blindcue);;Plik JSON (*.json)',
    'Salvataggio show':
        'Zapisywanie przedstawienia',
    'Vuoi copiare i file audio/video dentro la cartella dello show?\n\nSì: archivio portatile, lo show si apre anche su un altro PC.\nNo: salva solo i collegamenti ai file originali (nessuna copia).\n\nIn entrambi i casi i file originali non vengono mai modificati.':
        'Czy skopiować pliki audio/wideo do folderu przedstawienia?\n\nTak: przenośne archiwum, przedstawienie otworzy się też na innym komputerze.\nNie: zapisuje tylko odnośniki do oryginalnych plików (bez kopiowania).\n\nW obu przypadkach oryginalne pliki nie są zmieniane.',
    'Sessione ripristinata con successo ({} cue)':
        'Przywrócono sesję (cue: {})',
    'Nuovo Show':
        'Nowe przedstawienie',
    'Ci sono modifiche non salvate nel progetto corrente.\nVuoi salvarle prima di creare un nuovo show?':
        'Bieżący projekt ma niezapisane zmiany.\nZapisać je przed utworzeniem nowego przedstawienia?',
    'Apri Show':
        'Otwórz przedstawienie',
    'Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?':
        'Są niezapisane zmiany.\nZapisać przed otwarciem innego przedstawienia?',
    'Caricato: {} ({} cue)':
        'Wczytano: {} (cue: {})',
    'Chiusura BlindCue':
        'Zamykanie BlindCue',
    'Ci sono modifiche non salvate nel progetto.\nVuoi salvare prima di uscire?':
        'Projekt ma niezapisane zmiany.\nZapisać przed wyjściem?',
    '\n… e altre {} cue':
        '\n… i jeszcze {} cue',
    'Salvato {} con {} file media copiati':
        'Zapisano {}, skopiowano plików mediów: {}',
    '— Inattivo / Nero —':
        '— bezczynny / czerń —',
    'Nuovo Spettacolo':
        'Nowe przedstawienie',
    '{} Cue ({} scene)':
        '{} cue ({} scen)',
    'PROGETTAZIONE: LIVE MIRROR ATTIVO (Modifiche visibili sullo schermo esterno)':
        'PROJEKTOWANIE: LIVE MIRROR WŁ. (zmiany widać na ekranie zewnętrznym)',
    'LIVE MIRROR DISATTIVATO — Anteprima isolata (Pronto per lo spettacolo)':
        'LIVE MIRROR WYŁ. — odizolowany podgląd (gotowe do przedstawienia)',
    'Selezione mista: {} cue':
        'Mieszane zaznaczenie: {} cue',
    'BLACKOUT — Output ripristinato a Layer 0 (Tappo)':
        'WYGASZENIE — obraz wrócił do warstwy 0 (zaślepka)',
    '🚨 PANIC (0ms) — STOP TOTALE ESEGUITO':
        '🚨 PANIC (0 ms) — WSZYSTKO ZATRZYMANE',
    'Scaletta vuota — Aggiungi prima dei file multimediali':
        'Pusta lista cue — najpierw dodaj pliki multimedialne',
    "LIVE → {} '{}' (Layer {}) | Standby: {} '{}'":
        "GRA → {} '{}' (warstwa {}) | Następny: {} '{}'",
    "LIVE → {} '{}' (Layer {}) — Fine scaletta (premi GO per rilanciare)":
        "LIVE → {} '{}' (warstwa {}) — koniec listy (naciśnij GO, aby zacząć od nowa)",
    '↶ Annulla (Ctrl+Z) — Stato precedente ripristinato ({} nel registro)':
        '↶ Cofnij (Ctrl+Z) — przywrócono poprzedni stan ({} w historii)',
    '↷ Ripeti — Modifica ripristinata ({} ripetibili)':
        '↷ Ponów — przywrócono zmianę ({} do ponowienia)',
    'BlindCue – [{}{}] – Director Panel v{}':
        'BlindCue – [{}{}] – Panel reżyserski v{}',
    'Nessuna operazione da annullare':
        'Nie ma czego cofnąć',
    'Nessuna operazione da ripetere':
        'Nie ma czego ponowić',
    'zoom {}%  ·  rotellina = zoom · centrale = sposta · Ctrl+0 = 100%':
        'zoom {}%  ·  kółko = zoom · środkowy = przesuwanie · Ctrl+0 = 100%',
    'Maschera poligonale immagine':
        'Maska wielokątna obrazu',
    'Clic per aggiungere un punto · trascina un punto per spostarlo · clic destro per eliminarlo (minimo 3 punti).\nRotellina del mouse = zoom sul cursore · trascina con il tasto centrale per spostarti · Ctrl+0 = 100%.\nLa linea tratteggiata segue il cursore e mostra il lato successivo: il poligono si chiude da solo.\nIl file originale non viene mai modificato: la maschera viene salvata nel progetto.':
        'Kliknij, aby dodać punkt · przeciągnij punkt, aby go przesunąć · prawy klik usuwa punkt (minimum 3 punkty).\nKółko myszy = zoom w miejscu kursora · przeciąganie środkowym przyciskiem przesuwa widok · Ctrl+0 = 100%.\nLinia przerywana podąża za kursorem i pokazuje kolejny bok: wielokąt zamyka się sam.\nOryginalny plik nie jest zmieniany: maska jest zapisywana w projekcie.',
    '0 punti':
        '0 punktów',
    'Svuota':
        'Wyczyść',
    'Riduci zoom (Ctrl+−)':
        'Pomniejsz (Ctrl+−)',
    'Aumenta zoom (Ctrl++)':
        'Powiększ (Ctrl++)',
    "Torna all'immagine intera (Ctrl+0)":
        'Wróć do całego obrazu (Ctrl+0)',
    'Bordo sfumato':
        'Miękka krawędź',
    'Ammorbidisce il contorno della maschera: 0 = taglio netto.\nLa sfumatura è proporzionata al frame, quindi identica sul proiettore e in Pre-Viz.':
        'Zmiękcza krawędź maski: 0 = ostre cięcie.\nZmiękczenie jest proporcjonalne do kadru, więc wygląda tak samo na projektorze i w Pre-Viz.',
    'Applica':
        'Zastosuj',
    '{} punti':
        '{} punktów',
    'Nessun punto':
        'Brak punktów',
    'Immagine non disponibile':
        'Obraz niedostępny',
    '📐 CALIBRAZIONE SUPERFICI LIVE · Premi F7 per Chiudere':
        '📐 KALIBRACJA POWIERZCHNI LIVE · naciśnij F7, aby zamknąć',
    'BlindCue – Live Output [Monitor Simulato]':
        'BlindCue – wyjście Live [monitor symulowany]',
    'GIUNZIONE 50% (DUAL)':
        'ŁĄCZENIE 50% (PODWÓJNE)',
    ' · ⭕ Ellisse':
        ' · ⭕ Elipsa',
    ' · 🔲 Buco':
        ' · 🔲 Otwór',
    '⭕ BUCO ELLITTICO':
        '⭕ OTWÓR ELIPTYCZNY',
    '⭕ SAGOMA ELLISSE':
        '⭕ KSZTAŁT ELIPSY',
    '🔲 BUCO / FORATURA':
        '🔲 OTWÓR / WYCIĘCIE',
    '🔲 SAGOMA INTERNA':
        '🔲 KSZTAŁT WEWNĘTRZNY',
    '🎵 RIPRODUZIONE AUDIO IN ANTEPRIMA (PRE-VIZ)':
        '🎵 ODTWARZANIE AUDIO W PODGLĄDZIE (PRE-VIZ)',
    'Pre-ascolto attivo in cuffia • Monitor sala mutato':
        'Odsłuch w słuchawkach aktywny • nagłośnienie sali wyciszone',
    "Premi ▶ Play sotto l'anteprima per pre-ascoltare in cuffia":
        'Naciśnij ▶ Odtwórz pod podglądem, aby odsłuchać w słuchawkach',
    '🎬 VIDEO CARICATO IN PRE-VIZ — PREMI PLAY':
        '🎬 WIDEO WCZYTANE DO PRE-VIZ — NACIŚNIJ ODTWÓRZ',
    'ANTEPRIMA PRE-VIZ (Sandbox)':
        'PODGLĄD PRE-VIZ (piaskownica)',
    'Riproduci anteprima / Pre-viz':
        'Odtwórz podgląd / Pre-viz',
    "Metti in pausa l'anteprima":
        'Wstrzymaj podgląd',
    '⏹  Stop':
        '⏹  Stop',
    'Arresta anteprima e riavvolgi':
        'Zatrzymaj podgląd i przewiń na początek',
    "Se attivo (default), l'anteprima è muta. Clicca per ascoltare l'audio su richiesta.":
        'Gdy włączone (domyślnie), podgląd jest wyciszony. Kliknij, aby odsłuchać dźwięk.',
    '🔗 MIRROR LIVE: OFF':
        '🔗 MIRROR LIVE: WYŁ.',
    "Modalità Progettazione: se ATTIVO, le modifiche a Crop, Scala e Posizione vengono proiettate in tempo reale sullo schermo LIVE per calibrare il videoproiettore/schermo.\nIn Spettacolo dal vivo: lasciare DISATTIVATO per isolare completamente l'anteprima.":
        'Tryb projektowania: gdy WŁĄCZONY, zmiany przycięcia, skali i pozycji są od razu wyświetlane na ekranie LIVE, aby skalibrować projektor/ekran.\nPodczas przedstawienia: zostaw WYŁĄCZONY, aby podgląd był całkowicie odizolowany.',
    '🔴 MIRROR: ON':
        '🔴 MIRROR: WŁ.',
    '🔒 MUTE: ON':
        '🔒 ODSŁUCH: WYŁ.',
    '🔊 CUFFIA: ON':
        '🔊 SŁUCHAWKI: WŁ.',
    "\n<b>Indirizzo OSC:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br>\n• <b style='color:#4ade80;'>/go</b> oppure <b>/cue/go</b> &nbsp;→&nbsp; Esegue GO sulla cue in Standby<br>\n• <b style='color:#f87171;'>/panic</b> &nbsp;→&nbsp; Arresto immediato 0ms (Tutti i livelli)<br>\n• <b style='color:#f87171;'>/stop</b> oppure <b>/blackout</b> &nbsp;→&nbsp; Blackout live (Ritorno a Layer 0)<br>\n• <b style='color:#fbbf24;'>/pause</b> oppure <b>/resume</b> &nbsp;→&nbsp; Mette in pausa o riprende l'emissione<br>\n• <b style='color:#38bdf8;'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Sposta la selezione della scaletta<br>\n• <b style='color:#38bdf8;'>/cue/&lt;numero&gt;/go</b> &nbsp;→&nbsp; Esegue subito la cue indicata (es. <i>/cue/3/go</i>)<br>\n• <b style='color:#a855f7;'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Autentica l'IP per inviare comandi protetti\n        ":
        "\n<b>Adres OSC:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br>\n• <b style='color:#4ade80;'>/go</b> lub <b>/cue/go</b> &nbsp;→&nbsp; GO dla cue w standby<br>\n• <b style='color:#f87171;'>/panic</b> &nbsp;→&nbsp; natychmiastowy stop 0 ms (wszystkie warstwy)<br>\n• <b style='color:#f87171;'>/stop</b> lub <b>/blackout</b> &nbsp;→&nbsp; wygaszenie Live (powrót do warstwy 0)<br>\n• <b style='color:#fbbf24;'>/pause</b> lub <b>/resume</b> &nbsp;→&nbsp; pauza lub wznowienie<br>\n• <b style='color:#38bdf8;'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; przesuwa zaznaczenie na liście<br>\n• <b style='color:#38bdf8;'>/cue/&lt;numer&gt;/go</b> &nbsp;→&nbsp; od razu uruchamia wskazany cue (np. <i>/cue/3/go</i>)<br>\n• <b style='color:#a855f7;'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; uwierzytelnia IP do wysyłania chronionych poleceń\n        ",
    '📡 Controllo Remoto LAN (Web & OSC) — BlindCUE':
        '📡 Zdalne sterowanie LAN (web i OSC) — BlindCUE',
    '📡 CONTROLLO REMOTO IN RETE LOCALE (LAN REGIA)':
        '📡 ZDALNE STEROWANIE W SIECI LOKALNEJ (LAN)',
    'Telecomando Operatore (GO/Pause/Panic), Monitor Regista (Sola Lettura) e Server OSC per automazione.':
        'Pilot operatora (GO/pauza/panic), monitor reżysera (tylko podgląd) i serwer OSC do automatyzacji.',
    '🔴 SERVIZI REMOTI: DISATTIVATI (Avvia)':
        '🔴 USŁUGI ZDALNE: WYŁ. (uruchom)',
    '📱 Telecomando Operatore (Master LIVE)':
        '📱 Pilot operatora (sterowanie LIVE)',
    '👁️ Monitor Regista (Sola Lettura)':
        '👁️ Monitor reżysera (tylko podgląd)',
    '🎛️ Automazione OSC && Porte':
        '🎛️ Automatyzacja OSC i porty',
    '🛡️ SICUREZZA REGIA — PROTEZIONE PIN (ANTI-BURLONE)':
        '🛡️ BEZPIECZEŃSTWO — OCHRONA KODEM PIN',
    'Proteggi con Codice PIN a 6 Cifre':
        'Chroń 6-cyfrowym kodem PIN',
    'PIN Attuale:':
        'Aktualny PIN:',
    '🎲 Nuovo PIN Casuale':
        '🎲 Nowy losowy PIN',
    'Genera un nuovo codice PIN casuale a 6 cifre e revoca le sessioni precedenti':
        'Tworzy nowy losowy 6-cyfrowy PIN i unieważnia poprzednie sesje',
    '⛔ Disconnetti Tutti':
        '⛔ Rozłącz wszystkich',
    "Sbatte fuori all'istante tutti i dispositivi connessi":
        'Natychmiast rozłącza wszystkie podłączone urządzenia',
    'Includi PIN nel codice QR (Accesso immediato con fotocamera)':
        'Dołącz PIN do kodu QR (wejście od razu aparatem)',
    "💡 <b>Massima Tranquillità in Teatro:</b> Inquadrando il monitor con lo smartphone si entra all'istante senza digitare nulla. Chiunque altro sulla LAN che tenti di accedere via browser troverà il tastierino PIN casuale a 6 cifre con blocco forzatura dopo 5 errori.":
        '💡 <b>Spokój w teatrze:</b> zeskanowanie kodu z monitora smartfonem daje dostęp od razu, bez wpisywania. Każdy inny w sieci LAN, kto spróbuje wejść przez przeglądarkę, zobaczy klawiaturę z losowym 6-cyfrowym PIN-em i blokadę po 5 błędach.',
    '📱 Client Web connessi: 0':
        '📱 Połączone urządzenia: 0',
    'Chiudi':
        'Zamknij',
    'Inquadra con Smartphone\nper aprire il Telecomando LIVE':
        'Zeskanuj smartfonem,\naby otworzyć pilota LIVE',
    '📱 TELECOMANDO MASTER LIVE (OPERATORE)':
        '📱 PILOT LIVE (OPERATOR)',
    "Ideale per il tecnico sul palco o in sala durante le prove e il montaggio. Offre il controllo completo sull'emissione dei media.":
        'Idealny dla technika na scenie lub na sali podczas prób i montażu. Daje pełną kontrolę nad emisją mediów.',
    'Indirizzo Web:':
        'Adres www:',
    '📋 Copia Link':
        '📋 Kopiuj link',
    '🌐 Apri nel Browser':
        '🌐 Otwórz w przeglądarce',
    'Inquadra con Tablet / iPad\nper aprire il Monitor Regia':
        'Zeskanuj tabletem / iPadem,\naby otworzyć monitor reżysera',
    '👁️ MONITOR REGISTA && DIRETTORE DI SCENA (SOLA LETTURA)':
        '👁️ MONITOR REŻYSERA I INSPICJENTA (TYLKO PODGLĄD)',
    'Interfaccia di sola visualizzazione passiva per tablet, iPad o computer del regista e del direttore di scena. Mostra in tempo reale come lavorano i 3 layer e la scaletta, garantendo zero rischi.':
        'Pasywny widok tylko do podglądu na tablet, iPada lub komputer reżysera i inspicjenta. Pokazuje na żywo pracę 3 warstw i listy cue, bez żadnego ryzyka.',
    'Indirizzo Monitor:':
        'Adres monitora:',
    '📋 Copia Link Monitor':
        '📋 Kopiuj link monitora',
    '🗣️ <b>Come collegare il regista che si trova in platea:</b>':
        '🗣️ <b>Jak podłączyć reżysera siedzącego na widowni:</b>',
    "1. <b>A voce / Intercom (se digita a mano):</b> Digli di collegarsi al Wi-Fi del teatro, aprire il browser (Safari, Chrome o Edge) e digitare l'indirizzo IP con la porta e <code>/monitor</code> (oppure <code>/regia</code>). Inserirà poi il PIN a 6 cifre visualizzato in basso.":
        '1. <b>Głosowo / przez interkom (gdy wpisuje ręcznie):</b> niech połączy się z Wi-Fi teatru, otworzy przeglądarkę (Safari, Chrome lub Edge) i wpisze adres IP z portem oraz <code>/monitor</code> (albo <code>/regia</code>). Potem wpisze 6-cyfrowy PIN widoczny poniżej.',
    '2. <b>Via Messaggio / WhatsApp / Email:</b> Clicca su <b>[ 📋 Copia Link Monitor ]</b> e incollaglielo in chat. Il link copiato include già il token PIN autorizzato: al regista basterà toccare il link per entrare subito senza digitare nulla!':
        '2. <b>Przez wiadomość / WhatsApp / e-mail:</b> kliknij <b>[ 📋 Kopiuj link monitora ]</b> i wklej w czacie. Skopiowany link zawiera już autoryzowany PIN: reżyser tylko dotyka linku i od razu wchodzi!',
    '⚙ CONFIGURAZIONE PORTE DI RETE && PROTOCOLLI':
        '⚙ KONFIGURACJA PORTÓW SIECIOWYCH I PROTOKOŁÓW',
    'Abilita Servizio Web (Telecomando && Monitor Regia)':
        'Włącz usługę web (pilot i monitor reżysera)',
    'Porta Web:':
        'Port web:',
    'Abilita Server OSC UDP':
        'Włącz serwer OSC (UDP)',
    'Porta OSC UDP:':
        'Port OSC (UDP):',
    '🔄 Applica Nuove Porte':
        '🔄 Zastosuj nowe porty',
    '🎛 PRONTUARIO COMANDI OSC (QLab / Mixer Luci / TouchOSC)':
        '🎛 ŚCIĄGA POLECEŃ OSC (QLab / konsoleta świateł / TouchOSC)',
    'Ultima attività: Nessun comando ricevuto':
        'Ostatnia aktywność: brak poleceń',
    '✓ Disconnessi!':
        '✓ Rozłączono!',
    '✅ <b>Pulsante GO tattile gigante</b> con vibrazione aptica':
        '✅ <b>Duży dotykowy przycisk GO</b> z wibracją',
    '✅ <b>Monitor Cue in onda</b> con barra countdown in tempo reale':
        '✅ <b>Podgląd cue na wizji</b> z paskiem odliczania na żywo',
    '✅ <b>Pulsanti di emergenza:</b> Pausa/Riprendi, Blackout e PANIC 0ms':
        '✅ <b>Przyciski awaryjne:</b> pauza/wznowienie, wygaszenie i PANIC 0 ms',
    '✅ <b>Scaletta completa:</b> navigazione rapida e lancio diretto [ ▶ GO ] per singola Cue':
        '✅ <b>Pełna lista cue:</b> szybkie przewijanie i bezpośrednie [ ▶ GO ] dla każdego cue',
    '👁️ <b>Panoramica 3 Layer Live:</b> stato simultaneo di Layer 1 (Fondo), Layer 2 (Medio) e Layer 3 (Overlay)':
        '👁️ <b>Przegląd 3 warstw Live:</b> stan warstwy 1 (tło), 2 (środek) i 3 (nakładka) jednocześnie',
    '👁️ <b>Prossimo Lancio in Standby:</b> Q in attesa, destinazione layer, fade e tempi di transizione':
        '👁️ <b>Następny w standby:</b> oczekujące Q, docelowa warstwa, przejście i czasy',
    '👁️ <b>Scaletta Dinamica Completa:</b> stato live, tipi media, tempi ed avanzamento':
        '👁️ <b>Pełna lista cue na żywo:</b> stan, typy mediów, czasy i postęp',
    "🔒 <b style='color:#f87171;'>Zero comandi e zero click:</b> nessun pulsante interattivo, nessun rischio di errore accidentale":
        "🔒 <b style='color:#f87171;'>Zero poleceń i kliknięć:</b> brak przycisków, brak ryzyka przypadkowego błędu",
    '🟢 SERVIZI: ATTIVI{} (Arresta)':
        '🟢 USŁUGI: WŁ.{} (zatrzymaj)',
    '🔴 SERVIZI REMOTI: OFF (Avvia)':
        '🔴 USŁUGI ZDALNE: WYŁ. (uruchom)',
    'QR Code\nNon disponibile':
        'Kod QR\nniedostępny',
    '✓ Copiato!':
        '✓ Skopiowano!',
    'Rimuovi questa sezione e uniscila alla adiacente':
        'Usuń tę sekcję i połącz z sąsiednią',
    'OUT/Fine':
        'OUT/koniec',
    'Sezione {} ({}s – {})\nClicca per saltare subito qui':
        'Sekcja {} ({}s – {})\nKliknij, aby od razu tu przeskoczyć',
    'Ripetizioni o salto automatico per la Sezione {} (default: x1)':
        'Powtórzenia lub automatyczne pominięcie sekcji {} (domyślnie: x1)',
    'Fine File':
        'Koniec pliku',
    '{} (Copia)':
        '{} (kopia)',
    'BlindCue – Studio Superfici di Proiezione, Mapping & Maschere':
        'BlindCue – studio powierzchni projekcji, mappingu i masek',
    'Studio Superfici di Proiezione, Mapping & Maschere':
        'Studio powierzchni projekcji, mappingu i masek',
    'Schermi virtuali, keystone 4 angoli, maschere circolari, forature sagomate e mascherature PNG':
        'Ekrany wirtualne, korekcja trapezu 4 narożników, maski okrągłe, wycięcia i maski PNG',
    '👁 Mostra Guide sul Proiettore Live (F7)':
        '👁 Pokaż linie pomocnicze na projektorze (F7)',
    'SUPERFICI DEFINITE':
        'ZDEFINIOWANE POWIERZCHNIE',
    '＋ Nuova':
        '＋ Nowa',
    '⎘ Duplica':
        '⎘ Duplikuj',
    '✕ Elimina':
        '✕ Usuń',
    'GEOMETRIA & PRESET':
        'GEOMETRIA I USTAWIENIA GOTOWE',
    '⬛ Rettangolare':
        '⬛ Prostokąt',
    '⬡ Prospettiva (4 Angoli)':
        '⬡ Perspektywa (4 narożniki)',
    '— Seleziona Preset Rapido —':
        '— wybierz gotowe ustawienie —',
    "REGOLAZIONE FINE & UNITA'":
        'DOKŁADNE USTAWIENIA I JEDNOSTKI',
    '📐 Pixel (px)':
        '📐 Piksele (px)',
    '％ Percentuale (%)':
        '％ Procenty (%)',
    '🎭 MASCHERA & RITAGLIO (MASK)':
        '🎭 MASKA I PRZYCIĘCIE',
    'Nessuna (Piena)':
        'Brak (pełna)',
    '⭕ Ellisse / Cerchio':
        '⭕ Elipsa / koło',
    '🔲 Rettangolo / Finestra (Cutout)':
        '🔲 Prostokąt / okno (wycięcie)',
    '🖼 Maschera Immagine PNG':
        '🖼 Maska z obrazu PNG',
    'Comportamento / Direzione:':
        'Działanie / kierunek:',
    "🔘 Proietta all'Interno (Sagoma)":
        '🔘 Wyświetlaj wewnątrz (kształt)',
    '🔲 Buca al Centro (Foratura)':
        '🔲 Otwór w środku (wycięcie)',
    '📁 Scegli Immagine PNG...':
        '📁 Wybierz obraz PNG...',
    '✕ Rimuovi':
        '✕ Usuń',
    'Nessun file selezionato':
        'Nie wybrano pliku',
    '👁 Evidenzia Bordo Maschera sul Proiettore Live':
        '👁 Podświetl krawędź maski na projektorze',
    '🖥 MULTI-PROIETTORE & SPAN':
        '🖥 WIELE PROJEKTORÓW I ROZCIĄGNIĘCIE',
    'Per 2 o 3 proiettori affiancati, estendi il desktop nel sistema operativo e usa lo Span:':
        'Dla 2 lub 3 projektorów obok siebie rozszerz pulpit w systemie i użyj rozciągnięcia (span):',
    'Estendi su Tutti i Monitor Esterni (Span)':
        'Rozciągnij na wszystkie monitory zewnętrzne (span)',
    '💡 Mouse: trascina i vertici o il riquadro. Trascina direttamente il buco sul canvas. Bordo Guida: proietta il contorno esatto sul palco per allinearlo al millimetro.':
        '💡 Mysz: przeciągaj wierzchołki lub ramkę. Otwór przeciągasz bezpośrednio na płótnie. Krawędź pomocnicza wyświetla dokładny obrys na scenie, by wyrównać go co do milimetra.',
    'Le modifiche sono applicate in tempo reale al motore di riproduzione.':
        'Zmiany są od razu stosowane w silniku odtwarzania.',
    'Salva & Chiudi':
        'Zapisz i zamknij',
    'Superficie':
        'Powierzchnia',
    'Seleziona Immagine Maschera (PNG / Immagine)':
        'Wybierz obraz maski (PNG / obraz)',
    'Immagini (*.png *.jpg *.jpeg *.bmp *.webp);;Tutti i file (*.*)':
        'Obrazy (*.png *.jpg *.jpeg *.bmp *.webp);;Wszystkie pliki (*.*)',
    'Nome:':
        'Nazwa:',
    'Preset:':
        'Ustawienie:',
    'C1 · Alto SX (TL)':
        'C1 · lewy górny (TL)',
    'C2 · Alto DX (TR)':
        'C2 · prawy górny (TR)',
    'C3 · Basso DX (BR)':
        'C3 · prawy dolny (BR)',
    'C4 · Basso SX (BL)':
        'C4 · lewy dolny (BL)',
    'Forma:':
        'Kształt:',
    'Sfumatura Bordo (Feather):':
        'Zmiękczenie krawędzi:',
    'Netto (0px)':
        'Ostra (0px)',
    'Morbido (15px)':
        'Miękka (15px)',
    'Vignetta (35px)':
        'Winieta (35px)',
    'Larghezza:':
        'Szerokość:',
    'Altezza:':
        'Wysokość:',
    'Multi-Monitor Esteso':
        'Rozszerzony pulpit na wiele monitorów',
    "La finestra di uscita è stata estesa su tutti i monitor ({}×{} px).\nI preset 'Doppio Proiettore' mapperanno automaticamente ciascuna metà dello schermo!":
        "Okno wyjścia rozciągnięto na wszystkie monitory ({}×{} px).\nUstawienia 'Dwa projektory' same przypiszą każdą połowę ekranu!",
    'Monitor Singolo Rilevato':
        'Wykryto jeden monitor',
    'È presente un solo schermo collegato. Per usare lo spanning multi-proiettore, collega un secondo monitor/proiettore alle uscite HDMI o DisplayPort.':
        'Podłączony jest tylko jeden ekran. Aby rozciągnąć obraz na kilka projektorów, podłącz drugi monitor/projektor do wyjścia HDMI lub DisplayPort.',
    '🔲 Buco: {}, {} px · Dim: {} × {} px':
        '🔲 Otwór: {}, {} px · rozmiar: {} × {} px',
    'Pos: {}, {} px · Dim: {} × {} px':
        'Poz.: {}, {} px · rozmiar: {} × {} px',
    'Angolo Attivo:':
        'Aktywny narożnik:',
    'Corner X:':
        'Narożnik X:',
    'Corner Y:':
        'Narożnik Y:',
    '▲ ALTO / TOP ▲':
        '▲ GÓRA ▲',
    '▼ BASSO ▼':
        '▼ DÓŁ ▼',
    '◀ SX':
        '◀ L',
    'DX ▶':
        'P ▶',
    'L0 TAPPO • {}×{} ({})':
        'L0 TŁO • {}×{} ({})',
    'Obsidian Slate (Regia Pro · Predefinito)':
        'Obsidian Slate (reżyserka pro · domyślny)',
    'Tema scuro broadcast calibrato per ambienti di regia con luce soffusa. Morbido e riposante.':
        'Ciemny motyw dopasowany do słabo oświetlonej reżyserki. Miękki i łagodny dla oczu.',
    'Carbon Monocromo (100% Scala di Grigi · Bianco Puro)':
        'Carbon Mono (100% skala szarości · czysta biel)',
    'Architettura al 100% in scala di grigi senza alcun colore: solo seta bianca, argento e grafite per la massima chiarezza e accessibilità assoluta.':
        'W 100% skala szarości, bez kolorów: biel, srebro i grafit dla maksymalnej czytelności i dostępności.',
    'Warm Amber Studio (Caldo Analogico · Valvolare)':
        'Warm Amber Studio (ciepły, analogowy)',
    'Palette calda e organica ispirata ai banchi audio analogici valvolari: toni caffè tostato, accenti ambra dorata e rame per il massimo comfort visivo.':
        'Ciepła paleta inspirowana analogowymi konsoletami lampowymi: odcienie kawy, złoty bursztyn i miedź dla komfortu oczu.',
    'Nessun Colore (Predefinito)':
        'Bez koloru (domyślnie)',
    'Rosso — Atto / Effetto':
        'Czerwony — akt / efekt',
    'Ambra — Dialogo / Luce Calda':
        'Bursztynowy — dialog / ciepłe światło',
    'Verde — Musica / Ambiente':
        'Zielony — muzyka / tło dźwiękowe',
    'Ciano — Video / Proiezione':
        'Błękitny — wideo / projekcja',
    'Blu — Cambio Scena':
        'Niebieski — zmiana sceny',
    'Viola — Sogno / Atmosfera':
        'Fioletowy — sen / nastrój',
    'Magenta — Evento Speciale':
        'Purpurowy — wydarzenie specjalne',
    'Curva Fade IN / OUT':
        'Krzywa Fade IN / OUT',
    "Forma d'Onda e Automazioni (Timeline)":
        'Przebieg i automatyzacja (oś czasu)',
    '↦ IN Testina':
        '↦ IN na głowicy',
    'Imposta il punto IN esattamente sulla testina di lettura (Scorciatoia: I)':
        'Ustawia punkt IN dokładnie na głowicy (skrót: I)',
    'OUT Testina ↤':
        'OUT na głowicy ↤',
    'Imposta il punto OUT esattamente sulla testina di lettura (Scorciatoia: O)':
        'Ustawia punkt OUT dokładnie na głowicy (skrót: O)',
    'Testina: --:--.--':
        'Głowica: --:--.--',
    '⟲ Reset IN/OUT':
        '⟲ Reset IN/OUT',
    'Ripristina IN a 0.00s e OUT a Fine file':
        'Przywróć IN na 0,00 s i OUT na koniec pliku',
    '🔊 Volume':
        '🔊 Głośność',
    "Modifica la curva Volume sulla forma d'onda":
        'Edytuj krzywą głośności na przebiegu',
    '👁 Opacità':
        '👁 Krycie',
    "Modifica l'opacità lungo il file video sulla stessa timeline":
        'Edytuj krycie wzdłuż pliku wideo na tej samej osi czasu',
    'Finestra temporale visiva per immagini a durata infinita':
        'Okno czasu dla obrazów wyświetlanych bez końca',
    'Forma della rampa Fade IN / OUT (Logaritmica consigliata per audio)':
        'Kształt narastania Fade IN / OUT (dla audio zalecana logarytmiczna)',
    '⟲ Reset Punti':
        '⟲ Wyzeruj punkty',
    'Elimina tutti i punti sulla linea Volume/Opacità':
        'Usuwa wszystkie punkty na linii głośności/krycia',
    '✂ Dividi':
        '✂ Podziel',
    'Dividi virtualmente il file alla testina in sezioni A, B, C...':
        'Wirtualnie dzieli plik na głowicy na sekcje A, B, C...',
    '⏭ Esci Loop':
        '⏭ Wyjdź z pętli',
    'Salta immediatamente fuori dalla sezione ripetuta verso la successiva':
        'Natychmiast wychodzi z powtarzanej sekcji do następnej',
    '↺ Reset Sez.':
        '↺ Wyzeruj sekcje',
    'Rimuovi tutte le sezioni virtuali e torna al file intero':
        'Usuń wszystkie wirtualne sekcje i wróć do całego pliku',
    "Zoom indietro forma d'onda (rotella giù)":
        'Pomniejsz przebieg (kółko w dół)',
    "Zoom forma d'onda — clicca per ripristinare 1.0× (o doppio clic / Ctrl+0)":
        'Zoom przebiegu — kliknij, aby przywrócić 1,0× (albo dwuklik / Ctrl+0)',
    "Zoom avanti forma d'onda (rotella su)":
        'Powiększ przebieg (kółko w górę)',
    "Nessuna forma d'onda caricata":
        'Nie wczytano przebiegu',
    'IN: 0.00s':
        'IN: 0.00s',
    'OUT: Fine':
        'OUT: koniec',
    'Vista {}s':
        'Widok {}s',
    'Opacità':
        'Krycie',
    'Volume':
        'Głośność',
    'Layer {}':
        'Warstwa {}',
    'Layer comune: L{}':
        'Wspólna warstwa: L{}',
    'Fade: {}':
        'Fade: {}',
    'Logaritmica':
        'Logarytmiczna',
    '🖥️ <b>CPU:</b> {} Core ({}) | 💾 <b>RAM:</b> {} GB (Disp: {} GB) | 🎮 <b>GPU:</b> {}':
        '🖥️ <b>CPU:</b> {} rdz. ({}) | 💾 <b>RAM:</b> {} GB (wolne: {} GB) | 🎮 <b>GPU:</b> {}',
    'VA-API Attiva':
        'VA-API aktywne',
    'PRONTO':
        'GOTOWY',
    'ATTESA':
        'CZEKA',
    'Testina: {}':
        'Głowica: {}',
    'Added: {}':
        'Dodano: {}',
    '💡 {}':
        '💡 {}',
    '📁 {} cue nel gruppo · Durata stimata: {}':
        '📁 {} cue w grupie · szacowany czas: {}',
    ' (Manuale)':
        ' (ręcznie)',
    '+ Text':
        '+ Tekst',
    'Add an on-screen caption (text cue, Layer 3)':
        'Dodaj napis na ekranie (cue tekstowe, warstwa 3)',
    'Add Text':
        'Dodaj tekst',
    '✏ Edit text…':
        '✏ Edytuj napis…',
    'Text cue (caption)':
        'Cue tekstowe (napis)',
    'Type the text shown on the projector…':
        'Wpisz tekst, który pojawi się na projektorze…',
    'Bottom':
        'Na dole',
    'Center':
        'Na środku',
    'Top':
        'Na górze',
    'Bold':
        'Pogrubienie',
    'Dark band behind the text':
        'Ciemny pasek pod tekstem',
    'Shadow':
        'Cień',
    'Text:':
        'Tekst:',
    'Font size:':
        'Wielkość liter:',
    'Text colour:':
        'Kolor tekstu:',
    'Position on screen:':
        'Położenie na ekranie:',
    'Preview (projector):':
        'Podgląd (projektor):',
    'Tip: the caption goes on Layer 3 (on top of video and photos). Fade In/Out, position and crossfade are set in the Inspector like for a photo.':
        'Wskazówka: napis trafia na warstwę 3 (nad filmem i zdjęciami). Fade In/Out, położenie i przenikanie ustawisz w Inspektorze tak jak dla zdjęcia.',
    'Cancel':
        'Anuluj',
    'Text colour':
        'Kolor tekstu',
    'Text cue':
        'Cue tekstowe',
    'The selected cue is not a text cue. Add one with the "+ Text" button.':
        'Zaznaczony cue nie jest cue tekstowym. Napis dodasz przyciskiem „+ Tekst”.',
    'Crossfade:':
        'Przenikanie:',
    'Crossfade':
        'Przenikanie',
    "Crossfade: the picture currently shown on this cue's layer dissolves into this cue over the given time (0 = hard cut). Set Fade In to 0 when using it.":
        'Przenikanie: obraz widoczny teraz na warstwie tego cue płynnie przechodzi w ten cue w podanym czasie (0 = ostre cięcie). Przy przenikaniu ustaw Fade In na 0.',
    # ── strings found by a runtime crawl of every widget and dialog ──
    'Colore Cue: {}':
        'Kolor cue: {}',
    'Colore Scena: {}':
        'Kolor sceny: {}',
    'Posizione: #{}':
        'Pozycja: #{}',
    'Q (Copione): {}':
        'Q (scenariusz): {}',
    'Nome: {}':
        'Nazwa: {}',
    'Note di Regia: {}':
        'Uwagi: {}',
    'File: {}':
        'Plik: {}',
    '⚠️ ATTENZIONE: {}':
        '⚠️ UWAGA: {}',
    'Blocco manuale':
        'Stop (ręczne GO)',
    'Auto-GO a fine cue':
        'Auto-GO po końcu cue',
    'Simultanea con successiva':
        'Razem z następnym',
    'Durata {}':
        'Czas {}',
    '{} | {}':
        '{} | {}',
    'STUDIO COMPOSITORE TIMELINE · {}':
        'STUDIO OSI CZASU · {}',
    '⏱ Durata Scena: {}':
        '⏱ Czas sceny: {}',
    'Web: {} | OSC: {}':
        'Web: {} | OSC: {}',
    'Nessuna azione web ricevuta':
        'brak poleceń z sieci',
    '⬛ Schermo Intero (Default)':
        '⬛ Cały ekran (domyślny)',
    '⬛  Schermo Intero (Default)':
        '⬛  Cały ekran (domyślny)',
    'Dissolvenza in uscita {}':
        'Wygaszanie: {}',
    'Pausa o Riprendi {}':
        'Pauza lub wznowienie: {}',
    'Riavvolgi 10 secondi {}':
        'Cofnij o 10 s: {}',
    'Regolazione Opacità':
        'Regulacja krycia',
    'Regolazione Scala':
        'Regulacja skali',
    'Regolazione Volume':
        'Regulacja głośności',
    'Ripristina Opacità':
        'Przywróć krycie',
    'Ripristina Scala':
        'Przywróć skalę',
    'Ripristina Volume':
        'Przywróć głośność',
    'Layer 0':
        'Zaślepka L0',
    # ── user manual window (Help → User manual, F1) ──
    '📖 Manuale utente':
        '📖 Instrukcja obsługi',
    'BlindCue – Manuale utente':
        'BlindCue – instrukcja obsługi',
    '⌂ Indice':
        '⌂ Spis treści',
    '← Indietro':
        '← Wstecz',
    '🌐 Apri nel browser':
        '🌐 Otwórz w przeglądarce',
    'Manuale non trovato: {}':
        'Nie znaleziono instrukcji: {}',
    # ── device settings dialog ──
    'Uscita video non applicata':
        'Nie zastosowano wyjścia wideo',
    'La modalità selezionata non è applicabile con gli schermi attuali.\nCollega il proiettore esterno richiesto e riprova.':
        'Wybranego trybu nie da się zastosować przy obecnych ekranach.\nPodłącz wymagany projektor zewnętrzny i spróbuj ponownie.',
    'Proiettori coinvolti: ':
        'Używane projektory: ',
    'Schermi coinvolti: ':
        'Używane ekrany: ',
    # ── second launch while the program is already running ──
    'BlindCue è già in esecuzione ma non risponde.\n\nPotrebbe essere ancora in fase di avvio. Se la sua finestra non compare, chiudi BlindCue già aperto e riavvia il programma.':
        'BlindCue już działa, ale nie odpowiada.\n\nMoże jeszcze się uruchamia. Jeśli jego okno się nie pojawi, zamknij działający BlindCue i uruchom program ponownie.',
    # ── text cues, crossfade and the cue list (feature PRs) ──
    'In basso':
        'Na dole',
    'Al centro':
        'Na środku',
    'In alto':
        'Na górze',
    'Cue di testo (didascalia)':
        'Cue tekstowe (napis)',
    'Scrivi il testo da mostrare sul proiettore…':
        'Wpisz tekst, który pojawi się na projektorze…',
    'Grassetto':
        'Pogrubienie',
    'Fascia scura dietro il testo':
        'Ciemny pasek pod tekstem',
    'Ombra':
        'Cień',
    'Testo:':
        'Tekst:',
    'Dimensione carattere:':
        'Wielkość liter:',
    'Colore del testo:':
        'Kolor tekstu:',
    'Posizione sullo schermo:':
        'Położenie na ekranie:',
    'Suggerimento: la didascalia va sul Layer 3 (sopra video e foto). Fade In/Out, posizione e crossfade si impostano nell\'Inspector come per una foto.':
        'Wskazówka: napis trafia na warstwę 3 (nad filmem i zdjęciami). Fade In/Out, położenie i przenikanie ustawisz w Inspektorze tak jak dla zdjęcia.',
    'Anteprima (proiettore):':
        'Podgląd (projektor):',
    'Colore del testo':
        'Kolor tekstu',
    '+ Testo':
        '+ Napis',
    'Aggiungi una didascalia sullo schermo (cue di testo, Layer 3)':
        'Dodaj napis na ekranie (cue tekstowe, warstwa 3)',
    'Aggiungi Testo':
        'Dodaj tekst',
    '✏ Modifica testo…':
        '✏ Edytuj napis…',
    'Cue di testo':
        'Cue tekstowe',
    'Il cue selezionato non è un cue di testo. Aggiungine uno con il pulsante "+ Testo".':
        'Zaznaczony cue nie jest cue tekstowym. Napis dodasz przyciskiem „+ Tekst”.',
    'Crossfade: l\'immagine mostrata ora sul layer di questo cue sfuma nel nuovo cue nel tempo indicato (0 = stacco netto). Se lo usi, imposta il Fade In a 0.':
        'Przenikanie: obraz widoczny teraz na warstwie tego cue płynnie przechodzi w ten cue w podanym czasie (0 = ostre cięcie). Przy przenikaniu ustaw Fade In na 0.',
    # ── speakers remembered per computer (feature PR) ──
    'Predefinito di sistema, segue il sistema (ora: {})':
        'Domyślne wyjście systemowe (teraz: {})',
    '{} (non collegato)':
        '{} (niepodłączone)',
    'Uscita audio scelta non collegata ({}): suona l\'uscita predefinita ({})':
        'Wybrane głośniki nie są podłączone ({}): dźwięk idzie na domyślne wyjście ({})',
    'Uscita audio scelta di nuovo collegata: {}':
        'Wybrane głośniki znów podłączone: {}',
    # ── strings from 3157c0a (PANIC on ESC twice, VA-API, OSC, bundle masks) ──
    '<b>Indirizzo OSC:</b> <span style=\'color:#38bdf8;\'>{}</span><br>• <b style=\'color:#4ade80;\'>/go</b> oppure <b>/cue/go</b> &nbsp;→&nbsp; Esegue GO sulla cue in Standby<br>• <b style=\'color:#f87171;\'>/panic</b> &nbsp;→&nbsp; Arresto immediato 0ms (Tutti i livelli)<br>• <b style=\'color:#f87171;\'>/stop</b> oppure <b>/blackout</b> &nbsp;→&nbsp; Blackout live (Ritorno a Layer 0)<br>• <b style=\'color:#fbbf24;\'>/pause</b> / <b>/resume</b> / <b>/pause_toggle</b> &nbsp;→&nbsp; Pausa, ripresa o toggle<br>• <b style=\'color:#38bdf8;\'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Sposta la selezione della scaletta<br>• <b style=\'color:#38bdf8;\'>/cue/&lt;numero&gt;/go</b> &nbsp;→&nbsp; Esegue subito la cue indicata (es. <i>/cue/3/go</i>)<br>• <b style=\'color:#a855f7;\'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Autentica l\'IP per inviare comandi protetti':
        '<b>Adres OSC:</b> <span style=\'color:#38bdf8;\'>{}</span><br>• <b style=\'color:#4ade80;\'>/go</b> lub <b>/cue/go</b> &nbsp;→&nbsp; GO dla cue w standby<br>• <b style=\'color:#f87171;\'>/panic</b> &nbsp;→&nbsp; natychmiastowy stop 0 ms (wszystkie warstwy)<br>• <b style=\'color:#f87171;\'>/stop</b> lub <b>/blackout</b> &nbsp;→&nbsp; wygaszenie Live (powrót do warstwy 0)<br>• <b style=\'color:#fbbf24;\'>/pause</b> / <b>/resume</b> / <b>/pause_toggle</b> &nbsp;→&nbsp; pauza, wznowienie lub przełączenie<br>• <b style=\'color:#38bdf8;\'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; przesuwa zaznaczenie na liście<br>• <b style=\'color:#38bdf8;\'>/cue/&lt;numer&gt;/go</b> &nbsp;→&nbsp; od razu uruchamia wskazany cue (np. <i>/cue/3/go</i>)<br>• <b style=\'color:#a855f7;\'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; uwierzytelnia IP do wysyłania chronionych poleceń',
    'Attiva (VA-API / Hardware Decode)':
        'Aktywna (VA-API / dekodowanie sprzętowe)',
    'EMERGENZA (0ms): Taglia immediatamente Audio, Video e Immagini su tutti i layer. Mostra Nero assoluto se il Tappo è quello di calibrazione (o Tappo personalizzato se impostato).\nDa tastiera: premi ESC due volte entro 0,6s (protezione anti-tocco accidentale).':
        'AWARIA (0 ms): natychmiast ucina audio, wideo i obrazy na wszystkich warstwach. Pokazuje czerń, jeśli zaślepka jest kalibracyjna (lub własną zaślepkę, jeśli ustawiono).\nZ klawiatury: naciśnij ESC dwa razy w ciągu 0,6 s (ochrona przed przypadkowym naciśnięciem).',
    'Layer 0 (Tappo)':
        'Zaślepka L0',
    'Maschera superficie \'{}\'':
        'Maska powierzchni \'{}\'',
    'OpenGL / EGL (solo compositing, decode CPU)':
        'OpenGL / EGL (tylko kompozycja, dekodowanie na CPU)',
    'Software / Headless Renderer':
        'Renderowanie programowe / bez ekranu',
    'Software Renderer (nessuna accelerazione GPU)':
        'Renderowanie programowe (bez akceleracji GPU)',
    '⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms) — oppure clicca il pulsante PANIC':
        '⚠ Naciśnij ESC jeszcze raz w ciągu 0,6 s, aby włączyć PANIC (0 ms) — albo kliknij przycisk PANIC',
    '🔒 Controlli Layer Protetti — Sblocca con il Lucchetto (1,2s)':
        '🔒 Sterowanie warstwami chronione — odblokuj kłódką (1,2 s)',
    '🚨  PANIC  —  STOP TOTALE   [ ESC ×2 ]':
        '🚨  PANIC  —  STOP WSZYSTKIEGO   [ ESC ×2 ]',
    'GO ignorato: secondo GO entro {} ms':
        'GO zignorowane: drugie GO w ciągu {} ms',
    '&Dissolvenza totale (Fade All)':
        '&Wygaś wszystko',
    'Dissolvenza totale in {} s':
        'Wygaszanie wszystkiego w {} s',
    '🔉 DISSOLVI [⇧ESC]':
        '🔉 WYGAŚ [⇧ESC]',
    '⚠  TASTIERA NON SUL PANNELLO REGIA — SPAZIO ed ESC non arrivano a BlindCue. Clicca qui per riprenderla.':
        '⚠  KLAWIATURA NIE JEST NA PANELU REŻYSERA — SPACJA i ESC nie trafiają do BlindCue. Kliknij tutaj, aby ją odzyskać.',
    '⚠ Tastiera non sul pannello regia: SPAZIO ed ESC non arrivano a BlindCue':
        '⚠ Klawiatura nie jest na panelu reżysera: SPACJA i ESC nie trafiają do BlindCue',
    '{} pronta — premi GO per avviarla (il doppio clic in LIVE non avvia)':
        '{} gotowy — naciśnij GO, aby go uruchomić (podwójne kliknięcie w trybie LIVE nie uruchamia)',
    '⛔ Esclusiva: blocca il GO finché è in onda':
        '⛔ Wyłączny: blokuje GO, dopóki trwa',
    "Mentre questa cue è in onda il GO manuale viene rifiutato (anche da remoto), così un GO dato per errore non la copre. Ctrl+Spazio forza comunque il GO.\nAttenzione: un'immagine senza durata resta in onda finché non viene fermata.":
        'Dopóki ten cue trwa, ręczne GO jest odrzucane (także z pilota), więc przypadkowe GO go nie przykryje. Ctrl+Spacja mimo to wymusza GO.\nUwaga: obraz bez czasu trwania trwa, dopóki go nie zatrzymasz.',
    "GO bloccato: '{}' è esclusiva ed è in onda — Ctrl+Spazio per forzare":
        "GO zablokowane: '{}' jest wyłączny i trwa — Ctrl+Spacja, aby wymusić",
    'GO &forzato (ignora cue esclusiva)':
        'GO &wymuszone (pomija cue wyłączny)',
    'Dissolvenza totale: audio, video e immagini su tutti i layer sfumano insieme, poi si fermano. Il prossimo GO riparte dalla cue avviata a mano che è stata fermata.':
        'Wygaś wszystko: audio, wideo i obrazy na wszystkich warstwach wygasają razem, potem się zatrzymują. Następne GO rusza od zatrzymanego cue, który uruchomiono ręcznie.',
    '+ Azione':
        '+ Akcja',
    'Aggiungi Azione':
        'Dodaj akcję',
    'Aggiungi una cue senza file: ferma, dissolve, cambia livello o opacità di altre cue, oppure mostra una nota per la regia':
        'Dodaj cue bez pliku: zatrzymuje, wygasza, zmienia poziom lub krycie innych cue albo pokazuje notatkę dla operatora',
    '🔉 Dissolvi e ferma':
        '🔉 Wygaś i zatrzymaj',
    '⏹ Ferma subito':
        '⏹ Zatrzymaj od razu',
    '🔁 Rilascia loop':
        '🔁 Zwolnij pętlę',
    '🎚 Cambio livello':
        '🎚 Zmiana poziomu',
    '🌓 Opacità layer':
        '🌓 Krycie warstwy',
    '📝 Nota per la regia':
        '📝 Notatka dla operatora',
    '☑ Checklist prima dello spettacolo':
        '☑ Lista kontrolna przed spektaklem',
    'Ferma subito':
        'Zatrzymaj od razu',
    'Rilascia loop':
        'Zwolnij pętlę',
    'Cambio livello':
        'Zmiana poziomu',
    'Opacità layer':
        'Krycie warstwy',
    'Nota per la regia':
        'Notatka dla operatora',
    'Checklist prima dello spettacolo':
        'Lista kontrolna przed spektaklem',
    'Microfoni accesi':
        'Mikrofony włączone',
    'Proiettore acceso':
        'Projektor włączony',
    'Telefono in silenzioso':
        'Telefon wyciszony',
    '⚡ Azione':
        '⚡ Akcja',
    'Durata: scheda Azione':
        'Czas: zakładka Akcja',
    'Azione:':
        'Akcja:',
    'Su cosa:':
        'Na co:',
    'Cue:':
        'Cue:',
    'Modo:':
        'Tryb:',
    'Livello:':
        'Poziom:',
    'Variazione:':
        'Zmiana:',
    'Durata:':
        'Czas:',
    'Curva:':
        'Krzywa:',
    'Voci:':
        'Pozycje:',
    'Tipo di azione':
        'Rodzaj akcji',
    'Su cosa agisce':
        'Na co działa',
    "Cue su cui agisce l'azione":
        'Cue, na które działa akcja',
    'Testo della nota':
        'Tekst notatki',
    'Voci della checklist, una per riga':
        'Pozycje listy kontrolnej, jedna w wierszu',
    'Tutto ciò che è in onda':
        'Wszystko, co gra',
    'Un layer':
        'Jedna warstwa',
    'Cue scelte':
        'Wybrane cue',
    'Uscita A':
        'Wyjście A',
    'Uscita B':
        'Wyjście B',
    'Conta solo con due proiettori indipendenti':
        'Ma znaczenie tylko przy dwóch niezależnych projektorach',
    "Spunta le cue su cui agisce l'azione (un gruppo = tutte le sue cue)":
        'Zaznacz cue, na które działa akcja (grupa = wszystkie jej cue)',
    'Assoluto (%)':
        'Bezwzględnie (%)',
    'Relativo (dB)':
        'Względnie (dB)',
    '0 = subito':
        '0 = od razu',
    "Es. Aspetta l'ingresso di Anna, poi GO":
        'Np. Czekaj na wejście Ani, potem GO',
    'Una voce per riga':
        'Jedna pozycja w wierszu',
    'Ambra':
        'Bursztynowy',
    'Rosso — attenzione':
        'Czerwony — uwaga',
    'Verde':
        'Zielony',
    'Blu':
        'Niebieski',
    'Viola':
        'Fioletowy',
    'Grigio chiaro':
        'Jasnoszary',
    'Abbassa audio e immagine delle cue scelte nel tempo indicato, poi le ferma. Il loro Post-Delay e Auto-GO non partono.':
        'Ścisza dźwięk i wygasza obraz wybranych cue w podanym czasie, potem je zatrzymuje. Ich Post-Delay i Auto-GO nie ruszają.',
    'Ferma subito le cue scelte, anche quelle in attesa del Pre-Delay.':
        'Od razu zatrzymuje wybrane cue, także te czekające na koniec Pre-Delay.',
    'La cue in loop finisce il giro in corso e poi prosegue: passa alla sezione successiva o termina normalmente (con Post-Delay e Auto-GO).':
        'Zapętlony cue kończy bieżące okrążenie i idzie dalej: przechodzi do następnej sekcji albo kończy się normalnie (z Post-Delay i Auto-GO).',
    'Cambia il volume di ciò che suona, senza fermarlo. Assoluto: come se il Volume della cue fosse quello indicato. Relativo: più o meno dB rispetto ad ora.':
        'Zmienia głośność tego, co gra, bez zatrzymywania. Bezwzględnie: tak, jakby Głośność cue miała podaną wartość. Względnie: o tyle dB głośniej lub ciszej niż teraz.',
    'Rende più o meno trasparente tutto il layer (immagini e video). La cue successiva sullo stesso layer riparte piena.':
        'Zmienia przezroczystość całej warstwy (obrazy i wideo). Następny cue na tej warstwie startuje z pełnym kryciem.',
    'Mostra il testo in cima alla finestra di regia (non sul proiettore). Non blocca il GO; sparisce al GO successivo o con ✕.':
        'Pokazuje tekst u góry okna reżysera (nie na projektorze). Nie blokuje GO; znika przy następnym GO albo po kliknięciu ✕.',
    'Lista da spuntare prima dello spettacolo: compare con il GO e anche entrando in LIVE finché non è tutta spuntata. Le spunte non vengono salvate.':
        'Lista do odhaczenia przed spektaklem: pojawia się po GO, a także przy wejściu w tryb LIVE, dopóki nie jest cała odhaczona. Zaznaczenia nie są zapisywane.',
    'nessuna cue scelta':
        'nie wybrano cue',
    'tutto in onda':
        'wszystko, co gra',
    'Nota: {}':
        'Notatka: {}',
    'Nota (vuota)':
        'Notatka (pusta)',
    'Checklist: {} voci':
        'Lista kontrolna: {} poz.',
    'Stop: {}':
        'Zatrzymaj: {}',
    'Dissolvi in {} s: {}':
        'Wygaś w {} s: {}',
    'Rilascia loop: {}':
        'Zwolnij pętlę: {}',
    'Livello {} dB in {} s: {}':
        'Poziom {} dB w {} s: {}',
    'Livello {}% in {} s: {}':
        'Poziom {}% w {} s: {}',
    'Opacità {}% in {} s: {}':
        'Krycie {}% w {} s: {}',
    '⚡ {}':
        '⚡ {}',
    'Azione: {}':
        'Akcja: {}',
    "Azione {} '{}': nessun bersaglio in onda, niente da fare":
        "Akcja {} '{}': żaden z jej celów nie gra, nic do zrobienia",
    "AZIONE → {} '{}': {}":
        "AKCJA → {} '{}': {}",
    'Checklist: {} di {} spuntate':
        'Lista kontrolna: odhaczono {} z {}',
    '✕ Chiudi':
        '✕ Zamknij',
    'Nascondi la nota (non ferma niente)':
        'Ukryj notatkę (niczego nie zatrzymuje)',
    'Dissolvi e ferma':
        'Wygaś i zatrzymaj',
    '? cue eliminata dalla scaletta':
        '? cue usunięty z listy',
    'GO: avvia la cue indicata sul pulsante [SPAZIO]':
        'GO: uruchamia cue wskazany na przycisku [SPACJA]',
    'Da dove parte lo spettacolo?':
        'Od którego miejsca zacząć?',
    "Dall'inizio: {}":
        'Od początku: {}',
    'Riprendi da: {}':
        'Wznów od: {}',
    'Dalla cue selezionata: {}':
        'Od zaznaczonego: {}',
    '⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms)':
        '⚠ Naciśnij ESC jeszcze raz w ciągu 0,6 s, aby włączyć PANIC (0 ms)',
    "Aggiunta dopo '{}', alla fine della catena Simultanea / Auto-GO o del gruppo":
        'Dodano za „{}” – na końcu łańcucha Razem / Auto-GO albo grupy',
    '▶ GO: {}':
        '▶ GO: {}',
    "La cue selezionata non è l'inizio della scaletta.\nDa quale cue deve partire il GO?":
        'Zaznaczony cue nie jest początkiem listy.\nOd którego cue ma ruszyć GO?',
    'La selezione è cambiata da quando hai lasciato LIVE.\nDa quale cue deve partire il GO?':
        'Zaznaczenie zmieniło się od wyjścia z LIVE.\nOd którego cue ma ruszyć GO?',
    'File non supportati, ignorati: {}':
        'Pominięto nieobsługiwane pliki: {}',
    'Unsupported File':
        'Nieobsługiwany plik',
    'Cannot determine media type for:':
        'Nie można rozpoznać rodzaju pliku:',
    '⌨ Clicca qui: la tastiera è altrove — GO: {}':
        '⌨ Kliknij tutaj: klawiatura jest w innym oknie — GO: {}',
    '⚠ File mancante — GO: {}':
        '⚠ Brak pliku — GO: {}',
    "⏳ GO in attesa (Ctrl+Spazio per forzare): '{}' è esclusiva":
        '⏳ GO czeka (Ctrl+Spacja wymusza): „{}” jest wyłączny',
    '↻ Già in onda, riparte — GO: {}':
        '↻ Już gra, zacznie od nowa — GO: {}',
    'Elenco scaletta ad alto contrasto per il live. Frecce Su e Giù per standby, Spazio per il GO, Esc due volte per il Panic.':
        'Kontrastowa lista cue na żywo. Strzałki w górę i w dół = następny cue, Spacja = GO, Esc dwa razy = PANIC.',
    'MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC ×2 = PANIC]':
        'PRZEDSTAWIENIE — uproszczony ekran prowadzenia [ESC ×2 = PANIC]',
    'Sessione precedente messa da parte: {}':
        'Poprzednią sesję odłożono (nie usunięto): {}',
    'Lo spettacolo è in corso.\nChiudere il programma ferma tutto ciò che è in onda.':
        'Trwa przedstawienie.\nZamknięcie programu zatrzyma wszystko, co gra.',
    'Resta nel programma':
        'Zostań w programie',
    'Chiudi il programma':
        'Zamknij program',
    '● LIVE':
        '● GRA',
    '○ Preparazione':
        '○ Przygotowanie',
    '○ PREPARAZIONE':
        '○ PRZYGOTOWANIE',
    '○ Preparazione  (tieni 1,5 s)':
        '○ Przygotowanie  (trzymaj 1,5 s)',
    '● Spettacolo':
        '● Przedstawienie',
    '● SPETTACOLO':
        '● PRZEDSTAWIENIE',
    'Modalità preparazione (attiva)':
        'Tryb przygotowania (włączony)',
    'Modalità spettacolo (attiva)':
        'Tryb przedstawienia (włączony)',
    'Entra nello spettacolo':
        'Wejdź w przedstawienie',
    'Entra nello spettacolo [F5]':
        'Wejdź w przedstawienie [F5]',
    'Torna alla preparazione: tieni premuto 1,5 secondi':
        'Powrót do przygotowania: przytrzymaj 1,5 sekundy',
    'Tieni premuto 1,5 s per tornare alla preparazione (ciò che è in onda continua). Da tastiera: Ctrl+Maiusc+F5':
        'Przytrzymaj 1,5 s, aby wrócić do przygotowania (to, co gra, gra dalej). Z klawiatury: Ctrl+Shift+F5',
    '🚨 PANIC [ESC ×2]':
        '🚨 PANIC [ESC ×2]',
    'Dissolvenza totale: tutto ciò che è in onda sfuma e si ferma [Maiusc+Esc]':
        'Wygaś wszystko: wszystko, co gra, łagodnie wygasa i się zatrzymuje [Shift+Esc]',
    'PANIC: ferma subito tutto (0 ms) [Esc due volte]':
        'PANIC: natychmiast zatrzymuje wszystko (0 ms) [Esc dwa razy]',
    'Termina lo spettacolo…':
        'Zakończ przedstawienie…',
    'Termina lo spettacolo':
        'Zakończ przedstawienie',
    'Tornare alla preparazione? Ciò che è in onda continua a suonare.':
        'Wrócić do przygotowania? To, co gra, gra dalej.',
    'Resta nello spettacolo':
        'Zostań w przedstawieniu',
    'Torna alla preparazione':
        'Wróć do przygotowania',
    'Per uscire dallo spettacolo: tieni premuto «○ Preparazione» per 1,5 s oppure Ctrl+Maiusc+F5':
        'Aby wyjść z przedstawienia: przytrzymaj „○ Przygotowanie” przez 1,5 s albo Ctrl+Shift+F5',
    'Nello spettacolo la scaletta non cambia: per modificarla torna alla preparazione (tieni premuto «○ Preparazione»)':
        'W przedstawieniu lista się nie zmienia: aby ją edytować, wróć do przygotowania (przytrzymaj „○ Przygotowanie”)',
    'Nello spettacolo le cue non cambiano: per modificarle torna alla preparazione':
        'W przedstawieniu cue się nie zmieniają: aby je edytować, wróć do przygotowania',
    'Annulla non serve nello spettacolo: lo spettacolo non è stato cambiato':
        'Cofanie nie jest potrzebne w przedstawieniu: pokaz nie został zmieniony',
    'Volume generale dello spettacolo':
        'Głośność główna przedstawienia',
    'Volume generale di tutto ciò che suona [Ctrl+↑ / Ctrl+↓]':
        'Głośność główna wszystkiego, co gra [Ctrl+↑ / Ctrl+↓]',
    'Silenzia':
        'Wycisz',
    '🔇 SILENZIATO':
        '🔇 WYCISZONE',
    "Silenzia tutto (l'anteprima resta) [Ctrl+M]":
        'Wycisz wszystko (podgląd zostaje) [Ctrl+M]',
    '🔇 Tutto silenziato (volume generale) — Ctrl+M per riattivare':
        '🔇 Wszystko wyciszone (głośność główna) — Ctrl+M włącza dźwięk',
    'Volume generale {} %':
        'Głośność główna {} %',
    'Lo spettacolo era in corso: si torna nello spettacolo.':
        'Trwało przedstawienie: program wróci do przedstawienia.',
    'Riprendi: prossima {}':
        'Wznów: następny {}',
    "Ripeti l'ultima: {}":
        'Jeszcze raz ostatni: {}',
    "Dall'inizio":
        'Od początku',
    'Apri senza ripristinare':
        'Otwórz bez przywracania',
    '✓ ULTIMA':
        '✓ OSTATNIO',
    '· {} fa':
        '· {} temu',
    '+ {} insieme':
        '+ {} razem',
    '· manuale (GO)':
        '· ręcznie (GO)',
    '· parte da sola tra {}':
        '· rusza sam za {}',
    '· parte da sola dopo {}':
        '· rusza sam po {}',
    "↶ Annulla l'ultimo GO":
        '↶ Cofnij ostatnie GO',
    'sfumo {} (1 s)':
        'wygaszę {} (1 s)',
    'tolgo {} dallo schermo':
        'zdejmę {} z ekranu',
    "l'immagine {} torna":
        'obraz {} wróci',
    '{} non è ancora partita: la annullo':
        '{} jeszcze nie ruszył – anuluję',
    '{} è già finita':
        '{} już się skończył',
    '{} interrotta: non torna da sola':
        '{} przerwany – sam nie wróci',
    "l'azione {} resta":
        'akcja {} zostaje',
    'prossima di nuovo {}':
        'następny znów {}',
    'Annullo:':
        'Cofnę:',
    '↶ Annulla GO {} · {}':
        '↶ Cofnij GO {} · {}',
    'Questo GO non si annulla (azione)':
        'Tego GO nie cofnę (akcja)',
    'Annulla GO {} ({} s)':
        'Cofnij GO {} ({} s)',
    'Nessun GO da annullare':
        'Nie ma GO do cofnięcia',
    '↶ GO {} annullato':
        '↶ Cofnięto GO {}',
    'GO {} annullato · prossima: {}':
        'Cofnięto GO {} · następny: {}',
    'Prima dello spettacolo':
        'Przed przedstawieniem',
    '✓ SÌ':
        '✓ TAK',
    '✗ NO':
        '✗ NIE',
    '– NON VERIFICATO':
        '– NIE SPRAWDZONO',
    '↻ Ricontrolla':
        '↻ Sprawdź ponownie',
    '{} (schermo {})':
        '{} (ekran {})',
    '(non salvato)':
        '(niezapisany)',
    'modifiche non salvate':
        'niezapisane zmiany',
    'Immagine: {}':
        'Obraz: {}',
    "L'immagine va sullo schermo del portatile: proiettore non trovato. Se gli schermi sono duplicati, premi Win+P → Estendi.":
        'Obraz idzie na ekran laptopa – projektor niewykryty. Jeśli ekrany są powielone, naciśnij Win+P → Rozszerz.',
    "L'immagine va sullo schermo del portatile, anche se c'è un altro schermo.":
        'Obraz idzie na ekran laptopa, choć podłączony jest drugi ekran.',
    'Mostra i numeri degli schermi':
        'Pokaż numery ekranów',
    'Scegli lo schermo…':
        'Wybierz ekran…',
    'Volume generale 100 %, senza silenziamento':
        'Głośność główna 100 %, bez wyciszenia',
    'Volume generale {} % · SILENZIATO':
        'Głośność główna {} % · WYCISZONE',
    'Riporta a 100 %':
        'Przywróć 100 %',
    '{} (scelte qui)':
        '{} (przypięte)',
    'Audio: {} – si sente in sala':
        'Dźwięk: {} – słychać w sali',
    "Le casse scelte '{}' non sono collegate: suona l'uscita predefinita di Windows.":
        "Wybrany głośnik '{}' nie jest podłączony – gra domyślne wyjście Windows.",
    'Scegli le casse…':
        'Wybierz głośnik…',
    'Audio: {} – il tono non si sente in sala':
        'Dźwięk: {} – tonu nie słychać w sali',
    '▶ Tono di prova':
        '▶ Ton próbny',
    'Sì, si sente':
        'Tak, słychać',
    'Non si sente':
        'Nie słychać',
    'Audio: {} – il tono non è disponibile, qualcosa suona. Si sente in sala?':
        'Dźwięk: {} – ton niedostępny, coś gra. Słychać to w sali?',
    'Audio: {} – si sente in sala?':
        'Dźwięk: {} – słychać w sali?',
    'Audio: {} – suona il tono di prova e ascolta in sala':
        'Dźwięk: {} – zagraj ton próbny i posłuchaj w sali',
    'Tutti i file al loro posto ({})':
        'Wszystkie pliki na miejscu ({})',
    'File mancanti ({}): {}':
        'Brak plików ({}): {}',
    'Mostra nella lista':
        'Pokaż na liście',
    "Portatile collegato all'alimentatore":
        'Laptop na zasilaczu',
    "Portatile a batteria ({} %): collega l'alimentatore":
        'Laptop na baterii ({} %) – podłącz zasilacz',
    'Lo spettacolo non ha una checklist':
        'Pokaz nie ma listy kontrolnej',
    'Aggiungi la checklist predefinita':
        'Dodaj domyślną listę kontrolną',
    'Spettacolo: {}':
        'Pokaz: {}',
    '▶ Inizia: {}':
        '▶ Zacznij: {}',
    'Problemi: {}. Puoi iniziare lo stesso.':
        'Problemy: {}. Możesz zacząć mimo to.',
    'Tutto pronto.':
        'Wszystko gotowe.',
    'Torna allo spettacolo':
        'Wróć do przedstawienia',
    'Resta in Preparazione':
        'Zostań w Przygotowaniu',
    'proiettore':
        'projektor',
    'alimentatore':
        'zasilacz',
    'Controllo prima dello spettacolo: problemi: {}':
        'Kontrola przed przedstawieniem: problemy: {}',
    'Checklist predefinita aggiunta in cima alla scaletta':
        'Dodano domyślną listę kontrolną na początku listy',
    'Alimentatore collegato al portatile':
        'Zasilacz podłączony do laptopa',
    'Notifiche disattivate (Windows: Non disturbare)':
        'Powiadomienia wyłączone (Windows: Nie przeszkadzać)',
    'Altri programmi chiusi (Teams, browser, OneDrive)':
        'Inne programy zamknięte (Teams, przeglądarka, OneDrive)',
    'Schermo del portatile abbassato':
        'Ekran laptopa przyciemniony',
    'Amplificatore e casse accesi, manopola come alla prova':
        'Wzmacniacz i głośniki włączone, pokrętło jak na próbie',
    'Copia dello spettacolo su chiavetta (File → Salva con nome, portatile)':
        'Kopia pokazu na pendrive (Plik → Zapisz jako, przenośny)',
    'Telefono del telecomando carico, nella stessa rete':
        'Telefon z pilotem naładowany, w tej samej sieci',
    'file':
        'pliki',
    'audio':
        'dźwięk',
    'volume':
        'głośność',
    'checklist':
        'lista kontrolna',
    'Pronto. Non verificato: {}.':
        'Gotowe. Nie sprawdzono: {}.',
    'Sfuma':
        'Wygaś',
    'Sfuma e ferma questa cue (non sposta il GO)':
        'Wygaś i zatrzymaj ten cue (GO zostaje, gdzie jest)',
    'Pausa / riprendi questa cue':
        'Pauza / wznów ten cue',
    'Il loop finisce dopo questo giro':
        'Pętla skończy się po tym przebiegu',
    'Ora in onda':
        'Teraz gra',
    'ORA IN ONDA':
        'TERAZ GRA',
    'Niente in onda.':
        'Nic nie gra.',
    'parte tra {}':
        'startuje za {}',
    'PAUSA':
        'PAUZA',
    'attesa {}':
        'czeka {}',
    'LOOP ∞':
        'PĘTLA ∞',
    'tempo: {}':
        'czas: {}',
    'finisce – il prossimo GO è tuo':
        'kończy się – następne GO należy do Ciebie',
    '✓ suonata':
        '✓ zagrany',
    'in pausa':
        'pauza',
    'in onda':
        'gra',
    'prossima':
        'następny',
    'in attesa':
        'czeka',
    'pronta':
        'gotowy',
    'Indietro di 10 s (tieni premuto)':
        '10 s do tyłu (przytrzymaj)',
    'Avanti di 10 s (tieni premuto)':
        '10 s do przodu (przytrzymaj)',
    'Livello di questa cue (Ctrl+clic = livello della cue)':
        'Poziom tego cue (Ctrl+klik = poziom z cue)',
    'Livello di questa cue':
        'Poziom tego cue',
    '{} a {} % ({} s) da {}':
        '{} do {} % ({} s) przez {}',
    'Auto-GO dopo {} di nuovo attivo':
        'Auto-GO po {} znów działa',
    'Auto-GO dopo {} fermato: la prossima aspetta il GO':
        'Auto-GO po {} wstrzymane: następny czeka na GO',
    'Auto-GO fermato: {} aspetta il GO':
        'Auto-GO wstrzymane: {} czeka na GO',
    'Trattieni':
        'Wstrzymaj',
    'Riprendi Auto-GO':
        'Puść Auto-GO',
    "L'Auto-GO aspetta il GO: la prossima cue non parte da sola":
        'Auto-GO poczeka na GO: następny cue nie ruszy sam',
    '· aspetta il GO (Auto-GO fermato)':
        '· czeka na GO (Auto-GO wstrzymane)',
    '▾ ANTEPRIMA USCITA':
        '▾ PODGLĄD WYJŚCIA',
    '▸ ANTEPRIMA USCITA':
        '▸ PODGLĄD WYJŚCIA',
    'ANTEPRIMA USCITA':
        'PODGLĄD WYJŚCIA',
    "Anteprima dell'uscita":
        'Podgląd wyjścia',
    '◐ Prova':
        '◐ Próba',
    '◐ PROVA':
        '◐ PRÓBA',
    'Prova: lo spettacolo come in scena, con piccole correzioni [Maiusc+F5]':
        'Próba: przedstawienie jak na scenie, z drobnymi poprawkami [Shift+F5]',
    '◐ Prova  (tieni 1,5 s)':
        '◐ Próba  (trzymaj 1,5 s)',
    'Tieni premuto 1,5 s per passare alla prova (ciò che è in onda continua)':
        'Przytrzymaj 1,5 s, żeby przejść do próby (to, co gra, gra dalej)',
    'Passa alla prova: tieni premuto 1,5 secondi':
        'Przejdź do próby: przytrzymaj 1,5 sekundy',
    'Modalità prova (attiva)':
        'Tryb próby (włączony)',
    'Passa alla prova':
        'Przejdź do próby',
    'Correzioni della prova':
        'Poprawki z próby',
    'Chiudi le correzioni (le modifiche restano)':
        'Zamknij poprawki (zmiany zostają)',
    'Chiudi le correzioni':
        'Zamknij poprawki',
    'Nome':
        'Nazwa',
    'Note':
        'Uwagi',
    'Livello della cue':
        'Poziom cue',
    'Livello':
        'Poziom',
    'Entra':
        'Pojawianie',
    'Inizio':
        'Początek',
    'Fine':
        'Koniec',
    'fine':
        'koniec',
    'Poi':
        'Potem',
    'Manuale (GO)':
        'Ręcznie (GO)',
    'Insieme alla successiva':
        'Razem z następnym',
    'Rivedi':
        'Przejrzyj',
    'Altre impostazioni → Preparazione':
        'Więcej ustawień → Przygotowanie',
    'Si cambia quando la cue non suona':
        'Zmienisz, gdy cue nie gra',
    'nome':
        'nazwa',
    'note':
        'uwagi',
    'livello':
        'poziom',
    'entrata':
        'pojawianie',
    'sfumatura':
        'wygaszanie',
    'inizio':
        'początek',
    'poi':
        'potem',
    'Prova: lo spettacolo con piccole correzioni (✎). Ciò che suona continua.':
        'Próba: przedstawienie z drobnymi poprawkami (✎). To, co gra, gra dalej.',
    "✎ CORREGGI {} '{}'":
        "✎ POPRAWIASZ {} '{}'",
    'Modifiche della prova: {}':
        'Zmiany z próby: {}',
    'Prova: {} {} {} → {}':
        'Próba: {} {} {} → {}',
    'Modifiche della prova':
        'Zmiany z próby',
    'Nessuna modifica nella prova.':
        'Brak zmian z próby.',
    'Correggi questa cue (prova)':
        'Popraw ten cue (próba)',
    'Correggi questa cue':
        'Popraw ten cue',
    'Ferma subito questa cue':
        'Zatrzymaj ten cue od razu',
    'Salta a 5 s dalla fine (per provare il finale)':
        'Skocz na 5 s przed końcem (żeby przećwiczyć zakończenie)',
    'Salva livello':
        'Zapisz poziom',
    'Il livello corretto diventa quello della cue':
        'Poprawiony poziom staje się poziomem cue',
    'Nella prova si correggono solo livello, tempi e note. Aggiungere, togliere e spostare: clicca «○ Preparazione»':
        'W Próbie poprawiasz tylko poziom, czasy i uwagi. Dodawanie, usuwanie i przesuwanie: kliknij „○ Przygotowanie”',
    'Spettacolo: {} · modifiche della prova: {}':
        'Pokaz: {} · zmiany z próby: {}',
    'Annulla modifica':
        'Cofnij',
    'Entra (dissolvenza in entrata)':
        'Pojawianie (narastanie)',
    'Sfuma (dissolvenza in uscita)':
        'Wygaszanie',
    'Inizio (dove parte il file)':
        'Początek (skąd rusza plik)',
    'Fine (dove si ferma; «fine» = fine del file)':
        'Koniec (gdzie się zatrzymuje; „koniec” = koniec pliku)',
    'Da / a':
        'Od / do',
    'PIN per uscire dallo spettacolo:':
        'PIN, aby wyjść z Przedstawienia:',
    'Invio – esci':
        'Enter – wyjdź',
    'Inserisci il PIN per uscire dallo spettacolo (GO e PANIC funzionano)':
        'Wpisz PIN, aby wyjść z Przedstawienia (GO i PANIC działają)',
    'Hai dimenticato il PIN? Chiudi il programma (File → Esci): lo spettacolo si riapre in Preparazione.':
        'Nie pamiętasz PIN-u? Zamknij program (Plik → Zakończ); pokaz otworzy się w Przygotowaniu.',
    'PIN sbagliato.':
        'Zły PIN.',
    'Il PIN si cambia in Preparazione':
        'PIN zmienia się w Przygotowaniu',
    'PIN di uscita dallo spettacolo':
        'PIN wyjścia z Przedstawienia',
    '4 cifre per uscire dallo spettacolo su questo computer (vuoto = basta tenere premuto 1,5 s):':
        '4 cyfry do wyjścia z Przedstawienia na tym komputerze (puste = wystarczy przytrzymać 1,5 s):',
    'Il PIN deve avere 4 cifre':
        'PIN musi mieć 4 cyfry',
    'PIN di uscita impostato':
        'Ustawiono PIN wyjścia',
    'PIN di uscita tolto':
        'Usunięto PIN wyjścia',
    'PIN di uscita dallo spettacolo…':
        'PIN wyjścia z Przedstawienia…',
    '{} torna da {}':
        '{} wróci od {}',
    'Cuffie collegate: i suoni per la regia sono spenti (GO, blocchi, cambio di modalità)':
        'Słuchawki podłączone: sygnały dla operatora są wyłączone (GO, blokady, zmiana trybu)',
    'Accendi':
        'Włącz',
    'I suoni per la regia tacciono: le cuffie sono le casse del pubblico':
        'Sygnały dla operatora milczą: słuchawki to głośniki widowni',
    '⚠ Impossibile riprodurre{} (L{}): file mancante, danneggiato o non supportato':
        '⚠ Nie można odtworzyć{} (W{}): brak pliku, plik uszkodzony albo nieobsługiwany',
    'Tieni premuto più a lungo (1,5 s) per uscire dallo spettacolo':
        'Przytrzymaj dłużej (1,5 s), aby wyjść z Przedstawienia',
    'Nessuna immagine nella scaletta':
        'W pokazie nie ma obrazów',
    "Nessun'altra immagine in questa direzione":
        'Nie ma dalszego obrazu w tę stronę',
    "✋ Aspetta l'OK: parte solo dopo la conferma":
        '✋ Czeka na OK: rusza dopiero po potwierdzeniu',
    "Il GO su questa cue la prepara e aspetta l'OK: Invio sulla lista, il pulsante OK o il GO del telecomando nel telefono. Se nel frattempo parte un'altra cue, l'attesa decade.":
        'GO na tym cue tylko go przygotowuje i czeka na OK: Enter na liście, przycisk OK albo GO z pilota w telefonie. Jeśli w międzyczasie ruszy inny cue, czekanie przepada.',
    "✋ {} aspetta l'OK: Invio, il pulsante OK o il GO del telefono":
        '✋ {} czeka na OK: Enter, przycisk OK albo GO z telefonu',
    "Nessuna cue aspetta l'OK":
        'Żaden cue nie czeka na OK',
    "Aspetta l'OK: Invio o il pulsante OK (il GO non basta)":
        'Czeka na OK: Enter albo przycisk OK (samo GO nie wystarczy)',
    'Conferma: la cue parte adesso (anche Invio sulla lista)':
        'Potwierdź: cue rusza teraz (także Enter na liście)',
    "· ✋ aspetta l'OK":
        '· ✋ czeka na OK',
    'Livello di uscita':
        'Poziom wyjścia',
    'Le modifiche della prova si rivedono nella prova o in preparazione':
        'Zmiany z próby przejrzysz w Próbie albo w Przygotowaniu',
    'Annullato: {} {} {} → {}':
        'Cofnięto: {} {} {} → {}',
    'Nessuna correzione della prova da annullare':
        'Brak poprawek z próby do cofnięcia',
    "Nella prova Ctrl+Z annulla l'ultima correzione; ripeti in preparazione":
        'W Próbie Ctrl+Z cofa ostatnią poprawkę; ponów w Przygotowaniu',
    'Sfuma: solo la cue di questa scheda':
        'Wygaś: tylko cue z tej karty',
    'Partenza annullata: la cue non parte':
        'Start anulowany: cue nie ruszy',
    'Annulla partenza':
        'Anuluj start',
    'La cue non partirà':
        'Cue nie ruszy',
    '○ Preparazione (1,5 s)':
        '○ Przygotowanie (1,5 s)',
    '◐ Prova (1,5 s)':
        '◐ Próba (1,5 s)',
    'La scaletta è nascosta: torna alla lista per modificarla':
        'Lista jest zasłonięta: wróć do listy, żeby ją zmienić',
    'Tieni premuto per saltare di 10 s (1,5 s nello spettacolo)':
        'Przytrzymaj, żeby przeskoczyć o 10 s (na przedstawieniu 1,5 s)',
    'IN:':
        'Początek:',
    'OUT:':
        'Koniec:',
    '▾ Più impostazioni':
        '▾ Więcej ustawień',
    '▴ Meno impostazioni':
        '▴ Mniej ustawień',
    'Mostra tutte le schede di questa cue nello stesso posto. Il layout della finestra non cambia.':
        'Pokazuje wszystkie karty ustawień tego cue w tym samym miejscu. Układ okna się nie zmienia.',
    '◐ Transizioni':
        '◐ Przejścia',
    'parte {} s dopo il GO':
        'startuje {} s po GO',
    'aspetta {} s dopo la fine':
        'czeka {} s po końcu',
    'il GO aspetta che finisca':
        'GO czeka, aż skończy',
    "aspetta l'OK":
        'czeka na OK',
    'suona in loop':
        'gra w pętli',
    'si ripete {}×':
        'powtarza się {}×',
    'sezioni: {}':
        'sekcje: {}',
    'il volume cambia nel tempo':
        'głośność zmienia się w czasie',
    'volume livellato':
        'wyrównana głośność',
    'immagine modificata (ritaglio, posizione o opacità)':
        'zmieniony obraz (kadr, położenie lub krycie)',
    'sul proiettore B':
        'na projektorze B',
    'Questa cue ha anche: {}':
        'Ten cue ma też: {}',
    '▦ Layout della finestra':
        '▦ Układ okna',
    '&Semplice – lista, GO e impostazioni di base':
        '&Prosty – lista, GO i podstawowe ustawienia',
    "&Esteso – in più la forma d'onda e tutte le schede":
        '&Rozszerzony – do tego przebieg dźwięku i wszystkie karty',
    '&Completo – tutto, anche i layer e il caricamento rapido':
        'P&ełny – wszystko, także warstwy i szybkie dodawanie',
    '↺ Ripristina layout':
        '↺ Przywróć układ',
    'Quanti pannelli mostra la preparazione (lo spettacolo non cambia)':
        'Ile paneli pokazuje Przygotowanie (pokaz się nie zmienia)',
    'Semplice':
        'Prosty',
    'Esteso':
        'Rozszerzony',
    'Completo':
        'Pełny',
    'Layout: {} ▾':
        'Układ: {} ▾',
    'Layout della finestra: {}':
        'Układ okna: {}',
    'Il layout {} si vede tornando in preparazione':
        'Układ {} zobaczysz po powrocie do Przygotowania',
    'Layout: {}':
        'Układ: {}',
    'Ripristinato il layout {}: larghezze dei pannelli e impostazioni della cue':
        'Przywrócono układ {}: domyślne szerokości paneli i ustawienia cue',
    'Standby: {} [{}]':
        'Następny: {} [{}]',
    "All'avvio sfuma le altre:":
        'Przy starcie wycisza inne:',
    'no':
        'nie',
    'Quando questa cue parte, gli altri suoni e video in onda sfumano in questi secondi (cambio di musica con una sola cue). Una musica sullo stesso layer sfuma invece di essere tagliata. 0 = no.':
        'Gdy ta pozycja startuje, inne grające dźwięki i filmy wyciszają się przez tyle sekund (zmiana muzyki jedną pozycją). Muzyka na tej samej warstwie wycisza się, zamiast zostać ucięta. 0 = nie.',
    "all'avvio sfuma le altre in {} s":
        'przy starcie wycisza inne w {} s',
    "🎵 Effetto a richiesta (fuori dall'ordine del GO)":
        '🎵 Efekt na żądanie (poza kolejnością GO)',
    'Il GO lo salta; parte dal suo tasto o dalla sua piastrella in «Ora in onda», su un lettore libero, senza spostare il GO e senza fermare ciò che suona.':
        'GO go pomija; startuje klawiszem albo kafelkiem w „Teraz gra”, na wolnym odtwarzaczu, bez przesuwania GO i bez zatrzymywania tego, co gra.',
    'Tasto:':
        'Klawisz:',
    "Una lettera o una cifra; nella prova e nello spettacolo fa partire l'effetto. Più cue sullo stesso tasto partono una dopo l'altra (passi).":
        'Litera albo cyfra; w próbie i przedstawieniu uruchamia efekt. Kilka pozycji na tym samym klawiszu startuje po kolei (kroki).',
    "Tasto dell'effetto":
        'Klawisz efektu',
    'Avvia (di nuovo = da capo)':
        'Start (ponownie = od początku)',
    'Avvia / ferma':
        'Start / stop',
    'Suona finché tieni premuto':
        'Gra, dopóki trzymasz klawisz',
    'effetto a richiesta (tasto {})':
        'efekt na żądanie (klawisz {})',
    "Effetto: {} '{}' (il GO resta su {})":
        'Efekt: {} „{}” (GO zostaje na {})',
    'Nessun effetto da ripetere':
        'Brak efektu do powtórzenia',
    "Tutti i lettori degli effetti sono occupati: '{}' lascia il posto":
        'Wszystkie odtwarzacze efektów zajęte: „{}” ustępuje miejsca',
    "↻ Ripeti l'ultimo effetto  [Ctrl+R]":
        '↻ Powtórz ostatni efekt  [Ctrl+R]',
    "Nessun lettore libero per l'effetto '{}': non parte":
        'Brak wolnego odtwarzacza dla efektu „{}”: nie startuje',
    "🤖 L'assistente AI può modificare lo spettacolo":
        '🤖 Asystent AI może zmieniać przedstawienie',
    'Un assistente AI su questo computer (Claude Desktop o un altro client MCP) può leggere lo spettacolo aperto e modificarlo nella preparazione. Ogni modifica si annulla con Ctrl+Z.':
        'Asystent AI na tym komputerze (Claude Desktop albo inny klient MCP) może czytać otwarte przedstawienie i zmieniać je w Przygotowaniu. Każdą zmianę cofa Ctrl+Z.',
    "🤖 Modifiche dall'assistente AI…":
        '🤖 Zmiany od asystenta AI…',
    'Assistente AI: impossibile aprire il collegamento locale':
        'Asystent AI: nie można otworzyć lokalnego połączenia',
    '🤖 Assistente AI collegabile: può modificare lo spettacolo nella preparazione':
        '🤖 Asystent AI może się połączyć: zmienia przedstawienie w Przygotowaniu',
    '🤖 Assistente AI: {}':
        '🤖 Asystent AI: {}',
    'salvato lo spettacolo':
        'zapisał przedstawienie',
    "Nessuna modifica dall'assistente.":
        'Brak zmian od asystenta.',
    "Modifiche dall'assistente AI":
        'Zmiany od asystenta AI',
    'Ogni modifica è un passo di Annulla (Ctrl+Z).':
        'Każda zmiana to jeden krok Cofnij (Ctrl+Z).',
    '(nuovo spettacolo non salvato)':
        '(nowe, niezapisane przedstawienie)',
    'aggiunta la cue':
        'dodał pozycję',
    'aggiunta la didascalia':
        'dodał napis',
    "aggiunta l'azione":
        'dodał akcję',
    'aggiunta la scena':
        'dodał scenę',
    'modificata la cue':
        'zmienił pozycję',
    'spostata la cue':
        'przesunął pozycję',
    'eliminate le cue':
        'usunął pozycje',
    '🤖 Assistente AI…':
        '🤖 Asystent AI…',
    'Assistente AI (MCP)':
        'Asystent AI (MCP)',
    "Un assistente AI (per esempio Claude Desktop) può preparare lo spettacolo per te: crea la scaletta da una cartella di file, aggiunge didascalie, scene e note per l'operatore. Lavora solo nelle cartelle che scegli, non suona niente e non cambia mai uno spettacolo in corso. Ai fornitori di AI arrivano i nomi delle cue, le note e i nomi dei file, non il contenuto dei file.":
        'Asystent AI (np. Claude Desktop) może przygotować przedstawienie za Ciebie: ułoży listę cue z folderu plików, doda napisy, sceny i notatki dla operatora. Działa tylko w folderach, które wskażesz, niczego nie odtwarza i nigdy nie zmienia trwającego przedstawienia. Do dostawcy AI trafiają nazwy cue, uwagi i nazwy plików, nie zawartość plików.',
    "1. Aggiungi l'assistente a Claude Desktop (una volta per computer):":
        '1. Dodaj asystenta do Claude Desktop (raz na komputer):',
    'Aggiungi a Claude Desktop…':
        'Dodaj do Claude Desktop…',
    "Crea il file dell'estensione e lo apre: Claude Desktop chiede quali cartelle l'assistente può usare.":
        'Tworzy plik rozszerzenia i go otwiera: Claude Desktop zapyta, z których folderów asystent może korzystać.',
    'Copia le impostazioni per altri programmi':
        'Kopiuj ustawienia dla innych programów',
    'Impostazioni «mcpServers» (JSON) per Claude Code, Cursor e altri client MCP.':
        'Ustawienia „mcpServers” (JSON) dla Claude Code, Cursora i innych klientów MCP.',
    "2. Se vuoi che l'assistente modifichi lo spettacolo aperto qui (si vede subito, Ctrl+Z annulla), permettilo:":
        '2. Jeśli asystent ma zmieniać przedstawienie otwarte tutaj (widać to od razu, Ctrl+Z cofa), pozwól mu:',
    "L'assistente AI può modificare lo spettacolo (solo nella preparazione)":
        'Asystent AI może zmieniać przedstawienie (tylko w Przygotowaniu)',
    "Modifiche dall'assistente…":
        'Zmiany od asystenta…',
    'Impossibile creare il file: {}':
        'Nie można utworzyć pliku: {}',
    'Creato {}. Se Claude Desktop non si è aperto, trascina questo file nella sua finestra (Impostazioni → Estensioni).':
        'Utworzono {}. Jeśli Claude Desktop się nie otworzył, przeciągnij ten plik do jego okna (Ustawienia → Rozszerzenia).',
    "Creato {} e aperto: conferma l'installazione in Claude Desktop e scegli le cartelle.":
        'Utworzono {} i otwarto: potwierdź instalację w Claude Desktop i wybierz foldery.',
    'Impostazioni copiate (cartella: {}). Incollale nella configurazione del client MCP.':
        'Skopiowano ustawienia (folder: {}). Wklej je do konfiguracji klienta MCP.',
    'Partenza:':
        'Start:',
    'con il GO':
        'z GO',
    "dopo l'avvio di":
        'po starcie',
    'dopo la fine di':
        'po końcu',
    'prima della fine di':
        'przed końcem',
    'Partenza della cue':
        'Start pozycji',
    "Con il GO: come sempre. Le altre scelte fanno partire questa cue da sola rispetto a un'altra (il GO la salta): N s dopo il suo avvio, N s dopo la sua fine, o N s prima della sua fine.":
        'Z GO: jak zawsze. Pozostałe opcje uruchamiają tę pozycję samą, względem innej (GO ją pomija): N s po jej starcie, N s po jej końcu albo N s przed jej końcem.',
    'Cue di riferimento':
        'Pozycja odniesienia',
    'Secondi rispetto alla cue di riferimento':
        'Sekundy względem pozycji odniesienia',
    "Non possibile: quella cue parte già da questa (si avvierebbero a vicenda all'infinito).":
        'Nie można: tamta pozycja już startuje od tej (uruchamiałyby się nawzajem bez końca).',
    "parte da sola rispetto a un'altra cue":
        'startuje sama względem innej pozycji',
    'Partenze relative fermate: le cue si avviano a vicenda in un ciclo':
        'Zatrzymano starty względne: pozycje uruchamiają się nawzajem w kółko',
    '↪ Salta a una cue':
        '↪ Skok do pozycji',
    '📞 Chiama una cue':
        '📞 Wywołaj pozycję',
    '⏩ Sposta la riproduzione':
        '⏩ Przewiń odtwarzanie',
    'Salto: avvia la cue scelta (il GO prosegue da lì) oppure la mette soltanto come prossimo GO. «Al massimo» limita le ripetizioni (per esempio una scena ripetuta due volte).':
        'Skok: uruchamia wybraną pozycję (GO idzie dalej od niej) albo tylko ustawia ją jako następne GO. „Najwyżej” ogranicza powtórzenia (np. scena powtórzona dwa razy).',
    "Avvia la cue scelta senza spostare il GO, come un effetto. Le cue «solo su chiamata» sono fuori dall'ordine del GO.":
        'Uruchamia wybraną pozycję bez przesuwania GO, jak efekt. Pozycje „tylko na wywołanie” są poza kolejnością GO.',
    'Sposta la riproduzione delle cue scelte che stanno suonando: a una posizione del file, avanti o indietro di N secondi, oppure a N secondi dalla fine.':
        'Przesuwa odtwarzanie wybranych, grających pozycji: do miejsca w pliku, o N sekund do przodu lub do tyłu albo na N sekund przed końcem.',
    'Cue del salto o della chiamata':
        'Pozycja skoku lub wywołania',
    'Come:':
        'Jak:',
    'Avviala subito':
        'Uruchom od razu',
    'Solo come prossimo GO':
        'Tylko jako następne GO',
    'sempre':
        'zawsze',
    '0 = salta sempre; N = al massimo N volte, poi il GO prosegue':
        '0 = skacz zawsze; N = najwyżej N razy, potem GO idzie dalej',
    'Al massimo:':
        'Najwyżej:',
    'Dove:':
        'Dokąd:',
    'Alla posizione':
        'Do miejsca',
    'Avanti o indietro di':
        'Do przodu lub do tyłu o',
    'A N secondi dalla fine':
        'Na N sekund przed końcem',
    'Secondi:':
        'Sekundy:',
    'Chiama: {}':
        'Wywołaj: {}',
    'Salta e avvia{}: {}':
        'Skok i start{}: {}',
    'Prossimo GO{}: {}':
        'Następne GO{}: {}',
    ' (al massimo {}×)':
        ' (najwyżej {}×)',
    'Vai a {} s: {}':
        'Przewiń do {} s: {}',
    'Vai a {} s dalla fine: {}':
        'Przewiń na {} s przed końcem: {}',
    'Sposta di {} s: {}':
        'Przesuń o {} s: {}',
    'Salta a una cue':
        'Skok do pozycji',
    'Chiama una cue':
        'Wywołaj pozycję',
    'Sposta la riproduzione':
        'Przewiń odtwarzanie',
    "Salto o chiamata senza una cue valida: '{}'":
        'Skok lub wywołanie bez poprawnej pozycji: „{}”',
    "Salto '{}' già fatto {} volte: il GO prosegue":
        'Skok „{}” wykonany już {} razy: GO idzie dalej',
    'Chiamata: {}':
        'Wywołano: {}',
    'Salto: {}':
        'Skok: {}',
    'Prossimo GO: {}':
        'Następne GO: {}',
    "📞 Solo su chiamata (fuori dall'ordine del GO)":
        '📞 Tylko na wywołanie (poza kolejnością GO)',
    "La avvia soltanto un'azione «Chiama una cue» (o un salto); il GO la salta.":
        'Uruchamia ją tylko akcja „Wywołaj pozycję” (albo skok); GO ją pomija.',
    'Chiamata o salto da: {}':
        'Wywoływana lub skok z: {}',
    'solo su chiamata':
        'tylko na wywołanie',
    '⊘ ESCLUSA':
        '⊘ WYŁĄCZONA',
    'Cue esclusa in questa versione: non parte':
        'Pozycja wyłączona w tej wersji: nie startuje',
    '⊘ Escludi / includi in questa versione':
        '⊘ Wyłącz / włącz w tej wersji',
    '🎭 Versioni dello spettacolo':
        '🎭 Wersje przedstawienia',
    'Spettacolo completo':
        'Pełne przedstawienie',
    'Salva come nuova versione…':
        'Zapisz jako nową wersję…',
    'Elimina la versione «{}»':
        'Usuń wersję „{}”',
    'Versione: {}':
        'Wersja: {}',
    'Nuova versione dello spettacolo':
        'Nowa wersja przedstawienia',
    'Nome della versione (per esempio «ridotta», «secondo cast»):':
        'Nazwa wersji (np. „skrócona”, „druga obsada”):',
    '{} è usata da: {}':
        'na „{}” wskazuje: {}',
    'Incluse {} cue':
        'Włączono {} poz.',
    'Escluse {} cue':
        'Wyłączono {} poz.',
    'Attenzione: ':
        'Uwaga: ',
    'Versione: {} · {} cue escluse':
        'Wersja: {} · wyłączonych: {}',
    'insieme':
        'razem',
    'Nello spettacolo non si salta: usa la prova':
        'W przedstawieniu nie przeskakujemy: użyj Próby',
    'opacità {}%':
        'krycie {}%',
    'Prova da {}.':
        'Próba od {}.',
    'Prima di questa cue restano in onda:':
        'Przed tą pozycją zostają na scenie:',
    'Prima di questa cue non resta niente in onda.':
        'Przed tą pozycją nic nie zostaje na scenie.',
    'Ora suona qualcosa: verrà fermato.':
        'Teraz coś gra: zostanie zatrzymane.',
    'Prova da qui':
        'Próba od tego miejsca',
    '▶ Prepara la scena':
        '▶ Przygotuj scenę',
    'Scena pronta: il prossimo GO è {}':
        'Scena gotowa: następne GO to {}',
    '⏯ Prova da qui (prepara la scena)':
        '⏯ Próba od tego miejsca (przygotuj scenę)',
    'Conto alla rovescia':
        'Odliczanie',
    '⏳ Conto alla rovescia':
        '⏳ Odliczanie',
    '⏳ Conto alla rovescia…':
        '⏳ Odliczanie (przerwa)…',
    '🖥 Conto alla rovescia grande (quinte)':
        '🖥 Duże odliczanie (kulisy)',
    '⏹ Ferma il conto alla rovescia':
        '⏹ Zatrzymaj odliczanie',
    'Ferma il conto alla rovescia':
        'Zatrzymaj odliczanie',
    'Conto alla rovescia {}: {}':
        'Odliczanie {}: {}',
    'Intervallo':
        'Przerwa',
    "Minuti (per esempio l'intervallo):":
        'Minuty (np. przerwa):',
    'Fine del conto alla rovescia: {}':
        'Koniec odliczania: {}',
    'la volta scorsa a {}':
        'poprzednio o {}',
    "Avvia un conto alla rovescia (per esempio l'intervallo) sulla barra di stato e nella finestra grande per le quinte (menu Show). Il testo è il titolo; 0 minuti lo ferma.":
        'Uruchamia odliczanie (np. przerwy) na pasku stanu i w dużym oknie dla kulis (menu Przedstawienie). Tekst to tytuł; 0 minut zatrzymuje odliczanie.',
    'ferma':
        'stop',
    'Tempo rimanente':
        'Pozostały czas',
    'Piano orario sospeso':
        'Plan godzinowy wstrzymany',
    'Piano orario attivo':
        'Plan godzinowy aktywny',
    '(sospeso)':
        '(wstrzymany)',
    "'{}' saltata: più di un minuto di ritardo sull'orario {}":
        '„{}” pominięta: ponad minutę po godzinie {}',
    'Alle {}: {}':
        'O {}: {}',
    '🕐 Piano orario anche nella prova':
        '🕐 Plan godzinowy także w Próbie',
    'Alle ore:':
        'O godzinie:',
    "2.6: la cue parte da sola a quest'ora durante lo spettacolo (il GO la salta). Più di un minuto in ritardo: saltata. Vuoto = con il GO.":
        'Pozycja startuje sama o tej godzinie w czasie przedstawienia (GO ją pomija). Ponad minutę spóźniona: pominięta. Puste = z GO.',
    'Ora di partenza della cue':
        'Godzina startu pozycji',
    'parte alle {}':
        'startuje o {}',
    'al segno di':
        'na znaczniku',
    'Segno della cue di riferimento':
        'Znacznik pozycji odniesienia',
    'Segni:':
        'Znaczniki:',
    'Segni della cue':
        'Znaczniki pozycji',
    'Elimina il segno scelto (non se una cue parte da lì)':
        'Usuń wybrany znacznik (nie, gdy jakaś pozycja od niego startuje)',
    "Quella cue non ha segni: mettine uno sulla sua forma d'onda (◆ Segno).":
        'Ta pozycja nie ma znaczników: dodaj go na jej przebiegu (◆ Znacznik).',
    '◆ Segno':
        '◆ Znacznik',
    'Mette un segno sulla testina (Ctrl+K: anche sulla cue in onda, per esempio battendo a tempo in prova). Una cue può partire «al segno».':
        'Stawia znacznik na głowicy (Ctrl+K: także na grającej pozycji, np. wystukując rytm na próbie). Inna pozycja może startować „na znaczniku”.',
    'Segno: scegli una cue audio o video':
        'Znacznik: wybierz pozycję audio lub wideo',
    'Segno: nessuna posizione (fai partire la cue o sposta la testina)':
        'Znacznik: brak pozycji (uruchom pozycję albo przesuń głowicę)',
    'Segno ◆{} a {} s':
        'Znacznik ◆{} w {} s',
    'Il segno ◆{} è usato da {}: non si può eliminare':
        'Znacznik ◆{} jest używany przez {}: nie można go usunąć',
    'Cerca: nome, Q, note, file…  (Invio: primo risultato, Esc: chiudi)':
        'Szukaj: nazwa, Q, uwagi, plik…  (Enter: pierwszy wynik, Esc: zamknij)',
    'Cerca nella scaletta':
        'Szukaj na liście',
    'Cerca una cue':
        'Szukaj pozycji',
    'Nome, Q, note o file:':
        'Nazwa, Q, uwagi albo plik:',
    'Trovate {} cue su {}':
        'Znaleziono {} z {} pozycji',
    "Nessuna cue trovata: '{}'":
        'Nie znaleziono: „{}”',
    "'{}' ha sezioni: le cue che partono sui suoi segni non partono":
        "'{}' ma sekcje: pozycje startujące na jego znacznikach nie wystartują",
    'segni':
        'znaczniki',
    '⌛ Attendi, poi la successiva':
        '⌛ Czekaj, potem następna',
    '▶ Riprendi':
        '▶ Wznów',
    '⏱ Cronometro':
        '⏱ Stoper',
    "Un'attesa visibile nella scaletta: dopo i secondi indicati parte la cue successiva, senza GO. Pausa generale la trattiene, PANIC la annulla.":
        'Oczekiwanie widoczne na liście: po podanych sekundach startuje następna pozycja, bez GO. Pauza wszystkiego je wstrzymuje, PANIC kasuje.',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano.':
        'Wstrzymuje wybrane grające pozycje (dźwięk i wideo); pozostałe grają dalej.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate.':
        'Wznawia wybrane wstrzymane pozycje od miejsca, w którym stanęły.',
    'Cronometro sulla barra di stato (per esempio la durata di un atto): avvia, ferma (si riprende da lì) o azzera. PANIC non lo tocca.':
        'Stoper na pasku stanu (np. czas trwania aktu): start, stop (wznawia od tego miejsca) albo zerowanie. PANIC go nie rusza.',
    'Avvia':
        'Start',
    'Ferma':
        'Stop',
    'Azzera':
        'Zeruj',
    'Cronometro:':
        'Stoper:',
    'Cronometro':
        'Stoper',
    'Attendi {} s, poi la successiva':
        'Czekaj {} s, potem następna',
    'Cronometro: avvia':
        'Stoper: start',
    'Cronometro: ferma':
        'Stoper: stop',
    'Cronometro: azzera':
        'Stoper: zeruj',
    'Pausa: {}':
        'Pauza: {}',
    'Riprendi: {}':
        'Wznów: {}',
    'Attendi':
        'Czekaj',
    'Pausa':
        'Pauza',
    'Riprendi':
        'Wznów',
    'Partenza relativa persa (cue di riferimento eliminata): {} ora parte con il GO':
        'Start względny utracony (pozycja odniesienia usunięta): {} startuje teraz z GO',
    'Palco':
        'Scena',
    'Sala':
        'Sala',
    'Spie (ascolto palco)':
        'Odsłuch (dla aktorów)',
    'Muto':
        'Wycisz',
    'uscita predefinita':
        'wyjście domyślne',
    "'{}': {} non disponibile, suona su: {}":
        "'{}': {} niedostępne, gra na: {}",
    'Uscita:':
        'Wyjście:',
    'Dove suona questa cue. Quale altoparlante è Palco, Sala o Spie su questo computer si sceglie in Dispositivi → Uscite audio. Muto: un video senza il suo audio.':
        'Gdzie gra ta pozycja. Który głośnik jest Sceną, Salą albo Odsłuchem na tym komputerze, wybiera się w Przedstawienie → Wyjścia dźwięku. Wycisz: film bez dźwięku.',
    'Uscita audio della cue':
        'Wyjście dźwięku pozycji',
    'Uscite audio di questo computer':
        'Wyjścia dźwięku tego komputera',
    "Ogni cue suona su un'uscita: Palco, Sala o Spie (ascolto per gli attori). Qui si sceglie quale altoparlante è ognuna su questo computer; lo spettacolo non cambia su un altro computer.":
        'Każda pozycja gra na jednym wyjściu: Scena, Sala albo Odsłuch (dla aktorów). Tu wybierasz, który głośnik jest którym wyjściem na tym komputerze; przedstawienie na innym komputerze się nie zmienia.',
    'Uscita':
        'Wyjście',
    'Se manca':
        'Gdy brak',
    'Regolazione':
        'Korekta',
    '▶ Prova':
        '▶ Test',
    'Dispositivo: {}':
        'Urządzenie: {}',
    'Se manca: {}':
        'Gdy brak: {}',
    'Regolazione: {}':
        'Korekta: {}',
    'Prova: {}':
        'Test: {}',
    'Predefinito di sistema':
        'Domyślne systemowe',
    '— non impostata —':
        '— nieustawione —',
    'muto':
        'wyciszone',
    'muto (nessun suono)':
        'wyciszone (bez dźwięku)',
    'Durante lo spettacolo le uscite non si cambiano e non si provano.':
        'W czasie przedstawienia wyjść nie zmienia się ani nie testuje.',
    '▶ Prova tutte in ordine':
        '▶ Testuj wszystkie po kolei',
    'Esporta…':
        'Eksportuj…',
    'Importa…':
        'Importuj…',
    'Esporta le uscite audio':
        'Eksport wyjść dźwięku',
    'Importa le uscite audio':
        'Import wyjść dźwięku',
    'Esportato: {}':
        'Wyeksportowano: {}',
    'Non è una mappa di uscite audio: {}':
        'To nie jest mapa wyjść dźwięku: {}',
    'Uscita predefinita':
        'Wyjście domyślne',
    'Come il Palco':
        'Jak Scena',
    '🔊 Uscite audio (Palco / Sala / Spie)…':
        '🔊 Wyjścia dźwięku (Scena / Sala / Odsłuch)…',
    'Uscite audio: {}':
        'Wyjścia dźwięku: {}',
    'Uscite audio non impostate o scollegate: {}':
        'Wyjścia dźwięku nieustawione albo odłączone: {}',
    'Uscite audio…':
        'Wyjścia dźwięku…',
    'Dispositivo':
        'Urządzenie',
    'Playlist ({} brani)':
        'Playlista (utwory: {})',
    'Playlist':
        'Playlista',
    "{} file audio: farne una playlist (una riga che li suona uno dopo l'altro)?":
        'Pliki audio ({}): zrobić z nich playlistę (jeden wiersz, który gra je po kolei)?',
    'Una playlist':
        'Jedna playlista',
    'Cue separate':
        'Osobne pozycje',
    'Playlist non leggibile: {}':
        'Nie można odczytać playlisty: {}',
    "Playlist '{}': {} brani":
        "Playlista '{}' – utwory: {}",
    'non trovati o in streaming: {}':
        'nieznalezione albo strumienie: {}',
    'Importa playlist':
        'Import playlisty',
    '🎵 Importa playlist (.m3u)…':
        '🎵 Importuj playlistę (.m3u)…',
    '{} non collegato ({}): suona su {}':
        '{} niepodłączone ({}): gra na: {}',
    'lo stesso dispositivo del pubblico':
        'to samo urządzenie co dla widowni',
    'Le spie usano lo stesso dispositivo del pubblico: la traccia privata si sente in sala.':
        'Odsłuch używa tego samego urządzenia co widownia: prywatna ścieżka będzie słyszalna na sali.',
    'Qualcosa suona: la prova non parte.':
        'Coś gra: test nie wystartuje.',
    'Sostituire le uscite audio di questo computer con quelle del file?':
        'Zastąpić wyjścia dźwięku tego komputera tymi z pliku?',
    'uscite audio':
        'wyjścia dźwięku',
    'Addormenta in {} s: {}':
        'Uśpij w {} s: {}',
    'Risveglia in {} s: {}':
        'Obudź w {} s: {}',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano. Con una durata la musica si addormenta: sfuma e poi si ferma.':
        'Wstrzymuje wybrane grające pozycje (dźwięk i wideo); pozostałe grają dalej. Z czasem trwania muzyka się usypia: cichnie, potem staje.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate. Con una durata la musica si risveglia: entra piano fino al livello di prima.':
        'Wznawia wybrane wstrzymane pozycje od miejsca, w którym stanęły. Z czasem trwania muzyka się budzi: wchodzi powoli do poprzedniego poziomu.',
    "Taglia il silenzio all'inizio e alla fine: IN e OUT dove il suono comincia e finisce davvero (sotto -40 dB rispetto al picco).":
        'Utnij ciszę na początku i końcu: IN i OUT tam, gdzie dźwięk naprawdę się zaczyna i kończy (poniżej -40 dB względem szczytu).',
    "Taglia il silenzio all'inizio e alla fine":
        'Utnij ciszę na początku i końcu',
    "Taglia il silenzio: forma d'onda non ancora pronta o file muto":
        'Utnij ciszę: przebieg jeszcze niegotowy albo plik bez dźwięku',
    'Silenzio tagliato (sotto {} dB): IN {} s, OUT {}':
        'Cisza ucięta (poniżej {} dB): IN {} s, OUT {}',
    'Una playlist non può stare dentro una scena: aggiunte cue separate':
        'Playlista nie może być wewnątrz sceny: dodano osobne pozycje',
    'Dissolvenza:':
        'Przejście:',
    'subito':
        'od razu',
    '0 = subito; più secondi = la musica si addormenta / si risveglia piano':
        '0 = od razu; więcej sekund = muzyka usypia się / budzi powoli',
    'Mette in pausa le cue scelte che stanno suonando (audio e video); le altre continuano. Con una dissolvenza la musica si addormenta: sfuma e poi si ferma.':
        'Wstrzymuje wybrane grające pozycje (dźwięk i wideo); pozostałe grają dalej. Z przejściem muzyka się usypia: cichnie, potem staje.',
    'Fa ripartire le cue scelte messe in pausa, da dove si erano fermate. Con una dissolvenza la musica si risveglia: entra piano fino al livello di prima.':
        'Wznawia wybrane wstrzymane pozycje od miejsca, w którym stanęły. Z przejściem muzyka się budzi: wchodzi powoli do poprzedniego poziomu.',
    'Tempo:':
        'Tempo:',
    'Velocità di riproduzione: 100 % = come registrato (per adattare la musica a una coreografia).':
        'Szybkość odtwarzania: 100 % = jak nagrano (np. dopasowanie muzyki do choreografii).',
    'Tempo della cue in percento':
        'Tempo pozycji w procentach',
    "Mantieni l'intonazione":
        'Zachowaj wysokość dźwięku',
    "Più veloce o più lento senza cambiare l'altezza delle note.":
        'Szybciej albo wolniej bez zmiany wysokości dźwięków.',
    "📋 Copia il layout dell'immagine":
        '📋 Kopiuj układ obrazu',
    '📌 Incolla il layout sulle selezionate':
        '📌 Wklej układ na zaznaczone',
    "Layout: scegli un'immagine o un video":
        'Układ: wybierz zdjęcie albo film',
    "Layout copiato da '{}'":
        "Skopiowano układ z '{}'",
    "Prima copia il layout di un'immagine o di un video":
        'Najpierw skopiuj układ zdjęcia albo filmu',
    'Layout incollato su {} cue':
        'Wklejono układ na pozycje: {}',
    '🎞 Foto con questa musica':
        '🎞 Zdjęcia do tej muzyki',
    'Foto con musica: seleziona almeno due immagini e un solo audio':
        'Zdjęcia do muzyki: zaznacz co najmniej dwa zdjęcia i jeden dźwięk',
    'Foto con musica: non dentro una scena':
        'Zdjęcia do muzyki: nie wewnątrz sceny',
    "Foto con musica: durata di '{}' sconosciuta":
        "Zdjęcia do muzyki: nieznana długość '{}'",
    'Foto: {}':
        'Zdjęcia: {}',
    "Foto con musica: {} immagini da {} s su '{}' ({} s)":
        "Zdjęcia do muzyki: zdjęcia {} × {} s do '{}' ({} s)",
    "Foto con musica: '{}' ha un loop o sezioni":
        "Zdjęcia do muzyki: '{}' ma pętlę albo sekcje",
    'Foto con musica: troppe immagini (almeno 1 s ciascuna)':
        'Zdjęcia do muzyki: za dużo zdjęć (co najmniej 1 s na zdjęcie)',
    'Copione:':
        'Scenariusz:',
    'pag.':
        'str.',
    'Pagina del copione':
        'Strona scenariusza',
    'Battuta su cui parte…':
        'Kwestia, na której wchodzi…',
    'Battuta su cui parte la cue':
        'Kwestia, na której wchodzi pozycja',
    '📄 Esporta la scaletta (CSV)…':
        '📄 Eksportuj listę (CSV)…',
    '🖨 Stampa la scaletta per la regia…':
        '🖨 Drukuj listę dla operatora…',
    '🖨 Stampa la scaletta per il suggeritore…':
        '🖨 Drukuj listę dla suflera…',
    'Tipo':
        'Typ',
    'Layer':
        'Warstwa',
    'Pagina':
        'Strona',
    'Battuta':
        'Kwestia',
    'File':
        'Plik',
    'Esporta la scaletta':
        'Eksport listy',
    'Scaletta esportata: {}':
        'Lista wyeksportowana: {}',
    'regia':
        'operator',
    'suggeritore':
        'sufler',
    'Spettacolo':
        'Przedstawienie',
    'Stampa con Ctrl+P (orizzontale per molte colonne).':
        'Drukuj Ctrl+P (poziomo, gdy kolumn jest dużo).',
    'Scaletta aperta nel browser: stampa con Ctrl+P':
        'Lista otwarta w przeglądarce: drukuj Ctrl+P',
    'Rinumera le Q':
        'Przenumeruj Q',
    '🔢 Rinumera le Q…':
        '🔢 Przenumeruj Q…',
    'Le cue selezionate lanciate con GO ({})':
        'Zaznaczone pozycje uruchamiane GO ({})',
    'Tutte le cue lanciate con GO ({})':
        'Wszystkie pozycje uruchamiane GO ({})',
    'Prefisso:':
        'Przedrostek:',
    'Primo numero:':
        'Pierwszy numer:',
    'Passo:':
        'Krok:',
    'Passo 10 lascia spazio per le cue aggiunte dopo (Q10, Q15, Q20)':
        'Krok 10 zostawia miejsce na pozycje dodane później (Q10, Q15, Q20)',
    'Prima':
        'Przed',
    'Dopo':
        'Po',
    'Q rinumerate: {}':
        'Przenumerowane Q: {}',
    '📥 Importa cue da un altro spettacolo…':
        '📥 Importuj pozycje z innego przedstawienia…',
    'Importa cue da un altro spettacolo':
        'Import pozycji z innego przedstawienia',
    'Spunta le cue da importare (una scena porta le sue cue):':
        'Zaznacz pozycje do importu (scena przynosi swoje pozycje):',
    "'{}': partenza relativa a una cue non importata – parte con il GO":
        "'{}': start względem pozycji, której nie importujesz – startuje z GO",
    "'{}': {} cue bersaglio non importate":
        "'{}': pozycje docelowe bez importu: {}",
    "'{}': file non trovato":
        "'{}': nie znaleziono pliku",
    "Importate {} cue da '{}'":
        "Zaimportowane pozycje: {} z '{}'",
    'Esclusa':
        'Wyłączona',
    '⚠ Già usate da altre cue: {} – due cue avrebbero la stessa Q':
        '⚠ Już używane przez inne pozycje: {} – dwie pozycje miałyby to samo Q',
    "'{}': legata a una cue non importata (Simult. / Auto-GO) – ora parte con il GO":
        "'{}': powiązana z pozycją, której nie importujesz (Razem / Auto-GO) – teraz startuje z GO",
    "'{}': era esclusa in quello spettacolo – qui è inclusa":
        "'{}': była wyłączona w tamtym przedstawieniu – tu jest włączona",
    "'{}': il suo tasto è già usato da un effetto di questo spettacolo":
        "'{}': jej klawisz ma już efekt w tym przedstawieniu",
    "'{}': parte a un'ora del giorno":
        "'{}': startuje o wyznaczonej godzinie",
    "'{}': parte solo da un'azione, che non è stata importata":
        "'{}': startuje tylko z akcji, której nie importujesz",
    '… e altre {}':
        '… i jeszcze {}',
    '🔢 Identifica':
        '🔢 Identyfikuj',
    "Mostra per qualche secondo un grande numero su ogni schermo (lo stesso numero dell'elenco)":
        'Pokazuje na kilka sekund duży numer na każdym ekranie (ten sam co na liście)',
    'Identifica gli schermi':
        'Identyfikacja ekranów',
    'Qualcosa è in onda: il numero coprirebbe il proiettore davanti al pubblico. Riprova quando nulla è in onda.':
        'Coś jest na wizji: numer zasłoniłby projektor przed widownią. Spróbuj, gdy nic nie będzie na wizji.',
    'Regia':
        'Reżyserka',
    'Proiettore / esterno':
        'Projektor / zewnętrzny',
    'Schermo {}':
        'Ekran {}',
    "parte dopo una cue che non c'è più":
        'startuje po pozycji, której już nie ma',
    'le sue cue bersaglio non ci sono più: non fa nulla':
        'jej pozycji docelowych już nie ma: nic nie zrobi',
    "salta o chiama una cue che non c'è":
        'skacze do pozycji albo wywołuje pozycję, której nie ma',
    'scena senza nulla da suonare':
        'scena bez niczego do zagrania',
    'parte solo se chiamata, ma nessuna azione la chiama':
        'startuje tylko z wywołania, ale żadna akcja jej nie wywołuje',
    'Da sistemare nella lista ({}): {}':
        'Do poprawienia na liście ({}): {}',
    "Cue a un'ora del giorno: {} – l'orologio del computer segna {}. È giusto?":
        'Pozycje o wyznaczonej godzinie: {} – zegar komputera pokazuje {}. Czy to dobra godzina?',
    'Poco spazio libero sul disco dello spettacolo: {} MB – il salvataggio può non riuscire':
        'Mało miejsca na dysku przedstawienia: {} MB – zapis może się nie udać',
    'ℹ Informazioni sullo spettacolo…':
        'ℹ Informacje o przedstawieniu…',
    'Informazioni sullo spettacolo':
        'Informacje o przedstawieniu',
    'Titolo:':
        'Tytuł:',
    'Autore / regia:':
        'Autor / reżyseria:',
    'Note:':
        'Notatki:',
    'Cue: {} · GO: {} · video {} · audio {} · immagini {} · testi {} · scene {} · azioni {} · effetti {} · escluse {} · file mancanti {}':
        'Pozycje: {} · GO: {} · wideo {} · dźwięk {} · obrazy {} · napisy {} · sceny {} · akcje {} · efekty {} · wyłączone {} · brakujące pliki {}',
    'Informazioni sullo spettacolo salvate con lo spettacolo':
        'Informacje zostaną zapisane razem z przedstawieniem',
    '⌨ Tasti e telecomando di presentazione…':
        '⌨ Klawisze i pilot prezentera…',
    'Tasti e telecomando di presentazione':
        'Klawisze i pilot prezentera',
    'Tasti in più per questo computer, attivi nella prova e nello spettacolo. I tasti del programma restano (Spazio = GO, Esc due volte = PANIC). Un telecomando di presentazione funziona come una tastiera: premi i suoi pulsanti qui sotto.':
        'Dodatkowe klawisze na tym komputerze, działają w Próbie i w Przedstawieniu. Klawisze programu zostają (Spacja = GO, Esc dwa razy = PANIC). Pilot prezentera działa jak klawiatura: naciśnij jego przyciski poniżej.',
    'Funzione':
        'Funkcja',
    'Tasti':
        'Klawisze',
    'Aggiungi un tasto…':
        'Dodaj klawisz…',
    'Togli':
        'Usuń',
    '🎯 Procedura guidata del telecomando…':
        '🎯 Kreator pilota…',
    'Telecomando di presentazione (tasti tipici)':
        'Pilot prezentera (typowe klawisze)',
    'Predefiniti (nessun tasto in più)':
        'Domyślne (bez dodatkowych klawiszy)',
    'Premi un tasto':
        'Naciśnij klawisz',
    'Interrompi':
        'Przerwij',
    'Premi il tasto o il pulsante del telecomando per: {}':
        'Naciśnij klawisz albo przycisk pilota dla: {}',
    'Premi sul telecomando il pulsante per: {}':
        'Naciśnij na pilocie przycisk dla: {}',
    '⚠ {}: il programma lo usa già ({})':
        '⚠ {}: program już go używa ({})',
    '⚠ {}: assegnato a due funzioni – vale la prima':
        '⚠ {}: przypisany do dwóch funkcji – działa pierwsza',
    "⚠ {}: è il tasto di un effetto di questo spettacolo – vale l'effetto":
        '⚠ {}: to klawisz efektu w tym przedstawieniu – działa efekt',
    'Tasti aggiuntivi salvati per questo computer':
        'Dodatkowe klawisze zapisane na tym komputerze',
    'Cue precedente (solo selezione)':
        'Poprzednia pozycja (tylko zaznaczenie)',
    'Cue successiva (solo selezione)':
        'Następna pozycja (tylko zaznaczenie)',
    'Pausa tutto / riprendi':
        'Wstrzymaj wszystko / wznów',
    'Sfuma tutto':
        'Wygaś wszystko',
    'PANIC (2×)':
        'PANIC (2×)',
    'Selezione':
        'Zaznaczenie',
    'Punto IN':
        'Punkt IN',
    'Punto OUT':
        'Punkt OUT',
    'Elimina':
        'Usuń',
    '📁 Nuovo spettacolo da una cartella…':
        '📁 Nowe przedstawienie z folderu…',
    '📋 Importa una scaletta (CSV)…':
        '📋 Importuj listę pozycji (CSV)…',
    'Nuovo spettacolo da una cartella':
        'Nowe przedstawienie z folderu',
    'Nella cartella non ci sono video, suoni o immagini.':
        'W folderze nie ma filmów, dźwięków ani obrazów.',
    '{} file in ordine di nome. Come aggiungerli?':
        'Plików: {} (w kolejności nazw). Jak je dodać?',
    'Una scena (un GO per elemento)':
        'Jedna scena (GO na każdy element)',
    "Nuovo spettacolo: {} file da '{}'":
        "Nowe przedstawienie: plików {} z '{}'",
    'Importa una scaletta (CSV)':
        'Import listy pozycji (CSV)',
    'Il file non è una scaletta: serve una prima riga con i nomi delle colonne (almeno Nome o File).':
        'To nie jest lista pozycji: pierwszy wiersz musi zawierać nazwy kolumn (co najmniej Nazwa albo Plik).',
    'Nessuna riga da importare':
        'Brak wierszy do importu',
    "Importate {} righe da '{}'":
        "Zaimportowane wiersze: {} z '{}'",
    'senza file (da collegare): {}':
        'bez pliku (do dołączenia): {}',
    'Salva prima lo spettacolo, poi fissalo':
        'Najpierw zapisz przedstawienie, potem je przypnij',
    "Spettacolo fissato in 'Apri recenti'":
        'Przedstawienie przypięte w „Otwórz ostatnie”',
    'Spettacolo non più fissato':
        'Przedstawienie odpięte',
    '📌 Non fissare più questo spettacolo':
        '📌 Odepnij to przedstawienie',
    '📌 Fissa questo spettacolo in cima':
        '📌 Przypnij to przedstawienie na górze',
    '📂 Scegli il file…':
        '📂 Wybierz plik…',
    '🔎 Cerca i file mancanti in una cartella…':
        '🔎 Szukaj brakujących plików w folderze…',
    '🔎 Cerca in una cartella…':
        '🔎 Szukaj w folderze…',
    'Cerca i file mancanti in una cartella':
        'Szukanie brakujących plików w folderze',
    'Tutti i file sono al loro posto':
        'Wszystkie pliki są na miejscu',
    'Cue senza file: {} – clic destro → Scegli il file…':
        'Pozycje bez pliku: {} – prawy przycisk → Wybierz plik…',
    'Nessuno dei {} file mancanti è in questa cartella.':
        'Żadnego z brakujących plików ({}) nie ma w tym folderze.',
    'File ritrovati: {} di {}':
        'Odnalezione pliki: {} z {}',
    'Nomi trovati più volte (usato il primo): {}':
        'Nazwy znalezione kilka razy (użyty pierwszy): {}',
    'Scegli una cue video, audio o immagine':
        'Wybierz pozycję z filmem, dźwiękiem albo obrazem',
    "Scegli il file per '{}'":
        "Wybierz plik dla '{}'",
    'Formato non supportato: {}':
        'Nieobsługiwany format: {}',
    "'{}' suona ora: {}":
        "'{}' gra teraz plik: {}",
    '🕘 Storia delle modifiche…':
        '🕘 Historia zmian…',
    '🕘 Ripristina una copia di sicurezza…':
        '🕘 Przywróć kopię zapasową…',
    'Storia delle modifiche':
        'Historia zmian',
    'Le modifiche che Ctrl+Z può annullare, la più recente in alto:':
        'Zmiany, które Ctrl+Z może cofnąć, najnowsza na górze:',
    'Nessuna modifica da annullare':
        'Brak zmian do cofnięcia',
    '↶ Annulla fino a qui (compresa)':
        '↶ Cofnij do tego miejsca (włącznie)',
    'Annullate {} modifiche (Ctrl+Y le ripete)':
        'Cofnięte zmiany: {} (Ctrl+Y je przywraca)',
    'Aggiunte {} cue ({}…)':
        'Dodane pozycje: {} ({}…)',
    'Aggiunta {}':
        'Dodana {}',
    'Eliminate {} cue ({}…)':
        'Usunięte pozycje: {} ({}…)',
    'Eliminata {}':
        'Usunięta {}',
    'Cue sostituite ({}…)':
        'Pozycje zamienione ({}…)',
    'Ordine cambiato ({}…)':
        'Zmieniona kolejność ({}…)',
    '{}: {} campi ({})':
        '{}: zmienione pola: {} ({})',
    '{} cue cambiate: {}':
        'Zmienione pozycje: {} – {}',
    '{} cue cambiate':
        'Zmienione pozycje: {}',
    'Nessuna differenza nella lista':
        'Bez zmian na liście',
    'Ripristina una copia di sicurezza':
        'Przywracanie kopii zapasowej',
    'Lo spettacolo non è ancora salvato: non ha copie di sicurezza':
        'Przedstawienie nie jest jeszcze zapisane: nie ma kopii zapasowych',
    'Ancora nessuna copia: il programma ne fa una a ogni salvataggio.':
        'Jeszcze nie ma kopii: program robi ją przy każdym zapisie.',
    "La scaletta com'era al salvataggio delle:":
        'Lista pozycji z zapisu z dnia i godziny:',
    'Scaletta ripristinata dalla copia delle {} (Ctrl+Z torna indietro)':
        'Lista przywrócona z kopii z {} (Ctrl+Z cofa)',
    'layer':
        'warstwa',
    'inclusa':
        'włączona',
    'scena':
        'scena',
    'modo della scena':
        'tryb sceny',
    'colore':
        'kolor',
    'dissolvenza':
        'przenikanie',
    'tempo':
        'tempo',
    'pagina':
        'strona',
    'battuta':
        'kwestia',
    'tasto':
        'klawisz',
    'effetto':
        'efekt',
    'ora':
        'godzina',
    'azione':
        'akcja',
    'testo':
        'tekst',
    'marcatori':
        'znaczniki',
    'uscita audio':
        'wyjście dźwięku',
    'Scena':
        'Scena',
    '{} file: farne una scena (un GO per elemento)?':
        'Plików: {} – zrobić z nich jedną scenę (GO na każdy element)?',
    'Una scena':
        'Jedna scena',
    'Scena ({} elementi)':
        'Scena ({} elementów)',
    '❚❚  Pausa':
        '❚❚  Pauza',
    '❚❚  PAUSA TUTTO':
        '❚❚  PAUZA WSZYSTKO',
    '❚❚ SHOW IN PAUSA':
        '❚❚ PRZEDSTAWIENIE WSTRZYMANE',
    '❚❚ Metti in Pausa (Prove)':
        '❚❚ Pauza (próby)',
    '❚❚ TRACCIA AUDIO IN STANDBY':
        '❚❚ ŚCIEŻKA AUDIO W GOTOWOŚCI',
    '❚❚ PAUSA':
        '❚❚ PAUZA',
    '❚❚ Sospendi il piano orario':
        '❚❚ Wstrzymaj plan godzinowy',
    '❚❚ Pausa':
        '❚❚ Pauza',
    "Annulla l'ultimo GO":
        'Cofnij ostatnie GO',
    '❚❚ &Pausa / riprendi tutto':
        '❚❚ &Pauza / wznów wszystko',
}
