"use client";

import "leaflet/dist/leaflet.css";

import { useCallback, useEffect, useRef, useState } from "react";

import { browserTimeZone } from "@/lib/time";

function formatCoord(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "";
  return String(v);
}

type GeocodeHit = { lat: number; lng: number; label: string };

type LocationPickerProps = {
  initialLatitude?: number | null;
  initialLongitude?: number | null;
  initialTimezone?: string | null;
};

export default function LocationPicker({
  initialLatitude = null,
  initialLongitude = null,
  initialTimezone = null,
}: LocationPickerProps) {
  const mapHostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const markerRef = useRef<import("leaflet").Marker | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timezoneRequestRef = useRef(0);
  const browserLocationRequestedRef = useRef(false);

  const [lat, setLat] = useState(() => formatCoord(initialLatitude));
  const [lng, setLng] = useState(() => formatCoord(initialLongitude));
  const [timezone, setTimezone] = useState(initialTimezone ?? "");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [timezoneBusy, setTimezoneBusy] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [hits, setHits] = useState<GeocodeHit[]>([]);
  const [highlight, setHighlight] = useState(-1);
  const [geoErr, setGeoErr] = useState<string | null>(null);
  const [timezoneErr, setTimezoneErr] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);

  const initialLat = Number(formatCoord(initialLatitude));
  const initialLng = Number(formatCoord(initialLongitude));
  const hasInitialPoint = Number.isFinite(initialLat) && Number.isFinite(initialLng);

  const inferTimezoneFor = useCallback(async (latitude: number, longitude: number) => {
    const requestId = timezoneRequestRef.current + 1;
    timezoneRequestRef.current = requestId;
    setTimezoneBusy(true);
    setTimezoneErr(null);

    try {
      const params = new URLSearchParams({
        latitude: String(latitude),
        longitude: String(longitude),
      });
      const res = await fetch(`/api/timezone?${params.toString()}`);
      const data = (await res.json()) as { timezone?: string; error?: string };
      if (!res.ok) throw new Error(data.error ?? "Timezone lookup failed");
      if (requestId === timezoneRequestRef.current && data.timezone) {
        setTimezone(data.timezone);
      }
    } catch (e) {
      if (requestId === timezoneRequestRef.current) {
        setTimezone((current) => current || browserTimeZone());
        setTimezoneErr((e as Error).message || "Could not determine timezone.");
      }
    } finally {
      if (requestId === timezoneRequestRef.current) {
        setTimezoneBusy(false);
      }
    }
  }, []);

  const applyCoords = useCallback(
    (latitude: number, longitude: number, opts?: { zoom?: number; panOnly?: boolean; label?: string }) => {
      setLat(latitude.toFixed(6));
      setLng(longitude.toFixed(6));
      if (opts?.label) setConfirmed(opts.label);
      void inferTimezoneFor(latitude, longitude);
      const map = mapRef.current;
      const L = leafletRef.current;
      if (!map || !L) return;
      const ll = L.latLng(latitude, longitude);
      if (!markerRef.current) {
        const m = L.marker(ll, { draggable: true }).addTo(map);
        m.on("dragend", () => {
          const p = m.getLatLng();
          setLat(p.lat.toFixed(6));
          setLng(p.lng.toFixed(6));
          void inferTimezoneFor(p.lat, p.lng);
          setConfirmed(`Pin at ${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`);
        });
        markerRef.current = m;
      } else {
        markerRef.current.setLatLng(ll);
      }
      if (opts?.zoom != null) {
        map.setView(ll, opts.zoom);
      } else if (!opts?.panOnly) {
        map.panTo(ll);
      }
      requestAnimationFrame(() => map.invalidateSize());
    },
    [inferTimezoneFor],
  );

  const useBrowserLocation = useCallback(() => {
    setGeoErr(null);
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setGeoErr("Browser location is unavailable. Search or click the map instead.");
      return;
    }
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setBusy(false);
        const { latitude, longitude } = position.coords;
        setTimezone((current) => current || browserTimeZone());
        applyCoords(latitude, longitude, {
          zoom: 11,
          label: "Browser location",
        });
      },
      () => {
        setBusy(false);
        setGeoErr("Browser location unavailable. Search or click the map instead.");
      },
      { enableHighAccuracy: false, maximumAge: 60 * 60 * 1000, timeout: 10000 },
    );
  }, [applyCoords]);

  useEffect(() => {
    if (!initialTimezone) {
      setTimezone(browserTimeZone());
    }
  }, [initialTimezone]);

  useEffect(() => {
    if (hasInitialPoint && !initialTimezone) {
      void inferTimezoneFor(initialLat, initialLng);
    }
  }, [hasInitialPoint, inferTimezoneFor, initialLat, initialLng, initialTimezone]);

  function applyTypedCoords(nextLat = lat, nextLng = lng) {
    const typedLat = Number(nextLat);
    const typedLng = Number(nextLng);
    if (!Number.isFinite(typedLat) || !Number.isFinite(typedLng)) return;
    applyCoords(typedLat, typedLng, {
      zoom: 12,
      label: `Pin at ${typedLat.toFixed(4)}, ${typedLng.toFixed(4)}`,
    });
  }

  useEffect(() => {
    const el = mapHostRef.current;
    if (!el) return;

    let cancelled = false;

    void import("leaflet").then((mod) => {
      if (cancelled || !mapHostRef.current) return;
      const L = (mod as unknown as { default?: typeof import("leaflet") }).default ?? mod;
      leafletRef.current = L;

      delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });

      const startLat = Number(formatCoord(initialLatitude));
      const startLng = Number(formatCoord(initialLongitude));
      const hasPoint = Number.isFinite(startLat) && Number.isFinite(startLng);
      const center: [number, number] = hasPoint ? [startLat, startLng] : [20, 0];
      const zoom = hasPoint ? 12 : 2;

      const map = L.map(el, { zoomControl: true }).setView(center, zoom);
      mapRef.current = map;

      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" rel="noreferrer">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      if (hasPoint) {
        const m = L.marker(center, { draggable: true }).addTo(map);
        m.on("dragend", () => {
          const p = m.getLatLng();
          setLat(p.lat.toFixed(6));
          setLng(p.lng.toFixed(6));
          void inferTimezoneFor(p.lat, p.lng);
          setConfirmed(`Pin at ${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`);
        });
        markerRef.current = m;
      }

      map.on("click", (e) => {
        const { lat: clat, lng: clng } = e.latlng;
        applyCoords(clat, clng, {
          panOnly: true,
          label: `Pin at ${clat.toFixed(4)}, ${clng.toFixed(4)}`,
        });
      });

      setMapReady(true);
      requestAnimationFrame(() => map.invalidateSize());
    });

    return () => {
      cancelled = true;
      setMapReady(false);
      mapRef.current?.remove();
      mapRef.current = null;
      markerRef.current = null;
      leafletRef.current = null;
    };
  }, [applyCoords, inferTimezoneFor, initialLatitude, initialLongitude]);

  useEffect(() => {
    if (!mapReady || hasInitialPoint || browserLocationRequestedRef.current) return;
    browserLocationRequestedRef.current = true;
    useBrowserLocation();
  }, [hasInitialPoint, mapReady, useBrowserLocation]);

  const fetchSuggestions = useCallback(async (q: string): Promise<GeocodeHit[]> => {
    searchAbortRef.current?.abort();
    const ac = new AbortController();
    searchAbortRef.current = ac;

    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`, { signal: ac.signal });
    const data = (await res.json()) as { results?: GeocodeHit[]; error?: string };
    if (!res.ok) throw new Error(data.error ?? "Search failed");
    return data.results ?? [];
  }, []);

  async function runSearch(explicitQuery?: string) {
    const q = (explicitQuery ?? query).trim();
    setGeoErr(null);
    setHits([]);
    setHighlight(-1);

    if (q.length < 2) {
      setGeoErr("Enter at least 2 characters.");
      return;
    }
    if (!mapReady) {
      setGeoErr("Map is still loading.");
      return;
    }

    setBusy(true);
    try {
      const list = await fetchSuggestions(q);
      setHits(list);
      if (!list.length) {
        setGeoErr("No results. Try a street, city, or postal code.");
        return;
      }
      if (list.length === 1) {
        pickHit(list[0]);
        return;
      }
      setHighlight(0);
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setGeoErr((e as Error).message || "Could not reach the geocoder. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function pickHit(hit: GeocodeHit) {
    applyCoords(hit.lat, hit.lng, { zoom: 14, label: hit.label });
    setHits([]);
    setHighlight(-1);
    setQuery(hit.label);
    setGeoErr(null);
  }

  // Debounced suggestions while typing (Nominatim: max 1 req/s — 450ms debounce, min 3 chars)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 3) {
      setHits([]);
      setHighlight(-1);
      return;
    }

    debounceRef.current = setTimeout(() => {
      setBusy(true);
      setGeoErr(null);
      fetchSuggestions(q)
        .then((list) => {
          setHits(list);
          setHighlight(list.length ? 0 : -1);
          if (!list.length) setGeoErr("No matches yet — press Enter to search.");
        })
        .catch((e) => {
          if ((e as Error).name !== "AbortError") {
            setGeoErr((e as Error).message || "Search failed.");
          }
        })
        .finally(() => setBusy(false));
    }, 450);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, fetchSuggestions]);

  function onSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      if (highlight >= 0 && hits[highlight]) {
        pickHit(hits[highlight]);
      } else if (hits.length === 1) {
        pickHit(hits[0]);
      } else {
        void runSearch();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (hits.length) setHighlight((i) => (i + 1) % hits.length);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (hits.length) setHighlight((i) => (i <= 0 ? hits.length - 1 : i - 1));
      return;
    }
    if (e.key === "Escape") {
      setHits([]);
      setHighlight(-1);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="relative min-w-0 flex-1">
          <label className="label" htmlFor="location-search">
            Find on map
          </label>
          <input
            id="location-search"
            type="search"
            className="input"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setGeoErr(null);
              setConfirmed(null);
            }}
            onKeyDown={onSearchKeyDown}
            placeholder="Start typing an address…"
            disabled={!mapReady}
            autoComplete="off"
            role="combobox"
            aria-expanded={hits.length > 0}
            aria-controls="location-suggestions"
            aria-autocomplete="list"
          />
          {hits.length > 0 && (
            <ul
              id="location-suggestions"
              role="listbox"
              className="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded-md border border-ink/15 bg-white text-sm shadow-lg"
            >
              {hits.map((h, i) => (
                <li key={`${h.lat},${h.lng},${h.label.slice(0, 40)}`} role="option" aria-selected={i === highlight}>
                  <button
                    type="button"
                    className={`w-full px-3 py-2 text-left ${i === highlight ? "bg-ink/10" : "hover:bg-ink/5"}`}
                    onMouseEnter={() => setHighlight(i)}
                    onClick={() => pickHit(h)}
                  >
                    {h.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          type="button"
          className="btn-secondary shrink-0 px-4 py-2"
          disabled={!mapReady || busy}
          onClick={() => void runSearch()}
        >
          {busy ? "Searching…" : "Search"}
        </button>
        <button
          type="button"
          className="btn-secondary shrink-0 px-4 py-2"
          disabled={!mapReady || busy}
          onClick={useBrowserLocation}
        >
          Use browser location
        </button>
      </div>

      {geoErr && <p className="text-xs text-red-700">{geoErr}</p>}
      {timezoneErr && <p className="text-xs text-amber-700">{timezoneErr}</p>}
      {confirmed && !geoErr && (
        <p className="text-xs text-emerald-800">
          Location set: {confirmed}
        </p>
      )}

      <div
        ref={mapHostRef}
        className="relative z-0 h-52 w-full overflow-hidden rounded-md border border-ink/20 bg-ink/5 [&_.leaflet-container]:h-full [&_.leaflet-container]:w-full"
        aria-label="Map: click to place pin"
      />
      {!mapReady && <p className="text-xs text-ink-soft">Loading map…</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="latitude">
            Latitude
          </label>
          <input
            id="latitude"
            name="latitude"
            className="input"
            type="number"
            step="any"
            value={lat}
            onChange={(e) => {
              setLat(e.target.value);
              setConfirmed(null);
            }}
            onBlur={() => applyTypedCoords()}
            placeholder="Optional"
          />
        </div>
        <div>
          <label className="label" htmlFor="longitude">
            Longitude
          </label>
          <input
            id="longitude"
            name="longitude"
            className="input"
            type="number"
            step="any"
            value={lng}
            onChange={(e) => {
              setLng(e.target.value);
              setConfirmed(null);
            }}
            onBlur={() => applyTypedCoords()}
            placeholder="Optional"
          />
        </div>
      </div>

      <input type="hidden" name="timezone" value={timezone} />
      <p className="text-xs text-ink-soft">
        Timezone: <span className="font-medium text-ink">{timezone || "Detecting..."}</span>
        {timezoneBusy ? " (updating from location...)" : ""}
      </p>

      <p className="text-xs text-ink-soft">
        Suggestions appear as you type; press Enter to select. You can also click the map or drag the
        pin.{" "}
        <a
          className="underline"
          href="https://operations.osmfoundation.org/policies/nominatim/"
          target="_blank"
          rel="noreferrer"
        >
          Nominatim usage policy
        </a>
        .
      </p>
    </div>
  );
}
