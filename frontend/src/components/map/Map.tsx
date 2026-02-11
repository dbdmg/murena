import React, { useEffect, useState, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, useMap, GeoJSON, Popup } from 'react-leaflet';
import L from 'leaflet';
import useSupercluster from 'use-supercluster';
import type { MapMarker, LatLng, POI, MarkerTier } from '../../api/types';
import 'leaflet/dist/leaflet.css';

// ... (icons remain unchanged)

// Fix Leaflet Default Icon Issue
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom Icons (Refined & Elegant)
const clusterIcon = (count: number) => {
    // Dynamic sizing based on count
    const size = count > 100 ? 48 : count > 50 ? 44 : 40;
    const fontSize = count > 100 ? 'text-sm' : 'text-xs';

    return L.divIcon({
        html: `
            <div class="relative" style="width: ${size}px; height: ${size}px;">
                <div class="absolute inset-0 bg-linear-to-br from-slate-600/80 to-slate-800/80 rounded-full backdrop-blur-sm"></div>
                <div class="absolute inset-[2px] bg-linear-to-br from-cyan-500/90 to-blue-600/90 rounded-full"></div>
                <div class="absolute inset-0 flex items-center justify-center text-white font-semibold ${fontSize} drop-shadow-md">${count}</div>
                <div class="absolute inset-0 rounded-full border border-white/30 shadow-lg shadow-cyan-500/30"></div>
            </div>
        `,
        className: 'custom-cluster-icon',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
    });
};

// Custom helper to render stars above icons
const renderStarsOverlay = (rating?: number) => {
    if (!rating || rating <= 0) return '';

    let starsHtml = '';
    for (let i = 1; i <= 5; i++) {
        const color = i <= rating ? 'text-amber-400' : 'text-slate-600';
        starsHtml += `<span class="${color} drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">★</span>`;
    }

    return `
        <div class="absolute -top-5 left-1/2 -translate-x-1/2 flex text-[10px] whitespace-nowrap pointer-events-none z-50">
            ${starsHtml}
        </div>
    `;
};


// selectedClusterIcon (Vibrant Green with enhanced pulse)
const selectedClusterIcon = (count: number) => {
    return L.divIcon({
        html: `
            <div class="relative" style="width: 52px; height: 52px;">
                <div class="absolute inset-[-10px] bg-emerald-400/30 rounded-full animate-ping"></div>
                <div class="absolute inset-[-5px] bg-emerald-400/40 rounded-full animate-pulse"></div>
                <div class="absolute inset-0 bg-linear-to-br from-slate-900 to-black rounded-full backdrop-blur-md"></div>
                <div class="absolute inset-[2px] bg-linear-to-br from-emerald-400 via-green-500 to-teal-600 rounded-full"></div>
                <div class="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.5)]">${count}</div>
                <div class="absolute inset-0 rounded-full border-2 border-white/80 shadow-[0_0_20px_rgba(52,211,153,0.5)]"></div>
            </div>
        `,
        className: 'selected-cluster-icon',
        iconSize: [52, 52],
        iconAnchor: [26, 26],
    });
};


