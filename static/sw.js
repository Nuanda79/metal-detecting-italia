// Service worker minimo per Metal Detecting Italia.
// Strategia: "network first, cache come riserva" — mostra sempre la versione
// più fresca quando c'è connessione, e usa la cache solo quando sei offline
// o la rete è irraggiungibile. Adatto a un sito che pubblica contenuti nuovi
// ogni giorno: non vogliamo mai mostrare per sbaglio una pagina vecchia in cache
// se la connessione c'è.

const CACHE_NAME = "mdi-cache-v1";

const APP_SHELL = [
  "/metal-detecting-italia/",
  "/metal-detecting-italia/manifest.json",
  "/metal-detecting-italia/icon-192.png",
  "/metal-detecting-italia/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((chiavi) =>
      Promise.all(
        chiavi
          .filter((chiave) => chiave !== CACHE_NAME)
          .map((chiave) => caches.delete(chiave))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Ignoriamo richieste non-GET (es. invii di form) e richieste verso altri
  // domini (es. embed YouTube, immagini da img.youtube.com): il service
  // worker gestisce solo le risorse del nostro stesso sito.
  if (event.request.method !== "GET") return;
  if (!event.request.url.startsWith(self.location.origin)) return;

  event.respondWith(
    fetch(event.request)
      .then((risposta) => {
        const copia = risposta.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copia));
        return risposta;
      })
      .catch(() => caches.match(event.request))
  );
});
