import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { OFFLINE_DEMO } from '../demo/mode';
import type { GeoJsonObject } from 'geojson';
import { Map } from '../components/map/Map';
import { BuildingSidebar } from '../components/building/BuildingSidebar';
import { FilterPanel, defaultFilters } from '../components/filters/FilterPanel';
import type { FilterState } from '../components/filters/FilterPanel';
import { LayersPanel, defaultLayersState } from '../components/map/LayersPanel';
import type { LayersState } from '../components/map/LayersPanel';
import { MapRunSelector } from '../components/map/MapRunSelector';
import { ResultsCarousel } from '../components/map/ResultsCarousel';
import { MapLegend } from '../components/map/MapLegend';
import { SQLQueryPanel } from '../components/agent/SQLQueryPanel';
import { ResultsSidebar } from '../components/map/ResultsSidebar';
import { FeedbackPanel } from '../components/agent/FeedbackPanel';
import { feedbackApi } from '../api/endpoints/feedback';
import type { AgentFeedbackResponse } from '../api/types';

import { mapApi } from '../api/endpoints/map';
import { layersApi } from '../api/endpoints/layers';
import { buildingsApi } from '../api/endpoints/buildings';
import type { ApiCoordinates, MapConfig, MapMarker, POI } from '../api/types';
import { Loader2, Sparkles, Building2, Home, List } from 'lucide-react';

import { useSettings } from '../contexts/SettingsContext';
import { useMap } from '../contexts/MapContext';
import { useIntelligenceMap } from '../hooks/useIntelligenceMap';

const getCoordinateLng = (
    coordinates: ApiCoordinates,
    fallback: number
) => (
    typeof coordinates.lng === 'number'
        ? coordinates.lng
        : typeof coordinates.lon === 'number'
            ? coordinates.lon
            : fallback
);

const getConstructionYear = (value?: string | number | null): number | null => {
    if (value == null) return null;
    const match = String(value).match(/\d{4}/);
    return match ? Number(match[0]) : null;
};

const matchesConstructionPeriod = (value: string | number | undefined, periods: string[]): boolean => {
    const year = getConstructionYear(value);
    if (year === null) return false;

    return periods.some(period => {
        switch (period) {
            case 'Before 1919':
                return year < 1919;
            case '1919 to 1945':
                return year >= 1919 && year <= 1945;
            case '1946 to 1960':
                return year >= 1946 && year <= 1960;
            case '1961 to 1970':
                return year >= 1961 && year <= 1970;
            case '1971 to 1980':
                return year >= 1971 && year <= 1980;
            case '1981 to 1990':
                return year >= 1981 && year <= 1990;
            case '1991 to 2000':
                return year >= 1991 && year <= 2000;
            case '2001 to 2010':
                return year >= 2001 && year <= 2010;
            case 'After 2010':
                return year > 2010;
            default:
                return String(value).trim() === period;
        }
    });
};

