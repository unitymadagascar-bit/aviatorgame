# Crash Live Screen Counter

Crash Live Screen Counter est une application Python Streamlit qui scanne une zone de l'ecran ou l'historique d'un crash game est visible.

Elle compte en direct :

- Bleu
- Autres couleurs
- Total des tours visibles

Elle tente aussi de lire les gains publics visibles avec OCR, puis calcule :

- nombre de gains affiches
- somme totale des gains visibles
- gain moyen visible
- plus gros gain visible

L'application analyse seulement des informations visibles publiquement sur votre ecran. Elle ne se connecte pas au site, ne contourne aucune securite, n'automatise pas les mises, ne predit pas le prochain tour et ne garantit aucun gain.

## Installation

```bash
pip install -r requirements.txt
```

`pytesseract` est une interface Python. Pour que l'OCR fonctionne, le logiciel Tesseract OCR doit aussi etre installe sur la machine et accessible dans le PATH.

Si Tesseract est trop complique a installer, une future variante peut utiliser `easyocr` comme alternative, mais cette version reste basee sur `pytesseract`.

## Lancement

```bash
streamlit run app.py
```

## Utilisation

1. Ouvrir la page du jeu.
2. Lancer l'application.
3. Entrer les coordonnees `x`, `y`, `largeur`, `hauteur` de la zone a scanner.
4. Cliquer sur `Demarrer le scan`.
5. Ajuster les sliders HSV si necessaire.
6. Verifier le mode debug pour voir les rectangles detectes.
7. Telecharger le CSV si necessaire.

## Reglages

- `Hue/Saturation/Valeur bleu` : calibre la detection du bleu.
- `Saturation minimale du texte colore` : ignore les elements trop gris ou trop fades.
- `Luminosite minimale du texte colore` : ignore les elements trop sombres.
- `Surface minimale detectee` : evite les petits artefacts.
- `Distance de regroupement` : regroupe les chiffres proches pour eviter de compter le meme multiplicateur plusieurs fois.

## Export CSV

Le CSV contient :

- `datetime`
- `bleu`
- `autres_couleurs`
- `total_tours`
- `pourcentage_bleu`
- `pourcentage_autres`
- `nombre_gains_visibles`
- `somme_gains_visibles`
- `gain_moyen_visible`
- `plus_gros_gain_visible`

## Limites

- L'application ne predit pas le prochain tour.
- Les tours d'un crash game sont normalement independants.
- L'application ne garantit aucun gain.
- Les donnees OCR peuvent contenir des erreurs.
- Elle analyse seulement ce qui est visible sur l'ecran.
- Elle ne doit pas automatiser les paris.
