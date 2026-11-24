# AGENTS.md — Istruzioni permanenti per agenti AI su BlindCUE

Questo file definisce le regole permanenti e vincolanti per qualsiasi agente AI che lavora in questo repository.

## 1. Comunicazione e lingua
- Rispondi **sempre in italiano chiaro, schematico e diretto**, evitando gergo inutile.
- Quando descrivi modifiche, PR o risultati di test, riporta **solo fatti realmente verificati** (file esatti, esiti reali dei comandi, numeri osservati).

## 2. Vincoli di sicurezza operativa (HARD)
- **MAI** eseguire `git merge`, `git push`, `gh pr merge`, `gh pr close` o altre azioni irreversibili su Git/GitHub senza **conferma esplicita dell'utente**.
- **MAI** eseguire modifiche distruttive (`git reset --hard`, `rm -rf` su file tracciati, riscrittura della storia git) senza consenso esplicito.
- Non introdurre mai telemetria, chiamate di rete non richieste, dipendenze proprietarie/cloud o codice offuscato.
- Preserva la compatibilità multipiattaforma (**Linux Wayland, Windows 10/11, macOS**) e l'isolamento dei test (`tests/conftest.py`).

## 3. Checklist obbligatoria dopo ogni integrazione o modifica di feature
Dopo ogni modifica o integrazione di codice applicativo, verifica e riporta sempre tutti e 4 i punti seguenti:
1. **Test automatizzati**: esegui `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/` (e per modifiche al motore puro anche `.venv/bin/pytest -q tests/test_show_engine_pure.py`).
2. **Qualità codice (`ruff`)**: esegui `.venv/bin/ruff check` almeno su tutti i file Python aggiunti o modificati.
3. **Sicurezza (`bandit`)**: esegui `.venv/bin/bandit -ll` almeno su tutti i file Python aggiunti o modificati.
4. **Documentazione e manuali**: verifica se vanno aggiornati `README.md`, `docs/MANUAL.md`, `docs/ARCHITECTURE.md` e i sorgenti multilingua in `docs/manual/manual_{it,en,pl}.src.html` (ricompilando `blindcue/help/manual_*.html` con `.venv/bin/python tools/build_manual.py` se modificati).

## 4. Governance delle Pull Request
- Per il censimento e la revisione controllata delle PR aperte, usa la skill dedicata `.agents/skills/pr-triage/SKILL.md`.
- Rispetta sempre le regole definite in `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md` e `.github/workflows/pr-gatekeeper.yml`.
