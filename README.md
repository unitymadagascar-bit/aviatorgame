# Crash Live Counter

Crash Live Counter est une application Python Streamlit qui analyse une zone visible de votre ecran pour compter les multiplicateurs colores d'un crash game.

Categories :

- Bleu
- Autres couleurs : violet, rose, rouge, vert

L'application analyse seulement des resultats passes visibles ou deja enregistres. Elle ne predit pas le prochain tour, ne garantit aucun gain, ne propose aucune strategie de mise et ne gere pas d'argent reel.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Mode principal : scan ecran local

Fonctionnement :

1. Ouvrir vous-meme la page Aviator dans votre navigateur.
2. Placer l'historique des multiplicateurs bien visible a l'ecran.
3. Dans l'application, choisir la zone exacte a scanner avec `x`, `y`, `largeur` et `hauteur`.
4. Encadrer uniquement la boite `HISTORIQUE DE LA MANCHE`, pas toute la page Aviator.
5. Cliquer sur `Tester la zone` pour verifier l'apercu.
6. Ajuster la zone si necessaire.
7. Cliquer sur `Demarrer scan`.
8. Cliquer sur `Arreter scan` pour stopper le scan.
9. Cliquer sur `Ajouter ce scan au cumul` seulement quand vous voulez enregistrer le scan actuel.

Le scan utilise `mss` pour capturer directement ce qui est visible sur votre ecran, puis OpenCV analyse l'image.
Le cumul global ne s'incremente pas automatiquement pendant les rafraichissements.

## Mode manuel de secours

Si la detection automatique ne correspond pas a ce que vous voyez, utilisez le mode manuel :

- `+1 Bleu`
- `-1 Bleu`
- `+1 Autres couleurs`
- `-1 Autres couleurs`
- `Reset`

Le bouton `Ajouter le manuel au cumul` permet d'enregistrer la saisie manuelle dans l'historique.

## Statistiques

L'application affiche deux niveaux de statistiques.

### Scan actuel

- Bleu scan actuel
- Autres couleurs scan actuel
- Total scan actuel
- Pourcentage bleu scan actuel
- Pourcentage autres scan actuel

### Cumul global depuis le lancement

- Total Bleu global
- Total Autres couleurs global
- Total tours global
- Pourcentage Bleu global
- Pourcentage Autres couleurs global

Le cumul global garde les anciens scans meme quand ils ne sont plus visibles a l'ecran.

## Anti-doublon

Chaque scan recoit une signature construite avec les blocs detectes, leurs positions et leurs couleurs.

- Si le scan actuel est identique au scan precedent ajoute, il n'est pas ajoute automatiquement au cumul.
- Le bouton `Ajouter ce scan au cumul` enregistre le scan actuel.
- Si le scan actuel est identique au dernier scan ajoute, il n'est pas ajoute une deuxieme fois.
- Le bouton `Reinitialiser scan actuel` efface seulement la capture et les statistiques du scan courant.
- Le bouton `Reinitialiser cumul global` efface l'historique et les statistiques globales.

## Detection OpenCV

L'application utilise :

- HSV pour isoler les textes colores sur fond sombre
- connected components pour detecter les groupes de pixels
- regroupement de blocs proches pour compter des groupes de chiffres
- classification de la couleur dominante de chaque bloc

Si la couleur dominante est bleue, le bloc est compte en `Bleu`. Sinon il est compte en `Autres couleurs`.

Le mode debug affiche des rectangles autour des nombres detectes.
Il affiche aussi le nombre exact de blocs detectes dans la zone analysee.

## Historique et export

Le tableau `Historique enregistre` contient :

- `scan_id`
- `datetime`
- `source`
- `bleu`
- `autres_couleurs`
- `total`
- `pourcentage_bleu`
- `pourcentage_autres`

Vous pouvez supprimer la derniere entree, vider l'historique ou exporter le CSV.

## Limites

- L'application analyse seulement les resultats passes visibles a l'ecran.
- Elle ne lit plus directement une URL.
- Elle n'utilise pas d'iframe.
- Elle n'utilise pas Playwright.
- Elle ne predit pas le prochain tour.
- Elle ne garantit aucun gain.
- Les jeux de crash ont normalement des tours independants.
- Elle ne doit pas automatiser les paris.
- Elle ne gere pas d'argent reel.
- Le systeme anti-doublon evite d'ajouter plusieurs fois le meme scan identique, mais une page qui bouge ou se decale peut produire une nouvelle signature.
