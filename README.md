# Crash Live Screen Counter

Crash Live Screen Counter est une application Python Streamlit dont le fichier principal est `app.py`.

Elle sert a analyser une capture d'ecran ou une zone visible de l'ecran pour compter les couleurs d'un historique de crash game et lire, si possible, des gains visibles avec OCR.

Important : l'application ne predit pas le prochain tour, ne garantit aucun gain et ne doit pas automatiser les paris.

## Installation locale

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Lancement local

```bash
streamlit run app.py
```

## Utilisation

### Methode simple : Print Screen puis coller

1. Ouvrir la page du jeu.
2. Faire `PrtSc` ou `Win + Shift + S`.
3. Revenir dans l'application Streamlit.
4. Cliquer sur `Coller depuis le presse-papiers`.
5. Verifier la capture affichee et les resultats.
6. Activer le mode debug si necessaire.
7. Telecharger le CSV si besoin.

### Methode alternative : importer une image

1. Enregistrer une capture d'ecran en PNG/JPG.
2. Cliquer sur l'import d'image dans l'application.
3. Cliquer sur `Analyser l'image importee`.

### Methode avancee : scan live

1. Ouvrir la page du jeu.
2. Entrer les coordonnees `x`, `y`, `largeur`, `hauteur` de la zone a scanner.
3. Cliquer sur `Demarrer le scan`.
4. Ajuster les sliders HSV si necessaire.

### Methode automatique : scanner depuis une URL

1. Lancer l'application en local.
2. Coller l'URL du site dans `URL du site`.
3. Garder `Afficher le navigateur` active si le site demande une connexion ou une verification manuelle.
4. Cliquer sur `Demarrer l'analyse URL`.
5. Le premier scan sert de point de depart.
6. L'application compte ensuite seulement les nouveaux tours detectes apres ce point.
7. Ouvrir `Dernier tour a suivre` et placer le rectangle jaune sur le multiplicateur le plus recent.
8. Sur Bet261/Aviator, ce multiplicateur est generalement le premier chiffre a gauche dans `HISTORIQUE DE LA MANCHE`.
9. Activer `Mode debug` pour verifier que le rectangle jaune couvre bien ce chiffre, pas l'avion, le graphe ou les boutons.
10. Si la bande d'historique n'est pas bien cadree, ouvrir `Zone historique URL a analyser` et reduire la zone pour garder uniquement l'historique des multiplicateurs.

Ce mode observe seulement la page. Il ne clique pas, ne se connecte pas automatiquement et ne place aucune mise.

## Deploiement recommande

### Streamlit Community Cloud

Plateforme recommandee pour une app Streamlit simple.

1. Pousser ce depot sur GitHub.
2. Aller sur Streamlit Community Cloud.
3. Creer une nouvelle app depuis le depot GitHub.
4. Choisir `app.py` comme fichier principal.
5. Laisser Streamlit installer les dependances depuis `requirements.txt`.

Le fichier `packages.txt` installe `tesseract-ocr` sur Streamlit Community Cloud pour aider `pytesseract`.

### Render

Render peut lancer l'app comme service web Streamlit.

Le fichier `render.yaml` est fourni avec :

```bash
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

Sur Render, creer un Web Service depuis ce depot, ou utiliser le blueprint `render.yaml`.

## Ne pas utiliser Vercel pour cette app

Vercel n'est pas adapte ici pour lancer Streamlit directement. Son runtime Python attend une fonction exportee nommee `app`, `application` ou `handler`, comme pour une API Python.

Ce projet doit rester une application Streamlit avec :

```bash
streamlit run app.py
```

Il ne faut pas transformer `app.py` en fonction API Vercel.

## OCR et Tesseract

`pytesseract` est une interface Python. Pour que l'OCR fonctionne, le binaire Tesseract OCR doit aussi etre installe dans l'environnement.

- Sur Streamlit Community Cloud, `packages.txt` installe `tesseract-ocr`.
- En local, installer Tesseract OCR puis verifier qu'il est disponible dans le `PATH`.
- Si Tesseract est trop complique a installer, `easyocr` peut etre envisage comme alternative dans une version future.

## Playwright

Le mode `Scanner depuis une URL` utilise Playwright pour ouvrir la page et prendre des captures.

Apres l'installation Python, lancer une fois :

```bash
python -m playwright install chromium
```

## Limites importantes

- L'application analyse seulement ce qui est visible sur l'ecran.
- Sur un hebergement cloud, le serveur ne peut pas voir l'ecran local de l'utilisateur comme une application lancee sur son ordinateur.
- Le mode `Coller depuis le presse-papiers` et le scan live sont donc surtout adaptes a une execution locale.
- Le mode URL depend du chargement du site. Si le site bloque l'automatisation, demande un captcha ou une connexion, il faut verifier manuellement dans le navigateur ouvert.
- L'application ne doit pas contourner les protections du site.
- Les donnees OCR peuvent contenir des erreurs.
- Les tours d'un crash game sont normalement independants.
- L'application ne predit pas le prochain tour.
- L'application ne garantit aucun gain.
- Elle ne doit pas automatiser les paris.