// Tier 1 Icon - Indigo (Background markers) - Bigger & more visible
const tier1Icon = (rating?: number) => {
    return L.divIcon({
        html: `
            <div class="relative w-5 h-5 group transition-all duration-200 hover:scale-125">
                ${renderStarsOverlay(rating)}
                <div class="absolute inset-[-4px] bg-indigo-500/30 rounded-full blur-xs group-hover:opacity-100 transition-opacity"></div>
                <div class="absolute -inset-px bg-indigo-400/40 rounded-full"></div>
                <div class="relative w-5 h-5 rounded-full bg-linear-to-br from-indigo-500 to-indigo-800 border-2 border-white/60 shadow-lg transition-colors"></div>
                <div class="absolute inset-[6px] bg-white/30 rounded-full"></div>
            </div>
        `,
        className: 'tier1-point-icon',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
};

// Tier 2 Icon - Rich teal-blue (Search Results)
const tier2Icon = (rating?: number) => {
    return L.divIcon({
        html: `
            <div class="relative w-5 h-5 group transition-all duration-200">
                ${renderStarsOverlay(rating)}
                <div class="absolute inset-[-2px] bg-linear-to-br from-teal-400 to-cyan-500 rounded-full blur-xs opacity-50 group-hover:opacity-80 transition-opacity"></div>
                <div class="relative w-5 h-5 rounded-full bg-linear-to-br from-teal-400 to-cyan-600 border border-white/60 shadow-md shadow-cyan-500/30 transition-transform group-hover:scale-110"></div>
                <div class="absolute inset-[5px] bg-white/30 rounded-full"></div>
            </div>
        `,
        className: 'tier2-point-icon',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
    });
};

// Tier 3 Icon - Premium champagne/gold (Top Picks - AI evaluated)
const tier3Icon = (isHovered: boolean = false, rating?: number) => {
    const glowClass = isHovered ? 'opacity-90' : 'opacity-60';
    const scaleClass = isHovered ? 'scale-115' : '';

    return L.divIcon({
        html: `
            <div class="relative w-8 h-8 ${scaleClass} transition-all duration-300">
                ${renderStarsOverlay(rating)}
                <div class="absolute inset-[-4px] bg-linear-to-br from-amber-300 to-orange-400 rounded-full animate-pulse opacity-25"></div>
                <div class="absolute inset-[-2px] bg-linear-to-br from-amber-400/80 to-yellow-500/80 rounded-full blur-xs ${glowClass} transition-opacity"></div>
                <div class="absolute inset-0 bg-linear-to-br from-slate-800/90 to-slate-900/90 rounded-full backdrop-blur-sm"></div>
                <div class="absolute inset-[2px] bg-linear-to-br from-amber-300 via-yellow-400 to-orange-400 rounded-full"></div>
                <div class="absolute inset-0 flex items-center justify-center">
                    <span class="text-[11px] font-bold text-slate-900 drop-shadow-sm">★</span>
                </div>
                <div class="absolute inset-0 rounded-full border border-white/50 shadow-lg shadow-amber-500/40"></div>
            </div>
        `,
        className: 'tier3-point-icon',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
    });
};

// Location Marker Icon - Rich rose/coral (Search Location)
const locationIcon = () => {
    return L.divIcon({
        html: `
            <div class="relative" style="width: 36px; height: 36px;">
                <div class="absolute inset-[-6px] bg-rose-500/30 rounded-full animate-ping"></div>
                <div class="absolute inset-[-3px] bg-linear-to-br from-rose-400 to-red-500 rounded-full blur-[5px] opacity-60"></div>
                <div class="absolute inset-0 bg-linear-to-br from-slate-800/90 to-slate-900/90 rounded-full backdrop-blur-sm"></div>
                <div class="absolute inset-[2px] bg-linear-to-br from-rose-400 via-red-500 to-rose-600 rounded-full"></div>
                <div class="absolute inset-0 flex items-center justify-center">
                    <svg class="w-4 h-4 text-white drop-shadow-md" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
                    </svg>
                </div>
                <div class="absolute inset-0 rounded-full border border-white/40 shadow-lg shadow-rose-500/40"></div>
            </div>
        `,
        className: 'location-marker-icon',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
    });
};

// Get icon based on marker tier
const getTierIcon = (tier?: MarkerTier, isHovered: boolean = false, rating?: number) => {
    switch (tier) {
        case 3:
            return tier3Icon(isHovered, rating);
        case 2:
            return tier2Icon(rating);
        case 1:
        default:
            return tier1Icon(rating);
    }
};


// Selected marker icon (Vibrant Green/Emerald with enhanced pulse & ping)
const selectedIcon = (rating?: number) => {
    return L.divIcon({
        html: `
            <div class="relative" style="width: 36px; height: 36px;">
                ${renderStarsOverlay(rating)}
                <!-- Animated Rings -->
                <div class="absolute inset-[-14px] bg-emerald-400/20 rounded-full animate-ping"></div>
                <div class="absolute inset-[-7px] bg-emerald-400/40 rounded-full animate-pulse"></div>
                
                <!-- Glow & Base -->
                <div class="absolute inset-[-4px] bg-linear-to-br from-emerald-300 to-teal-500 rounded-full blur-sm"></div>
                <div class="absolute inset-0 bg-[#0a0d12] rounded-full"></div>
                
                <!-- Main Core -->
                <div class="absolute inset-[2px] bg-linear-to-br from-emerald-400 via-green-400 to-emerald-600 rounded-full"></div>
                
                <!-- Inner Reflection -->
                <div class="absolute top-[5px] left-[7px] w-2 h-1 bg-white/50 rounded-full blur-[1px] rotate-[-25deg]"></div>
                
                <!-- Border & Shadow -->
                <div class="absolute inset-0 rounded-full border-2 border-white shadow-[0_0_20px_rgba(52,211,153,0.7)]"></div>
            </div>
        `,
        className: 'selected-point-icon',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
    });
};

const getPoiIcon = (iconChar: string, color: string, zoom: number) => {
    // If zoom is low (<15), show small dot
    if (zoom < 15) {
        return L.divIcon({
            html: `
                <div class="w-3 h-3 rounded-full border border-white/50 shadow-sm" style="background-color: ${color}"></div>
            `,
            className: 'custom-poi-dot',
            iconSize: [12, 12],
            iconAnchor: [6, 6],
        });
    }

    // Modern, cleaner icon for high zoom
    return L.divIcon({
        html: `
            <div class="relative w-7 h-7 flex items-center justify-center transform hover:scale-110 transition-transform group">
               <div class="absolute inset-0 bg-[#0f1218]/90 rounded-full shadow-lg border border-white/20 group-hover:border-white/50 transition-colors"></div>
               <div class="absolute inset-0 rounded-full opacity-20" style="background-color: ${color}"></div>
               <div class="relative text-sm leading-none filter drop-shadow-sm">${iconChar}</div>
            </div>
        `,
        className: 'custom-poi-icon',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
    });
};

const getPoiClusterIcon = (count: number) => {
    // Determine size based on count, but keep it generally smaller/cleaner than main property clusters
    let size = 30;
    if (count > 100) size = 40;
    if (count > 1000) size = 50;

    return L.divIcon({
        html: `
            <div class="relative w-full h-full flex items-center justify-center transform hover:scale-105 transition-transform duration-200">
                <div class="absolute inset-0 bg-indigo-600/90 rounded-full blur-sm opacity-50"></div>
                <div class="relative w-[90%] h-[90%] bg-[#0f1218] rounded-full border border-indigo-500/50 flex items-center justify-center shadow-lg">
                    <span class="text-indigo-100 font-bold text-xs">${count}</span>
                </div>
                <div class="absolute -top-1 -right-1 w-3 h-3 bg-indigo-500 rounded-full animate-pulse"></div>
            </div>
        `,
        className: 'custom-poi-cluster',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
    });
};



// MapEvents Component extracted correctly
interface MapEventsProps {
    setBounds: (bounds: [number, number, number, number]) => void;
    setZoom: (zoom: number) => void;
}

const MapEvents: React.FC<MapEventsProps> = ({ setBounds, setZoom }) => {
    const map = useMap();

    useEffect(() => {
        const updateMap = () => {
            const b = map.getBounds();
            setBounds([
                b.getSouthWest().lng,
                b.getSouthWest().lat,
                b.getNorthEast().lng,
                b.getNorthEast().lat,
            ]);
            setZoom(map.getZoom());
        };

        map.on('moveend', updateMap);
        updateMap(); // Initial call

        return () => {
            map.off('moveend', updateMap);
        };
    }, [map, setBounds, setZoom]);
    return null;
};

interface MapProps {
    markers: MapMarker[];
    center: LatLng;
    zoom: number;
    tileUrl?: string;
    tileAttribution?: string;
    overlays?: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        municipi?: any;
    };
    pois?: POI[];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    zoneOMI?: any;
    selectedBuildingIds?: string[];
    focusMarkerId?: string | null;
    hoveredMarkerId?: string | null; // For carousel hover sync
    searchLocation?: { name: string; lat: number; lng: number } | null; // Red location marker
    buildingRatings?: Record<string, number>;
    onMarkerClick?: (marker: MapMarker) => void;
    onClusterClick?: (markers: MapMarker[]) => void;
}

export const Map: React.FC<MapProps> = ({
    markers,
    center,
    zoom,
    tileUrl,
    tileAttribution,
    overlays,
    pois = [],
    zoneOMI,
    selectedBuildingIds = [],
    focusMarkerId,
    hoveredMarkerId,
    searchLocation,
    buildingRatings = {},
    onMarkerClick,
    onClusterClick,
}) => {
    const [bounds, setBounds] = useState<[number, number, number, number] | null>(null);
    const [currentZoom, setCurrentZoom] = useState(zoom);
    const mapRef = useRef<L.Map>(null);

    useEffect(() => {
        if (!focusMarkerId) return;
        const marker = markers.find((m) => m.id === focusMarkerId);
        if (!marker) return;
        // Keep a reasonable zoom for “details focus” but don't aggressively zoom out
        const targetZoom = Math.max(currentZoom, 16);
        mapRef.current?.setView([marker.lat, marker.lng], targetZoom, { animate: true });
    }, [focusMarkerId, markers, currentZoom]);

    // Separate Tier 3 markers from clustering (always visible individually)
    const tier3Markers = useMemo(() => markers.filter(m => m.tier === 3), [markers]);
    const clusterableMarkers = useMemo(() => markers.filter(m => m.tier !== 3), [markers]);

    // Convert clusterable markers to GeoJSON points for Supercluster
    const points = useMemo(() => clusterableMarkers.map((marker) => ({
        type: 'Feature' as const,
        properties: { cluster: false, markerId: marker.id, category: 'real_estate', ...marker },
        geometry: {
            type: 'Point' as const,
            coordinates: [marker.lng, marker.lat],
        },
    })), [clusterableMarkers]);

    // Get clusters via hook
    const { clusters, supercluster } = useSupercluster({
        points,
        bounds: bounds || undefined,
        zoom: currentZoom,
        options: { radius: 75, maxZoom: 20 },
    });

    // --- POI Clusters ---
    const poiPoints = useMemo(() => pois.map(poi => ({
        type: 'Feature' as const,
        properties: { ...poi, cluster: false, poiId: poi.id, category: 'poi' },
        geometry: {
            type: 'Point' as const,
            coordinates: [poi.lon, poi.lat]
        }
    })), [pois]);

    const { clusters: poiClusters, supercluster: poiSupercluster } = useSupercluster({
        points: poiPoints,
        bounds: bounds || undefined,
        zoom: currentZoom,
        options: { radius: 60, maxZoom: 16 } // Create clusters earlier, break them apart sooner than real estate
    });

    // Memoize markers to avoid re-rendering all on every map move unless clusters change
    const renderedClusters = useMemo(() => clusters.map((cluster) => {
        const [longitude, latitude] = cluster.geometry.coordinates;
        const { cluster: isCluster, point_count: pointCount } = cluster.properties;

        if (isCluster) {
            // Check if this cluster contains any selected markers
            const leaves = supercluster.getLeaves(cluster.id, Infinity);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const clusterMarkerIds = leaves.map((leaf: any) => leaf.properties.markerId);
            const hasSelectedMarker = clusterMarkerIds.some((id: string) => selectedBuildingIds.includes(id));

            return (
                <Marker
                    key={`cluster-${cluster.id}`}
                    position={[latitude, longitude]}
                    icon={hasSelectedMarker ? selectedClusterIcon(pointCount) : clusterIcon(pointCount)}
                    zIndexOffset={hasSelectedMarker ? 1000 : 0}
                    eventHandlers={{
                        click: () => {
                            // Get the expansion zoom (could be >20 for coincident points)
                            const rawExpansionZoom = supercluster.getClusterExpansionZoom(cluster.id);

                            // If expansion zoom is >= 20, points are coincident/very close
                            // OR if we're already at high zoom and clicking again
                            if (rawExpansionZoom >= 20 || currentZoom >= 18) {
                                // Get all buildings in this cluster and open sidebar
                                if (onClusterClick) {
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    const clusterMarkers = leaves.map((leaf: any) => leaf.properties as MapMarker);
                                    onClusterClick(clusterMarkers);
                                }
                                // Also zoom to max for visual context
                                mapRef.current?.setView([latitude, longitude], 20, { animate: true });
                            } else {
                                // Normal zoom expansion
                                mapRef.current?.setView([latitude, longitude], rawExpansionZoom, {
                                    animate: true,
                                });
                            }
                        },
                    }}
                />
            );
        }


        const markerId = cluster.properties.markerId;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const markerData = cluster.properties as any as MapMarker;
        const isSelected = selectedBuildingIds.includes(markerId);
        const rating = buildingRatings[markerId];

        // Use tier-based icon for non-clustered markers
        const markerIcon = isSelected
            ? selectedIcon(rating)
            : getTierIcon(markerData.tier, false, rating);

        return (
            <Marker
                key={`marker-${markerId}`}
                position={[latitude, longitude]}
                icon={markerIcon}
                zIndexOffset={isSelected ? 1000 : (markerData.tier === 2 ? 100 : 0)}
                eventHandlers={{
                    click: () => {
                        if (onMarkerClick) {
                            onMarkerClick(markerData);
                        }
                    }
                }}
            />
        );

    }), [clusters, supercluster, selectedBuildingIds, onClusterClick, onMarkerClick, currentZoom]);

    // Memoize Tier 3 markers
    const renderedTier3Markers = useMemo(() => tier3Markers.map((marker) => {
        const isSelected = selectedBuildingIds.includes(marker.id);
        const isHovered = hoveredMarkerId === marker.id;
        const rating = buildingRatings[marker.id];

        return (
            <Marker
                key={`tier3-${marker.id}`}
                position={[marker.lat, marker.lng]}
                icon={isSelected ? selectedIcon(rating) : tier3Icon(isHovered, rating)}
                zIndexOffset={isSelected ? 2000 : 1500} // Always on top
                eventHandlers={{
                    click: () => {
                        if (onMarkerClick) {
                            onMarkerClick(marker);
                        }
                    }
                }}
            />
        );
    }), [tier3Markers, selectedBuildingIds, hoveredMarkerId, onMarkerClick]);

    // Memoize POI Clusters
    const renderedPoiClusters = useMemo(() => poiClusters.map(cluster => {
        const [longitude, latitude] = cluster.geometry.coordinates;
        const { cluster: isCluster, point_count: pointCount } = cluster.properties;

        if (isCluster) {
            return (
                <Marker
                    key={`poi-cluster-${cluster.id}`}
                    position={[latitude, longitude]}
                    icon={getPoiClusterIcon(pointCount)}
                    zIndexOffset={400} // Lower than Real Estate clusters
                    eventHandlers={{
                        click: () => {
                            const expansionZoom = Math.min(
                                poiSupercluster.getClusterExpansionZoom(cluster.id as number),
                                20
                            );
                            mapRef.current?.setView([latitude, longitude], expansionZoom, {
                                animate: true,
                            });
                        }
                    }}
                />
            );
        }

        // POI Leaf (Single POI)
        const poi = cluster.properties as POI;

        return (
            <Marker
                key={`poi-${poi.id}`}
                position={[latitude, longitude]}
                icon={getPoiIcon(poi.icon, poi.color, currentZoom)}
                zIndexOffset={500}
            >
                <Popup className="custom-popup" closeButton={false} offset={[0, -10]}>
                    <div className="p-1 min-w-[220px]">
                        <div className="flex items-start gap-3">
                            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-gray-800 to-black border border-white/10 flex items-center justify-center shrink-0 shadow-lg" style={{ borderTopColor: poi.color }}>
                                <span className="text-xl filter drop-shadow-md">{poi.icon}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5 mb-0.5">
                                    <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider bg-indigo-500/10 px-1.5 rounded-sm">{poi.category}</span>
                                </div>
                                <h3 className="font-bold text-sm text-white leading-tight mb-1">{poi.name || 'Punto di Interesse'}</h3>

                                {(poi.details?.address || poi.details?.city) && (
                                    <p className="text-[11px] text-gray-400 leading-snug truncate">
                                        {poi.details.address}
                                        {poi.details.address && poi.details.city && ', '}
                                        {poi.details.city}
                                    </p>
                                )}

                                {poi.details?.opening_hours && (
                                    <div className="mt-2 text-[10px] text-gray-500 flex items-center gap-1">
                                        <div className="w-1.5 h-1.5 rounded-full bg-green-500/50"></div>
                                        <span className="truncate max-w-[150px]">{poi.details.opening_hours}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </Popup>
            </Marker>
        );
    }), [poiClusters, poiSupercluster, currentZoom]);

    return (
        <div className="h-full w-full relative isolate z-0 rounded-3xl overflow-hidden border border-white/5 shadow-2xl ring-1 ring-white/10">
            <MapContainer
                center={[center.lat, center.lng]}
                zoom={zoom}
                zoomControl={false}
                className="h-full w-full"
                ref={mapRef}
                style={{ background: '#0f1115' }}
            >
                <MapEvents setBounds={setBounds} setZoom={setCurrentZoom} />

                <TileLayer
                    attribution={
                        tileAttribution ||
                        'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
                    }
                    url={
                        tileUrl ||
                        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                    }
                />

                {/* Zone OMI Overlay */}
                {zoneOMI && (
                    <GeoJSON
                        key="zone-omi-overlay"
                        data={zoneOMI}
                        style={(feature) => ({
                            color: feature?.properties.strokeColor || '#fb923c',
                            weight: 2,
                            opacity: 0.8,
                            fillColor: feature?.properties.fillColor || '#fb923c',
                            fillOpacity: 0.2,
                        })}
                        onEachFeature={(feature, layer) => {
                            if (feature.properties && feature.properties.CODZONA) {
                                layer.bindTooltip(`${feature.properties.CODZONA}`, {
                                    permanent: true,
                                    direction: "center",
                                    className: "bg-black/50 text-white text-xs px-1 rounded border-0 backdrop-blur-sm shadow-none"
                                });
                                layer.bindPopup(`
                                    <div class="font-sans text-gray-100 p-1 min-w-[150px]">
                                        <h3 class="font-bold text-sm mb-1 text-white flex items-center gap-2">
                                            <span class="w-3 h-3 rounded-full opacity-70" style="background-color: ${feature.properties.fillColor}"></span>
                                            ${feature.properties.CODZONA}
                                        </h3>
                                        <p class="text-xs text-gray-300">${feature.properties.Name}</p>
                                    </div>
                                `);
                            }
                        }}
                    />
                )}

                {/* POI Markers */}
                {renderedPoiClusters}

                {/* Clusters & Markers */}
                {renderedClusters}

                {/* Tier 3 Markers - Top Picks (never clustered, always visible) */}
                {renderedTier3Markers}

                {/* Location Marker - Red (Search Location Point) */}
                {searchLocation && (
                    <Marker
                        key="search-location"
                        position={[searchLocation.lat, searchLocation.lng]}
                        icon={locationIcon()}
                        zIndexOffset={3000} // Always on very top
                    >
                        <Popup className="custom-popup" closeButton={false} offset={[0, -10]}>
                            <div className="p-2 min-w-[180px]">
                                <div className="flex items-center gap-2 mb-1">
                                    <div className="w-3 h-3 rounded-full bg-linear-to-br from-red-500 to-rose-600"></div>
                                    <span className="text-[10px] uppercase font-bold text-red-400 tracking-wider">Location Cercata</span>
                                </div>
                                <h3 className="font-bold text-sm text-white leading-tight">{searchLocation.name}</h3>
                            </div>
                        </Popup>
                    </Marker>
                )}

                {/* Municipi Overlay (controlled via MapPage props, not LayersControl) */}
                {overlays?.municipi && (
                    <GeoJSON
                        key="municipi-overlay"
                        data={overlays.municipi}
                        style={{
                            color: '#3b82f6', // Primary Blue
                            weight: 2,
                            opacity: 0.6,
                            fillOpacity: 0.1,
                            dashArray: '5, 5'
                        }}
                    />
                )}

            </MapContainer>
        </div>
    );
};
