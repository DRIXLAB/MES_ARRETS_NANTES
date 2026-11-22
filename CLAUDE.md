# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Tableau de bord temps réel des prochains passages aux arrêts Naolib (Nantes), 100 % navigateur, publié sur GitHub Pages. La documentation technique détaillée (fichiers, SIRI, architecture des classes, persistance, glisser-déposer) est dans la section « Documentation technique » du `README.md` : la lire avant toute modification non triviale, et la tenir à jour quand l'architecture change.

## Commandes

Pas de build, pas de gestionnaire de paquets, pas de tests, pas de linter.

- Lancer l'appli : ouvrir `MES_ARRETS_NANTES.html` dans un navigateur, ou servir le dossier (`python3 -m http.server`) puis ouvrir `/MES_ARRETS_NANTES.html`. `index.html` n'est qu'une redirection pour GitHub Pages.
- Mettre à jour les données depuis le GTFS Naolib (transport.data.gouv.fr), **dans cet ordre** :
  1. `python3 tools/generate_stops.py gtfs.zip stops.js` (fusionne, ne retire jamais d'arrêt ni de quai)
  2. `python3 tools/generate_lines.py gtfs.zip stops.js lines.js`
- Régénérer la capture du README (`docs/apercu.png`) après un changement visible de l'interface : `node tools/capture_apercu.js` (Playwright, données d'exemple, API simulée).
- Vérifier un changement : charger la page avec Playwright/Chromium en simulant l'API via `page.route('https://api.okina.fr/**', …)` (réponse XML SIRI StopMonitoring), sans interroger la vraie API en boucle.

## Architecture en bref

- Toute l'appli tient dans `MES_ARRETS_NANTES.html` : `<style>`, balisage, puis un `<script>` inline (`CONFIG`, `AppState`, `StorageManager`, `Utils`, `TimeManager`, `StopManager`, `TransportManager`, `TrafficManager`, `DashboardApp`). `stops.js` (`STOP_LIST`) puis `lines.js` (`LINE_INFO`, `STOP_LINES`) sont chargés **avant** ce script comme globales.
- `stops.js` et `lines.js` sont **générés** : ne pas les éditer à la main, passer par `tools/`.
- Le « code d'arrêt » partout (état, `data-stop-code`, ids DOM `content-<code>` / `filter-<code>`) est le **placeId en chaîne** ; un lieu regroupe plusieurs quais, et les passages SIRI (par quai) sont regroupés par lieu.
- Un seul cycle : le décompte (`startCountdown`) déclenche `runScheduledRequest()` à 0 (info trafic si demandée, sinon `loadAllStopsData()`), qui relance le décompte. L'affichage est redessiné chaque seconde **depuis le cache** (`refreshDisplays`), sans requête ; écrire dans `#content-<code>` uniquement via `setContent()`.

## Règles à respecter

- **API Okina : 1 seul POST SIRI toutes les 30 s pour tous les arrêts réunis** (`CONFIG.FETCH_COOLDOWN_S`). Ne jamais ajouter de requête par arrêt, de second timer de polling, ni de requête quand l'onglet est masqué. L'info trafic (Situation Exchange) ne peut pas être combinée aux passages dans un même POST : elle n'est chargée qu'au clic et **prend le prochain créneau** à la place des passages (`requestTraffic` → `runScheduledRequest`).
- Aucun CDN ni service tiers : polices et icônes sont dans `vendor/` (Font Awesome style solid uniquement). La page ne doit contacter que `api.okina.fr`.
- Rendu par chaînes `innerHTML` : tout texte dynamique passe par `Utils.escapeHtml`. Le HTML des descriptions d'info trafic passe par `TrafficManager.cleanHtml` (liste blanche).
- Toute modification de `AppState.selectedStops` ou `AppState.filters` est suivie de `StorageManager.save()`. Si la forme des données sauvegardées change, incrémenter `CONFIG.STORAGE_KEY` (actuellement `nantes-dashboard-config-v2`).
- Le masquage des destinations d'une ligne masquée est centralisé dans `getFilterContext()` ; passer par lui plutôt que de recalculer.
- Dates et heures toujours dans le fuseau `CONFIG.TIMEZONE` (Europe/Paris) via `Utils`, jamais le fuseau de l'appareil.
- L'icône d'onglet est embarquée en data URI dans le `<head>` : la modifier implique d'éditer `icons/favicon.svg`, de réencoder les deux data URI et de régénérer `icons/apple-touch-icon.png`.
- Interface, commentaires et messages de commit **en français**.
