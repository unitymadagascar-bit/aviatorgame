# Crash Live Counter

Crash Live Counter est une application Python Streamlit pour analyser l'historique visible d'un crash game et compter les multiplicateurs par couleur.

Categories :

- Bleu
- Autres couleurs : violet, rose, rouge, vert

L'application analyse seulement des resultats passes visibles ou deja enregistres. Elle ne predit pas le prochain tour, ne garantit aucun gain et ne propose aucune strategie de mise.

## Installation

```bash
pip install -r requirements.txt
playwright install
```

## Lancement

```bash
streamlit run app.py
```

## Modes disponibles

### 1. URL avec Playwright

Ce mode ouvre l'URL avec Playwright, attend le chargement, prend une capture, puis analyse l'image avec OpenCV.

Options :

- Champ URL
- Bouton `Analyser URL`
- Capture pleine page
- Capture zone personnalisee avec `x`, `y`, `largeur`, `hauteur`
- Option `Afficher le navigateur pour fermer les popups ou se connecter manuellement`

Utilisation conseillee :

1. Garder `Afficher le navigateur` active.
2. Cliquer sur `Analyser URL`.
3. Quand le navigateur s'ouvre, fermer manuellement les popups, choisir les cookies et se connecter si necessaire.
4. Attendre la capture automatique apres le delai choisi.
5. Si le jeu reste masque ou inaccessible, utiliser le mode `Scan ecran local`.

Si l'URL est bloquee par login, iframe, Cloudflare ou restriction du site, l'application affiche :

```text
Impossible de lire automatiquement cette URL. Utilisez le mode scan ecran local.
```

### 2. Scan ecran local

Ce mode utilise `mss` pour scanner ce qui est visible sur votre ecran.

Reglages :

- `x`
- `y`
- `largeur`
- `hauteur`
- intervalle de scan de 1 a 10 secondes
- boutons `Demarrer scan` et `Arreter scan`

La derniere zone scannee est affichee dans le dashboard.

### 3. Manuel

Ce mode sert lorsque l'automatique ne lit pas bien l'historique.

Boutons :

- `+1 Bleu`
- `-1 Bleu`
- `+1 Autres couleurs`
- `-1 Autres couleurs`
- `Reset manuel`
- `Ajouter le manuel au cumul`

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
- L'option `Ajout automatique au cumul si nouveau scan detecte` ajoute seulement les scans nouveaux.
- Le bouton `Ajouter ce scan au cumul` permet de confirmer manuellement.

## Detection OpenCV

L'application utilise :

- HSV pour isoler les textes colores sur fond sombre
- connected components pour detecter les groupes de pixels
- regroupement de blocs proches pour compter des groupes de chiffres
- classification de la couleur dominante de chaque bloc

Si la couleur dominante est bleue, le bloc est compte en `Bleu`. Sinon il est compte en `Autres couleurs`.

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

- L'application analyse seulement les resultats passes.
- Elle ne predit pas le prochain tour.
- Elle ne garantit aucun gain.
- Les jeux de crash ont normalement des tours independants.
- Elle ne doit pas automatiser les paris.
- Elle ne gere pas d'argent reel.
- Si l'URL est bloquee, utilisez le scan ecran local.
- Le systeme anti-doublon evite d'ajouter plusieurs fois le meme scan identique, mais une page qui bouge ou se decale peut produire une nouvelle signature.
