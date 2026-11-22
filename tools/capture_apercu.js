#!/usr/bin/env node
// Régénère docs/apercu.png, la capture du README, avec des données d'exemple (l'API est simulée :
// aucune requête ne part vers api.okina.fr).
//
// Usage :
//     node tools/capture_apercu.js [fichier de sortie]      (par défaut : docs/apercu.png)
//
// Prérequis : Node.js et Playwright avec Chromium (npm install playwright && npx playwright install chromium).
// Si python3 et Pillow sont installés, l'image est ensuite recompressée sans perte (environ deux fois plus légère).
//
// Scène : mercredi 18 novembre 2026, 08:15:25 (heure de Paris), arrêts Commerce, Gare Sud et Médiathèque,
// un retard et un passage supprimé, décompte à 25 s. Page de 1200 px rendue à l'échelle 1,6 (1920 px de large).
'use strict';

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, 'docs', 'apercu.png'));
const WIDTH = 1200;
const SCALE = 1.6;
const SHOT = Date.parse('2026-11-18T08:15:25+01:00');   // heure affichée sur la capture
const STOPS = ['20', '732', '15'];                         // Commerce, Gare Sud, Médiathèque (identifiants de lieu)

// [quai, ligne, destination, minutes, retard en minutes, supprimé]
// Les minutes affichées sont arrondies : 7.85 s'affiche « 8 min » mais passe avant le C2 de 8 min.
const DEPARTURES = [
    // Commerce (lieu 20)
    [90, '1', 'Beaujoire', 2], [90, '2', 'Orvault Grand Val', 3], [90, '3', 'Marcel Paul', 4],
    [90, '1', 'François Mitterrand', 5], [90, '2', 'Gare de Pont-Rousseau', 7.85, 2], [90, 'C2', 'Le Cardo', 8],
    [90, '3', 'Neustrie', 9], [90, '1', 'Beaujoire', 11],
    // Gare Sud (lieu 732)
    [1758, '5', 'Hangar à Bananes', 1], [1758, 'C2', 'Le Cardo', 4], [1758, 'C8', 'Saupin', 6, 0, true],
    [1758, 'C3', 'Bd de Doulon', 9, 3], [1758, 'NA', 'Aéroport', 10], [1758, '5', 'Hangar à Bananes', 14],
    [1758, 'C2', 'Le Cardo', 18],
    // Médiathèque (lieu 15)
    [66, '1', 'François Mitterrand', 3], [66, '1', 'Beaujoire', 4], [66, '1', 'François Mitterrand', 9],
    [66, '1', 'Beaujoire', 12], [66, 'NO', 'Beauséjour', 14.85], [66, '1', 'François Mitterrand', 15]
];

// Réponse SIRI StopMonitoring simulée
function stopMonitoringResponse() {
    const iso = ms => new Date(ms).toISOString();
    const visits = DEPARTURES.map(([quay, line, destination, minutes, delay = 0, cancelled = false]) => {
        const expected = SHOT + minutes * 60000;
        const aimed = expected - delay * 60000;
        return `<MonitoredStopVisit><MonitoringRef>FR_NAOLIB:Quay:${quay}</MonitoringRef><MonitoredVehicleJourney>` +
            `<LineRef>FR_NAOLIB:Line:${line}:LOC</LineRef><DestinationName>${destination}</DestinationName><MonitoredCall>` +
            `<AimedDepartureTime>${iso(aimed)}</AimedDepartureTime><ExpectedDepartureTime>${iso(expected)}</ExpectedDepartureTime>` +
            `${cancelled ? '<DepartureStatus>cancelled</DepartureStatus>' : ''}</MonitoredCall></MonitoredVehicleJourney></MonitoredStopVisit>`;
    }).join('');
    return '<?xml version="1.0" encoding="utf-8"?><Siri xmlns="http://www.siri.org.uk/siri" version="2.0"><ServiceDelivery>' +
        `<StopMonitoringDelivery version="2.0">${visits}</StopMonitoringDelivery></ServiceDelivery></Siri>`;
}

// Petit serveur local pour les fichiers du dépôt (la page charge stops.js, lines.js et vendor/)
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.png': 'image/png', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
    const file = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(ROOT + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404);
        return res.end();
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
});

// Recompression sans perte, si python3 et Pillow sont disponibles
function optimize(file) {
    const script = 'import sys\nfrom PIL import Image\nImage.open(sys.argv[1]).convert("RGB").save(sys.argv[1], optimize=True)';
    try {
        execFileSync('python3', ['-c', script, file], { stdio: 'pipe' });
        return true;
    } catch {
        return false;
    }
}

(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const browser = await chromium.launch();
    try {
        const context = await browser.newContext({
            viewport: { width: WIDTH, height: 740 }, deviceScaleFactor: SCALE, timezoneId: 'Europe/Paris', locale: 'fr-FR'
        });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));

        // Requête de passages à 08:15:19,5 : à 08:15:25, le décompte affiche 25 s
        await page.clock.install({ time: SHOT - 5500 });
        await page.addInitScript((stops) => {
            localStorage.setItem('nantes-dashboard-config-v2', JSON.stringify({ selectedStops: stops, filters: {} }));
        }, STOPS);
        await page.route('https://api.okina.fr/**', route =>
            route.fulfill({ status: 200, contentType: 'text/plain', body: stopMonitoringResponse() }));

        await page.goto(`http://127.0.0.1:${server.address().port}/MES_ARRETS_NANTES.html`);
        await page.waitForSelector('.data-table');
        await page.evaluate(() => document.fonts.ready);
        await page.clock.pauseAt(SHOT);
        await page.mouse.move(0, 0);
        await page.waitForTimeout(800);   // fin des animations d'apparition des cartes

        // Fenêtre à la hauteur du contenu : le fond (background-attachment: fixed) couvre toute la capture
        const height = await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
        await page.setViewportSize({ width: WIDTH, height });
        await page.waitForTimeout(300);

        // Vérifier la scène avant d'écrire l'image
        const time = await page.textContent('#digital-time');
        const countdown = await page.textContent('#refreshLabel');
        const rows = await page.$$eval('.data-table tbody tr', r => r.length);
        const problems = [];
        if (time !== '08:15:25') problems.push(`heure affichée ${time}`);
        if (countdown.trim() !== '25s') problems.push(`décompte ${countdown}`);
        if (rows !== DEPARTURES.length) problems.push(`${rows} passages affichés sur ${DEPARTURES.length}`);
        if (errors.length) problems.push(`erreurs JavaScript : ${errors.join(' | ')}`);
        if (problems.length) throw new Error(`capture non conforme (${problems.join(', ')})`);

        await page.screenshot({ path: OUT });
        const optimized = optimize(OUT);
        const size = Math.round(fs.statSync(OUT).size / 1024);
        console.log(`${path.relative(process.cwd(), OUT)} : ${Math.round(WIDTH * SCALE)} x ${Math.round(height * SCALE)} px, ${size} Ko` +
            (optimized ? ' (recompressé sans perte)' : ' (non recompressé : python3 + Pillow introuvables)'));
    } finally {
        await browser.close();
        server.close();
    }
})().catch(error => {
    console.error(`Erreur : ${error.message}`);
    process.exit(1);
});
