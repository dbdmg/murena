# MURENA — knowledge bundle OKF v0.2

## Installazione

Estrarre l'archivio **nella root del repository `murena-demo`**. Verrà creata la directory `docs/okf/`. Non sovrascrive o modifica il backend/frontend.

## Navigazione

Aprire `docs/okf/index.md`, poi solo i file di interesse. Le `sources` relative al codice risolvono dopo l'estrazione nella root. Le fonti del manoscritto sono presenti in `docs/okf/references/paper/`.

## Convalida

`python verify_okf.py`

Lo script verifica la struttura del bundle, il frontmatter YAML, il campo `type`, i link ai file locali e il formato del log. Verifica statica **non** equivalente a test funzionale del progetto.

## Provenienza e limitazioni

Bundle ottenuto mediante lettura statica dei file caricati e del paper LaTeX. Non include dataset APE grezzi, ZIP originali, chiavi private né dati utente. Nessuna metrica del paper è stata riprodotta durante la generazione. Alcuni riferimenti `sources` puntano a file del repository esterni a `docs/okf` e sono intesi per l'installazione in-place.

Standard: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