export const MapPage: React.FC = () => {
    const navigate = useNavigate();
    const { markersLimit } = useSettings();
    const { setMarkersCount, setTotalCount } = useMap();

    // Intelligence Map hook
    const {
        allMarkers: apiMarkers,
        searchResults,
        topPicks,
        searchLocation,
        activeRunId,
        isLoading: isLoadingRun,
        history,
        loadRun,
        clearResults,
    } = useIntelligenceMap(markersLimit);

    const [localInventory, setLocalInventory] = useState<MapMarker[]>([]);
    const allMarkers = useMemo(() => {
        if (!OFFLINE_DEMO) return apiMarkers;
        const merged = new globalThis.Map(localInventory.map(marker => [marker.id, marker]));
        [...searchResults, ...topPicks].forEach(marker => merged.set(marker.id, marker));
        return [...merged.values()];
    }, [apiMarkers, localInventory, searchResults, topPicks]);

    useEffect(() => {
        if (!OFFLINE_DEMO) return;
        fetch('/data/estates.json')
            .then(response => {
                if (!response.ok) throw new Error(`Inventory request failed (${response.status})`);
                return response.json() as Promise<Array<Record<string, unknown>>>;
            })
            .then(rows => setLocalInventory(rows.slice(0, markersLimit).flatMap(row => {
                const lat = Number(row.latitude);
                const lng = Number(row.longitude);
                if (!row.id || !Number.isFinite(lat) || !Number.isFinite(lng)) return [];
                const street = typeof row.address === 'string' ? row.address.trim() : '';
                const houseNumber = row.house_number == null ? '' : String(row.house_number).trim();
                return [{
                    id: String(row.id), lat, lng, tier: 1 as const,
                    address: [street, houseNumber].filter(Boolean).join(' ') || undefined,
                    surface_area: typeof row.surface_area === 'number' ? row.surface_area : undefined,
                    construction_year: typeof row.construction_period === 'string' ? row.construction_period : undefined,
                    energy_class: typeof row.energy_class === 'string' ? row.energy_class : undefined,
                    property_type: typeof row.property_type === 'string' ? row.property_type : undefined,
                    omi_zone: typeof row.omi_zone === 'string' ? row.omi_zone : undefined,
                    cadastral_sheet: row.cadastral_sheet != null ? String(row.cadastral_sheet) : undefined,
                    cadastral_parcel: row.cadastral_parcel != null ? String(row.cadastral_parcel) : undefined,
                    cadastral_subaltern: row.cadastral_subaltern != null ? String(row.cadastral_subaltern) : undefined,
                    cadastral_units_count: typeof row.cadastral_units_count === 'number' ? row.cadastral_units_count : undefined,
                    id_list: typeof row.id_list === 'string' ? row.id_list : undefined,
                    effective_date: typeof row.effective_date === 'string' ? row.effective_date : undefined,
                    start_date: typeof row.effective_date === 'string' ? row.effective_date : undefined,
                    is_meta_building: row.is_meta_estate === true,
                    meta_immobile: row.is_meta_estate === true,
                    energy_scores: row.energy_scores as MapMarker['energy_scores'],
                    proximity_scores: row.proximity_scores as MapMarker['proximity_scores'],
                    energy_files: Array.isArray(row.ape_file_list_filtered) ? row.ape_file_list_filtered.filter((item): item is string => typeof item === 'string') : undefined,
                }];
            })))
            .catch(err => {
                console.error('Failed to load local estate inventory:', err);
                setError('Could not load the local estate inventory.');
            });
    }, [markersLimit]);

    const [config, setConfig] = useState<MapConfig | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedBuildings, setSelectedBuildings] = useState<MapMarker[]>([]);
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // Carousel sync state
    const [focusMarkerId, setFocusMarkerId] = useState<string | null>(null);
    const [hoveredMarkerId, setHoveredMarkerId] = useState<string | null>(null);
    const [carouselSelectedId, setCarouselSelectedId] = useState<string | null>(null);

    // Layer state
    const [layers, setLayers] = useState<LayersState>(defaultLayersState);
    const [pois, setPois] = useState<POI[]>([]);
    const [poiBounds, setPoiBounds] = useState<{ min_lat: number; max_lat: number; min_lon: number; max_lon: number } | null>(null);
    const [zoneOMIOverlay, setZoneOMIOverlay] = useState<GeoJsonObject | null>(null);

    // Filter state
    const [filters, setFilters] = useState<FilterState>(defaultFilters);

    const [isSQLPanelOpen, setIsSQLPanelOpen] = useState(false);

    // Results list sidebar state
    const [isListSidebarOpen, setIsListSidebarOpen] = useState(false);

    // Run feedback state
    const [runFeedbacks, setRunFeedbacks] = useState<AgentFeedbackResponse[]>([]);

    const globalFeedback = useMemo(() =>
        runFeedbacks.find(f => !f.agent_name && !f.building_id),
        [runFeedbacks]
    );

    const buildingRatings = useMemo(() => {
        const mapping: Record<string, number> = {};
        runFeedbacks.forEach(f => {
            if (f.building_id) {
                mapping[f.building_id] = f.rating;
            }
        });
        return mapping;
    }, [runFeedbacks]);
    const displayedBuildingRatings = OFFLINE_DEMO ? {} : buildingRatings;

    // Fetch all feedback when activeRunId changes
    const fetchRunFeedback = useCallback(async () => {
        if (OFFLINE_DEMO) {
            setRunFeedbacks([]);
            return;
        }
        if (activeRunId) {
            try {
                const feedbacks = await feedbackApi.getAllRunFeedback(activeRunId);
                setRunFeedbacks(feedbacks);
            } catch (err) {
                console.error("Failed to fetch run feedback:", err);
            }
        } else {
            setRunFeedbacks([]);
        }
    }, [activeRunId]);

    useEffect(() => {
        fetchRunFeedback();
    }, [fetchRunFeedback]);

    // Filter markers based on Intelligence Map filters
    const filteredMarkers = useMemo(() => {
        let result = allMarkers;

        // 1. Filter by Energy Class
        if (filters.energyClasses.length > 0) {
            result = result.filter(m => {
                if (!m.energy_class) return false;
                const cls = m.energy_class.toUpperCase();
                return filters.energyClasses.some(f => cls === f || cls.startsWith(f));
            });
        }

        // 2. Filter by Surface Area
        if (filters.minSurface !== null) {
            result = result.filter(m => (m.surface_area || 0) >= filters.minSurface!);
        }
        if (filters.maxSurface !== null) {
            result = result.filter(m => (m.surface_area || 0) <= filters.maxSurface!);
        }

        // 3. Filter by Construction Period
        if (filters.constructionPeriods.length > 0) {
            result = result.filter(m => matchesConstructionPeriod(m.construction_year, filters.constructionPeriods));
        }

        // 4. Filter by Property Type
        if (filters.propertyTypes.length > 0) {
            result = result.filter(m => m.property_type && filters.propertyTypes.includes(m.property_type));
        }

        // 5. Filter by Meta Building
        if (filters.isMetaBuilding !== null) {
            result = result.filter(m => {
                const isMeta = m.is_meta_building === true || m.meta_building === true || m.meta_immobile === true;
                return filters.isMetaBuilding ? isMeta : !isMeta;
            });
        }

        // 6. Intelligence Map Tiers
        if (filters.showOnlyTopPicks) {
            result = result.filter(m => m.tier === 3);
        } else if (filters.showOnlyResults) {
            result = result.filter(m => m.tier === 2 || m.tier === 3);
        }

        return result;
    }, [allMarkers, filters]);

    // Sync marker count to context whenever markers change
    useEffect(() => {
        setMarkersCount(filteredMarkers.length);
        setTotalCount(allMarkers.length);
    }, [allMarkers, filteredMarkers, setMarkersCount, setTotalCount]);

    // Check for run_id in URL on mount
    useEffect(() => {
        const queryParams = new URLSearchParams(location.search);
        const runId = queryParams.get('run_id');
        if (runId && !activeRunId) {
            loadRun(runId);
            setFilters(prev => ({ ...prev, showOnlyResults: !OFFLINE_DEMO }));
        }
    }, [loadRun, activeRunId]);

    // Initial load - map configuration only
    useEffect(() => {
        if (OFFLINE_DEMO) {
            setConfig({ center: { lat: 45.07, lng: 7.69 }, zoom: 12, style: '', attribution: 'Estate inventory' });
            setIsLoading(false);
            return;
        }
        const fetchInitialData = async () => {
            try {
                setIsLoading(true);
                const configData = await mapApi.getConfig();

                setConfig(configData);
            } catch (err) {
                console.error("Error loading map config:", err);
                setError("Failed to load map data.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchInitialData();
    }, []);

    // Load the configured OMI overlay on demand.
    useEffect(() => {
        if (!OFFLINE_DEMO && layers.showZoneOMI && !zoneOMIOverlay) {
            mapApi.getOverlay('omi').then(setZoneOMIOverlay).catch(console.error);
        }
    }, [layers.showZoneOMI, zoneOMIOverlay]);

    // Fetch POIs when categories change
    // Use stringified version to avoid unnecessary re-fetches
    const activePOICategoriesKey = useMemo(
        () => [...layers.activePOICategories].sort().join(','),
        [layers.activePOICategories]
    );

    useEffect(() => {
        const activeCategories = activePOICategoriesKey
            ? activePOICategoriesKey.split(',')
            : [];

        if (activeCategories.length === 0) {
            setPois([]);
            return;
        }
        if (!poiBounds) return;

        let cancelled = false;
        layersApi.getPOIs(activeCategories, poiBounds, OFFLINE_DEMO ? 1000 : 10000)
            .then(data => {
                if (!cancelled) setPois(data.pois);
            })
            .catch(err => {
                if (!cancelled) console.error("Error fetching POIs:", err);
            });
        return () => { cancelled = true; };
    }, [activePOICategoriesKey, poiBounds]);

    // Handle marker click from map
    const handleMarkerClick = useCallback(async (marker: MapMarker) => {
        // Optimistically set selected
        setSelectedBuildings([marker]);
        setIsSidebarOpen(true);

        // If it's a top pick, sync with carousel
        if (marker.tier === 3) {
            setCarouselSelectedId(marker.id);
        }

        // Check if we need to fetch details (Tier 1 background markers usually lack details)
        if (!OFFLINE_DEMO && (marker.tier === 1 || !marker.proximity_scores)) {
            try {
                // Fetch details
                const fullBuilding = await buildingsApi.getBuilding(marker.id);

                const richMarker: MapMarker = {
                    ...marker,
                    ...fullBuilding,
                    score: marker.ranking_score ?? marker.score ?? fullBuilding.score,
                    ranking_score: marker.ranking_score ?? fullBuilding.score,
                    lat: fullBuilding.coordinates.lat,
                    lng: getCoordinateLng(fullBuilding.coordinates, marker.lng),
                    tier: marker.tier
                };

                // Update selected buildings with the rich one
                setSelectedBuildings([richMarker]);
            } catch (err) {
                console.error("Failed to fetch building details", err);
            }
        }
    }, []);

    // Handle cluster click
    const handleClusterClick = useCallback(async (clusterMarkers: MapMarker[]) => {
        setSelectedBuildings(clusterMarkers);
        setIsSidebarOpen(true);

        // Fetch details for the first one at least, so something shows up.
        if (clusterMarkers.length > 0) {
            const first = clusterMarkers[0];
            if (!OFFLINE_DEMO && (first.tier === 1 || !first.proximity_scores)) {
                try {
                    const fullBuilding = await buildingsApi.getBuilding(first.id);
                    const richMarker: MapMarker = {
                        ...first,
                        ...fullBuilding,
                        score: first.ranking_score ?? first.score ?? fullBuilding.score,
                        ranking_score: first.ranking_score ?? fullBuilding.score,
                        lat: fullBuilding.coordinates.lat,
                        lng: getCoordinateLng(fullBuilding.coordinates, first.lng),
                        tier: first.tier
                    };

                    // Replace the first one in the array
                    const newMarkers = [...clusterMarkers];
                    newMarkers[0] = richMarker;
                    setSelectedBuildings(newMarkers);
                } catch (e) {
                    console.error("Failed to fetch cluster building details", e);
                }
            }
        }
    }, []);

    // Handle carousel card click - bidirectional sync
    const handleCarouselCardClick = useCallback((marker: MapMarker) => {
        setSelectedBuildings([marker]);
        setIsSidebarOpen(true);
        setCarouselSelectedId(marker.id);
        setFocusMarkerId(marker.id);

        // Reset focus after animation
        setTimeout(() => setFocusMarkerId(null), 1000);
    }, []);

    // Handle carousel hover
    const handleCarouselHover = useCallback((markerId: string | null) => {
        setHoveredMarkerId(markerId);
    }, []);

    // Handle run selection from dropdown
    const handleSelectRun = useCallback((runId: string) => {
        loadRun(runId);
        setFilters(prev => ({ ...prev, showOnlyResults: !OFFLINE_DEMO }));
        // Update URL without reload
        const url = new URL(window.location.href);
        url.searchParams.set('run_id', runId);
        window.history.pushState({}, '', url.toString());
    }, [loadRun]);

    // Handle clear results
    const handleClearResults = useCallback(() => {
        clearResults();
        setCarouselSelectedId(null);
        // Remove run_id from URL
        const url = new URL(window.location.href);
        url.searchParams.delete('run_id');
        window.history.pushState({}, '', url.toString());
    }, [clearResults]);

    if (isLoading) {
        return (
            <div className="h-full w-full flex items-center justify-center text-text-primary">
                <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            </div>
        );
    }

    if (error || !config) {
        return (
            <div className="h-full w-full flex items-center justify-center text-red-500">
                <p>{error || "Configuration error"}</p>
            </div>
        );
    }

    const carouselMarkers = OFFLINE_DEMO && activeRunId
        ? [...topPicks, ...searchResults]
            .sort((a, b) => (b.ranking_score ?? b.score ?? 0) - (a.ranking_score ?? a.score ?? 0))
            .slice(0, 10)
        : topPicks;
    const hasTopPicks = carouselMarkers.length > 0;

    return (
        <div className="h-full w-full relative flex flex-col overflow-hidden">
            {/* Top Controls Bar - Left side only */}
            <div className="absolute top-4 left-4 z-400 flex flex-col gap-2" style={{ marginLeft: isListSidebarOpen ? '320px' : '0', transition: 'margin-left 0.3s ease' }}>
                {/* Row 1: Map controls */}
                <div className="flex items-start gap-2">
                    {OFFLINE_DEMO && (
                        <button
                            onClick={() => navigate('/', { replace: true })}
                            className="flex h-12.5 w-12.5 items-center justify-center rounded-lg border border-white/10 bg-slate-900/80 text-gray-300 shadow-xl shadow-black/40 backdrop-blur-xl transition-colors hover:border-white/20 hover:bg-white/10 hover:text-white"
                            aria-label="Return to home"
                            title="Home"
                        >
                            <Home className="h-4 w-4" />
                        </button>
                    )}
                    {/* List Sidebar Toggle */}
                    <button
                        onClick={() => setIsListSidebarOpen(!isListSidebarOpen)}
                        className={`
                            flex items-center justify-center w-12.5 h-12.5 rounded-lg text-xs font-medium border backdrop-blur-xl transition-all duration-300 shadow-xl shadow-black/40
                            ${isListSidebarOpen
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                                : 'bg-slate-900/80 text-gray-400 border-white/10 hover:border-white/20 hover:text-white hover:bg-white/10'
                            }
                        `}
                    >
                        <List className="w-4 h-4" />
                    </button>
                    <FilterPanel
                        filters={filters}
                        onFiltersChange={setFilters}
                    />
                    <LayersPanel
                        layers={layers}
                        onLayersChange={setLayers}
                    />
                    <MapLegend hasSearchLocation={!!searchLocation} />
                </div>

                {/* Row 2: Run controls and SQL query access */}
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5">
                        <MapRunSelector
                            history={history}
                            activeRunId={activeRunId}
                            isLoading={isLoadingRun}
                            onSelectRun={handleSelectRun}
                            onClearResults={handleClearResults}
                        />
                    </div>

                    {activeRunId && (
                        <SQLQueryPanel
                            activeRunId={activeRunId}
                            isOpen={isSQLPanelOpen}
                            onToggle={() => setIsSQLPanelOpen(!isSQLPanelOpen)}
                        />
                    )}

                    {/* Stats Badge */}
                    <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl px-4 py-2.5 flex items-center gap-4 shadow-xl shadow-black/40">
                        <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-lg bg-slate-700/50 flex items-center justify-center">
                                <Building2 className="w-3.5 h-3.5 text-slate-300" />
                            </div>
                            <div className="flex flex-col">
                                <span className="text-xs text-slate-400 leading-none">Visible</span>
                                <span className="text-sm text-white font-bold leading-tight">{filteredMarkers.length}</span>
                            </div>
                        </div>
                        {activeRunId && !filters.showOnlyTopPicks && (
                            <>
                                <div className="w-px h-8 bg-white/10" />
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-lg bg-teal-500/20 flex items-center justify-center">
                                        <Building2 className="w-3.5 h-3.5 text-teal-400" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-xs text-slate-400 leading-none">Results</span>
                                        <span className="text-sm text-teal-400 font-bold leading-tight">
                                            {allMarkers.filter(m => m.tier === 2 || m.tier === 3).length}
                                        </span>
                                    </div>
                                </div>
                            </>
                        )}
                        {hasTopPicks && (
                            <>
                                <div className="w-px h-8 bg-white/10" />
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-lg bg-linear-to-br from-amber-400/30 to-orange-400/30 flex items-center justify-center">
                                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-xs text-slate-400 leading-none">{OFFLINE_DEMO ? 'Benchmark Top 10' : 'AI Top Picks'}</span>
                                        <span className="text-sm text-amber-400 font-bold leading-tight">{carouselMarkers.length}</span>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {!OFFLINE_DEMO && activeRunId && (
                        <FeedbackPanel
                            runId={activeRunId}
                            align="right"
                            existingFeedback={globalFeedback ? {
                                id: globalFeedback.id,
                                rating: globalFeedback.rating,
                                comment: globalFeedback.comment
                            } : undefined}
                            onSubmitSuccess={fetchRunFeedback}
                        />
                    )}
                </div>
            </div>

            {/* Map Container */}
            {/* Results List Sidebar */}
            <ResultsSidebar
                isOpen={isListSidebarOpen}
                onClose={() => setIsListSidebarOpen(false)}
                markers={filteredMarkers}
                selectedId={selectedBuildings[0]?.id || null}
                onSelect={(marker) => {
                    setSelectedBuildings([marker]);
                    setIsSidebarOpen(true);
                    setFocusMarkerId(marker.id);
                    setCarouselSelectedId(marker.id);
                }}
                hasActiveRun={!!activeRunId}
                buildingRatings={displayedBuildingRatings}
            />

            <div className={`flex-1 relative rounded-xl overflow-hidden shadow-2xl border border-white/5 m-4 mt-1 ${hasTopPicks ? 'mb-36' : ''}`} style={{ marginLeft: isListSidebarOpen ? '320px' : '0', transition: 'margin-left 0.3s ease' }}>
                <Map
                    markers={filteredMarkers}
                    center={config.center}
                    zoom={config.zoom}
                    pois={pois}
                    zoneOMI={layers.showZoneOMI ? zoneOMIOverlay ?? undefined : undefined}
                    selectedBuildingIds={selectedBuildings.map(b => b.id)}
                    focusMarkerId={focusMarkerId}
                    hoveredMarkerId={hoveredMarkerId}
                    searchLocation={searchLocation}
                    buildingRatings={displayedBuildingRatings}
                    onMarkerClick={handleMarkerClick}
                    onClusterClick={handleClusterClick}
                    onBoundsChange={setPoiBounds}
                />
            </div>

            {/* Results Carousel - Bottom */}
            {hasTopPicks && (
                <div
                    className="absolute bottom-0 left-0 right-0 bg-linear-to-t from-[#0a0d12] via-[#0a0d12]/95 to-transparent pt-6 pb-4 z-300"
                    style={{ marginLeft: isListSidebarOpen ? '320px' : '0', transition: 'margin-left 0.3s ease' }}
                >
                    <ResultsCarousel
                        topPicks={carouselMarkers}
                        title={OFFLINE_DEMO ? 'Benchmark Top 10' : 'Top Picks AI'}
                        selectedId={carouselSelectedId}
                        hoveredId={hoveredMarkerId}
                        onCardClick={handleCarouselCardClick}
                        onCardHover={handleCarouselHover}
                        sidebarOpen={isSidebarOpen}
                        buildingRatings={displayedBuildingRatings}
                    />
                </div>
            )}

            {/* Building Sidebar */}
            <BuildingSidebar
                isOpen={isSidebarOpen}
                onClose={() => setIsSidebarOpen(false)}
                selectedBuildings={selectedBuildings}
                runId={activeRunId}
                onFeedbackSuccess={fetchRunFeedback}
            />
        </div>
    );
};
