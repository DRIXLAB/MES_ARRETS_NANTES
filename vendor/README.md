# Ressources tierces hébergées

Ces fichiers sont copiés tels quels depuis leurs paquets officiels, pour que la page ne contacte aucun CDN (ni Google Fonts, ni cdnjs). Chaque dossier contient le texte de sa licence.

| Ressource | Version | Source | Licence |
|---|---|---|---|
| Police **Inter** (variable, sous-ensemble latin) | 5.3.0 | paquet npm `@fontsource-variable/inter` (fichier `files/inter-latin-wght-normal.woff2`) | SIL Open Font License 1.1 — voir `inter/LICENSE.txt` |
| **Font Awesome Free** (style « solid » uniquement) | 6.7.2 | paquet npm `@fortawesome/fontawesome-free` (`css/fontawesome.min.css`, `css/solid.min.css`, `webfonts/fa-solid-900.woff2`) | Icônes CC BY 4.0, polices SIL OFL 1.1, code MIT — voir `fontawesome/LICENSE.txt` |

La page n'utilise que le style `fas` (solid) de Font Awesome : les styles regular et brands ne sont pas inclus. Pour utiliser une autre icône solid, il suffit de l'ajouter dans le HTML ; pour un autre style, ajouter les fichiers correspondants du même paquet.

Pour mettre à jour : récupérer les fichiers dans la nouvelle version du paquet npm, remplacer ceux d'ici, mettre à jour ce tableau et vérifier l'affichage de la page.
