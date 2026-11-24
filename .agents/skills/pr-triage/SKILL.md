---
name: pr-triage
description: Censimento e revisione controllata delle Pull Request di BlindCUE tramite gh CLI, CodeRabbit e test locali in worktree isolato.
---

# Skill `pr-triage` — Governance e Revisione PR per BlindCUE

Questa skill gestisce l'analisi e la revisione delle Pull Request del repository BlindCUE in due modalità operative distinte.

## Prerequisiti obbligatori (entrambe le modalità)

1. Verifica sempre prima che GitHub CLI sia autenticato:
   ```bash
   gh auth status
   ```
   Se `gh` non è autenticato o restituisce errore, **fermati** e chiedi all'utente di autenticarsi prima di procedere.
2. **Vincoli di sicurezza assoluti**:
   - **NON** eseguire mai `git push`.
   - **NON** eseguire mai `gh pr merge` o chiusure di PR (`gh pr close`) in autonomia.
   - **NON** modificare il branch principale (`main`) o la working directory principale durante triage o review.
   - Usa sempre un linguaggio **italiano chiaro, schematico e senza gergo inutile**.

---

## Modalità 1 — Censimento (`triage`)

Usa questa modalità quando l'utente chiede `triage`, un censimento delle PR aperte o di aggiornare il report generale.

### Regole ferree
- Opera **esclusivamente in sola lettura** via `gh` / API GitHub.
- **NON** fare `git checkout`, **NON** cambiare branch, **NON** creare worktree.

### Procedura
1. Elenca tutte le PR aperte (fino a 150):
   ```bash
   gh pr list --state open --limit 150 --json number,title,author,createdAt,updatedAt,additions,deletions,changedFiles,mergeable,reviewDecision,labels,url
   ```
2. Per ciascuna PR aperta, ispeziona:
   - I file modificati e il riepilogo via `gh pr view <NUMERO> --json number,title,body,files,mergeable,reviewDecision,reviews,comments`.
   - I commenti e le review di **CodeRabbit** (`coderabbitai[bot]`) tramite:
     ```bash
     gh api repos/{owner}/{repo}/pulls/<NUMERO>/comments
     gh api repos/{owner}/{repo}/pulls/<NUMERO>/reviews
     ```
3. Analizza **cosa fa davvero** la PR guardando diff/file/contenuto reale (senza fidarti solo del titolo), i problemi segnalati da CodeRabbit, eventuali conflitti con `main` (`mergeable == "CONFLICTING"`), e la coerenza con la governance (dimensione, scopo singolo, eventuale presenza di rischi sicurezza/telemetria/dipendenze).
4. Scrivi o aggiorna nella root del repository il file `PR_TRIAGE_REPORT.md` (già ignorato in `.gitignore`), strutturato in italiano semplice con:
   - **Data/ora aggiornamento** e numero totale di PR aperte analizzate.
   - **Tabella riepilogativa**:
     `| #PR | Titolo | Cosa fa davvero (1 riga semplice) | File toccati | Problemi CodeRabbit | Conflitti con main | Verdetto consigliato |`
     dove il verdetto consigliato è esclusivamente uno tra: `VALUTA`, `RINVIARE`, `CHIUDERE` (con breve motivazione sintetica se utile nella sezione sottostante).
   - **Raggruppamento PR simili o sovrapposte**: elenca i cluster tematici (es. PR che toccano gli stessi moduli, duplicano funzioni o vanno in conflitto tra loro) indicando quale conviene valutare per prima e quali accorpare/chiudere.
5. Presenta all'utente un riepilogo sintetico e il link a `PR_TRIAGE_REPORT.md`.

---

## Modalità 2 — Revisione singola (`review #NUMERO`)

Usa questa modalità quando l'utente chiede `review #NUMERO` (es. `review #46`).

### Procedura obbligatoria passo-passo

1. **Isolamento in worktree esterno al repository**:
   - Ricava il percorso assoluto del repository principale (`REPO_ROOT`) e verifica che la working directory corrente resti intatta.
   - Crea un worktree isolato **fuori** dal repository, in `/tmp/blindcue-pr-<NUMERO>`:
     ```bash
     git fetch origin pull/<NUMERO>/head
     git worktree add --detach /tmp/blindcue-pr-<NUMERO> FETCH_HEAD
     ```
     *(Se `/tmp/blindcue-pr-<NUMERO>` esiste già da una sessione precedente, rimuovilo prima in sicurezza con `git worktree remove --force /tmp/blindcue-pr-<NUMERO>`).*

2. **Estrazione delle funzionalità reali dal diff**:
   - Confronta la PR rispetto a `origin/main` (`git -C /tmp/blindcue-pr-<NUMERO> diff origin/main...HEAD` o `gh pr diff <NUMERO>`).
   - Stila la **lista completa e concreta** delle funzionalità introdotte, dei file modificati e di eventuali side-effect nascosti (nuove dipendenze, chiamate di rete, accesso al filesystem, modifiche a UI/shortcut/persistenza).

3. **Analisi commenti CodeRabbit e rischi**:
   - Leggi tutti i commenti e le review di CodeRabbit sulla PR:
     ```bash
     gh pr view <NUMERO> --comments --json comments,reviews
     gh api repos/{owner}/{repo}/pulls/<NUMERO>/comments
     ```
   - Verifica ogni segnalazione di bug, edge case, regressione live, incompatibilità multipiattaforma (Linux Wayland, Windows, macOS) o problema di sicurezza.

4. **Verifica locale con `ruff`, `bandit` e `pytest`**:
   - Esegui i controlli dentro il worktree `/tmp/blindcue-pr-<NUMERO>` usando il `.venv` del repository principale:
     - Calcola i file `.py` aggiunti o modificati rispetto a `origin/main`:
       ```bash
       git -C /tmp/blindcue-pr-<NUMERO> diff --name-only --diff-filter=ACMR origin/main...HEAD -- '*.py'
       ```
     - Esegui `.venv/bin/ruff check` sui soli file `.py` toccati dalla PR.
     - Esegui `.venv/bin/bandit -ll` sui soli file `.py` toccati dalla PR.
     - Esegui la suite test completa:
       ```bash
       QT_QPA_PLATFORM=offscreen "$REPO_ROOT/.venv/bin/pytest" -q /tmp/blindcue-pr-<NUMERO>/tests/
       ```
   - Riporta fedelmente l'esito reale osservato (numeri test passati/falliti, eventuali warning o errori esatti).

5. **Verifica allineamento documentazione e manuali**:
   - Controlla se le modifiche della PR rendono obsoleti o incompleti:
     - `README.md`
     - `docs/MANUAL.md`
     - `docs/manual/manual_it.src.html`, `manual_en.src.html`, `manual_pl.src.html` e relativi HTML compilati `blindcue/help/manual_*.html` (generati con `tools/build_manual.py`)
     - `docs/ARCHITECTURE.md`
   - Se mancano aggiornamenti documentali, proponi all'utente le modifiche esatte necessarie.

6. **Pulizia worktree e stop obbligatorio**:
   - Rimuovi il worktree temporaneo a fine revisione (o segnalalo esplicitamente se l'utente desidera mantenerlo per ispezione):
     ```bash
     git worktree remove /tmp/blindcue-pr-<NUMERO>
     ```
   - **Fermati** e presenta il verdetto tecnico completo in italiano chiaro, attendendo **approvazione esplicita dell'utente** prima di qualsiasi ulteriore azione (MAI eseguire `merge`, `push` o chiusura PR in autonomia).
